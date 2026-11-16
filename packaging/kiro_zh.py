#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kiro-zh 单文件入口：apply / verify / restore。

源码运行时走仓库里的 scripts/；打包成 exe 后由 PyInstaller 把 scripts/ 一起收进去。
不带参数双击时进入引导模式，按回车才开始改文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

DEV = Path(__file__).resolve().parent / "scripts"
ALT = Path(__file__).resolve().parent.parent / "scripts"
for cand in (DEV, ALT):
    if cand.is_dir() and str(cand) not in sys.path:
        sys.path.insert(0, str(cand))

try:  # 先把控制台切到 UTF-8，否则英文版 Windows（cp1252）下打印中文直接崩
    import io_util  # noqa: F401
except Exception:  # pragma: no cover - 打包环境缺失时不影响主流程
    pass

USAGE = """kiro-zh — Kiro 界面汉化

用法:
  kiro-zh apply     汉化 + 重启（可选 --dry-run / --no-restart / --skip-nls）
  kiro-zh verify    验收：检查关键中文文案是否就位
  kiro-zh restore   回滚：--list 看备份，--restore 执行还原
  kiro-zh --help    显示本帮助
"""


def _ask_enter() -> None:
    try:
        input("\n按回车开始汉化，Ctrl+C 取消… ")
    except (KeyboardInterrupt, EOFError):
        print("\n已取消")
        raise SystemExit(1)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        _ask_enter()
        args = ["apply"]
    if args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if args[0] in ("-V", "--version"):
        from kiro_paths import __version__ as ver

        print(f"kiro-zh {ver}")
        return 0

    cmd, rest = args[0], args[1:]
    sys.argv = [f"kiro-zh {cmd}"] + rest

    if cmd == "apply":
        import apply

        apply.main()
    elif cmd == "verify":
        import verify

        verify.main()
    elif cmd == "restore":
        import restore

        restore.main()
    else:
        print(f"未知命令：{cmd}\n\n{USAGE}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
