import sqlite3
from pathlib import Path
from datetime import datetime

def backup_database(source_path, backup_dir):
    source = Path(source_path)
    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"business_erp_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return str(target)

def restore_database(backup_path, target_path):
    # Restore is intentionally an explicit administrative operation.
    source = sqlite3.connect(backup_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
