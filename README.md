# 艾露莎注入器 (Elusha Injector) v1.0

> 为 EnigmaVB 打包的《世間知らずの猫エルーシャ》提供运行时插件加载。**不需要解包，不需要修改 Game.exe。**

---

## 玩家使用

### 安装

1. 将 `ElushaInjector.exe` 放到游戏目录（和 `Game.exe` 同级）
2. 双击 `ElushaInjector.exe` 启动注入器
3. **直接双击 `Game.exe` 即可加载插件**

首次启动会自动创建必要目录并注册 `.elsmod` 文件关联。

### 管理插件

| 操作 | 方法 |
|------|------|
| 安装插件 | 点击「导入」选择 `.elsmod` 文件，或直接拖放 `.elsmod` 到窗口 |
| 启用/禁用 | 点击插件右侧开关 |
| 调整顺序 | 上下拖拽插件条目 |
| 查看详情 | 双击插件条目 |
| 卸载插件 | 详情页点击「卸载插件」 |
| 启动游戏 | 点击「启动游戏」或直接双击 `Game.exe` |

### 卸载注入器

双击 `UninstallElusha.exe`（注入器首次运行时自动生成）。可选择保留插件文件。

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
  "gameVersion": "1.051",
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

提供打包、解包、模板生成、终端、工具链接。

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
           │ 同步 enabled_plugins.txt
┌──────────▼───────────────────┐
│  version.dll (C)             │  ← 注入核心
│  Hook ReadFile → main.js     │
│  动态注入 $plugins.push()    │
└──────────────────────────────┘
```

### 注入原理

```
Game.exe 启动
  → Enigma 加载 version.dll
  → DllMain: Hook kernel32!ReadFile
  → NW.js 读取 main.js (270B)
  → Hook 拦截 → 读取 elsmod_data/enabled_plugins.txt
  → 为每个启用的插件生成 $plugins.push({"name":"XXX",...})
  → 插入到 PluginManager.setup($plugins) 之前
  → NW.js 拿到修改后的 main.js → V8 正常执行

Enigma VFS fallback:
  PluginManager.loadScript("js/plugins/XXX.js")
  → Enigma 查 VFS → 不存在
  → 自动 fallback 到磁盘 www/js/plugins/XXX.js
  → 找到！加载执行
```

### 关键设计决策

- **version.dll 不代理 version API**：导出返回 0。不需要版本信息，避免残留进程
- **一个 DLL + 一个文本文件**：不需要共享内存，不需要 IPC，不需要 injector.exe
- **Enigma VFS fallback**：利用了 Enigma 在 VFS 中找不到文件时自动查磁盘的行为
- **双击 Game.exe 就能用**：不需要 launcher，不需要 bat

### 技术栈

| 层 | 技术 |
|----|------|
| GUI | PySide6 (Qt), 19 个主题, 3 语言 |
| 引擎 | Python 3.10, argparse CLI |
| 注入 | C (MinGW GCC 32-bit), Win32 API Hook |
| 打包 | PyInstaller (onefile, windowed) |

### 目录结构

```
游戏目录/
├── Game.exe                     ← 游戏本体
├── ElushaInjector.exe           ← 注入器
├── UninstallElusha.exe          ← 卸载器
├── version.dll                  ← 注入 DLL
├── elsmod_data/                 ← 插件存储 + 注册表
│   ├── registry.json            ← 导入记录
│   └── *.elsmod                 ← 插件源文件
└── www/js/plugins/              ← 已安装插件
```

### 编译 version.dll

```bash
gcc -shared -s -Os -static -Wl,--kill-at \
  -o version.dll version_proxy_v46.c -lkernel32
```

必须通过 MSYS2 MinGW 32-bit shell 编译。
