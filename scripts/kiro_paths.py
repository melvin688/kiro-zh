# -*- coding: utf-8 -*-
"""定位 Kiro 安装目录、数据目录与语言包，并统一 stdout 编码。

所有脚本都通过这里拿路径，避免把个人机器路径写死。
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

APP_HINT_ENV = "KIRO_APP"


def enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get(APP_HINT_ENV)
    if env:
        out.append(Path(env))
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    for base in filter(None, (local, os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""))):
        for pattern in ("Programs/*iro*/resources/app", "*iro*/resources/app"):
            out.extend(Path(p) for p in glob.glob(os.path.join(base, pattern)))
    # 少数安装方式把程序放在 APPDATA 下
    if roaming:
        out.extend(Path(p) for p in glob.glob(os.path.join(roaming, "*iro*", "resources", "app")))
    return out


def find_app_root(explicit: str | None = None) -> Path:
    """返回 .../resources/app 目录。"""
    if explicit:
        p = Path(explicit)
        if (p / "out").is_dir():
            return p
        if (p / "resources" / "app" / "out").is_dir():
            return p / "resources" / "app"
        raise SystemExit(f"指定的 Kiro 目录无效：{p}")

    for cand in _candidates():
        if (cand / "out").is_dir() and (cand / "extensions").is_dir():
            return cand
    raise SystemExit(
        "未找到 Kiro 安装目录。请用 --app 指定，例如\n"
        "  python scripts/apply.py --app \"C:/Users/<你>/AppData/Local/Programs/Kiro/resources/app\"\n"
        f"也可以设置环境变量 {APP_HINT_ENV}。"
    )


def kiro_agent_dir(app: Path) -> Path:
    return app / "extensions" / "kiro.kiro-agent"


def chat_assets(app: Path) -> Path:
    return kiro_agent_dir(app) / "packages" / "kiro-ui-agent-chat" / "dist" / "assets"


def session_assets(app: Path) -> Path:
    return kiro_agent_dir(app) / "packages" / "kiro-ui-session-details" / "dist" / "assets"


def chat_dist(app: Path) -> Path:
    return kiro_agent_dir(app) / "packages" / "kiro-ui-agent-chat" / "dist"


def session_dist(app: Path) -> Path:
    return kiro_agent_dir(app) / "packages" / "kiro-ui-session-details" / "dist"


def user_dir() -> Path:
    """~/.kiro（argv.json、steering、skills、extensions）。"""
    return Path(os.path.expanduser("~")) / ".kiro"


def data_dir() -> Path:
    """%APPDATA%/Kiro（logs、clp 缓存、languagepacks.json）。"""
    roaming = os.environ.get("APPDATA")
    if roaming:
        return Path(roaming) / "Kiro"
    return Path(os.path.expanduser("~")) / ".config" / "Kiro"


def find_language_pack(locale: str = "zh-hans") -> Path | None:
    """找简体中文语言包的 main.i18n.json。"""
    roots = [user_dir() / "extensions", Path(os.path.expanduser("~")) / ".vscode" / "extensions"]
    for root in roots:
        hits = sorted(glob.glob(str(root / f"*language-pack-{locale}*" / "translations" / "main.i18n.json")))
        if hits:
            return Path(hits[-1])
    return None


def bundle(app: Path, relative: str) -> Path:
    return app / Path(*relative.split("/"))
