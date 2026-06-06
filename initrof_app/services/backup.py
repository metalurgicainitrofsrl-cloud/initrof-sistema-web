from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from initrof_app.core.paths import backups_dir, db_path


def create_backup() -> Path:
    target = backups_dir() / f"initrof_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    shutil.copy2(db_path(), target)
    return target


def restore_backup(source: Path) -> None:
    shutil.copy2(source, db_path())
