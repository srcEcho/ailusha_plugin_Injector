# 艾露莎注入器 (Elusha Injector) v1.0

> 为 EnigmaVB 打包的《世間知らずの猫エルーシャ》提供运行时插件加载。**不需要解包，不需要修改 Game.exe。**
>
> ✅ `.elsmod` 文件关联 | ✅ 3 层卸载清理 | ✅ 3 语言 (zh/en/ja) | ✅ 19 主题 | ✅ CLI 工具链

---

## 玩家使用

### 安装

1. 下载 `ElushaInstaller.exe`（约 50-100MB，唯一需要的文件）
2. 双击运行 → 多页面向导：选择语言 → 选择游戏程序（`Game.exe` / `nw.exe` / 其他）→ 确认安装信息
3. 点击「安装」→ 进度条显示复制进度 → 注入器释放到游戏目录
4. 安装完成后可选择删除安装器

### 管理插件

| 操作 | 方法 |
|------|------|
| 安装插件 | 点击「导入」选择 `.elsmod` 文件，或直接拖放 `.elsmod` 到窗口 |
| 启用/禁用 | 点击插件右侧开关 |
| 调整顺序 | 上下拖拽插件条目 |
| 查看详情 | 双击插件条目 |
| 卸载插件 | 详情页点击「卸载插件」 |
| 启动游戏 | 在「启动游戏」旁的下拉框选择要启动的 exe，点击启动 |

游戏程序名称可能因解包方式不同而异（`Game.exe`、`nw.exe` 等）。注入器启动按钮旁的**下拉框**会自动检测当前目录下所有 exe，选择一个即可。

### 破损插件修复

如果插件文件意外丢失，注入器会自动检测并标记为破损（红色描边）。点击「修复」按钮即可从源文件恢复。如果 `.elsmod` 源文件也丢失了但有残留文件，修复会重新扫描并更新注册表。

### 卸载注入器

双击游戏目录下的 `UninstallElusha.exe`。可选择：
- 保留已下载的插件（保留 `elsmod_data/`）
- 保留已加载的插件（保留 `www/js/plugins/`）

卸载器会删除所有注入器文件（EXE、DLL、pyd、运行库目录）、`winhttp.dll`（旧版残留的 `version.dll` 一并删除）、`ElushaInstaller.exe` 及 bootstrap 文件。采用三层清理（Manifest → 模式匹配 → 批处理），自身进程锁定的文件通过延迟批处理在退出后循环删除。

---

## 插件开发者

### .elsmod 格式

`.elsmod` 是一个 zip 压缩包，内部结构：

```
PluginName.elsmod
└── www/
    └── js/
        └── plugins/
            ├── <PluginName>.js          ← 插件本体
            └── data/
                └── <PluginName>_<Author>/   ← 插件数据
                    └── plugin.json      ← 元数据（必须）
```

### plugin.json

```json
{
  "name": "MyPlugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "插件简介",
  "gameVersion": "1.06",
  "dependencies": [],
  "conflicts": []
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 插件唯一标识 |
| `version` | ✅ | 语义化版本 (如 `1.0.0`) |
| `author` | ✅ | 插件作者 |
| `description` | ✅ | 简介 |
| `gameVersion` | ✅ | 支持的游戏版本 |
| `dependencies` | 否 | 依赖的其他插件 |
| `conflicts` | 否 | 冲突的插件 |

### 依赖声明

```json
{
  "dependencies": [
    { "name": "MiniMap", "author": "elusha_mod", "version": ">=0.6.0" }
  ]
}
```

- `name`：必须
- `author`：可选（不填 = 匹配任何作者）
- `version`：可选（`>=` / `=` / `<=`）

### 文件冲突规则

卸载插件时，只删除 `plugin.json` 中 `files` 列表内的文件。`data/<Name>_<Author>/` 下用户运行时产生的数据不会被删除。重装/升级时，新版本文件与旧版 `files` 列表外的文件冲突会报错——这是插件作者的职责。

### CLI 工具

```bash
# 生成项目模板
ElushaInjector.exe --cli template --name MyPlugin --author Me --dir ./output

# 打包
ElushaInjector.exe --cli pack ./output -o MyPlugin.elsmod

# 解包
ElushaInjector.exe --cli unpack MyPlugin.elsmod -o ./extracted

# 完整 CLI 列表见「设置 → 开发者模式」或 --cli help
```

### 开发者面板

```bash
ElushaInjector.exe --dev
```

提供打包、解包、模板生成、终端、工具链接、孤立启动。

---

## 架构

### 三层结构

```
┌──────────────────────────────┐
│  GUI (PySide6)               │  ← 用户交互
│  主窗口 · 详情 · 设置 · 开发者 │
└──────────┬───────────────────┘
           │ 调用
┌──────────▼───────────────────┐
│  CLI 引擎 (Python)           │  ← 全部业务逻辑
│  安装 · 卸载 · 启用 · 依赖    │
│  打包 · 解包 · 模板 · 部署    │
└──────────┬───────────────────┘
           │ 同步 enabled_plugins.txt + registry.json
┌──────────▼───────────────────┐
│  winhttp.dll (C)             │  ← 注入核心
│  MinHook: CreateFileW 重定向  │
│  Bootstrap: fs+eval 加载插件  │
└──────────────────────────────┘
```

### 注入原理

```
Game.exe 启动
  → Enigma 加载 winhttp.dll
  → DllMain: 转发全部 WinHTTP 导出 + MinHook Hook CreateFileW + ReadFile
  → 读取 elsmod_data/injector_config.json
  → CreateFileW 重定向：目标 JS → Bootstrap
  → Bootstrap 执行:
    ① fs.readFileSync(原版文件) → eval (原版照跑)
    ② fs.readFileSync(www/js/plugins/PluginA.js) → eval (MOD 加载)
```

### 关键设计决策

- **winhttp.dll 侧载而非 version.dll**：MTOOL 的 Lazy Inject 会删除/覆盖 `version.dll` 与 `winmm.dll`（自用侧载），`winhttp.dll` 是游戏静态导入的第 3 个非 KnownDLL、MTOOL 不碰
- **转发全部 27 个 WinHTTP 导出**：`nw.dll` 延迟加载 `WinHttpGetProxyForUrl` 等函数，漏转发会 exit 127 无法启动
- **Bootstrap = CreateFileW 重定向 + fs+eval**：小型加载器（<250B）替换目标 JS，原版放 `originals/` 备份
- **MinHook 永久 trampoline**：消除 P5/U5 与 Enigma Hook 的竞态，100% 可靠
- **Bootstrap 路径用 `p.dirname(process.execPath)`**：不依赖 `process.cwd()`，第三方启动器任意 CWD 拉起都能正确解析
- **三层卸载清理**：Manifest 精确删除 + 模式匹配兜底 + 批处理清理进程锁定文件
- **Nuitka standalone** 编译游戏目录组件（避开 EnigmaVB 对 PyInstaller bootloader 的检测）
- **PyInstaller onefile** 打包安装器（成熟稳定，不接触游戏进程）

### 技术栈

| 层 | 技术 |
|----|------|
| GUI | PySide6 (Qt), 19 个主题, 3 语言 |
| 引擎 | Python 3.10, argparse CLI |
| 注入 | C (MinGW GCC 32-bit), MinHook 1.3.3 |
| 打包 | Nuitka standalone（游戏目录组件）, PyInstaller onefile（安装器） |

### 目录结构

```
游戏目录/
├── Game.exe                     ← 游戏本体（名称可能不同）
├── ElushaInstaller.exe          ← 安装器（可选保留）
├── ElushaInjector.exe           ← 注入器 GUI（Nuitka standalone）
├── UninstallElusha.exe          ← 卸载器（Nuitka standalone, tkinter）
├── python310.dll                ← Nuitka 运行时（flat 布局）
├── *.pyd / *.dll                ← Nuitka 运行时模块
├── PySide6/ shiboken6/          ← Qt 库目录
├── tcl/ tk/ tcl8/               ← Tcl/Tk 运行时（卸载器依赖）
├── injector/                    ← 嵌入资源（图标等）
├── winhttp.dll                  ← 注入 DLL（MinHook）
├── elsmod_data/                 ← 插件存储 + 注册表 + 配置 + 日志
│   ├── registry.json            ← 注册表
│   ├── injector_config.json     ← 注入策略配置
│   ├── install_manifest.json    ← 安装清单
│   ├── ui_config.json           ← GUI 配置（语言、主题、选中 exe）
│   ├── logs/                    ← 诊断日志
│   └── *.elsmod                 ← 插件源文件
└── www/js/plugins/              ← 已安装插件
```
> Nuitka 采用 flat 布局（所有 DLL/pyd 与 EXE 同级），区别于 PyInstaller 的 `_internal/` 集中模式。

### 编译 winhttp.dll

```bash
mkdir -p /c/tmp/mh_build/hde /c/tmp/include
cp src/minhook/*.h /c/tmp/mh_build/
cp src/minhook/MinHook.h /c/tmp/include/MinHook.h   # hook.c 引用 ../include/MinHook.h
cp src/minhook/*.c /c/tmp/mh_build/
cp src/minhook/hde32.c src/minhook/hde32.h src/minhook/pstdint.h src/minhook/table32.h /c/tmp/mh_build/hde/
cp src/mainline/version_proxy_v55_winhttp.c /c/tmp/mh_build/v55.c
/c/Programs/msys64/msys2_shell.cmd -mingw32 -defterm -no-start -c \
  'cd /c/tmp/mh_build && gcc -shared -s -Os -static -Wl,--kill-at -I. -Ihde -o winhttp.dll v55.c buffer.c hook.c trampoline.c hde/hde32.c -lkernel32'
cp /c/tmp/mh_build/winhttp.dll 游戏目录/winhttp.dll
```

必须通过 MSYS2 MinGW 32-bit shell 编译。

### 完整构建

```bash
python build.py
# Step 1: UninstallElusha.exe (Nuitka standalone + tk-inter)
# Step 2: ElushaInjector/ (Nuitka standalone + pyside6)
# Step 3: ElushaInstaller.exe (PyInstaller onefile, 内含 ElushaInjector/)
```

---

[github.com/srcEcho/ailusha_plugin_Injector](https://github.com/srcEcho/ailusha_plugin_Injector)
