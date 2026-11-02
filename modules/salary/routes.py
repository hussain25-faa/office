from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

salary_bp = Blueprint("salary", __name__, url_prefix="/salary")


@salary_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ("owner", "accountant"):
            abort(403)
        emp = int(request.form["employee_id"])
        amount = float(request.form["amount"])
        if amount <= 0:
            abort(400)
        try:
            db.execute("""INSERT INTO salary_advances(employee_id,division_id,amount,payment_date,note,created_by)
                          SELECT id,division_id,?,?,?,? FROM employees WHERE id=?""",
                       (amount, request.form["payment_date"], request.form.get("note"), session["user_id"], emp))
            db.commit()
            log_activity("ADVANCE", "salary_advance", db.execute("SELECT last_insert_rowid()").fetchone()[0], f"₹{amount}")
            db.commit()
            flash(f"Salary advance of ₹{amount:,.2f} recorded.", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Could not record advance: {exc}", "danger")
        return redirect(url_for("salary.index"))

    if role == "employee":
        rows = db.execute("SELECT * FROM salary_payments WHERE employee_id=? ORDER BY payment_date DESC",
                          (session.get("employee_id"),)).fetchall()
        advances = db.execute("SELECT * FROM salary_advances WHERE employee_id=? ORDER BY payment_date DESC",
                              (session.get("employee_id"),)).fetchall()
    else:
        active_division = session.get("active_division_id") or session.get("division_id")
        rows = db.execute("""SELECT s.*, e.full_name, e.employee_code, b.name division_name
                             FROM salary_payments s
                             JOIN employees e ON e.id=s.employee_id
                             JOIN business_divisions b ON b.id=s.division_id""" +
                          (" WHERE s.division_id=?" if active_division else "") +
                          " ORDER BY payment_date DESC, s.id DESC",
                          (active_division,) if active_division else ()).fetchall()
        advances = db.execute("""SELECT a.*, e.full_name, e.employee_code, b.name division_name
                                 FROM salary_advances a
                                 JOIN employees e ON e.id=a.employee_id
                                 JOIN business_divisions b ON b.id=a.division_id""" +
                              (" WHERE a.division_id=?" if active_division else "") +
                              " ORDER BY payment_date DESC, a.id DESC",
                              (active_division,) if active_division else ()).fetchall()

    active_division = session.get("active_division_id") or session.get("division_id")
    employees = db.execute("SELECT id, employee_code, full_name, monthly_salary, daily_wage, division_id FROM employees WHERE active=1" +
                           (" AND division_id=?" if active_division else "") + " ORDER BY full_name",
                           (active_division,) if active_division else ()).fetchall()
    return render_template("salary.html", rows=rows, advances=advances, employees=employees,
                           can_edit=role in ("owner", "accountant"))


@salary_bp.post("/pay")
def record_payroll():
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    emp_id = request.form.get("employee_id", type=int)
    period = request.form.get("period_month")
    gross = float(request.form.get("gross_amount") or 0)
    deductions = float(request.form.get("deductions") or 0)
    advance_deducted = float(request.form.get("advance_deducted") or 0)
    overtime_amount = float(request.form.get("overtime_amount") or 0)
    net = round(gross + overtime_amount - deductions - advance_deducted, 2)
    pay_date = request.form.get("payment_date")
    method = request.form.get("payment_method", "Bank Transfer")

    try:
        emp = db.execute("SELECT division_id, full_name FROM employees WHERE id=?", (emp_id,)).fetchone()
        db.execute("""INSERT INTO salary_payments(employee_id,division_id,period_month,gross_amount,deductions,
                      overtime_amount,advance_deducted,net_amount,payment_date,payment_method,created_by)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                   (emp_id, emp["division_id"], period, gross, deductions, overtime_amount,
                    advance_deducted, net, pay_date, method, session["user_id"]))
        db.commit()
        log_activity("SALARY", "salary_payment", db.execute("SELECT last_insert_rowid()").fetchone()[0], f"Paid {emp['full_name']} ₹{net}")
        db.commit()
        flash(f"Payroll payment of ₹{net:,.2f} recorded for {emp['full_name']}.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not record salary payment: {exc}", "danger")
    return redirect(url_for("salary.index"))


@salary_bp.post("/advance/<int:advance_id>/delete")
def delete_advance(advance_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    try:
        db.execute("DELETE FROM salary_advances WHERE id=?", (advance_id,))
        db.commit()
        log_activity("DELETE", "salary_advance", advance_id)
        db.commit()
        flash("Advance record removed.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete advance: {exc}", "danger")
    return redirect(url_for("salary.index"))


@salary_bp.post("/payment/<int:payment_id>/delete")
def delete_payment(payment_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    try:
        db.execute("DELETE FROM salary_payments WHERE id=?", (payment_id,))
        db.commit()
        log_activity("DELETE", "salary_payment", payment_id)
        db.commit()
        flash("Salary payment record removed.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete payment: {exc}", "danger")
    return redirect(url_for("salary.index"))
