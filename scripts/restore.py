# -*- coding: utf-8 -*-
"""从 .zhbak 备份回滚所有改动。

用法：
    python scripts/restore.py --app <resources/app> --list   # 列出可回滚文件
    python scripts/restore.py --app <resources/app>          # 全部回滚
"""
from __future__ import annotations

import argparse
from pathlib import Path

from kiro_paths import enable_utf8, find_app_root


def backups(app: Path) -> list[Path]:
    return sorted(p for p in app.rglob("*.zhbak") if p.is_file())


def run(app: Path, do_restore: bool) -> None:
    files = backups(app)
    if not files:
        print("没有 .zhbak 备份，无需回滚")
        return
    for bak in files:
        target = Path(str(bak)[: -len(".zhbak")])
        if do_restore:
            bak.replace(target)
            print(f"已还原 {target.relative_to(app)}")
        else:
            print(f"可回滚 {target.relative_to(app)}")
    if do_restore:
        print(f"\n共还原 {len(files)} 个文件。重启 Kiro 生效。")
    else:
        print(f"\n共 {len(files)} 个文件可回滚（加 --restore 实际执行）")


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="回滚 Kiro 汉化")
    ap.add_argument("--app")
    ap.add_argument("--list", action="store_true", help="只列出，不还原")
    ap.add_argument("--restore", action="store_true", help="执行还原（默认只列清单）")
    args = ap.parse_args()
    run(find_app_root(args.app), args.restore and not args.list)


if __name__ == "__main__":
    main()
