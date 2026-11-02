from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ("owner", "manager"):
            abort(403)
        code = request.form["project_code"].strip()
        name = request.form["name"].strip()
        div_id = int(request.form["division_id"])

        if db.execute("SELECT 1 FROM projects WHERE project_code=?", (code,)).fetchone():
            flash(f"Project code '{code}' already exists.", "danger")
            return redirect(url_for("projects.index"))

        try:
            db.execute("""INSERT INTO projects(division_id,project_code,name,site_address,start_date,expected_end_date,budget,status,description)
                          VALUES(?,?,?,?,?,?,?,?,?)""",
                       (div_id, code, name, request.form.get("site_address"),
                        request.form.get("start_date") or None, request.form.get("expected_end_date") or None,
                        float(request.form.get("budget") or 0), request.form.get("status", "Planning"),
                        request.form.get("description")))
            proj_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()
            log_activity("CREATE", "project", proj_id, f"Project {name}")
            db.commit()
            flash(f"Project '{name}' created successfully.", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Project could not be created: {exc}", "danger")
        return redirect(url_for("projects.index"))

    active_division = session.get("active_division_id") or session.get("division_id")
    where = (" WHERE p.division_id=?" if active_division else "")
    rows = db.execute(f"""SELECT p.*, b.name division_name,
                         (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id) AS total_tasks,
                         (SELECT COALESCE(SUM(amount), 0) FROM expenses x WHERE x.project_id=p.id) AS total_expenses
                         FROM projects p
                         JOIN business_divisions b ON b.id=p.division_id
                         {where} ORDER BY p.created_at DESC""",
                      (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    return render_template("projects.html", rows=rows, divisions=divisions, can_edit=role in ("owner", "manager"))


@projects_bp.post("/<int:project_id>/edit")
def edit(project_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    proj = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not proj:
        flash("Project not found.", "danger")
        return redirect(url_for("projects.index"))

    code = request.form.get("project_code", "").strip()
    name = request.form.get("name", "").strip()
    div_id = request.form.get("division_id", type=int)

    if not code or not name or not div_id:
        flash("Code, name, and workspace are required.", "danger")
        return redirect(url_for("projects.index"))

    # Check unique project code
    existing = db.execute("SELECT id FROM projects WHERE project_code=? AND id<>?", (code, project_id)).fetchone()
    if existing:
        flash(f"Project code '{code}' is already used by another project.", "danger")
        return redirect(url_for("projects.index"))

    try:
        db.execute("""UPDATE projects SET
            division_id=?, project_code=?, name=?, site_address=?, start_date=?,
            expected_end_date=?, budget=?, status=?, description=?
            WHERE id=?""",
            (div_id, code, name, request.form.get("site_address") or None,
             request.form.get("start_date") or None, request.form.get("expected_end_date") or None,
             float(request.form.get("budget") or 0), request.form.get("status", "Planning"),
             request.form.get("description") or None, project_id))
        db.commit()
        log_activity("UPDATE", "project", project_id, f"Edited {name}")
        db.commit()
        flash(f"Project '{name}' updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update project: {exc}", "danger")
    return redirect(url_for("projects.index"))


@projects_bp.post("/<int:project_id>/delete")
def delete(project_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    proj = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not proj:
        flash("Project not found.", "danger")
        return redirect(url_for("projects.index"))

    try:
        # Check if tasks or expenses linked
        expenses = db.execute("SELECT COUNT(*) FROM expenses WHERE project_id=?", (project_id,)).fetchone()[0]
        tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (project_id,)).fetchone()[0]

        if expenses > 0 or tasks > 0:
            db.execute("UPDATE projects SET status='Cancelled' WHERE id=?", (project_id,))
            db.commit()
            log_activity("STATUS", "project", project_id, "Set to Cancelled")
            db.commit()
            flash(f"Project '{proj['name']}' has linked tasks/expenses, so its status was marked as 'Cancelled'.", "warning")
        else:
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
            db.commit()
            log_activity("DELETE", "project", project_id, f"Deleted {proj['name']}")
            db.commit()
            flash(f"Project '{proj['name']}' was deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete project: {exc}", "danger")
    return redirect(url_for("projects.index"))
