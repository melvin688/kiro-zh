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
import os
import subprocess
import sys
import time
from pathlib import Path

import fix_checksums
import localize_nls
import patch_ui
from kiro_paths import data_dir, enable_utf8, find_app_root


def exe_path(app: Path) -> Path | None:
    install = app.parent.parent
    for name in ("Kiro.exe", "kiro.exe"):
        cand = install / name
        if cand.exists():
            return cand
    hits = sorted(install.glob("*.exe"))
    return hits[0] if hits else None


def restart(app: Path) -> None:
    exe = exe_path(app)
    if not exe:
        print("没找到 Kiro.exe，跳过重启，请手动启动")
        return
    subprocess.run(["taskkill", "/IM", exe.name], capture_output=True, text=True)
    time.sleep(6)
    cache = data_dir() / "clp"
    if cache.exists():
        import shutil

        shutil.rmtree(cache, ignore_errors=True)
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
        print("== 1/4 界面汉化")
        rows = patch_ui.run(app, args.dry_run)
        if not args.dry_run:
            for status, name, done, miss in rows:
                print(f"  {status:<4} {name:<34} 替换 {done:>3}  未命中 {miss:>3}")

    if not args.skip_nls:
        print("\n== 2/4 NLS 烘焙")
        localize_nls.run(app, args.dry_run)

    if not args.dry_run:
        print("\n== 3/4 校验值")
        fix_checksums.run(app)

    print("\n== 4/4 重启")
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
