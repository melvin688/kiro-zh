# -*- coding: utf-8 -*-
"""一键执行：界面汉化 -> NLS 烘焙 -> 校验值回填 -> 清缓存 -> 重启 Kiro。

用法：
    python scripts/apply.py                # 全量，最后自动重启
    python scripts/apply.py --no-restart    # 只改文件
    python scripts/apply.py --dry-run       # 只看会动哪些文件
    python scripts/apply.py --skip-nls      # 只做字面量汉化
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import asar_tool
import fix_checksums
import localize_nls
import patch_ui
from kiro_paths import assets_dir, data_dir, enable_utf8, find_app_root
from io_util import load_json

WELCOME_ENTRY = "@kiro/sign-in-page/dist/index.js"


def patch_welcome(app: Path) -> int:
    """欢迎页 / 登录页在 node_modules.asar 里，用等长替换处理。"""
    asar = app / "node_modules.asar"
    mapping_path = assets_dir() / "asar-welcome-zh.json"
    if not asar.exists() or not mapping_path.exists():
        print("  跳过：找不到 node_modules.asar 或文案表")
        return 0
    mapping = load_json(mapping_path)
    return asar_tool.apply_map(asar, WELCOME_ENTRY, mapping)


def exe_path(app: Path) -> Path | None:
    if sys.platform == "darwin":
        # .../Kiro.app/Contents/Resources/app  ->  .../Kiro.app/Contents/MacOS/Kiro
        macos = app.parent.parent / "MacOS"
        for name in ("Kiro", "kiro"):
            cand = macos / name
            if cand.exists():
                return cand
        hits = sorted(p for p in macos.glob("*") if p.is_file())
        return hits[0] if hits else None

    install = app.parent.parent
    names = ("kiro", "Kiro") if sys.platform.startswith("linux") else ("Kiro.exe", "kiro.exe")
    for name in names:
        cand = install / name
        if cand.exists():
            return cand
    hits = sorted(install.glob("*.exe")) if os.name == "nt" else sorted(install.glob("*iro*"))
    return hits[0] if hits else None


def _clear_cache() -> None:
    """clp 是 NLS 文案缓存；Cache / Code Cache 是 webview 的 JS 缓存。
    只清 clp 时，改过的聊天面板 bundle 可能仍从缓存读旧字节。
    """
    import shutil

    for name in ("clp", "Cache", "Code Cache", "GPUCache"):
        cache = data_dir() / name
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)


def _run_quiet(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def restart(app: Path) -> None:
    exe = exe_path(app)
    if not exe:
        print("没找到 Kiro 可执行文件，跳过重启，请手动启动")
        return

    if sys.platform == "darwin":
        _run_quiet(["osascript", "-e", 'quit app "Kiro"'])
        time.sleep(4)
        _run_quiet(["pkill", "-f", "Kiro.app/Contents/MacOS"])
        time.sleep(2)
        _clear_cache()
        _run_quiet(["open", "-a", "Kiro"])
        print(f"已重启：{exe}")
        return

    if sys.platform.startswith("linux"):
        _run_quiet(["pkill", "-x", exe.name])
        _run_quiet(["pkill", "-f", str(exe)])
        time.sleep(4)
        _clear_cache()
        subprocess.Popen(
            [str(exe)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"已重启：{exe}")
        return

    subprocess.run(["taskkill", "/IM", exe.name], capture_output=True, text=True)
    time.sleep(6)
    _clear_cache()
    os.startfile(str(exe))  # noqa: S606 - 需要以桌面应用方式启动
    print(f"已重启：{exe}")


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="Kiro 汉化一键脚本")
    ap.add_argument("--app", help="Kiro 的 resources/app 目录，留空自动探测")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-restart", action="store_true")
    ap.add_argument("--skip-nls", action="store_true", help="跳过 NLS 烘焙（只改界面字面量）")
    ap.add_argument("--skip-ui", action="store_true", help="跳过界面字面量（只做 NLS）")
    args = ap.parse_args()

    app = find_app_root(args.app)
    print(f"Kiro：{app}\n")

    if not args.skip_ui:
        print("== 1/5 界面汉化")
        rows = patch_ui.run(app, args.dry_run)
        if not args.dry_run:
            for status, name, done, miss in rows:
                print(f"  {status:<4} {name:<34} 替换 {done:>3}  未命中 {miss:>3}")

        print("\n== 2/5 欢迎页（node_modules.asar）")
        if args.dry_run:
            print("  dry-run：跳过 asar")
        else:
            patch_welcome(app)

    if not args.skip_nls:
        print("\n== 3/5 NLS 烘焙")
        localize_nls.run(app, args.dry_run)

    if not args.dry_run:
        print("\n== 4/5 校验值")
        fix_checksums.run(app)

    print("\n== 5/5 重启")
    if args.dry_run:
        print("dry-run：跳过重启")
        return
    if args.no_restart:
        print("已跳过重启。改完请手动重启 Kiro，否则界面不变。")
        return
    restart(app)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
