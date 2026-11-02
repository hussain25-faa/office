import sqlite3
from flask import current_app, g

def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE_PATH"], timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 20000")
        g.db = conn
    return g.db

def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)

def log_activity(action, entity_type=None, entity_id=None, details=None):
    from flask import request, session
    db = get_db()
    db.execute(
        "INSERT INTO activity_logs(user_id, action, entity_type, entity_id, details, ip_address) VALUES(?,?,?,?,?,?)",
        (session.get("user_id"), action, entity_type, entity_id, details, request.remote_addr)
    )
