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
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from kiro_paths import enable_utf8, find_app_root, find_language_pack
import io_util  # noqa: F401  导入即把控制台切到 UTF-8

PH = re.compile(r"\{\d+\}|%[sd]|\$\([^)]+\)|\$\{[^}]+\}|<[a-zA-Z/][^>]*>")

RULES = """你是 VS Code / Kiro 界面本地化译员。输入是 JSON：{模块: {key: 英文文案}}。
输出必须是同构 JSON，key 原样保留，只把 value 译成简体中文。
规则：
1. 占位符 {0} {1} %s %d $(icon) ${var} <tag> 原样保留，位置与数量不变。
2. 产品名、命令 ID、配置键、路径、代码片段不译：Kiro / AWS / MCP / CLI / IDE / Agent Focus。
3. 术语统一：Agent、chat=聊天、session=会话、workspace=工作区、credit=积分、artifact=产物、worktree=工作树、steering 保留、approve=批准、skill=技能。
4. 不输出解释、不加 Markdown 代码块，只输出 JSON。"""


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


def build_chunks(missing: dict[str, dict[str, str]], budget: int = 6000) -> list[dict[str, dict[str, str]]]:
    """按字符预算切块，块内保持 module -> key -> 英文。"""
    chunks: list[dict[str, dict[str, str]]] = []
    cur: dict[str, dict[str, str]] = {}
    size = 0
    for module, kv in missing.items():
        for key, en in kv.items():
            cost = len(en) + len(key) + 8
            if cur and size + cost > budget:
                chunks.append(cur)
                cur, size = {}, 0
            cur.setdefault(module, {})[key] = en
            size += cost
    if cur:
        chunks.append(cur)
    return chunks


def parse_reply(text: str) -> dict:
    """从模型回复里抠出 JSON（容忍 ```json 围栏与前后废话）。"""
    body = (text or "").strip()
    body = re.sub(r"^```[a-zA-Z]*\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("回复里没有 JSON 对象")
    return json.loads(body[start:end + 1])


def validate(chunk: dict[str, dict[str, str]], out: dict) -> tuple[dict[str, dict[str, str]], list[str]]:
    """返回（合格译文, 问题条目）。占位符不一致、空值、漏条目都算问题。"""
    good: dict[str, dict[str, str]] = {}
    bad: list[str] = []
    if not isinstance(out, dict):
        return good, ["整体不是 JSON 对象"]
    for module, kv in chunk.items():
        got = out.get(module)
        if not isinstance(got, dict):
            bad.extend(f"{module}::{k}" for k in kv)
            continue
        for key, en in kv.items():
            zh = got.get(key)
            if not isinstance(zh, str) or not zh.strip():
                bad.append(f"{module}::{key}")
                continue
            if set(PH.findall(en)) != set(PH.findall(zh)):
                bad.append(f"{module}::{key}")
                continue
            good.setdefault(module, {})[key] = zh.strip()
    return good, bad


def _post(url: str, payload: dict, key: str, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def translate_chunk(chunk: dict, api_url: str, model: str, key: str, retries: int = 2) -> dict:
    """调一次（含重试）翻译一块；返回合格条目，全部失败抛 RuntimeError。"""
    messages = [
        {"role": "system", "content": RULES},
        {"role": "user", "content": json.dumps(chunk, ensure_ascii=False)},
    ]
    last = "未知错误"
    for attempt in range(retries + 1):
        try:
            data = _post(api_url, {"model": model, "messages": messages, "temperature": 0.2}, key)
            reply = data["choices"][0]["message"]["content"]
            good, bad = validate(chunk, parse_reply(reply))
            if not bad:
                return good
            last = f"{len(bad)} 条不合格（占位符/空值），例：{', '.join(bad[:3])}"
            messages += [
                {"role": "assistant", "content": reply},
                {
                    "role": "user",
                    "content": "以下条目不合格：" + ", ".join(bad[:30])
                    + "。请只重发这些条目，结构同输入，占位符原样，纯 JSON。",
                },
            ]
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"翻译失败：{last}")


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

    (outdir / "RULES.txt").write_text(RULES, encoding="utf-8")
    print(f"规则写到 {outdir / 'RULES.txt'}")


def merge_out(app: Path, outdir: Path) -> tuple[int, int, int]:
    """把 nls_out_*.json 合并进语言包；返回（写入, 跳过, 占位符问题）。"""
    pack_path = find_language_pack("zh-hans")
    if not pack_path:
        raise SystemExit("没找到简体中文语言包")
    doc = json.load(io.open(pack_path, encoding="utf-8"))
    contents = doc["contents"]

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
    return added, skipped, problem


def cmd_auto(args) -> None:
    app = find_app_root(args.app)
    key = os.environ.get(args.key_env) or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(f"没找到 API key：请设置 {args.key_env}（或 DEEPSEEK_API_KEY / OPENAI_API_KEY）")

    missing = collect(app)
    total = sum(len(v) for v in missing.values())
    chunks = build_chunks(missing, args.chunk_chars)
    if args.limit:
        chunks = chunks[: args.limit]
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"缺失 {total} 条 → {len(chunks)} 块（每块约 {args.chunk_chars} 字符），模型 {args.model}")

    todo = []
    for i, chunk in enumerate(chunks, 1):
        dst = outdir / f"nls_out_{i}.json"
        if dst.exists() and dst.stat().st_size > 2:
            print(f"  跳过 {dst.name}（已存在）")
            continue
        todo.append((i, chunk, dst))

    def work(item):
        _i, chunk, dst = item
        try:
            good = translate_chunk(chunk, args.api_url, args.model, key)
        except RuntimeError as exc:
            return dst, None, str(exc)
        dst.write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
        return dst, good, None

    done = failed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for dst, good, err in pool.map(work, todo):
            if good is None:
                failed += 1
                print(f"  失败 {dst.name}：{err}")
            else:
                done += 1
                print(f"  {dst.name}: {sum(len(v) for v in good.values())} 条")

    print(f"翻译完成 {done} 块，失败 {failed} 块，产物在 {outdir}")
    if done:
        print("接下来合并进语言包：")
        print(f"  python scripts/translate_missing.py merge --out {outdir}")


def cmd_merge(args) -> None:
    app = find_app_root(args.app)
    added, skipped, problem = merge_out(app, Path(args.out))
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
    for name in ("chunks", "auto", "merge"):
        p = sub.add_parser(name)
        p.add_argument("--app")
        p.add_argument("--out", default="./work")
        if name == "chunks":
            p.add_argument("--chunks", type=int, default=8)
        if name == "auto":
            p.add_argument("--api-url", default=os.environ.get("KIRO_ZH_API_URL", "https://api.deepseek.com/v1"))
            p.add_argument("--model", default=os.environ.get("KIRO_ZH_MODEL", "deepseek-chat"))
            p.add_argument("--key-env", default="KIRO_ZH_API_KEY")
            p.add_argument("--chunk-chars", type=int, default=6000)
            p.add_argument("--workers", type=int, default=4)
            p.add_argument("--limit", type=int, default=0, help="只译前 N 块，0 表示全部")
    args = ap.parse_args()
    {"chunks": cmd_chunks, "auto": cmd_auto, "merge": cmd_merge}[args.cmd](args)


if __name__ == "__main__":
    main()
