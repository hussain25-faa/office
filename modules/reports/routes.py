from flask import Blueprint, render_template, request, session, abort, jsonify
from database.db import get_db
import json

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
def index():
    if not session.get("user_id"):
        abort(403)
    if session.get("role") not in ("owner", "manager", "accountant"):
        abort(403)

    db = get_db()
    active_division = session.get("active_division_id") or session.get("division_id")

    # Filters
    div_filter = request.args.get("division_id", type=int) or active_division
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    emp_filter = request.args.get("employee_id", type=int)
    project_filter = request.args.get("project_id", type=int)

    # Base WHERE builders
    def build_where(alias, date_col, div_col=None):
        conds = []
        p = []
        if div_filter:
            conds.append(f"{alias}.{div_col or 'division_id'}=?")
            p.append(div_filter)
        if start_date and date_col:
            conds.append(f"{alias}.{date_col} >= ?")
            p.append(start_date)
        if end_date and date_col:
            conds.append(f"{alias}.{date_col} <= ?")
            p.append(end_date)
        return (" WHERE " + " AND ".join(conds)) if conds else "", p

    # 1. Financial: Invoices
    inv_where, inv_p = build_where("i", "invoice_date")
    invoices = db.execute(f"""
        SELECT i.*, b.name AS division_name
        FROM invoices i
        JOIN business_divisions b ON b.id=i.division_id
        {inv_where}
        ORDER BY i.invoice_date DESC
    """, tuple(inv_p)).fetchall()

    total_invoiced = sum(row["total_amount"] for row in invoices)
    total_collected = sum(row["amount_paid"] for row in invoices)
    total_outstanding = round(total_invoiced - total_collected, 2)

    # 2. Financial: Expenses
    exp_where, exp_p = build_where("x", "expense_date")
    if project_filter:
        exp_where += (" AND " if exp_where else " WHERE ") + "x.project_id=?"
        exp_p.append(project_filter)

    expenses = db.execute(f"""
        SELECT x.*, b.name AS division_name, p.name AS project_name
        FROM expenses x
        JOIN business_divisions b ON b.id=x.division_id
        LEFT JOIN projects p ON p.id=x.project_id
        {exp_where}
        ORDER BY x.expense_date DESC
    """, tuple(exp_p)).fetchall()
    total_expenses = sum(row["amount"] for row in expenses)

    # Category breakdown for expenses
    category_summary = db.execute(f"""
        SELECT x.category, COUNT(*) AS count, SUM(x.amount) AS total
        FROM expenses x
        {exp_where}
        GROUP BY x.category
        ORDER BY total DESC
    """, tuple(exp_p)).fetchall()

    # 3. Tasks & Productivity
    task_conds = []
    task_p = []
    if div_filter:
        task_conds.append("t.division_id=?")
        task_p.append(div_filter)
    if emp_filter:
        task_conds.append("t.assigned_to=?")
        task_p.append(emp_filter)
    if project_filter:
        task_conds.append("t.project_id=?")
        task_p.append(project_filter)
    if start_date:
        task_conds.append("t.created_at >= ?")
        task_p.append(start_date)
    if end_date:
        task_conds.append("t.created_at <= ? || ' 23:59:59'")
        task_p.append(end_date)
    task_where = (" WHERE " + " AND ".join(task_conds)) if task_conds else ""

    tasks = db.execute(f"""
        SELECT t.*, e.full_name AS employee_name, e.employee_code,
               p.name AS project_name, b.name AS division_name
        FROM tasks t
        LEFT JOIN employees e ON e.id=t.assigned_to
        LEFT JOIN projects p ON p.id=t.project_id
        LEFT JOIN business_divisions b ON b.id=t.division_id
        {task_where}
        ORDER BY t.created_at DESC
    """, tuple(task_p)).fetchall()

    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t["status"] == "Completed")
    in_progress_tasks = sum(1 for t in tasks if t["status"] == "In Progress")
    pending_tasks = sum(1 for t in tasks if t["status"] == "Pending")
    total_est_hours = sum(t["estimated_hours"] or 0 for t in tasks)
    total_act_hours = sum(t["actual_hours"] or 0 for t in tasks)

    # Employee leaderboard
    employee_productivity = db.execute(f"""
        SELECT e.id, e.full_name, e.employee_code, b.name AS division_name,
               COUNT(t.id) AS total_assigned,
               SUM(CASE WHEN t.status='Completed' THEN 1 ELSE 0 END) AS completed_count,
               COALESCE(SUM(t.estimated_hours), 0) AS total_est_hours,
               COALESCE(SUM(t.actual_hours), 0) AS total_act_hours
        FROM employees e
        JOIN business_divisions b ON b.id=e.division_id
        LEFT JOIN tasks t ON t.assigned_to=e.id {("AND " + " AND ".join(task_conds[1:])) if len(task_conds) > 1 else ""}
        {("WHERE e.division_id=?" if div_filter else "")}
        GROUP BY e.id
        ORDER BY completed_count DESC, total_act_hours DESC
    """, (div_filter,) if div_filter else ()).fetchall()

    # 4. Attendance summary
    att_where, att_p = build_where("a", "attendance_date")
    if emp_filter:
        att_where += (" AND " if att_where else " WHERE ") + "a.employee_id=?"
        att_p.append(emp_filter)

    attendance_counts = db.execute(f"""
        SELECT a.status, COUNT(*) AS count
        FROM attendance a
        {att_where}
        GROUP BY a.status
    """, tuple(att_p)).fetchall()
    att_summary = {r["status"]: r["count"] for r in attendance_counts}
    total_attendance_records = sum(att_summary.values())

    # 5. Projects
    proj_conds = []
    proj_p = []
    if div_filter:
        proj_conds.append("p.division_id=?")
        proj_p.append(div_filter)
    proj_where = (" WHERE " + " AND ".join(proj_conds)) if proj_conds else ""
    projects_report = db.execute(f"""
        SELECT p.*, b.name AS division_name,
               (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id) AS task_count,
               (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id AND t.status='Completed') AS completed_task_count,
               (SELECT COALESCE(SUM(amount), 0) FROM expenses x WHERE x.project_id=p.id) AS actual_expenses
        FROM projects p
        JOIN business_divisions b ON b.id=p.division_id
        {proj_where}
        ORDER BY p.created_at DESC
    """, tuple(proj_p)).fetchall()

    # 6. Inventory valuation
    inv_conds = []
    inv_params = []
    if div_filter:
        inv_conds.append("m.division_id=?")
        inv_params.append(div_filter)
    inv_where_sql = (" WHERE " + " AND ".join(inv_conds)) if inv_conds else ""
    materials_report = db.execute(f"""
        SELECT m.*, b.name AS division_name,
               (m.current_stock <= m.reorder_level) AS is_low_stock
        FROM materials m
        JOIN business_divisions b ON b.id=m.division_id
        {inv_where_sql}
        ORDER BY m.current_stock ASC
    """, tuple(inv_params)).fetchall()

    low_stock_count = sum(1 for m in materials_report if m["is_low_stock"])

    # Net Profit
    net_profit = round(total_invoiced - total_expenses, 2)

    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    all_employees = db.execute("SELECT id, employee_code, full_name, division_id FROM employees WHERE active=1 ORDER BY full_name").fetchall()
    all_projects = db.execute("SELECT id, name, project_code, division_id FROM projects ORDER BY name").fetchall()

    # Chart data packages
    expense_chart_labels = [r["category"] for r in category_summary]
    expense_chart_values = [float(r["total"]) for r in category_summary]

    task_chart_labels = ["Completed", "In Progress", "Pending", "Under Review"]
    task_chart_values = [
        completed_tasks,
        in_progress_tasks,
        pending_tasks,
        sum(1 for t in tasks if t["status"] == "Under Review")
    ]

    return render_template("reports.html",
                           invoices=invoices, total_invoiced=total_invoiced,
                           total_collected=total_collected, total_outstanding=total_outstanding,
                           expenses=expenses, total_expenses=total_expenses,
                           category_summary=category_summary,
                           tasks=tasks, total_tasks=total_tasks, completed_tasks=completed_tasks,
                           in_progress_tasks=in_progress_tasks, pending_tasks=pending_tasks,
                           total_est_hours=total_est_hours, total_act_hours=total_act_hours,
                           employee_productivity=employee_productivity,
                           att_summary=att_summary, total_attendance_records=total_attendance_records,
                           projects_report=projects_report, materials_report=materials_report,
                           low_stock_count=low_stock_count, net_profit=net_profit,
                           divisions=divisions, all_employees=all_employees, all_projects=all_projects,
                           div_filter=div_filter, start_date=start_date, end_date=end_date,
                           emp_filter=emp_filter, project_filter=project_filter,
                           expense_chart_labels=json.dumps(expense_chart_labels),
                           expense_chart_values=json.dumps(expense_chart_values),
                           task_chart_labels=json.dumps(task_chart_labels),
                           task_chart_values=json.dumps(task_chart_values))
