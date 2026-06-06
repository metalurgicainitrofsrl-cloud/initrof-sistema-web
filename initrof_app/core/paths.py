from __future__ import annotations

import os
import sys
import json
from pathlib import Path


APP_NAME = "INITROF Gestion"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_root()))
    return base / relative


def default_logo_path() -> Path:
    return resource_path("resources/initrof_logo.png")


def user_config_path() -> Path:
    base = Path(os.environ.get("APPDATA", app_root()))
    path = base / "INITROF Gestion"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        path = app_root() / "config"
        path.mkdir(parents=True, exist_ok=True)
    return path / "config.json"


def configured_data_dir() -> Path | None:
    config_file = user_config_path()
    if not config_file.exists():
        return None
    try:
        value = json.loads(config_file.read_text(encoding="utf-8")).get("data_dir")
    except Exception:
        return None
    return Path(value) if value else None


def set_configured_data_dir(path: Path) -> None:
    user_config_path().write_text(json.dumps({"data_dir": str(path)}, indent=2), encoding="utf-8")


def data_dir() -> Path:
    override = os.environ.get("INITROF_DATA_DIR")
    path = Path(override) if override else configured_data_dir() or app_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "initrof.sqlite"


def exports_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
