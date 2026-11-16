# -*- coding: utf-8 -*-
"""把简体中文语言包的中文烘焙进 Kiro 自己的 NLS 消息表。

背景：Kiro 的 workbench/sessions 渲染进程用 localize(index) 走
resources/app/out/nls.messages.json 里的字符串数组，语言包
（main.i18n.json）只覆盖按「模块 + key」取文案的那部分代码。
所以菜单、设置项说明这类字符串改语言包不生效，必须写进这张表。

做法：用 out/nls.metadata.json 的英文原文对照语言包里的中文，
按「英文 -> 中文」映射替换数组元素。同一英文有多种译法时取出现最多的那个；
这样不会错位（按索引写会串行，因为 sessions 与 workbench 的数组顺序不同）。

用法：
    python scripts/localize_nls.py --app <resources/app> [--dry-run] [--clear-cache]
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import shutil
from pathlib import Path

from kiro_paths import data_dir, enable_utf8, find_app_root, find_language_pack

CJK = lambda s: any("\u4e00" <= ch <= "\u9fff" for ch in s)  # noqa: E731


def build_map(metadata: dict, contents: dict) -> dict[str, str]:
    """英文原文 -> 中文（同英文多译时取众数）。"""
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    keys = metadata.get("keys", {})
    for module, messages in metadata.get("messages", {}).items():
        mod_keys = keys.get(module, [])
        table = contents.get(module, {})
        for i, en in enumerate(messages):
            if not isinstance(en, str):
                continue
            raw = mod_keys[i] if i < len(mod_keys) else None
            key = raw.get("key") if isinstance(raw, dict) else raw
            if not key:
                continue
            zh = table.get(key)
            if zh and zh != en:
                votes[en][zh] += 1
    return {en: counter.most_common(1)[0][0] for en, counter in votes.items()}


def bake_array(arr: list[str], mapping: dict[str, str]) -> int:
    n = 0
    for i, value in enumerate(arr):
        zh = mapping.get(value)
        if zh and zh != value:
            arr[i] = zh
            n += 1
    return n


def load_js_array(path: Path) -> tuple[str, str, list[str]]:
    raw = io.open(path, encoding="utf-8").read()
    marker = "globalThis._VSCODE_NLS_MESSAGES="
    idx = raw.find(marker)
    if idx < 0:
        raise SystemExit(f"{path.name} 结构不认识：找不到 {marker}")
    head = raw[: idx + len(marker)]
    arr = json.loads(raw[len(head):].rstrip().rstrip(";"))
    return head, raw[len(head):], arr


def run(app: Path, dry_run: bool = False, clear_cache: bool = False) -> dict[str, int]:
    out = app / "out"
    pack = find_language_pack("zh-hans")
    if not pack:
        raise SystemExit("没找到简体中文语言包（ms-ceintl.vscode-language-pack-zh-hans）。请先在 Kiro 里装好中文语言包。")
    print(f"语言包：{pack}")

    metadata = json.load(io.open(out / "nls.metadata.json", encoding="utf-8"))
    contents = json.load(io.open(pack, encoding="utf-8"))["contents"]
    mapping = build_map(metadata, contents)
    print(f"对照表：{len(mapping)} 条英文可译")

    stats: dict[str, int] = {}
    for name in ("nls.messages.json", "nls.messages.js"):
        path = out / name
        if not path.exists():
            continue
        if name.endswith(".json"):
            arr = json.load(io.open(path, encoding="utf-8"))
            n = bake_array(arr, mapping)
            if n and not dry_run:
                shutil.copy2(path, path.with_suffix(path.suffix + ".zhbak"))
                io.open(path, "w", encoding="utf-8", newline="").write(
                    json.dumps(arr, ensure_ascii=False, separators=(",", ":"))
                )
        else:
            head, _tail, arr = load_js_array(path)
            n = bake_array(arr, mapping)
            if n and not dry_run:
                shutil.copy2(path, path.with_suffix(path.suffix + ".zhbak"))
                io.open(path, "w", encoding="utf-8", newline="").write(
                    head + json.dumps(arr, ensure_ascii=False, separators=(",", ":")) + ";"
                )
        pct = 100 * sum(1 for x in arr if CJK(x)) / len(arr)
        stats[name] = n
        print(f"{name}: {'可替换' if dry_run else '替换'} {n} 条，中文覆盖 {pct:.1f}%（{len(arr)} 条）")

    if clear_cache and not dry_run:
        cache = data_dir() / "clp"
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
            print(f"已清空 NLS 缓存：{cache}")
    elif not dry_run:
        print("提示：改完必须清掉 %APPDATA%/Kiro/clp 缓存并重启，否则界面仍是旧文案（本脚本 --clear-cache 可代做）。")
    return stats


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="把中文烘焙进 Kiro 的 NLS 消息表")
    ap.add_argument("--app", help="Kiro 的 resources/app 目录")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clear-cache", action="store_true", help="顺带删除 %APPDATA%/Kiro/clp")
    args = ap.parse_args()
    run(find_app_root(args.app), args.dry_run, args.clear_cache)


if __name__ == "__main__":
    main()
