import sqlite3
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from config import Config

db_path = Path(Config.DATABASE_PATH)
db_path.parent.mkdir(parents=True, exist_ok=True)
schema = (BASE / "database" / "schema.sql").read_text(encoding="utf-8")
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript(schema)
conn.commit()
conn.close()
print(f"Database initialized safely: {db_path}")
