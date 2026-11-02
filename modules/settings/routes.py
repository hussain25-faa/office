from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from werkzeug.security import generate_password_hash
from database.db import get_db, log_activity

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")
MODULES = ("dashboard", "employees", "attendance", "tasks", "inventory", "projects", "expenses", "salary", "invoices", "reports", "settings")


def _is_owner():
    return (session.get("role") or "").lower() == "owner"


@settings_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    if not _is_owner():
        flash("Settings & System Access is reserved for owners and administrators.", "warning")
        return redirect(url_for("owner.dashboard"))

    db = get_db()
    action = request.form.get("action") if request.method == "POST" else None
    try:
        if action == "division":
            db.execute("INSERT INTO business_divisions(name,code) VALUES(?,?)",
                       (request.form["name"].strip(), request.form["code"].strip().upper()))
            flash("Business workspace added.", "success")
        elif action == "user":
            username = request.form["username"].strip()
            db.execute("INSERT INTO users(username,email,password_hash,role_id,employee_id,division_id) VALUES(?,?,?,?,?,?)",
                       (username, request.form.get("email") or None,
                        generate_password_hash(request.form["password"]),
                        request.form["role_id"], request.form.get("employee_id") or None,
                        request.form.get("division_id") or None))
            flash(f"User account '{username}' created successfully.", "success")
        elif action == "permissions":
            for role in db.execute("SELECT id FROM roles").fetchall():
                for module in MODULES:
                    view = int(bool(request.form.get(f"view_{role['id']}_{module}")))
                    manage = int(bool(request.form.get(f"manage_{role['id']}_{module}")))
                    db.execute("""INSERT INTO role_permissions(role_id,module_name,can_view,can_manage) VALUES(?,?,?,?)
                        ON CONFLICT(role_id,module_name) DO UPDATE SET can_view=excluded.can_view,can_manage=excluded.can_manage""",
                               (role["id"], module, view, manage))
            flash("Role access permissions saved.", "success")
        elif action == "theme":
            db.execute("INSERT INTO company_settings(setting_key,setting_value) VALUES('ui_theme',?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                       (request.form.get("ui_theme", "violet"),))
            flash("Theme updated.", "success")
        elif action == "user_status":
            uid = request.form["user_id"]
            new_active = 1 if request.form.get("active") == "1" else 0
            db.execute("UPDATE users SET active=? WHERE id=?", (new_active, uid))
            flash("User access status updated.", "success")
        elif action == "edit_user":
            uid = request.form["user_id"]
            username = request.form["username"].strip()
            email = request.form.get("email") or None
            role_id = request.form["role_id"]
            division_id = request.form.get("division_id") or None
            employee_id = request.form.get("employee_id") or None
            new_pwd = request.form.get("new_password", "").strip()

            if new_pwd:
                db.execute("""UPDATE users SET username=?, email=?, role_id=?, division_id=?,
                              employee_id=?, password_hash=? WHERE id=?""",
                           (username, email, role_id, division_id, employee_id, generate_password_hash(new_pwd), uid))
            else:
                db.execute("""UPDATE users SET username=?, email=?, role_id=?, division_id=?,
                              employee_id=? WHERE id=?""",
                           (username, email, role_id, division_id, employee_id, uid))
            flash(f"User '{username}' updated successfully.", "success")
        elif action == "delete_user":
            uid = request.form["user_id"]
            if int(uid) == session.get("user_id"):
                flash("You cannot delete your own logged-in user account.", "danger")
            else:
                db.execute("DELETE FROM users WHERE id=?", (uid,))
                flash("User account deleted.", "success")

        if action:
            db.commit()
            log_activity("UPDATE", "settings", None, action)
            db.commit()
    except Exception as exc:
        db.rollback()
        flash(f"Settings could not be saved: {exc}", "danger")

    if action:
        return redirect(url_for("settings.index"))

    roles = db.execute("SELECT * FROM roles ORDER BY id").fetchall()
    permissions = {(p["role_id"], p["module_name"]): p for p in db.execute("SELECT * FROM role_permissions").fetchall()}
    divisions = db.execute("SELECT * FROM business_divisions ORDER BY name").fetchall()
    employees = db.execute("SELECT id, employee_code, full_name FROM employees WHERE active=1 ORDER BY full_name").fetchall()
    users = db.execute("""SELECT u.id, u.username, u.email, u.active, u.role_id, u.division_id, u.employee_id,
                                 r.name AS role, b.name AS division_name, e.full_name AS employee_name
                          FROM users u
                          JOIN roles r ON r.id=u.role_id
                          LEFT JOIN business_divisions b ON b.id=u.division_id
                          LEFT JOIN employees e ON e.id=u.employee_id
                          ORDER BY u.id ASC""").fetchall()
    theme_row = db.execute("SELECT setting_value FROM company_settings WHERE setting_key='ui_theme'").fetchone()
    theme = theme_row["setting_value"] if theme_row else "violet"

    return render_template("settings.html", roles=roles, modules=MODULES, permissions=permissions,
                           divisions=divisions, employees=employees, users=users, theme=theme)
