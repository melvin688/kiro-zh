# -*- coding: utf-8 -*-
"""统一的文本读写，保证句柄关闭。

脚本会在写完文件后立刻重启 Kiro，未 flush 的缓冲会让 Kiro 读到截断的
bundle，所以这里一律走 `with`，不用 `io.open(...).write(...)` 的裸调用。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


def safe_console() -> None:
    """把 stdout/stderr 切到 UTF-8。

    脚本输出大量中文，在英文版 Windows（cp1252）或 CI 上直接 print 会抛
    UnicodeEncodeError 而不是降级成问号，所以导入本模块即切换。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


safe_console()


def read_text(path: Path | str) -> str:
    with io.open(path, encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read()


def write_text(path: Path | str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(text)


def load_json(path: Path | str):
    return json.loads(read_text(path))


def dump_json(path: Path | str, obj, indent: int | None = None, separators=None) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=indent, separators=separators)
    write_text(path, text)
