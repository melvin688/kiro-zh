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

import os  # noqa: E402

os.environ.setdefault("KIRO_ZH_PROG", "kiro-zh translate")

USAGE = """kiro-zh — Kiro 界面汉化

用法:
  kiro-zh apply      汉化 + 重启（可选 --dry-run / --no-restart / --skip-nls）
  kiro-zh verify     验收：检查关键中文文案是否就位
  kiro-zh restore    回滚：--list 看备份，--restore 执行还原
  kiro-zh translate  补译语言包缺失条目（交互式：自动翻译 -> 合并 -> 烘焙）
  kiro-zh --help     显示本帮助

translate 也可以走命令行:
  kiro-zh translate auto  --api-url https://api.deepseek.com/v1 --model deepseek-chat
  kiro-zh translate merge
  （key 放环境变量 KIRO_ZH_API_KEY，也认 DEEPSEEK_API_KEY / OPENAI_API_KEY）
"""


def _work_dir() -> Path:
    """exe 双击时 cwd 不可控，固定放到用户目录下。"""
    d = Path.home() / ".kiro-zh" / "work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_key(prompt: str) -> str:
    """控制台里用 getpass（不回显）；管道/重定向输入时退回普通读行，避免卡死。"""
    import getpass

    try:
        if sys.stdin is not None and sys.stdin.isatty():
            return getpass.getpass(prompt)
        print(prompt)
        return (sys.stdin.readline() if sys.stdin else "").strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def _translate_wizard() -> int:
    import os

    import translate_missing

    if not (os.environ.get("KIRO_ZH_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")):
        print("补译需要 OpenAI 兼容接口的 API key（默认 DeepSeek，key 只在本地用，不会上传别处）。")
        key = _read_key("粘贴 key（输入不回显，直接回车取消）：").strip()
        if not key:
            print("已取消")
            return 1
        os.environ["KIRO_ZH_API_KEY"] = key

    work = _work_dir()
    print(f"\n=== 1/2 翻译缺失条目（产物在 {work}）")
    sys.argv = ["kiro-zh translate", "auto", "--out", str(work)]
    translate_missing.main()

    sys.argv = ["kiro-zh translate", "merge", "--out", str(work)]
    print("\n=== 2/2 合并进语言包")
    try:
        translate_missing.main()
    except SystemExit:
        print("没有可合并的译文，跳过。")
        return 0

    try:
        ans = input("\n要现在烘焙并重启 Kiro 让新译文生效吗？[Y/n] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = "n"
    if ans in ("", "y", "yes"):
        sys.argv = ["kiro-zh apply"]
        import apply

        apply.main()
    else:
        print("已跳过。之后运行 kiro-zh apply 即可生效。")
    return 0


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
    elif cmd == "translate":
        if not rest:
            return _translate_wizard()
        import translate_missing

        translate_missing.main()
    else:
        print(f"未知命令：{cmd}\n\n{USAGE}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
