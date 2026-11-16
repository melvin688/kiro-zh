# -*- coding: utf-8 -*-
"""重算 product.json 里的文件校验值。

改过 resources/app/out 下的文件后，Kiro 启动会做完整性校验，
校验不通过就弹「Kiro 安装似乎损坏，请重新安装」。这里按
base64(sha256(文件字节)) 去掉 padding 的格式回填 checksums，
键是相对 out/ 的路径。

用法：python scripts/fix_checksums.py --app <resources/app>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
from pathlib import Path

from kiro_paths import enable_utf8, find_app_root
from io_util import dump_json, load_json


def digest(path: Path) -> str:
    return base64.b64encode(hashlib.sha256(path.read_bytes()).digest()).decode().rstrip("=")


def run(app: Path) -> list[tuple[str, str, str]]:
    product_path = app / "product.json"
    product = load_json(product_path)
    checksums = product.get("checksums") or {}
    if not checksums:
        print("product.json 没有 checksums 字段，无需处理")
        return []

    changes: list[tuple[str, str, str]] = []
    for key, expected in list(checksums.items()):
        target = app / "out" / Path(*key.split("/"))
        if not target.exists():
            print(f"缺文件，跳过：{key}")
            continue
        actual = digest(target)
        if actual != expected:
            checksums[key] = actual
            changes.append((key, str(expected)[:12], actual[:12]))

    if changes:
        shutil.copy2(product_path, product_path.with_suffix(".json.zhbak"))
        dump_json(product_path, product, indent=2)
        for key, old, new in changes:
            print(f"更新校验值 {key}  {old}… -> {new}…")
    else:
        print("全部校验值一致，无需更新")
    return changes


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="重算 Kiro product.json 的文件校验值")
    ap.add_argument("--app")
    args = ap.parse_args()
    run(find_app_root(args.app))


if __name__ == "__main__":
    main()
