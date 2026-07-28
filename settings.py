"""ユーザー設定(テーマ選択)の永続化。"""
from __future__ import annotations

import json
from pathlib import Path

_APP_DIR_NAME = "BMSWavDurationChecker"
_VALID_THEMES = ("dark", "light")


def _settings_path() -> Path:
    import os

    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    directory = base / _APP_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "settings.json"


def load_theme(default: str = "dark") -> str:
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    theme = data.get("theme")
    return theme if theme in _VALID_THEMES else default


def save_theme(theme: str) -> None:
    if theme not in _VALID_THEMES:
        return
    try:
        _settings_path().write_text(
            json.dumps({"theme": theme}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # 設定保存に失敗してもアプリの動作は継続する
