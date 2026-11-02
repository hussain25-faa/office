from werkzeug.security import generate_password_hash
from database.db import get_db

def create_owner(username, password, email=None):
    db=get_db()
    role=db.execute("SELECT id FROM roles WHERE name='owner'").fetchone()
    if not role: raise RuntimeError("Initialize database first")
    db.execute("INSERT INTO users(username,email,password_hash,role_id) VALUES(?,?,?,?)",
               (username,email,generate_password_hash(password),role["id"]))
    db.commit()
