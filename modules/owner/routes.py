from flask import Blueprint, render_template, session, abort, redirect, url_for
from database.db import get_db
import json
from datetime import datetime, timedelta

owner_bp = Blueprint("owner", __name__)


@owner_bp.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    role = session.get("role")
    if role not in ("owner", "manager", "accountant", "employee"):
        abort(403)
    db = get_db()
    division_id = session.get("active_division_id") or session.get("division_id")
    params = () if not division_id else (division_id,)
    where = "" if not params else " WHERE division_id=?"

    stats = {
        "employees": db.execute("SELECT COUNT(*) FROM employees WHERE active=1" + (" AND division_id=?" if division_id else ""), params).fetchone()[0],
        "projects": db.execute("SELECT COUNT(*) FROM projects" + where, params).fetchone()[0],
        "tasks": db.execute("SELECT COUNT(*) FROM tasks" + where, params).fetchone()[0],
        "expenses": db.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses" + where, params).fetchone()[0],
        "materials": db.execute("SELECT COUNT(*) FROM materials" + where, params).fetchone()[0],
        "invoices": db.execute("SELECT COALESCE(SUM(total_amount), 0) FROM invoices" + where, params).fetchone()[0],
        "revenue_collected": db.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM invoices" + where, params).fetchone()[0],
    }

    # 1. Task Status Breakdown for Doughnut Chart
    task_status_rows = db.execute("""
        SELECT status, COUNT(*) as count 
        FROM tasks""" + where + """ GROUP BY status
    """, params).fetchall()
    task_status_map = {r["status"]: r["count"] for r in task_status_rows}
    task_chart_labels = ["In Progress", "Pending", "Completed", "Under Review"]
    task_chart_values = [
        task_status_map.get("In Progress", 0),
        task_status_map.get("Pending", 0),
        task_status_map.get("Completed", 0),
        task_status_map.get("Under Review", 0)
    ]

    # 2. Monthly Revenue vs Expense (Last 6 Months)
    now = datetime.now()
    month_labels = []
    revenue_series = []
    expense_series = []

    for i in range(5, -1, -1):
        # Calculate year and month
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_str = f"{y:04d}-{m:02d}"
        month_label = datetime(y, m, 1).strftime("%b %Y")
        month_labels.append(month_label)

        div_cond_inv = " AND division_id=?" if division_id else ""
        div_cond_exp = " AND division_id=?" if division_id else ""

        inv_sum = db.execute(f"SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE strftime('%Y-%m', invoice_date) = ?{div_cond_inv}",
                             (month_str, division_id) if division_id else (month_str,)).fetchone()[0]
        exp_sum = db.execute(f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE strftime('%Y-%m', expense_date) = ?{div_cond_exp}",
                             (month_str, division_id) if division_id else (month_str,)).fetchone()[0]

        revenue_series.append(float(inv_sum))
        expense_series.append(float(exp_sum))

    # 3. Live Active Tasks with real-time employee progress
    live_tasks_query = """
        SELECT t.*, e.full_name AS employee_name, p.name AS project_name, b.name AS division_name
        FROM tasks t
        LEFT JOIN employees e ON e.id=t.assigned_to
        LEFT JOIN projects p ON p.id=t.project_id
        LEFT JOIN business_divisions b ON b.id=t.division_id
    """
    if role == "employee":
        emp_id = session.get("employee_id")
        live_tasks = db.execute(live_tasks_query + " WHERE t.assigned_to=? ORDER BY CASE t.status WHEN 'In Progress' THEN 1 WHEN 'Pending' THEN 2 ELSE 3 END, t.due_date ASC LIMIT 6",
                                (emp_id,)).fetchall() if emp_id else []
    else:
        live_tasks = db.execute(live_tasks_query + (" WHERE t.division_id=?" if division_id else "") +
                                " ORDER BY CASE t.status WHEN 'In Progress' THEN 1 WHEN 'Pending' THEN 2 WHEN 'Under Review' THEN 3 ELSE 4 END, t.due_date ASC LIMIT 6",
                                params).fetchall()

    # 4. Recent Activity Logs
    recent_activities = db.execute("""
        SELECT a.*, u.username 
        FROM activity_logs a 
        LEFT JOIN users u ON u.id=a.user_id 
        ORDER BY a.created_at DESC LIMIT 8
    """).fetchall()

    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1").fetchall()
    active_division = next((d for d in divisions if d["id"] == division_id), None)

    return render_template("dashboard.html",
                           stats=stats,
                           divisions=divisions,
                           active_division=active_division,
                           live_tasks=live_tasks,
                           recent_activities=recent_activities,
                           task_chart_labels=json.dumps(task_chart_labels),
                           task_chart_values=json.dumps(task_chart_values),
                           month_labels=json.dumps(month_labels),
                           revenue_series=json.dumps(revenue_series),
                           expense_series=json.dumps(expense_series))
