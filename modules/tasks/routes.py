from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    active_division = session.get("active_division_id") or session.get("division_id")

    if request.method == "POST":
        if role not in ("owner", "manager"):
            abort(403)
        assigned_to = request.form.get("assigned_to", type=int) or None
        division_id = request.form.get("division_id", type=int)
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        instructions = request.form.get("instructions", "").strip()
        priority = request.form.get("priority", "Normal")
        start_date = request.form.get("start_date") or None
        due_date = request.form.get("due_date") or None
        estimated_hours = float(request.form.get("estimated_hours") or 0)
        project_id = request.form.get("project_id", type=int) or None
        initial_status = request.form.get("status") or ("In Progress" if assigned_to else "Pending")
        requires_approval = 1 if request.form.get("requires_approval") else 0

        if not title or not division_id:
            flash("Task title and workspace division are required.", "danger")
            return redirect(url_for("tasks.index"))

        try:
            db.execute("""INSERT INTO tasks(
                division_id, title, description, instructions, assigned_to, assigned_by,
                project_id, priority, status, start_date, due_date, estimated_hours,
                actual_hours, progress_percent, requires_approval
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
            (division_id, title, description or None, instructions or None, assigned_to,
             session["user_id"], project_id, priority, initial_status, start_date, due_date,
             estimated_hours, requires_approval))

            task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Send straight notification to the employee's user account
            if assigned_to:
                emp_user = db.execute("SELECT id FROM users WHERE employee_id=?", (assigned_to,)).fetchone()
                if emp_user:
                    db.execute("""INSERT INTO notifications(user_id, title, message)
                                  VALUES(?, 'New Task Assigned', ?)""",
                               (emp_user["id"], f"You have been assigned task: '{title}'. Target time: {estimated_hours}h."))

            db.commit()
            log_activity("CREATE", "task", task_id, f"Title: {title}")
            db.commit()
            flash(f"Task '{title}' assigned straight to employee successfully!", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Task could not be saved: {exc}", "danger")
        return redirect(url_for("tasks.index"))

    # Filtering parameters
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    employee_filter = request.args.get("employee_id", type=int)

    base_query = """
        SELECT t.*, e.full_name, e.employee_code, p.name AS project_name,
               b.name AS division_name, u.username AS assigner_name
        FROM tasks t
        LEFT JOIN employees e ON e.id=t.assigned_to
        LEFT JOIN projects p ON p.id=t.project_id
        LEFT JOIN business_divisions b ON b.id=t.division_id
        LEFT JOIN users u ON u.id=t.assigned_by
    """
    conditions = []
    params = []

    if role == "employee":
        emp_id = session.get("employee_id")
        if emp_id:
            conditions.append("t.assigned_to=?")
            params.append(emp_id)
        else:
            # Fallback if unlinked: match by user email
            user_row = db.execute("SELECT email, username FROM users WHERE id=?", (session["user_id"],)).fetchone()
            emp_row = db.execute("SELECT id FROM employees WHERE email=? OR email=?",
                                 (user_row["email"], user_row["username"])).fetchone() if user_row else None
            if emp_row:
                session["employee_id"] = emp_row["id"]
                conditions.append("t.assigned_to=?")
                params.append(emp_row["id"])
            else:
                conditions.append("t.assigned_to=-1")
    else:
        if active_division:
            conditions.append("t.division_id=?")
            params.append(active_division)
        if employee_filter:
            conditions.append("t.assigned_to=?")
            params.append(employee_filter)

    if status_filter:
        conditions.append("t.status=?")
        params.append(status_filter)
    if priority_filter:
        conditions.append("t.priority=?")
        params.append(priority_filter)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order_clause = """
        ORDER BY 
        CASE t.status 
            WHEN 'In Progress' THEN 1 
            WHEN 'Pending' THEN 2 
            WHEN 'Under Review' THEN 3 
            WHEN 'Completed' THEN 4 
            ELSE 5 
        END,
        COALESCE(t.due_date, '9999-12-31') ASC,
        t.created_at DESC
    """

    rows = db.execute(f"{base_query} {where_clause} {order_clause}", tuple(params)).fetchall()

    # Employee metrics calculation
    task_counts = {
        "total": len(rows),
        "in_progress": sum(1 for r in rows if r["status"] == "In Progress"),
        "pending": sum(1 for r in rows if r["status"] == "Pending"),
        "completed": sum(1 for r in rows if r["status"] == "Completed"),
        "review": sum(1 for r in rows if r["status"] == "Under Review")
    }

    employees = db.execute("SELECT id, employee_code, full_name, designation, division_id FROM employees WHERE active=1" +
                           (" AND division_id=?" if active_division else "") + " ORDER BY full_name",
                           (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    projects = db.execute("SELECT id, name, division_id FROM projects" +
                          (" WHERE division_id=?" if active_division else "") + " ORDER BY name",
                          (active_division,) if active_division else ()).fetchall()

    return render_template("tasks.html", rows=rows, employees=employees, divisions=divisions,
                           projects=projects, task_counts=task_counts,
                           can_create=role in ("owner", "manager"), role=role,
                           status_filter=status_filter, priority_filter=priority_filter,
                           employee_filter=employee_filter)


@tasks_bp.post("/<int:task_id>/edit")
def edit_task(task_id):
    if not session.get("user_id"):
        abort(403)
    if session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.index"))

    title = request.form.get("title", "").strip()
    division_id = request.form.get("division_id", type=int)
    assigned_to = request.form.get("assigned_to", type=int) or None
    project_id = request.form.get("project_id", type=int) or None

    if not title or not division_id:
        flash("Title and workspace are required.", "danger")
        return redirect(url_for("tasks.index"))

    try:
        db.execute("""UPDATE tasks SET
            title=?, division_id=?, description=?, instructions=?, assigned_to=?,
            project_id=?, priority=?, status=?, start_date=?, due_date=?,
            estimated_hours=?, actual_hours=?, progress_percent=?, requires_approval=?
            WHERE id=?""",
            (title, division_id, request.form.get("description") or None,
             request.form.get("instructions") or None, assigned_to, project_id,
             request.form.get("priority", "Normal"), request.form.get("status", "Pending"),
             request.form.get("start_date") or None, request.form.get("due_date") or None,
             float(request.form.get("estimated_hours") or 0),
             float(request.form.get("actual_hours") or 0),
             int(request.form.get("progress_percent") or 0),
             1 if request.form.get("requires_approval") else 0, task_id))
        db.commit()
        log_activity("UPDATE", "task", task_id, f"Edited {title}")
        db.commit()
        flash("Task details updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update task: {exc}", "danger")
    return redirect(url_for("tasks.index"))


@tasks_bp.post("/<int:task_id>/update-progress")
def update_progress(task_id):
    if not session.get("user_id"):
        abort(403)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.index"))

    # Employees can only update their own tasks
    if session.get("role") == "employee" and task["assigned_to"] != session.get("employee_id"):
        abort(403)

    status = request.form.get("status", task["status"])
    actual_hours = float(request.form.get("actual_hours") or task["actual_hours"] or 0)
    progress_percent = int(request.form.get("progress_percent") or task["progress_percent"] or 0)
    employee_notes = request.form.get("employee_notes", "").strip() or task["employee_notes"]

    if status == "Completed" and task["requires_approval"] and session.get("role") == "employee":
        status = "Under Review"
        flash("Task submitted for manager review and approval.", "info")

    completed_at = "CURRENT_TIMESTAMP" if status == "Completed" else "completed_at"

    try:
        db.execute(f"""UPDATE tasks SET
            status=?, actual_hours=?, progress_percent=?, employee_notes=?,
            completed_at=CASE WHEN ?='Completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id=?""",
            (status, actual_hours, min(100, max(0, progress_percent)), employee_notes, status, task_id))
        db.commit()
        log_activity("PROGRESS", "task", task_id, f"status={status}, hours={actual_hours}, progress={progress_percent}%")
        db.commit()
        flash(f"Task work progress updated ({progress_percent}% done, {actual_hours}h spent).", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update progress: {exc}", "danger")
    return redirect(url_for("tasks.index"))


@tasks_bp.post("/<int:task_id>/status")
def update_status(task_id):
    if not session.get("user_id"):
        abort(403)
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        abort(404)
    if session.get("role") == "employee" and row["assigned_to"] != session.get("employee_id"):
        abort(403)
    status = request.form.get("status")
    if status not in ("Pending", "In Progress", "Completed", "Under Review", "Rejected"):
        abort(400)

    if status == "Completed" and row["requires_approval"] and session.get("role") == "employee":
        status = "Under Review"
        flash("Task submitted for manager review.", "info")

    progress = 100 if status == "Completed" else (row["progress_percent"] or 0)
    db.execute("""UPDATE tasks SET status=?, progress_percent=?,
                  completed_at=CASE WHEN ?='Completed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                  WHERE id=?""", (status, progress, status, task_id))
    db.commit()
    log_activity("UPDATE", "task", task_id, f"status={status}")
    db.commit()
    flash(f"Task status changed to '{status}'.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.post("/<int:task_id>/delete")
def delete_task(task_id):
    if not session.get("user_id"):
        abort(403)
    if session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.index"))

    try:
        db.execute("DELETE FROM task_attachments WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        db.commit()
        log_activity("DELETE", "task", task_id, f"Title: {task['title']}")
        db.commit()
        flash(f"Task '{task['title']}' was deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete task: {exc}", "danger")
    return redirect(url_for("tasks.index"))
