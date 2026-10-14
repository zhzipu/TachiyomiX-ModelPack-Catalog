"""生成 TachiyomiX 模型包插件目录（README.md + index.json + index.min.json）。

数据全部来自 GitHub API，没有手写清单：
  * 每个仓库的 `build.gradle.kts`  → applicationId / modelpackId / modelpackName / versionCode / versionName
  * `src/main/assets/modelpack.json` → 该包提供哪些模型（key/name/engine/scales/denoiseLevels/supportsNpu）
  * releases                        → 最新 tag、APK 附件名/体积/sha256/下载地址
仓库清单靠 `TachiyomiX-ModelPack-*` 前缀自动发现（排掉本目录仓库自己），以后加新插件包重新跑一次即可。

用法（本机 hosts 把 github.com 指到 127.0.0.1，必须走系统代理让 Clash 去解析）：
    $env:HTTPS_PROXY = "http://127.0.0.1:7897"
    $env:GH_TOKEN    = "<token>"          # 只为提高 API 配额，公开数据也需要它更稳
    python gen_catalog.py <输出目录>
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "zhzipu"
PREFIX = "TachiyomiX-ModelPack-"
EXCLUDE = {"TachiyomiX-ModelPack-Catalog"}
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "")
PROXY = os.environ.get("GH_PROXY") or os.environ.get("HTTPS_PROXY") or ""

# ⚠️ Windows 上 `urlopen` 的默认 opener 会因为 WinINET 的 bypass 检查绕过代理（本机 github 被 hosts
# 指到 127.0.0.1 → TLS 直接 EOF）。必须显式建 ProxyHandler 的 opener，代理才真正生效。
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}) if PROXY else urllib.request.ProxyHandler({}),
)


def api(path: str, raw: bool = False, attempts: int = 4):
    url = path if path.startswith("http") else f"{API}{path}"
    last: Exception | None = None
    for i in range(attempts):
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
        req.add_header("User-Agent", "tachiyomix-catalog-generator")
        if TOKEN:
            req.add_header("Authorization", f"token {TOKEN}")
        # 第 3 次起换成一个"不带代理"的 opener 试试（万一代理本身在抖）
        opener = OPENER if i < 2 else urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=60) as resp:
                data = resp.read()
            break
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"      .. 第 {i + 1} 次失败：{type(e).__name__}: {e}", flush=True)
            __import__("time").sleep(1.5)
    else:
        raise RuntimeError(f"{url} 连续 {attempts} 次失败：{last}")
    if raw:
        return data.decode("utf-8", "replace")
    return json.loads(data.decode("utf-8"))


def parse_gradle(text: str) -> dict:
    def grab(pattern: str, default: str = "") -> str:
        m = re.search(pattern, text)
        return m.group(1) if m else default

    return {
        "pkg": grab(r'applicationId\s*=\s*"([^"]+)"'),
        "id": grab(r'modelpackId"\]\s*=\s*"([^"]+)"'),
        "name": grab(r'modelpackName"\]\s*=\s*"([^"]+)"'),
        "versionCode": int(grab(r"versionCode\s*=\s*(\d+)", "0")),
        "versionName": grab(r'versionName\s*=\s*"([^"]+)"'),
    }


def aapt2_path() -> str | None:
    """从 ANDROID_HOME 的 build-tools 里挑一个 aapt2（用来读 APK 的真实版本号）。"""
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        return None
    tools = Path(sdk) / "build-tools"
    if not tools.is_dir():
        return None
    candidates = sorted(
        (d / "aapt2.exe" for d in tools.iterdir() if (d / "aapt2.exe").is_file()),
        key=lambda p: [int(x) if x.isdigit() else 0 for x in p.parent.name.split(".")],
    )
    return str(candidates[-1]) if candidates else None


def apk_meta(path: Path) -> dict | None:
    """读 APK 里的 package name / versionCode / versionName。"""
    aapt2 = aapt2_path()
    if not aapt2:
        return None
    try:
        out = subprocess.run([aapt2, "dump", "badging", str(path)], capture_output=True, text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        print(f"      !! aapt2 执行失败：{e}", flush=True)
        return None
    m = re.search(r"package: name='([^']*)' versionCode='([^']*)' versionName='([^']*)'", out.stdout)
    if not m:
        return None
    return {"pkg": m.group(1), "versionCode": int(m.group(2) or 0), "versionName": m.group(3)}


def ensure_apk(cache_dir: Path, repo: str, asset: dict) -> Path | None:
    """把 release 附件下到本地缓存（大小一致就复用），供 aapt2 解析。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{repo}.apk"
    if target.is_file() and target.stat().st_size == asset["size"]:
        return target
    try:
        with OPENER.open(asset["url"], timeout=300) as resp, target.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    except Exception as e:  # noqa: BLE001
        print(f"      !! 下载 {repo} 的 APK 失败：{e}", flush=True)
        target.unlink(missing_ok=True)
        return None
    if target.stat().st_size != asset["size"]:
        target.unlink(missing_ok=True)
        return None
    return target


def collect(repo: str, cache_dir: Path) -> dict | None:
    try:
        meta = api(f"/repos/{OWNER}/{repo}")
        gradle = parse_gradle(api(f"/repos/{OWNER}/{repo}/contents/build.gradle.kts", raw=True))
        modelpack = json.loads(api(f"/repos/{OWNER}/{repo}/contents/src/main/assets/modelpack.json", raw=True))
    except urllib.error.HTTPError as e:
        print(f"  !! {repo}: HTTP {e.code}", flush=True)
        return None

    releases = api(f"/repos/{OWNER}/{repo}/releases")
    latest = releases[0] if releases else None
    apk = None
    if latest and latest.get("assets"):
        a = latest["assets"][0]
        apk = {
            "name": a["name"],
            "size": a["size"],
            "sha256": (a.get("digest") or "").replace("sha256:", "") or None,
            "url": a["browser_download_url"],
            "tag": latest["tag_name"],
            "published": latest.get("published_at"),
            "release": latest["html_url"],
        }

    # ⚠️ 版本号必须取**实际发布的 APK**里的值：仓库源码经常已经升到 6，而 release 附件还是旧的 1，
    # 只读源码会让 App 误判「可更新」，点下去装到的却是同一个包。
    published = None
    if apk:
        cached = ensure_apk(cache_dir, repo, apk)
        if cached:
            published = apk_meta(cached)

    return {
        "repo": repo,
        "repoUrl": meta["html_url"],
        "description": meta.get("description"),
        "updatedAt": meta.get("pushed_at"),
        "package": (published or {}).get("pkg") or gradle["pkg"],
        "id": gradle["id"],
        "name": gradle["name"] or modelpack.get("name"),
        # 对外展示/比较用发布包的版本；源码里的版本另存，便于发现「改了源码但没发版」
        "versionCode": (published or {}).get("versionCode") or gradle["versionCode"],
        "versionName": (published or {}).get("versionName") or gradle["versionName"],
        "sourceVersionCode": gradle["versionCode"],
        "sourceVersionName": gradle["versionName"],
        "apk": apk,
        "models": [
            {
                "key": m.get("key"),
                "name": m.get("name"),
                "engine": m.get("engine"),
                "scales": m.get("scales", []),
                "denoiseLevels": m.get("denoiseLevels", []),
                "supportsNpu": bool(m.get("supportsNpu")),
                "npuScales": m.get("npuScales", []),
            }
            for m in modelpack.get("models", [])
        ],
    }


def human_size(n: int | None) -> str:
    if not n:
        return "-"
    return f"{n / 1024 / 1024:.2f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


def render_readme(packs: list[dict], generated: str, sample: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# TachiyomiX 模型包插件目录")
    lines.append("")
    lines.append(
        "TachiyomiX「图像增强」的全部**外置模型包插件**目录：每个插件的**名称、地址、版本**"
        "（另有包名、体积、sha256 与机器可读索引）。宿主不内置任何模型：装一个显示一个、卸载即消失。",
    )
    lines.append("")
    lines.append(f"> 数据由 [`generate.py`](./generate.py) 直接读 GitHub API 生成，最后更新：`{generated}`（UTC）。")
    lines.append("")
    lines.append(
        "> 📘 **想自己做一个模型包插件？** 看 **[模型插件开发文档 PLUGIN-DEVELOPMENT.md](./PLUGIN-DEVELOPMENT.md)**："
        "描述符字段表、engine 约定与模型文件命名、BGR 通道坑、PyTorch→ncnn 转换流水线与实测坑表、"
        "自带原生库 ABI、工程模板、发布规范、验收清单。",
    )
    lines.append("")
    lines.append("## 安装方式")
    lines.append("")
    lines.append("1. 从下表「APK」列下载对应模型包，用系统安装器安装（侧载）。")
    lines.append("2. 打开 TachiyomiX → `设置 → 高级 → 模型包`，应当能看到该包与它的版本号。")
    lines.append("3. 阅读器内 →「增强设置」→ **模型**一栏选择要用的模型（显示的是模型名，不是包名）。")
    lines.append("")
    lines.append("> ⚠️ 若阅读器里「处理后端」选的是**骁龙 NPU**，列表只会显示声明支持 NPU 的模型；")
    lines.append("> 下表末列标注了各包是否支持 NPU，看不到某个包时先切回 **Vulkan**。")
    lines.append("")
    lines.append("## 插件清单（名称 / 地址 / 版本）")
    lines.append("")
    lines.append("| 名称 | 版本 | 插件地址（仓库） | APK 下载地址 |")
    lines.append("| --- | --- | --- | --- |")
    for p in packs:
        ver = f"{p['versionName']} (code {p['versionCode']})"
        if p["apk"]:
            apk = f"[{human_size(p['apk']['size'])}]({p['apk']['url']})"
        else:
            apk = "（暂无 release）"
        lines.append(f"| {p['name']} | {ver} | [{p['repo']}]({p['repoUrl']}) | {apk} |")
    lines.append("")
    stale = [p for p in packs if (p.get("sourceVersionCode") or 0) > (p.get("versionCode") or 0)]
    if stale:
        lines.append("> ⚠️ 下面这些仓库的**源码版本已经升上去了但还没发 Release**（App 与上表用的是实际发布包的版本）：")
        for p in stale:
            lines.append(
                f"> - `{p['id']}`：发布 `{p['versionName']} (code {p['versionCode']})`"
                f"，源码 `{p['sourceVersionName']} (code {p['sourceVersionCode']})`",
            )
        lines.append("")
    lines.append("## 标识信息")
    lines.append("")
    lines.append("| 名称 | 插件 ID | 包名（packageName） | versionCode |")
    lines.append("| --- | --- | --- | --- |")
    for p in packs:
        lines.append(f"| {p['name']} | `{p['id']}` | `{p['package']}` | {p['versionCode']} |")
    lines.append("")
    lines.append("## 每个包含的模型")
    lines.append("")
    lines.append("| 模型包 | 模型 key | 阅读器显示名 | engine | 倍率 | 降噪 | NPU |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for p in packs:
        for m in p["models"]:
            scales = "/".join(f"{s}x" for s in m["scales"]) or "-"
            denoise = ",".join(str(d) for d in m["denoiseLevels"]) or "无"
            npu = "是" if m["supportsNpu"] else "否"
            lines.append(
                f"| {p['name']} | `{m['key']}` | {m['name']} | `{m['engine']}` | {scales} | {denoise} | {npu} |",
            )
    lines.append("")
    lines.append("## 机器可读索引")
    lines.append("")
    lines.append("- [`index.json`](./index.json)：完整字段（含模型清单、APK 体积与 sha256、更新时间）。")
    lines.append("- [`index.min.json`](./index.min.json)：精简字段，形如扩展仓库的索引，便于程序消费：")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(sample[:2], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 相关")
    lines.append("")
    lines.append("- 宿主（TachiyomiX）：https://github.com/zhzipu/TachiyomiX")
    lines.append("- 模型包契约：`tachiyomix.modelpack` feature + `assets/modelpack.json` 描述符；宿主按已安装的包列模型。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"[proxy] PROXY={PROXY!r}  GH_TOKEN={'有' if TOKEN else '无'}", flush=True)

    print("[1/4] 发现 TachiyomiX-ModelPack-* 仓库")
    repos = [
        r["name"]
        for r in api(f"/users/{OWNER}/repos?per_page=100&sort=pushed")
        if r["name"].startswith(PREFIX) and r["name"] not in EXCLUDE
    ]
    print(f"      {len(repos)} 个：{', '.join(sorted(repos))}")

    print("[2/4] 抓取每个包的元数据（含下载 release APK 读真实版本号，缓存在 ../apk-cache）")
    cache_dir = outdir.parent / "apk-cache"
    packs: list[dict] = []
    for repo in sorted(repos):
        pack = collect(repo, cache_dir)
        if pack:
            packs.append(pack)
            flag = ""
            if (pack.get("sourceVersionCode") or 0) > (pack.get("versionCode") or 0):
                flag = f"  ⚠️源码已到 {pack['sourceVersionName']}({pack['sourceVersionCode']})"
            print(f"      {pack['id']:<20} {pack['versionName']} ({pack['versionCode']})  "
                  f"{human_size(pack['apk']['size'] if pack['apk'] else None)}  "
                  f"{len(pack['models'])} 个模型{flag}")
    packs.sort(key=lambda p: p["package"])

    print("[3/4] 写 index.json / index.min.json")
    generated = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M")
    index = {"schemaVersion": 1, "generatedAt": generated, "count": len(packs), "packs": packs}
    (outdir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    minimal = [
        {
            "name": p["name"],
            "id": p["id"],
            "pkg": p["package"],
            "version": p["versionName"],
            "code": p["versionCode"],
            "apk": p["apk"]["url"] if p["apk"] else None,
            "size": p["apk"]["size"] if p["apk"] else None,
            "sha256": p["apk"]["sha256"] if p["apk"] else None,
            "repo": p["repoUrl"],
        }
        for p in packs
    ]
    (outdir / "index.min.json").write_text(json.dumps(minimal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("[4/4] 写 README.md")
    (outdir / "README.md").write_text(render_readme(packs, generated, minimal), encoding="utf-8")

    print(f"完成：{outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
