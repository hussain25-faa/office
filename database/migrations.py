"""Small, repeatable migrations for databases created before new features existed."""
from database.db import get_db


def apply_migrations():
    db = get_db()
    columns = {row["name"] for row in db.execute("PRAGMA table_info(employees)").fetchall()}
    for name, definition in {
        "email": "TEXT", "aadhaar_number": "TEXT", "date_of_birth": "TEXT",
        "gender": "TEXT", "bank_name": "TEXT", "bank_account": "TEXT",
        "ifsc_code": "TEXT"
    }.items():
        if name not in columns:
            db.execute(f"ALTER TABLE employees ADD COLUMN {name} {definition}")

    # Task migrations for detailed work tracking
    task_columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)").fetchall()}
    for name, definition in {
        "start_date": "TEXT",
        "estimated_hours": "REAL DEFAULT 0",
        "actual_hours": "REAL DEFAULT 0",
        "progress_percent": "INTEGER DEFAULT 0",
        "project_id": "INTEGER REFERENCES projects(id)",
        "employee_notes": "TEXT",
        "instructions": "TEXT"
    }.items():
        if name not in task_columns:
            db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")

    # Auto-link orphaned user accounts if email matches an employee
    db.execute("""
        UPDATE users
        SET employee_id = (SELECT e.id FROM employees e WHERE e.email = users.email OR e.email = users.username LIMIT 1)
        WHERE employee_id IS NULL AND (email IS NOT NULL OR username IS NOT NULL)
        AND EXISTS (SELECT 1 FROM employees e WHERE e.email = users.email OR e.email = users.username)
    """)

    db.execute("""CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INTEGER NOT NULL REFERENCES roles(id),
        module_name TEXT NOT NULL,
        can_view INTEGER NOT NULL DEFAULT 1,
        can_manage INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(role_id, module_name))""")
    modules = ("dashboard", "employees", "attendance", "tasks", "inventory", "projects", "expenses", "salary", "invoices", "reports", "settings")
    roles = db.execute("SELECT id, name FROM roles").fetchall()
    for role in roles:
        for module in modules:
            manage = int(role["name"] == "owner")
            view = int(role["name"] == "owner" or module not in ("settings", "reports"))
            if role["name"] == "employee" and module not in ("dashboard", "attendance", "tasks", "salary"):
                view = 0
            db.execute("INSERT OR IGNORE INTO role_permissions(role_id,module_name,can_view,can_manage) VALUES(?,?,?,?)",
                       (role["id"], module, view, manage))
    db.commit()
