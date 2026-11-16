# -*- coding: utf-8 -*-
"""冒烟验收：关键中文串是否在位，改动过的 bundle 语法是否还合法。

用法：python scripts/verify.py [--app <resources/app>]
退出码 0 表示全部通过。
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from kiro_paths import (
    chat_assets,
    enable_utf8,
    find_app_root,
    kiro_agent_dir,
    session_assets,
)

CHECKS = [
    ("out/nls.messages.json", "打开 Agent Focus"),
    ("out/nls.messages.json", "新增功能"),
    ("out/vs/workbench/workbench.desktop.main.js", "文件"),
    ("extensions/kiro.kiro-agent/dist/extension.js", "沙箱：关闭"),
    ("extensions/kiro.kiro-agent/dist/extension.js", "自动补全"),
    ("extensions/kiro.kiro-agent/package.json", "审查 Markdown"),
]


def read(path: Path) -> str:
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        return ""


def _node(suffix: str, path: Path) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as fh:
        tmp = Path(fh.name)
    shutil.copy2(path, tmp)
    try:
        return subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
    finally:
        tmp.unlink(missing_ok=True)


def node_check(path: Path) -> str:
    if not shutil.which("node"):
        return "skip"
    res = _node(".cjs", path)
    if res.returncode == 0:
        return "ok"
    # ESM 文件用 .cjs 检查会报 "To load an ES module..."，换 .mjs 再试
    if "ES module" in (res.stderr or "") or "import" in (res.stderr or ""):
        res = _node(".mjs", path)
        if res.returncode == 0:
            return "ok"
    return f"fail: {(res.stderr or '').strip()[:120]}"


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="Kiro 汉化验收")
    ap.add_argument("--app")
    args = ap.parse_args()
    app = find_app_root(args.app)

    failed = 0
    print("== 文案")
    for rel, needle in CHECKS:
        text = read(app / Path(*rel.split("/")))
        ok = needle in text
        print(f"  {'OK  ' if ok else '缺失'} {rel}  ← 「{needle}」")
        failed += 0 if ok else 1

    print("\n== 语法")
    targets = [app / "out" / "nls.messages.js",
               app / "out" / "vs" / "workbench" / "workbench.desktop.main.js",
               app / "out" / "vs" / "sessions" / "sessions.desktop.main.js",
               kiro_agent_dir(app) / "dist" / "extension.js"]
    targets += [p for p in chat_assets(app).glob("mermaid-*.js")]
    targets += [p for p in session_assets(app).glob("mermaid-*.js")]
    for path in targets:
        if not path.exists():
            continue
        verdict = node_check(path)
        if verdict.startswith("fail"):
            failed += 1
        print(f"  {verdict:<28} {path.name}")

    print(f"\n{'通过' if failed == 0 else f'{failed} 项未通过'}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
