# TachiyomiX 模型包插件开发文档

> 适用宿主：**TachiyomiX 1.0.4+**（描述符 `schemaVersion 1`、原生库 `MODELPACK_ABI_VERSION 1`）
>
> 本文里的字段名、常量、加载顺序、文件命名**全部取自宿主源码**，不是约定俗成的说法：
> `app/src/main/java/eu/kanade/tachiyomi/modelpack/{ModelPack,ModelPackLoader,ModelPackDescriptor,ModelPackManager}.kt`、
> `app/src/main/java/eu/kanade/tachiyomi/util/waifu2x/{EnhancementEngine,PackNativeEngine,Waifu2x}.kt`、
> `app/src/main/cpp/{modelpack_abi.h,waifu2x_jni.cpp}`。

---

## 目录

- [0. 先看结论：最小可用插件](#0-先看结论最小可用插件)
- [1. 模型包是什么，宿主怎么加载它](#1-模型包是什么宿主怎么加载它)
- [2. 描述符 `assets/modelpack.json` 字段表](#2-描述符-assetsmodelpackjson-字段表)
- [3. 引擎（engine）约定：模型文件该叫什么名字](#3-引擎engine约定模型文件该叫什么名字)
- [4. 通道顺序：宿主是 BGR（最容易踩的坑）](#4-通道顺序宿主是-bgr最容易踩的坑)
- [5. 进阶：自带原生推理库 `libmodelpack.so`](#5-进阶自带原生推理库-libmodelpackso)
- [6. 权重转换流水线（PyTorch → ncnn）](#6-权重转换流水线pytorch--ncnn)
- [7. 工程模板与构建](#7-工程模板与构建)
- [8. 发布到 GitHub 并登记进本目录](#8-发布到-github-并登记进本目录)
- [9. 验收清单](#9-验收清单)
- [10. 常见问题 / 排错](#10-常见问题--排错)
- [附录 A：关键日志行](#附录-a关键日志行)

---

## 0. 先看结论：最小可用插件

宿主**不内置任何模型**，一个「模型包插件」就是一个**没有代码的 APK**，只往 `assets/` 里塞权重和一份描述符。

以本目录里真实存在的 `omni-small`（SPAN 2x）为例，完整仓库就这些文件：

```
TachiyomiX-ModelPack-omni-small/
├── build.gradle.kts                 # 单模块 Android 工程（不需要 Kotlin 代码）
├── settings.gradle.kts
├── gradle.properties
├── gradlew / gradlew.bat
├── gradle/wrapper/…                 # Gradle 9.6.1 wrapper
├── .gitattributes                   # *.bin binary / *.param -text（必须）
├── .gitignore
├── README.md
└── src/main/
    ├── AndroidManifest.xml          # 声明 tachiyomix.modelpack
    └── assets/
        ├── modelpack.json           # 描述符：这个包提供哪些模型
        └── omni-small/
            ├── 2x-HFA2kSPAN.param   # ncnn 网络结构
            ├── 2x-HFA2kSPAN.bin     # ncnn 权重
            └── ATTRIBUTION.txt      # 来源与许可（非必需，但强烈建议）
```

五步流程：

1. 把权重转成 ncnn 的 `<stem>.param` + `<stem>.bin`（见 [§6](#6-权重转换流水线pytorch--ncnn)）；
2. 写 `assets/modelpack.json`，`engine` 填宿主已实现的算法值（见 [§3](#3-引擎engine约定模型文件该叫什么名字)）；
3. 用 [§7](#7-工程模板与构建) 的工程模板打包（`./gradlew assembleRelease`）；
4. 装机后在 `设置 → 高级 → 模型包` 确认宿主认到了它（版本号要对）；发布到 GitHub Release 后，**这一页会直接列出它并支持一键安装/更新**（下面 [§8](#8-发布到-github-并登记进本目录)）；
5. 阅读器 →「增强设置」→ 模型一栏选中它，出图验收（见 [§9](#9-验收清单)）。

---

## 1. 模型包是什么，宿主怎么加载它

### 1.1 契约（四条，缺一不可）

| # | 要求 | 说明 |
| --- | --- | --- |
| 1 | `<uses-feature android:name="tachiyomix.modelpack" android:required="false" />` | 宿主靠它识别「这是模型包」。**必须带 `GET_CONFIGURATIONS` 才能读到**，宿主已处理 |
| 2 | meta-data `tachiyomix.modelpack.id` / `tachiyomix.modelpack.name` | `id` 必填（解压目录名、日志、去重都用它）；`name` 缺省时等于 `id` |
| 3 | 模型文件放 `assets/` 下，保留相对路径 | 宿主是**无代码 APK**，读不到别的 APK 的 AssetManager，所以会把 `assets/` 全部解压到磁盘 |
| 4 | `assets/modelpack.json` 描述符 | 声明提供哪些模型、用什么 engine、有哪些倍率/降噪/精度可选 |

### 1.2 安装后的解压与失效规则（**改包必须升版本号**）

```
filesDir/model-packs/<id>/          ← assets/ 的内容按原相对路径落盘
filesDir/model-packs/<id>/.pack-state   ← 内容为 "<packageName>:<versionCode>"
```

- 解压状态用 `packageName:versionCode` 判断：**状态一致就直接复用，不重新解压**。
  所以**只要改了 `assets/` 里的任何东西（哪怕只改描述符里的显示名），都必须升 `versionCode`**，否则设备上跑的还是旧文件，改动静默不生效。
- 有效性：解压目录里存在 `.bin`/`.param`，**或**存在 `modelpack.json`（纯原生包可以没有权重文件）。
- 卸载模型包时宿主会清理残留目录；扫描时机是应用启动与模型包增删广播。

### 1.3 两条实现通路

```
EnhancementEngines.engineFor(model)
   ├─ 1. PackNativeEngines.engineFor(...)   ← 包内 lib/<abi>/libmodelpack.so（可选，优先级最高）
   └─ 2. builtIn[model.engine]              ← 宿主内置算法实现（绝大多数插件走这里）
未命中 → 跳过本页增强并写日志，不崩溃
```

- **纯权重包**（本目录里全部 12 个包都是这种）：只提供 `.param/.bin`，走宿主内置引擎；新增同架构模型**不需要**宿主改动。
- **自带原生库的包**：可以带自己的推理实现（见 [§5](#5-进阶自带原生推理库-libmodelpackso)），此时该包优先走包内实现。

---

## 2. 描述符 `assets/modelpack.json` 字段表

解析器行为（`ModelPackDescriptorParser`）：

- `ignoreUnknownKeys = true` + `isLenient = true`：**多写字段不会炸**，字段缺失一律取默认值；
- `schemaVersion > 1` → **整包忽略**（日志会写明）；
- `models[]` 里有 `key` / `engine` / `assetPath` 任一为空的条目会被**过滤掉**；
- `models` 为空 → 整包忽略；
- 描述符里的 `id` 与 manifest 不一致时**以 manifest 为准**（只打日志）；
- 描述符文件缺失或 JSON 非法 → 只跳过这个包，不影响其它包。

### 2.1 顶层

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `schemaVersion` | int | `1` | 只支持 `1`（更大值整包被忽略） |
| `id` | string | `""` | 应与 manifest 的 `tachiyomix.modelpack.id` 一致 |
| `name` | string | `""` | 包显示名（出现在 `设置 → 高级 → 模型包`） |
| `models` | array | `[]` | 见 2.2，**不能为空** |
| `options` | object | `null` | 见 2.4；缺失时宿主不展示对应设置行 |

### 2.2 `models[]`

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `key` | string | 必填 | 稳定唯一标识，也是用户选择的持久化值 |
| `name` | string | `""` | **阅读器「模型」一栏显示的就是它**（不是包名） |
| `engine` | string | 必填 | 见 [§3](#3-引擎engine约定模型文件该叫什么名字) |
| `assetPath` | string | 必填 | 模型目录相对解压根目录的路径，如 `omni-small`、`realesrgan-models/v3-anime` |
| `scales` | int[] | `[]` | 允许的输出倍率，如 `[2]`、`[2,3,4]` |
| `denoiseLevels` | int[] | `[]` | 允许的降噪档位；空数组 = 该模型没有降噪选项 |
| `precisions` | int[] | `[0,1,2,3]` | `0=FP16`、`1=FP32`、`2=INT8`、`3=BF16` |
| `supportsNpu` | bool | `false` | 是否有 Qualcomm NPU(QNN) 实现 |
| `npuScales` | int[] | `[]` | NPU 通路允许的倍率；空则等同 `scales` |
| `defaults` | object | `{}` | 回退默认值：`scale` / `denoise` / `style` / `precision` |
| `styles` | array | `[]` | 可选「风格」，见 2.3 |
| `defaultStyle` | int? | `null` | 缺省取 `styles[0]` |

> **重要**：阅读器里那条 chip 显示 `models[].name`；`设置 → 高级 → 模型包` 列表显示的是顶层 `name` + 包名。
> 用户按「插件名」找不到模型时，通常就是这两个名字不一致（例如插件叫 Omni Small，模型名是 `Omni Small (HFA2k SPAN) x2`）。
>
> 另外：**升级插件必须递增 `versionCode`** —— 宿主既用它判断解压缓存是否失效（见 1.2），
> 也用它和目录索引里的 `code` 比较来判断「有没有新版本」（见 [§8](#8-发布到-github-并登记进本目录)）。

### 2.3 `styles[]`（可选，Real-ESRGAN 这类多风格模型用）

| 字段 | 说明 |
| --- | --- |
| `value` | 风格值（持久化用） |
| `name` | 显示名 |
| `assetPath` | 覆盖模型级 `assetPath`（不同风格不同权重目录） |
| `scales` | 覆盖模型级 `scales` |
| `modelScale` | **底层模型自身的倍率**，例如用 4x 权重输出 2x 时填 `4`；空则等于输出倍率 |

### 2.4 `options`（包级可调项）

宿主持久化的仍是它自己的偏好项，这里只决定**设置行是否可见**与**可选值**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `preloadPages` | int[] | 「预加载页数」可选值 |
| `gpuPerformanceModes` | int[] | GPU 性能模式可选值 |
| `tileSizes` | int[] | 分块大小可选值（越大越快、越吃显存） |
| `maxProcessingResolution` | `{width,height}` | 处理分辨率上限（0 = 不限制） |
| `maxResolution` | `{width,height}` | 输出分辨率上限 |
| `fp16Arithmetic` | bool | 是否提供 FP16 运算开关 |

### 2.5 一个可直接抄的完整例子

```json
{
  "schemaVersion": 1,
  "id": "omni-small",
  "name": "Omni Small 模型",
  "models": [
    {
      "key": "omni-small",
      "name": "Omni Small (HFA2k SPAN) x2",
      "engine": "hfa2k-span",
      "assetPath": "omni-small",
      "scales": [2],
      "denoiseLevels": [],
      "precisions": [0, 1, 2, 3],
      "supportsNpu": false,
      "defaults": { "scale": 2, "precision": 0 }
    }
  ],
  "options": {
    "preloadPages": [1, 2, 3, 5, 8],
    "gpuPerformanceModes": [0, 1, 2],
    "tileSizes": [64, 96, 128, 192, 256],
    "maxProcessingResolution": { "width": 1600, "height": 1600 },
    "maxResolution": { "width": 0, "height": 0 },
    "fp16Arithmetic": true
  }
}
```

---

## 3. 引擎（engine）约定：模型文件该叫什么名字

`engine` 是**算法实现的名字**，不是模型目录。宿主认识的取值如下（未知值只会让该模型被跳过）。

### 3.1 宿主内置 engine 全表（11 个）

| engine | 算法 / 用途 | 模型文件命名（放在 `assetPath` 目录里） |
| --- | --- | --- |
| `waifu2x` | waifu2x | `noise<N>_scale2.0x_model.param/.bin`；scale=1 时为 `noise<N>_model.*`；`noise=-1` 时为 `scale2.0x_model.*` |
| `waifu2x-upconv7` | waifu2x UpConv7 | `noise<N>_scale2.0x_model.param/.bin` |
| `realcugan-se` | Real-CUGAN SE | `up<S>x-<档位>.param/.bin`，档位如 `no-denoise` / `denoise1x` / `denoise2x` / `denoise3x` / `conservative` |
| `realcugan-pro` | Real-CUGAN Pro | 同上（同一实现，换目录与可用档位） |
| `realcugan-nose` | Real-CUGAN no-denoise | `up2x-no-denoise.param/.bin` |
| `realesrgan` | Real-ESRGAN（支持 styles） | `x<modelScale>.param/.bin`，如 `x4.param` |
| `span-nomosuni` | SPAN NomosUni 2x | `<stem>.param/.bin`，走通用通道（见 3.2） |
| `span-nomosuni-4x` | SPAN NomosUni 4x | 同上 |
| `hfa2k-span` | HFA2k SPAN 2x（Omni Small 用） | 同上 |
| `sudo-ultracompact` | sudo UltraCompact | 同上 |
| `acnet` | ACNet（Anime4KCPP 同源） | 同上 |

### 3.2 通用 ncnn 通道（新增权重最省事的一条路）

后 5 个 engine 都走同一个宿主入口 `Waifu2x.initW2xEx(...)`：只吃 `<assetPath>/<stem>.param` + `<stem>.bin`，
`stem`、halo、QNN context 名由宿主引擎表写死：

| engine | `stem` | halo（tile 四周预留像素） | QNN context |
| --- | --- | --- | --- |
| `span-nomosuni` | `2x-NomosUni-SPAN-multijpg-ldl` | 24 | `span-nomosuni-x2` |
| `span-nomosuni-4x` | `4x-NomosUni-SPAN-multijpg` | 24 | 无（故 `supportsNpu: false`） |
| `hfa2k-span` | `2x-HFA2kSPAN` | 24 | 无 |
| `sudo-ultracompact` | `2x-sudo-UltraCompact` | 10 | 无 |
| `acnet` | `acnet` | 10 | 无 |

**实用结论**：

- 想换成**同架构的另一套权重**（同 stem、同倍率）：只改包里的 `.param/.bin`，描述符不用动 —— 换个 `versionCode` 重新发版即可。
- 想加 **SPAN 家族的又一个模型**（例如 2x 换成别的训练集、或 4x 的另一套权重）：可以复用上表某个 engine，
  也可以请宿主加一个新 engine 值（一行 `NcnnModelSpec`），宿主成本极低。
- halo 太小 → tile 边界会出现接缝；它是模型感受野决定的，别随意调小。

### 3.3 NPU（骁龙）通路

- `supportsNpu: true` 且宿主 `assets/qnn-contexts/` 里有对应 context 名，才可能走 NPU；
- **阅读器里「处理后端」选 NPU 时，模型列表只显示 `supportsNpu: true` 的模型** —— 纯重量包会被整条过滤掉，用户「找不到插件」多半是这个原因，切回 Vulkan 即可；
- 没有 QNN context 的权重（包括自己转的）应老实写 `"supportsNpu": false`。

---

## 4. 通道顺序：宿主是 BGR（最容易踩的坑）

宿主 ncnn 通路的输入/输出**都是 BGR 排列**（`waifu2x.cpp` 里 net 的 ch0 取源图 B，输出 ch0 写回 RGBA 的 byte 2；融合着色器用 `source_channel = 2 - gz`）。数据范围两端都是 `0..1`。

也就是说：

- 你从 PyTorch 转出来的图，如果原模型是 **RGB 训练**的（绝大多数 SR 模型都是），**必须做通道适配**，否则出图**红蓝互换**；
- 用 `pnnx` 直接转出来的图是「输入 RGB → 输出 RGB」；
- 转换脚本里的做法是**在模型两端各插一个 1×1 置换卷积**（不动权重、数值精确、可被 ncnn 正常执行）：

```python
perm = torch.tensor([[0,0,0],[0,0,1],[0,1,0]], dtype=torch.float32).view(3,3,1,1)
swap_in  = torch.nn.Conv2d(3, 3, 1, bias=False); swap_in.weight.data  = perm.clone()   # BGR -> RGB
swap_out = torch.nn.Conv2d(3, 3, 1, bias=False); swap_out.weight.data = perm.clone()   # RGB -> BGR
```

自检方法：同一个输入分别喂 PyTorch（加同样的置换）与 ncnn，逐像素比对（见 [§6.5](#65-数值自检必做)）。
经验性的旁证：把合成漫画页喂给已发布的模型，输出应落在 `0..1` 量级、与输入做最小二乘拟合斜率 ≈1、相关性 0.96~0.98。

---

## 5. 进阶：自带原生推理库 `libmodelpack.so`

模型包可选地带一个 `.so`，实现自己的推理（C/C++/Rust 均可，只要导出 C 符号）。
宿主用 `dlopen` 加载、校验 ABI 版本，成功则**该包的模型优先走包内实现**，失败或没有 `.so` 就回退内置引擎（行为与不带 `.so` 完全一致）。

### 5.1 稳定 C ABI（`MODELPACK_ABI_VERSION = 1`）

| 符号 | 必需 | 说明 |
| --- | --- | --- |
| `int modelpack_abi_version(void)` | ✅ | 必须返回 `1`，不匹配宿主直接忽略该库 |
| `const char *modelpack_describe(void)` | 可选 | 返回自描述 JSON（格式同 `modelpack.json`），宿主仅用于日志 |
| `int modelpack_init(const char *model_key, const char *options_json)` | ✅ | 按模型 `key` 初始化；返回 `0` 成功 |
| `int modelpack_process(const unsigned char *rgba_in, int width, int height, int stride_in, unsigned char *rgba_out, int stride_out)` | ✅ | 处理一帧 RGBA8888；返回 `0` 成功 |
| `void modelpack_release(void)` | ✅ | 释放 `init` 申请的资源 |
| `void modelpack_set_progress_callback(void (*)(int percent))` | 可选 | 宿主在 `init` 前调用，用于驱动阅读器左下角单页进度条 |

`options_json` 字段（宿主传入）：

```json
{"model":"<models[].key>","noise":0,"scale":2,"precision":0,
 "fp16Arithmetic":true,"tileSize":128,"tileSleepMs":0,"backend":0,"style":0}
```

### 5.2 实现要点

- **只导出 C 符号**（`extern "C"`），不要导出 C++ mangled 名；
- 输入/输出是 RGBA8888，`stride` 单位为**字节**（宿主可能传入带 stride 的缓冲，不要假设 `stride == width*4`）；
- **输出尺寸必须是 `scale × 输入尺寸`**，宿主据此分配输出 bitmap；
- 宿主保证同一时刻只有一个线程调用 `process`，你不必自己做并发控制；
- 版本不兼容变更 → 递增 ABI 版本号（宿主侧常量同步改）。

### 5.3 打包注意

- `.so` 放 `src/main/jniLibs/<abi>/libmodelpack.so`（或 `lib/<abi>/`）；
- 工程里必须 `packaging { jniLibs { useLegacyPackaging = true } }`：**原生库要被解压到 `nativeLibraryDir`**，
  宿主才能用系统认可的路径 `dlopen`；留在 APK 内会出现加载被拒；
- 宿主查找顺序：① `ApplicationInfo.nativeLibraryDir`；② 包内 `lib/<设备 ABI>/libmodelpack.so`（解压后）;
- **纯原生包**可以没有 `.param/.bin`，只要描述符 + `.so` 就算有效模型包。

---

## 6. 权重转换流水线（PyTorch → ncnn）

参考环境（本目录里的包就是这样转出来的）：`torch 2.14.1+cpu`、`spandrel 0.4.2`、`numpy 2.5.4`、`pnnx`（随 ncnn 发布）。

### 6.1 四步

```python
import torch, spandrel, subprocess

# 1) 读权重（spandrel 认大部分 SR 架构，支持 .safetensors / .pth）
model = spandrel.ModelLoader().load_from_file("2xHFA2kSPAN.safetensors").model.eval()

# 2) 必要时结构改写（见 6.4 的坑表），再包一层 BGR 适配（见 §4）
wrapped = torch.nn.Sequential(swap_in, model, swap_out).eval()

# 3) 固定尺寸 trace（尺寸要是模型能整除的，且尽量贴近真实 tile）
traced = torch.jit.trace(wrapped, torch.rand(1, 3, 192, 192))
torch.jit.save(traced, "traced.pt")

# 4) pnnx 转 ncnn
subprocess.run([
    "pnnx", "traced.pt",
    "inputshape=[1,3,192,192]f32",
    "device=cpu", "optlevel=2", "fp16=0",
], check=True)
# 产出 model.ncnn.param / model.ncnn.bin → 重命名成 <stem>.param / <stem>.bin
```

### 6.2 已验证「干净」的层集合

SPAN 家族（`span-nomosuni` / `span-nomosuni-4x` / `hfa2k-span`）转出来只有：
`Input / Convolution / Split / MemoryData / BinaryOp / Swish / Sigmoid / PixelShuffle` —— 这套在设备上已经跑了很久，风险极低。

### 6.3 `inputshape` 怎么选

- 用**真实会出现的 tile 尺寸**（宿主默认 128，可选到 256），太小会让某些结构退化；
- 某些架构里有 `pad_to_multiple` 之类的补边逻辑，**trace 尺寸取 8 的倍数时可能变成 no-op**，导致你自以为验证过其实没有；
- 有动态插值（`F.interpolate(..., x.size())`）的架构要特别注意 6.4 的最后两条。

### 6.4 实测坑表（症状 → 处理）

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `load_param` 返回 `-1`，日志 `invalid equation` | ncnn **没有 Einsum 层** | 把 attention 里的 `einsum` 改成等价 `@` / `matmul` |
| `torch.jit.trace` 报错，图里出现 `LayerNormFunction` | 自定义 `autograd.Function` 无法 trace | 换成等价的纯 torch 实现（如 LayerNorm2d） |
| pnnx 生成 `Normalize` 层，ncnn `load_model` 失败 | ncnn 的 `Normalize` 是「按通道跨空间」，与 `F.normalize(dim=-1)` 语义不同 | 用显式 `sum/sqrt/div` 重写 |
| `aten::clamp_min` 未翻译 + 出现没有输入的 `pnnx.Expression` | 转换器不认该算子 | 用 `norm + 1e-12` 之类等价写法替换 |
| 图里 `Interp 3=256 4=256` 写死 | trace 时把动态尺寸烘成了常量，**图只对 trace 尺寸正确** | 别用动态插值；实在要用就「尺寸锁定」并在描述符里把倍率/tile 收敛到该尺寸 |
| 上述都改完 pnnx 直接崩（`0xC0000005`） | 图里算子组合过于复杂（大量 Reshape/Permute/Slice/MatMul） | 该架构在当前工具链下放弃，换同家族别的网络 |
| 均匀噪声输入下 max\|Δ\| 巨大（几十~几百） | SR 模型对 OOD 输入会输出极端值，这是**误报** | 见 6.5：用结构化输入 + 相对容差 |
| 分块与整图结果在图片**外边界**差异很大 | 整图用网络自身补边、分块用复制补边，边界本来就不同 | 只比**内部区域** |

### 6.5 数值自检（必做）

转完**不要只看能不能出图**，至少做这三件事：

1. **PyTorch vs ncnn 逐像素比对**
   - 输入用**结构化图**（画一些线条/渐变/文字，像一张漫画页），
     **不要用均匀随机噪声**：SR 模型对分布外输入会吐出 ±400 的尖峰，绝对容差必然误报；
   - 容差用 `atol + rtol * max|ref|`（实测 SPAN 家族在 64/128/256/320/384 尺寸下 max|Δ| ≈ 1e-6 ~ 5e-6）；
   - 别忘了两侧都要加 §4 的 BGR 置换。
2. **分块 vs 整图**（验证 halo 够不够）
   - 用与宿主一致的分块方式切图（默认 tile 128，halo 见 3.2），
   - **只比较内部区域**，接缝应可忽略（实测 ≈3e-6）。
3. **形状/命名核对**
   - 目录里最终只有 `<stem>.param` + `<stem>.bin`，`stem` 与 [§3.2](#32-通用-ncnn-通道新增权重最省事的一条路) 的表一致；
   - 描述符 `assetPath` 指到该目录，`scales` 与实际放大倍数一致。

---

## 7. 工程模板与构建

单模块 Gradle 工程即可（不需要 Kotlin 代码、不需要版本目录、不需要 flavor）：

```
settings.gradle.kts      pluginManagement(google/mavenCentral/gradlePluginPortal) + rootProject.name
build.gradle.kts         com.android.application
gradle.properties        org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
gradlew / gradlew.bat / gradle/wrapper/*      Gradle 9.6.1
.gitattributes           *.bin binary / *.param -text
.gitignore               .gradle/ build/ .idea/ *.iml local.properties .DS_Store *.log
src/main/AndroidManifest.xml
src/main/assets/**
```

`build.gradle.kts` 的关键点（完整可抄的版本见任何一个插件仓库）：

```kotlin
plugins { id("com.android.application") version "9.2.1" }

android {
    namespace = "com.tachiyomix.modelpack.<yourpack>"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.tachiyomix.modelpack.<yourpack>"
        minSdk = 26
        targetSdk = 36
        versionCode = 7            // ⚠️ 改了 assets 必须 +1，否则设备不会重新解压
        versionName = "1.4"
        manifestPlaceholders["modelpackId"] = "<pack-id>"
        manifestPlaceholders["modelpackName"] = "<包显示名>"
    }

    buildTypes {
        named("release") {
            signingConfig = signingConfigs.getByName("debug")  // 侧载安装，与官方包一致用 debug 签名
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }

    // 带 libmodelpack.so 的包必须解压原生库，否则宿主无法 dlopen
    packaging { jniLibs { useLegacyPackaging = true } }

    lint { abortOnError = false; checkReleaseBuilds = false }
}

androidComponents {
    onVariants { variant ->
        variant.outputs.forEach { it.outputFileName.set("TachiyomiX-modelpack-<flavor>-release.apk") }
    }
}

// ⚠️ 工程里没有 Kotlin 源码：去掉标准库依赖，否则 kotlin-stdlib 会被 dex 进 APK，
//    白白大 0.6~0.7 MB（实测 1.54 MB → 2.18 MB）
configurations.configureEach {
    exclude(group = "org.jetbrains.kotlin", module = "kotlin-stdlib")
}
```

`src/main/AndroidManifest.xml`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-feature android:name="tachiyomix.modelpack" android:required="false" />
    <application android:hasCode="false" android:label="${modelpackName}">
        <meta-data android:name="tachiyomix.modelpack.id"   android:value="${modelpackId}" />
        <meta-data android:name="tachiyomix.modelpack.name" android:value="${modelpackName}" />
    </application>
</manifest>
```

构建：

```bash
./gradlew assembleRelease
# 产物：build/outputs/apk/release/TachiyomiX-modelpack-<flavor>-release.apk
```

需要 Android SDK（`compileSdk 37`）与 `ANDROID_HOME`（或 `local.properties` 里的 `sdk.dir`）。

---

## 8. 发布到 GitHub 并登记进本目录

一个插件一个仓库，建议命名 `TachiyomiX-ModelPack-<id>`。

**Release 约定**（与本目录、既有 12 个包保持一致）：

| 项 | 取值 |
| --- | --- |
| tag | `v<versionName>`，例如 `v1.4` |
| Release 名 | `<包显示名> v<versionName>`，例如 `Omni Small 模型 v1.4` |
| 附件 | 构建出来的 APK，文件名 `TachiyomiX-modelpack-<flavor>-release.apk` |
| 正文 | 模型 ID、版本（含 versionCode）、APK 名与体积、安装步骤、说明、权重来源与许可 |

上传后**核对附件 sha256**（GitHub API 的 `digest` 字段）与本地文件一致。

**登记进本目录**（本仓库的 `generate.py` 会自动扫 `TachiyomiX-ModelPack-*` 全部仓库）：

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:7897"   # 有代理时；直连可省
$env:GH_TOKEN    = "<你的 token>"            # 只读公开数据也需要它更稳
python generate.py .
git add -A; git commit -m "Update catalog"; git push
```

生成器会读每个仓库的 `build.gradle.kts`（版本/包名/描述符 id+name）、`assets/modelpack.json`（模型清单/engine/倍率/NPU）
和 releases（tag、APK 名/体积/sha256/下载地址），写入 `README.md` + `index.json` + `index.min.json`。

### 8.1 上架后 App 内就能装（这一段决定索引字段不能乱改）

TachiyomiX 的 `设置 → 高级 → 模型包` 会**直接读本目录的 `index.min.json`**，把每个插件的
`name` / `version` / `code` / `apk` / `size` / `sha256` 都用起来：

| 字段 | App 用途 |
| --- | --- |
| `name` | 列表标题 |
| `version` / `code` | 展示版本；`code` 与已安装包的 versionCode 比较 → 判断「可更新」（`code` 更大才算新） |
| `apk` | 下载地址（走「模型插件下载」代理作用域） |
| `size` | 列表里显示体积 |
| `sha256` | 下载后校验，不一致直接删文件、不交给安装器 |
| `id` | 与已安装模型包的 `tachiyomix.modelpack.id` 对应 → 判断「已安装 / 可安装」 |

所以要改索引字段名时，**宿主和本目录必须一起改**；`sha256` 也别省（省了 App 就少一层校验）。
App 侧还有两条代理作用域：`模型插件仓库`（读索引）与 `模型插件下载`（下 APK），默认都直连。

---

## 9. 验收清单

装机后逐条过一遍：

- [ ] `设置 → 高级 → 模型包` 里能看到该包，**版本号是刚发的那个**（不是旧的 → 忘了升 `versionCode`）
- [ ] **发布到目录仓库后**，同一页面里该插件显示为「可安装」（没装）或「可更新」（装了旧版），能一键下载安装
- [ ] 阅读器 →「增强设置」→ 模型一栏出现该模型，**名字等于 `models[].name`**
- [ ] 「处理后端」若是**骁龙 NPU**，`supportsNpu: false` 的模型会被过滤掉（这是预期行为）
- [ ] 打开一页增强：能出图、**颜色不偏（红蓝不互换）**、输出尺寸 = 输入 × `scales`
- [ ] 放大看 tile 接缝：不应有网格状接缝（有 → halo 太小）
- [ ] 换倍率/精度/降噪档（描述符里声明过的）都能正常切换
- [ ] `logcat -b crash` 无新增崩溃；
      诊断日志 `files/enhance_debug.log`（`/sdcard/Android/data/<宿主包名>/files/`）里能看到
      该包被扫描、模型目录解析成功、引擎初始化成功（见[附录 A](#附录-a关键日志行)）
- [ ] 卸载模型包后列表里消失，重新安装又能回来

---

## 10. 常见问题 / 排错

**Q：装了包，但 `模型包` 页面看不到 / 阅读器没有 chip。**
依次查：① `uses-feature` 是否写了（少了它宿主根本不认）；② `versionCode` 是否升过（旧解压目录被复用）；
③ `assets/modelpack.json` 是否存在且 JSON 合法、`models` 非空、`key/engine/assetPath` 都不为空；
④ `schemaVersion` 是否 > 1；⑤ 是不是后端选了 NPU 而 `supportsNpu: false`。

**Q：chip 出现了，但一开启就回退/无效果。**
看日志：`Engine <id>: model directory '<assetPath>' of <key> is missing` → `assetPath` 写错或目录里没有 `.param/.bin`；
若是 ncnn 载入失败（`load_param`/`load_model` 返回非 0），多半是 `.param` 与 `.bin` **不配套**，或 `stem` 与引擎表不一致。

**Q：出图红蓝互换。**
漏了 [§4](#4-通道顺序宿主是-bgr最容易踩的坑) 的 BGR 适配。

**Q：图上有方格接缝 / 边界一圈异常。**
halo（`padding`）太小，或分块尺寸与该模型的感受野不匹配；参考同类包（SPAN 24、sudo/acnet 10）。

**Q：描述符改了但设备上没变化。**
`versionCode` 没升 —— 宿主按 `packageName:versionCode` 复用解压结果。

**Q：想加一个全新架构（宿主 engine 表里没有）。**
通用通道只认 `<stem>.param/.bin` + 引擎表里的 halo，所以要么复用现有 engine（同 stem 换权重），
要么给宿主提 PR/issue 加一行 `NcnnModelSpec`。自带 `.so` 的包则可以完全自带实现（[§5](#5-进阶自带原生推理库-libmodelpackso)）。

**Q：包体积是不是越小越好？**
不影响功能，但注意别把 `kotlin-stdlib` 打进去（[§7](#7-工程模板与构建)），也别把调试用的多份权重都塞进去。

---

## 附录 A：关键日志行

宿主把诊断信息同时写到 logcat 与 `/sdcard/Android/data/<宿主包名>/files/enhance_debug.log`：

```
scan: packs=[acnet, omni-small, …, span-nomosuni-4x]                  # 本次识别到的模型包
scan: pack=omni-small nativeLibraryDir=… apk=… dir=…                 # 每个包的路径信息
scan: pack=omni-small probeLib=… exists=false dlopen=0               # 是否带原生库、能否加载
EnhancementEngine: engineFor model=omni-small engine=hfa2k-span native=false builtIn=true
Waifu2x: Initialized generic ncnn model: 2x-HFA2kSPAN, scale=2       # 通用 ncnn 通道初始化成功
PackNativeEngine: Model pack <id>: loaded native engine …            # 原生库通路（如有）
```

拿到日志：

```bash
adb shell "tail -50 /sdcard/Android/data/<宿主包名>/files/enhance_debug.log"
```

---

## 参考

- 插件目录与索引：[TachiyomiX-ModelPack-Catalog](https://github.com/zhzipu/TachiyomiX-ModelPack-Catalog)（`index.json` / `index.min.json`）
- 宿主：[zhzipu/TachiyomiX](https://github.com/zhzipu/TachiyomiX)
- 真实插件仓库（可直接 fork 改）：[omni-small](https://github.com/zhzipu/TachiyomiX-ModelPack-omni-small)、
  [span-nomosuni-4x](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni-4x)、
  [span-nomosuni](https://github.com/zhzipu/TachiyomiX-ModelPack-span-nomosuni)
