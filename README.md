# TachiyomiX 模型包插件目录

TachiyomiX「图像增强」的全部**外置模型包插件**清单：每个包的标识、版本、体积、仓库地址与 APK 下载地址。宿主不内置任何模型，装一个显示一个、卸载即消失。

> 数据由 [`generate.py`](./generate.py) 直接读 GitHub API 生成，最后更新：`2026-10-14 07:30`（UTC）。

## 安装方式

1. 从下表「APK」列下载对应模型包，用系统安装器安装（侧载）。
2. 打开 TachiyomiX → `设置 → 高级 → 模型包`，应当能看到该包与它的版本号。
3. 阅读器内 →「增强设置」→ **模型**一栏选择要用的模型（显示的是模型名，不是包名）。

> ⚠️ 若阅读器里「处理后端」选的是**骁龙 NPU**，列表只会显示声明支持 NPU 的模型；
> 下表末列标注了各包是否支持 NPU，看不到某个包时先切回 **Vulkan**。

## 插件清单

| 模型包 | ID | 包名 | 版本 | APK | 仓库 |
| --- | --- | --- | --- | --- | --- |
| ACNE 模型 | `acnet` | `com.tachiyomix.modelpack.acnet` | 1.3 (6) | [40 KB](https://github.com/zhzipu/TachiyomiX-ModelPack-acnet/releases/download/v1.3/TachiyomiX-modelpack-acnet-release.apk) | [TachiyomiX-ModelPack-acnet](https://github.com/zhzipu/TachiyomiX-ModelPack-acnet) |
| Anime4K 模型 | `anime4k` | `com.tachiyomix.modelpack.anime4k` | 1.3 (6) | [40 KB](https://github.com/zhzipu/TachiyomiX-ModelPack-anime4k/releases/download/v1.3/TachiyomiX-modelpack-anime4k-release.apk) | [TachiyomiX-ModelPack-anime4k](https://github.com/zhzipu/TachiyomiX-ModelPack-anime4k) |
| Omni Small 模型 | `omni-small` | `com.tachiyomix.modelpack.omnismall` | 1.4 (7) | [1.47 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-omni-small/releases/download/v1.4/TachiyomiX-modelpack-omni-small-release.apk) | [TachiyomiX-ModelPack-omni-small](https://github.com/zhzipu/TachiyomiX-ModelPack-omni-small) |
| Real-CUGAN 模型 | `realcugan` | `com.tachiyomix.modelpack.realcugan` | 1.3 (6) | [25.74 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan/releases/download/v1.3/TachiyomiX-modelpack-realcugan-release.apk) | [TachiyomiX-ModelPack-realcugan](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan) |
| Real-CUGAN Nose 模型 | `realcugan-nose` | `com.tachiyomix.modelpack.realcugannose` | 1.3 (6) | [2.27 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan-nose/releases/download/v1.3/TachiyomiX-modelpack-realcugan-nose-release.apk) | [TachiyomiX-ModelPack-realcugan-nose](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan-nose) |
| Real-CUGAN Pro 模型 | `realcugan-pro` | `com.tachiyomix.modelpack.realcuganpro` | 1.3 (6) | [13.74 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan-pro/releases/download/v1.3/TachiyomiX-modelpack-realcugan-pro-release.apk) | [TachiyomiX-ModelPack-realcugan-pro](https://github.com/zhzipu/TachiyomiX-ModelPack-realcugan-pro) |
| Real-ESRGAN 模型 | `realesrgan` | `com.tachiyomix.modelpack.realesrgan` | 1.3 (6) | [13.44 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-realesrgan/releases/download/v1.3/TachiyomiX-modelpack-realesrgan-release.apk) | [TachiyomiX-ModelPack-realesrgan](https://github.com/zhzipu/TachiyomiX-ModelPack-realesrgan) |
| SPAN NomosUni 模型 | `span-nomosuni` | `com.tachiyomix.modelpack.spannomosuni` | 1.3 (6) | [1.47 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni/releases/download/v1.3/TachiyomiX-modelpack-span-nomosuni-release.apk) | [TachiyomiX-ModelPack-span-nomosuni](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni) |
| NomosUni Span 4x 模型 | `span-nomosuni-4x` | `com.tachiyomix.modelpack.spannomosuni4x` | 1.4 (7) | [1.50 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni-4x/releases/download/v1.4/TachiyomiX-modelpack-span-nomosuni-4x-release.apk) | [TachiyomiX-ModelPack-span-nomosuni-4x](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni-4x) |
| sudo UltraCompact 模型 | `sudo-ultracompact` | `com.tachiyomix.modelpack.sudoultracompact` | 1.3 (6) | [1.09 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-sudo-ultracompact/releases/download/v1.3/TachiyomiX-modelpack-sudo-ultracompact-release.apk) | [TachiyomiX-ModelPack-sudo-ultracompact](https://github.com/zhzipu/TachiyomiX-ModelPack-sudo-ultracompact) |
| waifu2x 基础模型 | `waifu2x` | `com.tachiyomix.modelpack.waifu2x` | 1.3 (6) | [22.10 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-waifu2x/releases/download/v1.3/TachiyomiX-modelpack-waifu2x-release.apk) | [TachiyomiX-ModelPack-waifu2x](https://github.com/zhzipu/TachiyomiX-ModelPack-waifu2x) |
| waifu2x Upconv7 模型 | `waifu2x-upconv7` | `com.tachiyomix.modelpack.waifu2xupconv7` | 1.3 (6) | [4.92 MB](https://github.com/zhzipu/TachiyomiX-ModelPack-waifu2x-upconv7/releases/download/v1.3/TachiyomiX-modelpack-waifu2x-upconv7-release.apk) | [TachiyomiX-ModelPack-waifu2x-upconv7](https://github.com/zhzipu/TachiyomiX-ModelPack-waifu2x-upconv7) |

## 每个包含的模型

| 模型包 | 模型 key | 阅读器显示名 | engine | 倍率 | 降噪 | NPU |
| --- | --- | --- | --- | --- | --- | --- |
| ACNE 模型 | `acnet` | ACNet f8b4 x2 | `acnet` | 2x | 无 | 否 |
| Anime4K 模型 | `anime4k` | Anime4K Original x2 | `anime4k` | 2x | 无 | 否 |
| Omni Small 模型 | `omni-small` | Omni Small (HFA2k SPAN) x2 | `hfa2k-span` | 2x | 无 | 否 |
| Real-CUGAN 模型 | `realcugan-se` | Real-CUGAN SE | `realcugan-se` | 2x/3x/4x | 0,1,2,3,4 | 是 |
| Real-CUGAN Nose 模型 | `realcugan-nose` | Real-CUGAN Nose | `realcugan-nose` | 2x | 无 | 否 |
| Real-CUGAN Pro 模型 | `realcugan-pro` | Real-CUGAN Pro | `realcugan-pro` | 2x/3x | 0,3,4 | 是 |
| Real-ESRGAN 模型 | `realesrgan` | Real-ESRGAN | `realesrgan` | 2x/3x/4x | 无 | 是 |
| SPAN NomosUni 模型 | `span-nomosuni` | SPAN NomosUni Photo | `span-nomosuni` | 2x | 无 | 是 |
| NomosUni Span 4x 模型 | `span-nomosuni-4x` | NomosUni Span 4x | `span-nomosuni-4x` | 4x | 无 | 否 |
| sudo UltraCompact 模型 | `sudo-ultracompact` | sudo UltraCompact | `sudo-ultracompact` | 2x | 无 | 否 |
| waifu2x 基础模型 | `waifu2x` | Waifu2x | `waifu2x` | 2x | 0,1,2,3 | 否 |
| waifu2x Upconv7 模型 | `waifu2x-upconv7` | Waifu2x (Fast) | `waifu2x-upconv7` | 2x | 0,1,2,3 | 否 |

## 机器可读索引

- [`index.json`](./index.json)：完整字段（含模型清单、APK 体积与 sha256、更新时间）。
- [`index.min.json`](./index.min.json)：精简字段，形如扩展仓库的索引，便于程序消费：

```json
[
  {
    "name": "ACNE 模型",
    "id": "acnet",
    "pkg": "com.tachiyomix.modelpack.acnet",
    "version": "1.3",
    "code": 6,
    "apk": "https://github.com/zhzipu/TachiyomiX-ModelPack-acnet/releases/download/v1.3/TachiyomiX-modelpack-acnet-release.apk",
    "size": 41262,
    "sha256": "c60e0936f4e22bf939b5feb590944920158e57e6f57d069e023c7192ee304ab0",
    "repo": "https://github.com/zhzipu/TachiyomiX-ModelPack-acnet"
  },
  {
    "name": "Anime4K 模型",
    "id": "anime4k",
    "pkg": "com.tachiyomix.modelpack.anime4k",
    "version": "1.3",
    "code": 6,
    "apk": "https://github.com/zhzipu/TachiyomiX-ModelPack-anime4k/releases/download/v1.3/TachiyomiX-modelpack-anime4k-release.apk",
    "size": 41258,
    "sha256": "2c269c17d1cd680818d776fce84c4e6656b4fcff831fc61119c2c3062b63d32f",
    "repo": "https://github.com/zhzipu/TachiyomiX-ModelPack-anime4k"
  }
]
```

## 相关

- 宿主（TachiyomiX）：https://github.com/zhzipu/TachiyomiX
- 模型包契约：`tachiyomix.modelpack` feature + `assets/modelpack.json` 描述符；宿主按已安装的包列模型。
