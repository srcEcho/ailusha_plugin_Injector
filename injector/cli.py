"""CLI entry point — argparse dispatcher"""
import argparse
import json
import sys
from .core import cli_engine


def _print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _handle(args) -> dict:
    """Dispatch CLI command. Returns result dict."""
    if args.command == "list":
        return cli_engine.cmd_list(
            enabled_only=args.enabled, disabled_only=args.disabled)

    elif args.command == "info":
        return cli_engine.cmd_info(args.name)

    elif args.command == "enable":
        return cli_engine.cmd_enable(args.name)

    elif args.command == "disable":
        return cli_engine.cmd_disable(args.name)

    elif args.command == "install":
        return cli_engine.cmd_install(args.file)

    elif args.command == "uninstall":
        return cli_engine.cmd_uninstall(args.name)

    elif args.command == "repair":
        return cli_engine.cmd_repair(args.name)

    elif args.command == "imported":
        result = cli_engine.cmd_imported()
        return {"imported": result}

    elif args.command == "pack":
        return cli_engine.cmd_pack(args.file, args.output)

    elif args.command == "unpack":
        return cli_engine.cmd_unpack(args.file, args.output)

    elif args.command == "template":
        return cli_engine.cmd_template(args.name, args.author, args.dir)

    elif args.command == "deploy":
        return cli_engine.cmd_setup()

    elif args.command == "launch":
        return cli_engine.cmd_launch(skip_plugins=args.skip_plugins)

    elif args.command == "config":
        return cli_engine.cmd_config()

    elif args.command == "tools":
        if args.tool_action == "list":
            result = cli_engine.cmd_tools_list()
            return {"tools": result}
        elif args.tool_action == "open":
            import webbrowser
            for t in cli_engine.cmd_tools_list():
                if t["name"] == args.tool_name:
                    webbrowser.open(t["url"])
                    return {"opened": t["url"]}
            raise ValueError(f"工具 '{args.tool_name}' 未找到")

    elif args.command == "register":
        from .core import elsmod_register
        elsmod_register.register()
        return {"registered": True}

    elif args.command == "unregister":
        from .core import elsmod_register
        elsmod_register.unregister()
        return {"unregistered": True}

    elif args.command == "move-up":
        return cli_engine.cmd_move_up(args.name)

    elif args.command == "move-down":
        return cli_engine.cmd_move_down(args.name)

    elif args.command == "reorder":
        return cli_engine.cmd_reorder(args.names)

    elif args.command == "version":
        return {"name": "艾露莎注入器", "version": "1.0"}

    else:
        raise ValueError(f"未知命令：{args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ElushaInjector",
        description="艾露莎注入器 v1.0 — CLI")
    sub = parser.add_subparsers(dest="command")

    # list
    p = sub.add_parser("list", help="列出所有插件")
    p.add_argument("--enabled", action="store_true")
    p.add_argument("--disabled", action="store_true")

    # info
    p = sub.add_parser("info", help="查看插件详情")
    p.add_argument("name")

    # enable / disable
    sub.add_parser("enable", help="启用插件").add_argument("name")
    sub.add_parser("disable", help="禁用插件").add_argument("name")

    # install
    p = sub.add_parser("install", help="安装插件")
    p.add_argument("file")
    p.add_argument("--force", action="store_true")

    # uninstall
    sub.add_parser("uninstall", help="卸载插件").add_argument("name")

    # repair
    sub.add_parser("repair", help="修复破损插件").add_argument("name")

    # imported
    sub.add_parser("imported", help="列出已导入的 elsmod")

    # pack
    p = sub.add_parser("pack", help="从 JS 文件打包为 elsmod（自动发现 data 目录）")
    p.add_argument("file")
    p.add_argument("-o", "--output", default=None)

    # unpack
    p = sub.add_parser("unpack", help="解包 elsmod")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)

    # template
    p = sub.add_parser("template", help="生成项目模板")
    p.add_argument("--name", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--dir", required=True)

    # deploy
    p = sub.add_parser("deploy", help="部署环境")
    p.add_argument("--force", action="store_true")

    # move-up / move-down
    sub.add_parser("move-up", help="上移插件").add_argument("name")
    sub.add_parser("move-down", help="下移插件").add_argument("name")
    p = sub.add_parser("reorder", help="设置加载顺序")
    p.add_argument("names", nargs="+")

    # launch
    p = sub.add_parser("launch", help="启动游戏")
    p.add_argument("--skip-plugins", action="store_true")

    # config
    sub.add_parser("config", help="显示配置").add_argument("--show", action="store_true")

    # tools
    p = sub.add_parser("tools", help="开发者工具")
    p.add_argument("action", choices=["list", "open"], metavar="ACTION")
    p.add_argument("name", nargs="?", help="工具名（open 时需要）")

    # system
    sub.add_parser("register", help="注册 .elsmod 关联")
    sub.add_parser("unregister", help="取消 .elsmod 关联")
    sub.add_parser("version", help="显示版本")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    output_json = getattr(args, 'output_json', False)
    try:
        result = _handle(args)
        if output_json:
            _print_json(result)
        elif isinstance(result, dict):
            # Pretty print for human consumption
            for k, v in result.items():
                if isinstance(v, list):
                    print(f"{k}:")
                    for item in v:
                        if isinstance(item, dict):
                            print(f"  - {item.get('name', item)}")
                        else:
                            print(f"  - {item}")
                else:
                    print(f"{k}: {v}")
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    ver = item.get("version", "")
                    enabled = "✓" if item.get("enabled") else "✗"
                    desc = item.get("description", "")
                    print(f"  [{enabled}] {name} v{ver} — {desc}")
                else:
                    print(f"  - {item}")
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
