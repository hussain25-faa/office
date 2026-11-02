from pathlib import Path
from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_wtf.csrf import CSRFProtect
from config import Config
from database.db import init_app, get_db
from modules.authentication.routes import auth_bp
from modules.owner.routes import owner_bp
from modules.attendance.routes import attendance_bp
from modules.tasks.routes import tasks_bp
from modules.inventory.routes import inventory_bp
from modules.projects.routes import projects_bp
from modules.expenses.routes import expenses_bp
from modules.salary.routes import salary_bp
from modules.invoices.routes import invoices_bp
from modules.reports.routes import reports_bp
from modules.employee.routes import employee_bp
from modules.settings.routes import settings_bp
from database.migrations import apply_migrations

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    CSRFProtect(app)
    init_app(app)
    with app.app_context():
        apply_migrations()

    for folder in ["employee_documents","purchase_bills","material_photos","project_documents","task_attachments"]:
        (Path(app.config["UPLOAD_FOLDER"]) / folder).mkdir(parents=True, exist_ok=True)

    for bp in [auth_bp, owner_bp, attendance_bp, tasks_bp, inventory_bp,
               projects_bp, expenses_bp, salary_bp, invoices_bp, reports_bp, employee_bp, settings_bp]:
        app.register_blueprint(bp)

    @app.context_processor
    def inject_user():
        permissions, divisions = {}, []
        if session.get("user_id"):
            db = get_db()
            divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
            permissions = {row["module_name"]: {"can_view": row["can_view"], "can_manage": row["can_manage"]} for row in db.execute("SELECT module_name,can_view,can_manage FROM role_permissions rp JOIN roles r ON r.id=rp.role_id WHERE r.name=?", (session.get("role"),)).fetchall()}
        theme_row = get_db().execute("SELECT setting_value FROM company_settings WHERE setting_key='ui_theme'").fetchone() if session.get("user_id") else None
        return {"current_user": session, "nav_permissions": permissions, "nav_divisions": divisions, "ui_theme": theme_row["setting_value"] if theme_row else "violet"}

    @app.before_request
    def enforce_module_access():
        """Apply configurable role visibility/access before individual route safeguards."""
        if not session.get("user_id"):
            return None
        module = {"owner": "dashboard", "employee": "employees", "attendance": "attendance",
                  "tasks": "tasks", "inventory": "inventory", "projects": "projects",
                  "expenses": "expenses", "salary": "salary", "invoices": "invoices",
                  "reports": "reports", "settings": "settings"}.get((request.endpoint or "").split(".")[0])
        if not module:
            return None
        permission = get_db().execute("""SELECT rp.can_view,rp.can_manage FROM role_permissions rp
            JOIN roles r ON r.id=rp.role_id WHERE r.name=? AND rp.module_name=?""", (session.get("role"), module)).fetchone()
        if not permission or not permission["can_view"]:
            from flask import abort
            abort(403)
        # Allow employees to submit progress/status updates on their assigned tasks
        if session.get("role") == "employee" and request.endpoint in ("tasks.update_progress", "tasks.update_status"):
            return None
        if request.method not in ("GET", "HEAD", "OPTIONS") and not permission["can_manage"]:
            from flask import abort
            abort(403)

    @app.post("/switch-workspace")
    def switch_workspace():
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        division_id = request.form.get("division_id", type=int)
        division = get_db().execute("SELECT id FROM business_divisions WHERE id=? AND active=1", (division_id,)).fetchone()
        if not division:
            flash("That workspace is unavailable.", "danger")
        elif session.get("role") != "owner" and session.get("division_id") not in (None, division_id):
            flash("Your account is limited to its assigned workspace.", "danger")
        else:
            session["active_division_id"] = division_id
        return redirect(request.referrer or url_for("owner.dashboard"))

    @app.route("/")
    def index():
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return redirect(url_for("owner.dashboard"))

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="You are not authorized to access this page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="Page not found."), 404

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
