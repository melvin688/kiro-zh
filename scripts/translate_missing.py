# -*- coding: utf-8 -*-
"""补齐语言包缺失的条目：输出待译分块 -> 翻译后合并回 main.i18n.json。

Kiro 自带的中文语言包只覆盖上游 VS Code 的字符串，Kiro 自己新增的
设置项说明、命令描述是缺的。这里把它们按模块切块导出，交给任何翻译
手段（人或模型）产出同构 JSON，再合并并校验占位符。

用法：
    python scripts/translate_missing.py chunks --out ./work --chunks 8
    python scripts/translate_missing.py merge  --out ./work
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
from pathlib import Path

from kiro_paths import enable_utf8, find_app_root, find_language_pack

PH = re.compile(r"\{\d+\}|%[sd]|\$\([^)]+\)|\$\{[^}]+\}|<[a-zA-Z/][^>]*>")


def key_of(entry) -> str | None:
    if isinstance(entry, dict):
        return entry.get("key")
    return entry if isinstance(entry, str) else None


def collect(app: Path) -> dict[str, dict[str, str]]:
    metadata = json.load(io.open(app / "out" / "nls.metadata.json", encoding="utf-8"))
    pack = find_language_pack("zh-hans")
    if not pack:
        raise SystemExit("没找到简体中文语言包")
    contents = json.load(io.open(pack, encoding="utf-8"))["contents"]

    missing: dict[str, dict[str, str]] = {}
    for module, messages in metadata.get("messages", {}).items():
        mod_keys = metadata.get("keys", {}).get(module, [])
        table = contents.get(module, {})
        for i, en in enumerate(messages):
            if not isinstance(en, str) or len(en) < 2:
                continue
            key = key_of(mod_keys[i]) if i < len(mod_keys) else None
            if key and not table.get(key):
                missing.setdefault(module, {})[key] = en
    return missing


def cmd_chunks(args) -> None:
    app = find_app_root(args.app)
    missing = collect(app)
    total = sum(len(v) for v in missing.values())
    print(f"缺失 {total} 条，分布在 {len(missing)} 个模块")

    flat = [(m, k, v) for m, kv in missing.items() for k, v in kv.items()]
    size = max(1, -(-total // args.chunks))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for n in range(args.chunks):
        part = flat[n * size:(n + 1) * size]
        if not part:
            break
        chunk: dict[str, dict[str, str]] = {}
        for module, key, en in part:
            chunk.setdefault(module, {})[key] = en
        path = outdir / f"nls_chunk_{n + 1}.json"
        io.open(path, "w", encoding="utf-8").write(json.dumps(chunk, ensure_ascii=False, indent=1))
        print(f"  {path.name}: {len(part)} 条")

    (outdir / "RULES.txt").write_text(
        "把每个 nls_chunk_*.json 的英文 value 译成简体中文，另存为 nls_out_<n>.json，结构不变。\n"
        "规则：\n"
        "1. 保留全部占位符 {0} {1} %s %d $(icon) ${var} <tag>，位置与数量不变。\n"
        "2. 产品名、命令 ID、配置键、路径、代码片段不译：Kiro / AWS / MCP / CLI / IDE / Agent Focus。\n"
        "3. 术语统一：Agent、chat=聊天、session=会话、workspace=工作区、credit=积分、artifact=产物、"
        "worktree=工作树、steering 保留、approve=批准、skill=技能。\n"
        "4. 只输出合法 JSON。\n",
        encoding="utf-8",
    )
    print(f"规则写到 {outdir / 'RULES.txt'}")


def cmd_merge(args) -> None:
    app = find_app_root(args.app)
    pack_path = find_language_pack("zh-hans")
    if not pack_path:
        raise SystemExit("没找到简体中文语言包")
    doc = json.load(io.open(pack_path, encoding="utf-8"))
    contents = doc["contents"]

    outdir = Path(args.out)
    files = sorted(outdir.glob("nls_out_*.json"))
    if not files:
        raise SystemExit(f"{outdir} 下没有 nls_out_*.json")

    added = skipped = problem = 0
    for f in files:
        data = json.load(io.open(f, encoding="utf-8"))
        for module, kv in data.items():
            for key, zh in kv.items():
                if not isinstance(zh, str) or not zh.strip():
                    skipped += 1
                    continue
                en = _english_for(app, module, key)
                if en and set(PH.findall(en)) != set(PH.findall(zh)):
                    print(f"占位符不一致，跳过：{module} :: {key}")
                    problem += 1
                    continue
                contents.setdefault(module, {})[key] = zh
                added += 1

    if added:
        shutil.copy2(pack_path, pack_path.with_suffix(".json.zhbak"))
        io.open(pack_path, "w", encoding="utf-8", newline="").write(
            json.dumps(doc, ensure_ascii=False, indent=1)
        )
    print(f"合并 {added} 条，跳过 {skipped} 条，占位符问题 {problem} 条")
    print("改完要重跑 localize_nls.py 并重启，界面才会用到新译文。")


def _english_for(app: Path, module: str, key: str) -> str | None:
    cache = getattr(_english_for, "_cache", None)
    if cache is None:
        metadata = json.load(io.open(app / "out" / "nls.metadata.json", encoding="utf-8"))
        table: dict[tuple[str, str], str] = {}
        for mod, messages in metadata.get("messages", {}).items():
            mod_keys = metadata.get("keys", {}).get(mod, [])
            for i, en in enumerate(messages):
                k = key_of(mod_keys[i]) if i < len(mod_keys) else None
                if k and isinstance(en, str):
                    table[(mod, k)] = en
        _english_for._cache = table  # type: ignore[attr-defined]
        cache = table
    return cache.get((module, key))


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="补齐语言包缺失条目")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("chunks", "merge"):
        p = sub.add_parser(name)
        p.add_argument("--app")
        p.add_argument("--out", default="./work")
        if name == "chunks":
            p.add_argument("--chunks", type=int, default=8)
    args = ap.parse_args()
    cmd_chunks(args) if args.cmd == "chunks" else cmd_merge(args)


if __name__ == "__main__":
    main()
