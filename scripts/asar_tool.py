# -*- coding: utf-8 -*-
"""读写 Electron asar 里的单个文件，做等长字节替换。

背景：Kiro 的欢迎页 / 登录页（`@kiro/sign-in-page`）打包在
`resources/app/node_modules.asar` 里，文案是 JSX 里的硬编码字符串，
既不在语言包也不在 NLS 表里。asar 是「JSON 头 + 顺序文件区」的容器，
文件在区内的 offset/size 记在头上，所以直接改内容会让长度对不上。

这里的做法是**等长替换**：中文比英文短时用空格补齐，保证该文件字节数
不变，头部无需重写，asar 结构保持有效。中文比英文长则拒绝（需改写文案）。

用法：
    python scripts/asar_tool.py strings --asar <asar> --entry <路径>
    python scripts/asar_tool.py patch   --asar <asar> --entry <路径> --map map.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
from pathlib import Path

from io_util import load_json

LITERAL = re.compile(rb'(?:children|label|title|placeholder|description|aria-label|alt):"([^"]{2,120})"')


# ------------------------------------------------------------------ asar 解析

def load(asar: Path):
    data = bytearray(asar.read_bytes())
    start = data.find(b'{"files":')
    if start < 0:
        raise SystemExit("不是有效的 asar：找不到头部 JSON")
    text = bytes(data[start:start + 2_000_000]).decode("utf-8", "replace")
    header, used = json.JSONDecoder().raw_decode(text)
    data_start = (start + used + 3) // 4 * 4
    return data, header, data_start


def find_entry(node: dict, suffix: str, path: str = ""):
    want = suffix.lstrip("/")
    for name, entry in node.get("files", {}).items():
        here = f"{path}/{name}"
        if "files" in entry:
            got = find_entry(entry, suffix, here)
            if got:
                return got
        elif entry.get("offset") is not None and here.lstrip("/").endswith(want):
            return entry
    return None


def entry_bytes(data, data_start: int, entry: dict) -> bytes:
    off = data_start + int(entry["offset"])
    return bytes(data[off:off + entry["size"]])


# ------------------------------------------------------------------ 命令

def cmd_strings(args) -> None:
    data, header, dstart = load(Path(args.asar))
    entry = find_entry(header, args.entry)
    if not entry:
        raise SystemExit(f"找不到条目：{args.entry}")
    chunk = entry_bytes(data, dstart, entry)
    seen: dict[str, int] = {}
    for m in LITERAL.finditer(chunk):
        text = m.group(1).decode("utf-8", "replace")
        if re.search(r"[A-Za-z]{2}", text) and not text.startswith(("http", "codicon")):
            seen[text] = seen.get(text, 0) + 1
    for text in sorted(seen, key=lambda t: -len(t.encode())):
        print(f"{len(text.encode()):>5}  {text}")


def apply_map(asar: Path, entry_suffix: str, mapping: dict[str, str]) -> int:
    """等长替换指定条目里的字符串，返回替换条数。"""
    data, header, dstart = load(asar)
    entry = find_entry(header, entry_suffix)
    if not entry:
        raise SystemExit(f"找不到条目：{entry_suffix}")
    off = dstart + int(entry["offset"])
    size = entry["size"]
    chunk = bytes(data[off:off + size])

    changed = 0
    for en, zh in mapping.items():
        raw_en = en.encode()
        if raw_en not in chunk:
            continue
        need = len(raw_en)
        raw_zh = zh.encode()
        if len(raw_zh) > need:
            print(f"跳过（中文比英文长 {len(raw_zh) - need} 字节）：{en} -> {zh}")
            continue
        chunk = chunk.replace(raw_en, raw_zh + b" " * (need - len(raw_zh)))
        changed += 1

    if not changed:
        return 0
    if len(chunk) != size:
        raise SystemExit("内部错误：替换后长度变化，已中止")

    bak = asar.with_suffix(asar.suffix + ".zhbak")
    if not bak.exists():
        shutil.copy2(asar, bak)
        print(f"备份：{bak}")
    data[off:off + size] = chunk
    asar.write_bytes(bytes(data))
    print(f"已替换 {changed} 条，写入 {asar.name}")
    return changed


def cmd_patch(args) -> None:
    asar = Path(args.asar)
    mapping: dict[str, str] = load_json(args.map)
    apply_map(asar, args.entry, mapping)


def main() -> None:
    ap = argparse.ArgumentParser(description="asar 内文件等长字节替换")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("strings", "patch"):
        p = sub.add_parser(name)
        p.add_argument("--asar", required=True)
        p.add_argument("--entry", required=True)
        if name == "patch":
            p.add_argument("--map", required=True)
    args = ap.parse_args()
    cmd_strings(args) if args.cmd == "strings" else cmd_patch(args)


if __name__ == "__main__":
    main()
