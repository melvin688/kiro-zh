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
__version__ = "0.6.0"


def assets_dir() -> Path:
    """资产目录：源码运行时是仓库根/assets，打包成 exe 后在解包临时目录。"""
    local = Path(__file__).resolve().parent.parent / "assets"
    if local.is_dir():
        return local
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "assets"
    return local


def enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _platform_app_globs() -> list[str]:
    """各平台 Kiro 安装位置的 glob（大小写不敏感：*iro* 同时命中 Kiro / kiro）。"""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return [
            "/Applications/*iro*.app/Contents/Resources/app",
            f"{home}/Applications/*iro*.app/Contents/Resources/app",
        ]
    if sys.platform.startswith("linux"):
        return [
            "/usr/share/*iro*/resources/app",
            "/usr/lib/*iro*/resources/app",
            "/opt/*iro*/resources/app",
            "/opt/*iro*/*/resources/app",
            f"{home}/.local/share/*iro*/resources/app",
        ]
    # Windows：用户级安装优先，其次是 Program Files 与 APPDATA
    out: list[str] = []
    for base in filter(
        None,
        (
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("APPDATA", ""),
        ),
    ):
        out.append(os.path.join(base, "Programs", "*iro*", "resources", "app"))
        out.append(os.path.join(base, "*iro*", "resources", "app"))
    return out


def _candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get(APP_HINT_ENV)
    if env:
        out.append(Path(env))
    for pattern in _platform_app_globs():
        out.extend(Path(p) for p in glob.glob(pattern))
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
    """Kiro 的用户数据目录（logs、clp 缓存、languagepacks.json）。

    Windows: %APPDATA%/Kiro；macOS: ~/Library/Application Support/Kiro；
    Linux: $XDG_CONFIG_HOME/Kiro 或 ~/.config/Kiro。
    """
    if sys.platform == "darwin":
        return Path(os.path.expanduser("~")) / "Library" / "Application Support" / "Kiro"
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path(os.path.expanduser("~")) / ".config")
        return Path(base) / "Kiro"
    roaming = os.environ.get("APPDATA")
    if roaming:
        return Path(roaming) / "Kiro"
    return Path(os.path.expanduser("~")) / ".config" / "Kiro"


def find_language_pack(locale: str = "zh-hans") -> Path | None:
    """找简体中文语言包的 main.i18n.json。"""
    home = Path(os.path.expanduser("~"))
    roots = [
        user_dir() / "extensions",
        home / ".vscode" / "extensions",
        home / ".vscode-server" / "extensions",  # 远程开发
        home / ".cursor" / "extensions",
    ]
    for root in roots:
        hits = sorted(glob.glob(str(root / f"*language-pack-{locale}*" / "translations" / "main.i18n.json")))
        if hits:
            return Path(hits[-1])
    return None


def bundle(app: Path, relative: str) -> Path:
    return app / Path(*relative.split("/"))
