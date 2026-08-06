# EnigmaVB 打包下 NW.js 插件加载 — 完整技术分析

> 姊妹文档：分层架构分析.md / 路线总结.md / QuestLog注入流程总结.md / 深度战略分析.md / 最终解决方案.md
> 本文档专注于 EnigmaVB 相关发现和 V8 实验数据
> 最后更新：2026-08-05（v36 方案确认后）

---

## 一、EnigmaVB 版本与加密

- **版本**：Enigma Virtual Box 免费版
- **加密**：无。所有嵌入文件以**明文**存储在 EXE overlay 区域
- **确认来源**：Enigma 官方论坛确认 + 网上独立验证 + evbunpack 源码分析
- **解包工具**：`evbunpack`（GitHub: mos9527/evbunpack），支持 v7.80-11.00

### overlay 结构（evbunpack 源码分析）

```
Game.exe (1.4GB)
├─ PE 头 (~1.5MB 原始 nw.exe)
├─ .enigma1 节 → VFS 表 + 文件数据（明文，按文件表顺序连续存放）
│   ├─ EVB\x00 magic
│   ├─ MAIN node → objects_count（顶层对象数）
│   ├─ 文件表（前）
│   │   ├─ FOLDER: utf-16-le 名 + objects_count
│   │   └─ FILE:   utf-16-le 名 + original_size + stored_size + 文件时间...
│   └─ 文件数据（后）：从第一个文件节点计算出的 abs_offset 起连续存放
│       ├─ original_size == stored_size → 明文直接存（零压缩！）
│       └─ original_size != stored_size → aplib 分块压缩（本游戏未出现）
└─ .enigma2 → aplib 压缩的 Enigma loader DLL（运行时被解压后 Hook 文件 API）
```

### 关键数据
- **4176 个文件，全部明文（orig==stored），0 压缩**
- 94 个 .js 文件全部明文
- plugins.js：原版 overlay @ 0x5929FF9D, 95142 字节
- 原版 overlay 无 QuestLog.js（确认注入必要性）

## 二、EnigmaVB VFS 机制

### 启动流程
```
Game.exe 启动
  → Enigma Loader 最先执行（早于 NW.js 初始化）
  → Hook Windows 文件 API (CreateFileW/ReadFile/NtCreateFile/LoadLibrary...)
  → NW.js 初始化
  → NW.js 请求文件 → Enigma Hook 拦截 → 识别虚拟路径 → 从 overlay 返回明文数据
```

### VFS 行为特征
- Enigma Hook 在进程**最早阶段**安装，优先级高于我们的 DLL Hook
- 免费版不加密：文件从 overlay 直接返回，不经过解密步骤
- **管理范围**：仅管理 `www/` 目录下的虚拟文件
- **不存在文件的处理**：返回 `INVALID_HANDLE_VALUE`
- **非 www/ 路径**：透传到真实文件系统（**v36 方案的关键利用点**）

## 三、文件系统层拦截（完整测试结果）

### 渲染进程

| # | 尝试 | 结果 | 根因 |
|---|------|------|------|
| 1 | kernel32 ReadFile 替换 | ❌ | Chromium 不走 kernel32 读 JS |
| 2 | kernel32 CreateFileW 重定向 | ⚠️ | 自重定向OK，跨路径→Enigma状态不一致挂起 |
| 3 | kernel32 MapViewOfFile | ❌ | 纯直通崩溃(Hook链冲突) |
| 4 | ntdll NtReadFile 即时Hook | ❌ | 拦截到容器头`P...`(Enigma读自身overlay) |
| 5 | ntdll NtReadFile 延迟5秒Hook | ❌ | 同上 |
| 29 | NtReadFile v4（最小化、即时刷盘） | ⚠️ | 只捕获PE/DLL加载，无JS流量 |
| 30 | kernel32 ReadFile（渲染进程） | ⚠️ | 同上，确认JS不在渲染进程加载 |

### 浏览器进程（**突破**）

| # | 尝试 | 结果 | 根因 |
|---|------|------|------|
| 31 | **kernel32 ReadFile（浏览器进程）** | **✅ 突破** | **第734次调用截获 plugins.js 明文！** |
| 32 | 文本扫描器（浏览器进程） | ✅ | 确认文件加载顺序，main.js在readCnt=595 |
| 33 | **main.js 主动注入** | **✅ 突破** | $plugins.push注入成功 |
| 34 | CreateFileW+ReadFile双重服务 | ⚠️ | Enigma返回无效句柄，ReadFile不被调用 |
| 36 | **CreateFileW磁盘重定向** | **✅ 可行** | 重定向到非www/路径，Enigma透传 |

## 四、VFS 内存扫描发现

### 4.1 路径表
- 找到虚拟文件路径 @ 0x04770000 (MEM_PRIVATE, ~1MB)
- 格式：`"chrome-extension://{hash}/www/index.html"`
- **实际是 Chromium 扩展资源映射表，非 Enigma VFS 表**
- 包含 `"nwjs/default.js"` 等 NW.js 内部文件路径

### 4.2 渲染进程模块（27个）
```
nw_elf.dll (84.8MB, 10,480 exports) ← V8+Chromium+Node静态链接
ffmpeg.dll (3.1MB)
+ 25个 Windows 系统 DLL
无: node.dll, libuv.so, content.dll, blink_core.dll
```

### 4.3 浏览器进程模块（70+个）
```
nw.dll @ 0x10000000 (84.8MB) ← 与渲染进程 nw_elf.dll 同一二进制
nw_elf.dll @ 0x08280000 (472KB) ← 小型 loader
ffmpeg.dll @ 0x086C0000 (3.1MB)
+ 70+ Windows 系统 DLL
浏览器进程无活跃 V8 Isolate (测试2次,均返回NULL)
```

### 4.4 内存签名扫描（GLM）
- scan_plugins.c: 967区域, 393MB, found=0
- **结论：JS 正文非常驻内存**。Enigma VFS 惰性读取后丢弃。
- 内存改写路线（Z2）被正式否决。

## 五、V8 API 地址表

```
nw_elf.dll base: 0x10000000 (多次重启验证不变)

核心 API:
v8::Isolate::GetCurrent()               → 0xA17E00
v8::Isolate::GetCurrentContext()        → 0xA17E30
v8::String::NewFromUtf8() MaybeLocal    → 0xA178C0
v8::String::NewFromUtf8() Local         → 0xA3CE60
v8::String::NewFromOneByte()            → 0xA3CFE0
v8::Script::Compile(Local,Local)        → 0xA28130
v8::Script::Compile(Context,Local,Origin)→ 0xA27FE0
v8::Script::Run()                       → 0xA250B0
v8::Script::Run(Context)                → 0xA24C10
v8::Integer::New(Isolate*,int)          → 0xA46E20
v8::HandleScope::HandleScope()          → 0xA1E9B0
v8::HandleScope::~HandleScope()         → 0xA1EC60
v8::Context::Global()                   → 0xA3BED0
v8::Context::Enter()                    → 0xA1F8C0
v8::Context::Exit()                     → 0xA1F9B0
v8::Isolate::Enter()                    → 0xA17760
v8::Object::Set(Context,uint32,Value)   → 0xA31630
v8::Context::New(Isolate,Ext,Tpl,Glob)  → 0xA1E9D0

生命周期回调:
v8::Isolate::RequestInterrupt()         → 0xA47370
v8::Isolate::AddBeforeCallEnteredCallback()  → 0xA47AF0
v8::Isolate::AddCallCompletedCallback()      → 0xA47B10
v8::Isolate::AddMicrotasksCompletedCallback()→ 0xA47F40

V8 Inspector:
V8Inspector vtable                      → 0x142ADC00
  [0] ~V8Inspector                      → 0x110829A0
  [1] connect()                         → 0x11081010
V8InspectorClient vtable                → 0x142A58C0 (27项)
```

## 六、V8 重入墙实验矩阵（核心数据）

| V8 API | QPC Handler | BeforeCallEntered | MicrotasksCompleted |
|--------|------------|-------------------|-------------------|
| GetCurrent() | ✅ 0x048xxxxx | ✅ 参数传入 | ✅ 参数传入 |
| HandleScope | ✅ | ✅ | ✅ |
| GetContext() | ✅ 0x08xxxxxx | ⚠️ 有时有效 | ❌ 0x0078(无效) |
| Context::Enter | ❌ 崩溃 | ❌ 崩溃 | ❌ 崩溃 |
| Context::Global | — | ❌ 崩溃 | ❌ 崩溃 |
| NewFromUtf8() | ❌ 崩溃 | ⚠️ 返回Iso(不崩) | ⚠️ 返回Iso(不崩) |
| Integer::New(0) | ❌ 崩溃 | ❌ 崩溃 | ❌ 崩溃 |
| connect() | ❌ 崩溃 | ❌ 崩溃 | — |

**MCB (MicrotasksCompleted)**：唯一**稳定触发**(27次/30s)且 API 调用不崩溃的回调，但 Context 不可用(返回无效低地址)

## 七、已否决的路线

| 路线 | 证据 |
|------|------|
| V8 API 直接调用（6条） | V8 重入墙：所有分配型 API 崩溃 |
| Inspector CDP（4条） | connect() 重入崩溃 |
| 渲染进程文件 Hook（5条） | JS 在浏览器进程加载，不在渲染进程 |
| 内存改写（Z2） | scan_plugins.log: 393MB 全扫 found=0 |
| 静态重打包 | 用户明确拒绝，要求运行时注入 |

## 八、最终可行方案

### 核心机制
1. **浏览器进程 ReadFile Hook** → 拦截 main.js → 注入 `$plugins.push(QuestLog)`
2. **浏览器进程 CreateFileW Hook** → 检测 QuestLog 文件请求 → 重定向到磁盘
3. QuestLog 文件放在游戏根目录（Enigma 不管理此路径，透传到磁盘）

### 为什么之前的路线失败
- 所有 hook 都在渲染进程 → JS 文件不在渲染进程加载
- V8 层注入 → 重入墙无法突破
- NtReadFile → 只能看到 Enigma 读自身容器的 PE 数据

### 为什么 v36 成功
- **找到正确的进程**：浏览器进程（JS 加载发生的地方）
- **找到正确的 API**：kernel32 ReadFile/CreateFileW（文件 I/O 必经之路）
- **找到正确的文件**：main.js（270B、位置关键、buffer 有充足空间）
- **利用 Enigma 盲区**：非 www/ 路径透传到磁盘
