from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")
ALLOWED = {"owner", "manager"}


@attendance_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ALLOWED:
            abort(403)
        emp = int(request.form["employee_id"])
        date = request.form["attendance_date"]
        division = int(request.form["division_id"])
        status = request.form["status"]
        check_in = request.form.get("check_in") or None
        check_out = request.form.get("check_out") or None
        overtime = float(request.form.get("overtime_hours") or 0)
        notes = request.form.get("notes") or None
        try:
            db.execute("""INSERT INTO attendance(employee_id,division_id,attendance_date,status,check_in,check_out,overtime_hours,notes,created_by)
                          VALUES(?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(employee_id, attendance_date) DO UPDATE SET
                          division_id=excluded.division_id, status=excluded.status, check_in=excluded.check_in,
                          check_out=excluded.check_out, overtime_hours=excluded.overtime_hours, notes=excluded.notes""",
                       (emp, division, date, status, check_in, check_out, overtime, notes, session["user_id"]))
            db.commit()
            log_activity("CREATE", "attendance", None, f"{emp}:{date}")
            db.commit()
            flash("Attendance record saved.", "success")
        except Exception as e:
            db.rollback()
            flash(f"Could not save attendance: {e}", "danger")
        return redirect(url_for("attendance.index"))

    if role == "employee":
        rows = db.execute("""SELECT a.*, e.full_name, e.employee_code, b.name division_name
                             FROM attendance a
                             JOIN employees e ON e.id=a.employee_id
                             JOIN business_divisions b ON b.id=a.division_id
                             WHERE a.employee_id=? ORDER BY attendance_date DESC""",
                          (session.get("employee_id"),)).fetchall()
    else:
        active_division = session.get("active_division_id") or session.get("division_id")
        rows = db.execute("""SELECT a.*, e.full_name, e.employee_code, b.name division_name
                             FROM attendance a
                             JOIN employees e ON e.id=a.employee_id
                             JOIN business_divisions b ON b.id=a.division_id""" +
                          (" WHERE a.division_id=?" if active_division else "") +
                          " ORDER BY attendance_date DESC, a.id DESC LIMIT 200",
                          (active_division,) if active_division else ()).fetchall()

    active_division = session.get("active_division_id") or session.get("division_id")
    employees = db.execute("SELECT id, employee_code, full_name, division_id FROM employees WHERE active=1" +
                           (" AND division_id=?" if active_division else "") + " ORDER BY full_name",
                           (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions ORDER BY name").fetchall()
    return render_template("attendance.html", rows=rows, employees=employees, divisions=divisions, can_edit=role in ALLOWED)


@attendance_bp.post("/<int:attendance_id>/edit")
def edit_attendance(attendance_id):
    if not session.get("user_id") or session.get("role") not in ALLOWED:
        abort(403)
    db = get_db()
    status = request.form.get("status")
    check_in = request.form.get("check_in") or None
    check_out = request.form.get("check_out") or None
    overtime = float(request.form.get("overtime_hours") or 0)
    notes = request.form.get("notes") or None

    try:
        db.execute("""UPDATE attendance SET status=?, check_in=?, check_out=?, overtime_hours=?, notes=?
                      WHERE id=?""", (status, check_in, check_out, overtime, notes, attendance_id))
        db.commit()
        log_activity("UPDATE", "attendance", attendance_id, f"status={status}")
        db.commit()
        flash("Attendance updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update attendance: {exc}", "danger")
    return redirect(url_for("attendance.index"))


@attendance_bp.post("/<int:attendance_id>/delete")
def delete_attendance(attendance_id):
    if not session.get("user_id") or session.get("role") not in ALLOWED:
        abort(403)
    db = get_db()
    try:
        db.execute("DELETE FROM attendance WHERE id=?", (attendance_id,))
        db.commit()
        log_activity("DELETE", "attendance", attendance_id)
        db.commit()
        flash("Attendance entry removed.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete attendance: {exc}", "danger")
    return redirect(url_for("attendance.index"))
