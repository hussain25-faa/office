import re
from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash, jsonify
from werkzeug.security import generate_password_hash
from database.db import get_db, log_activity

employee_bp = Blueprint("employee", __name__, url_prefix="/employees")


def _allowed():
    return session.get("role") in ("owner", "manager")


def _generate_unique_username(db, full_name, employee_code):
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', full_name).strip().lower()
    parts = cleaned.split()
    base = ".".join(parts) if parts else f"emp{employee_code.lower()}"
    base = re.sub(r'\.+', '.', base).strip('.')
    if not base:
        base = f"emp_{employee_code.lower()}"
    username = base
    counter = 1
    while db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        username = f"{base}{counter}"
        counter += 1
    return username


@employee_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    active_division = session.get("active_division_id") or session.get("division_id")

    if request.method == "POST":
        if not _allowed():
            abort(403)
        required = ("employee_code", "full_name", "division_id")
        if not all(request.form.get(field, "").strip() for field in required):
            flash("Employee code, full name and workspace division are required.", "danger")
            return redirect(url_for("employee.index"))

        emp_code = request.form["employee_code"].strip()
        full_name = request.form["full_name"].strip()
        div_id = int(request.form["division_id"])
        email = request.form.get("email", "").strip() or None
        phone = request.form.get("phone", "").strip() or None

        # Check for duplicate employee code
        if db.execute("SELECT 1 FROM employees WHERE employee_code=?", (emp_code,)).fetchone():
            flash(f"Employee code '{emp_code}' is already registered.", "danger")
            return redirect(url_for("employee.index"))

        try:
            db.execute("""INSERT INTO employees
                (employee_code,division_id,full_name,phone,email,address,designation,department,employee_type,salary_type,
                 monthly_salary,daily_wage,joining_date,emergency_contact,aadhaar_number,date_of_birth,gender,bank_name,bank_account,ifsc_code)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (emp_code, div_id, full_name, phone, email,
                 request.form.get("address"), request.form.get("designation"), request.form.get("department"),
                 request.form.get("employee_type", "Permanent"), request.form.get("salary_type", "Monthly"),
                 float(request.form.get("monthly_salary") or 0), float(request.form.get("daily_wage") or 0),
                 request.form.get("joining_date"), request.form.get("emergency_contact"),
                 request.form.get("aadhaar_number"), request.form.get("date_of_birth"),
                 request.form.get("gender"), request.form.get("bank_name"), request.form.get("bank_account"),
                 request.form.get("ifsc_code")))
            employee_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Automatic user account creation in their name
            auto_create_user = request.form.get("auto_create_user", "1") == "1"
            created_login_info = ""
            if auto_create_user:
                desired_user = request.form.get("login_username", "").strip()
                if desired_user:
                    username = re.sub(r'[^a-zA-Z0-9._]', '', desired_user.lower())
                    if db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                        username = _generate_unique_username(db, desired_user, emp_code)
                else:
                    username = _generate_unique_username(db, full_name, emp_code)

                raw_pwd = request.form.get("login_password", "").strip() or f"{emp_code}@123"

                emp_role = db.execute("SELECT id FROM roles WHERE name='employee'").fetchone()
                role_id = emp_role["id"] if emp_role else 4

                db.execute("""INSERT INTO users(username, email, password_hash, role_id, employee_id, division_id, active)
                              VALUES(?,?,?,?,?,?,1)""",
                           (username, email, generate_password_hash(raw_pwd), role_id, employee_id, div_id))
                created_login_info = f" Login account created: Username: <strong>{username}</strong> | Password: <strong>{raw_pwd}</strong>."

            db.commit()
            log_activity("CREATE", "employee", employee_id, f"Code: {emp_code}")
            db.commit()
            flash(f"Employee '{full_name}' added successfully!{created_login_info}", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Employee could not be saved: {exc}", "danger")
        return redirect(url_for("employee.index"))

    where = []
    params = []
    if session.get("role") != "owner" or active_division:
        if active_division:
            where.append("e.division_id=?")
            params.append(active_division)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    query = f"""
        SELECT e.*, b.name AS division_name, u.id AS user_id, u.username AS user_username, 
               u.active AS user_active, r.name AS user_role
        FROM employees e
        JOIN business_divisions b ON b.id=e.division_id
        LEFT JOIN users u ON u.employee_id=e.id
        LEFT JOIN roles r ON r.id=u.role_id
        {where_sql}
        ORDER BY e.created_at DESC
    """
    employees = db.execute(query, tuple(params)).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    roles = db.execute("SELECT * FROM roles ORDER BY id").fetchall()
    return render_template("employees.html", employees=employees, divisions=divisions, roles=roles,
                           can_manage=_allowed(), active_division=active_division)


@employee_bp.post("/<int:employee_id>/edit")
def edit(employee_id):
    if not session.get("user_id") or not _allowed():
        abort(403)
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("employee.index"))

    emp_code = request.form.get("employee_code", "").strip()
    full_name = request.form.get("full_name", "").strip()
    div_id = request.form.get("division_id", type=int)

    if not emp_code or not full_name or not div_id:
        flash("Code, name, and workspace division are required.", "danger")
        return redirect(url_for("employee.index"))

    # Check unique code if changed
    existing = db.execute("SELECT id FROM employees WHERE employee_code=? AND id<>?", (emp_code, employee_id)).fetchone()
    if existing:
        flash(f"Employee code '{emp_code}' is already used by another employee.", "danger")
        return redirect(url_for("employee.index"))

    try:
        db.execute("""UPDATE employees SET
            employee_code=?, division_id=?, full_name=?, phone=?, email=?, address=?,
            designation=?, department=?, employee_type=?, salary_type=?, monthly_salary=?,
            daily_wage=?, joining_date=?, emergency_contact=?, aadhaar_number=?,
            date_of_birth=?, gender=?, bank_name=?, bank_account=?, ifsc_code=?, active=?
            WHERE id=?""",
            (emp_code, div_id, full_name, request.form.get("phone") or None,
             request.form.get("email") or None, request.form.get("address") or None,
             request.form.get("designation") or None, request.form.get("department") or None,
             request.form.get("employee_type", "Permanent"), request.form.get("salary_type", "Monthly"),
             float(request.form.get("monthly_salary") or 0), float(request.form.get("daily_wage") or 0),
             request.form.get("joining_date") or None, request.form.get("emergency_contact") or None,
             request.form.get("aadhaar_number") or None, request.form.get("date_of_birth") or None,
             request.form.get("gender") or None, request.form.get("bank_name") or None,
             request.form.get("bank_account") or None, request.form.get("ifsc_code") or None,
             1 if request.form.get("active") in ("1", "on") else 0, employee_id))

        # Also update linked user's division and active status
        db.execute("UPDATE users SET division_id=?, active=? WHERE employee_id=?",
                   (div_id, 1 if request.form.get("active") in ("1", "on") else 0, employee_id))

        db.commit()
        log_activity("UPDATE", "employee", employee_id, f"Updated {full_name}")
        db.commit()
        flash(f"Employee '{full_name}' updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update employee: {exc}", "danger")
    return redirect(url_for("employee.index"))


@employee_bp.post("/<int:employee_id>/delete")
def delete(employee_id):
    if not session.get("user_id") or not _allowed():
        abort(403)
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("employee.index"))

    try:
        # Check references in tasks or attendance
        tasks_count = db.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (employee_id,)).fetchone()[0]
        attendance_count = db.execute("SELECT COUNT(*) FROM attendance WHERE employee_id=?", (employee_id,)).fetchone()[0]

        if tasks_count > 0 or attendance_count > 0:
            # Soft delete to preserve integrity
            db.execute("UPDATE employees SET active=0 WHERE id=?", (employee_id,))
            db.execute("UPDATE users SET active=0 WHERE employee_id=?", (employee_id,))
            db.commit()
            log_activity("DEACTIVATE", "employee", employee_id)
            db.commit()
            flash(f"Employee '{emp['full_name']}' has linked work records and was set to Inactive (login disabled).", "warning")
        else:
            db.execute("DELETE FROM users WHERE employee_id=?", (employee_id,))
            db.execute("DELETE FROM employees WHERE id=?", (employee_id,))
            db.commit()
            log_activity("DELETE", "employee", employee_id)
            db.commit()
            flash(f"Employee '{emp['full_name']}' and associated login account were deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete employee: {exc}", "danger")
    return redirect(url_for("employee.index"))


@employee_bp.post("/<int:employee_id>/create-account")
def create_account(employee_id):
    if not session.get("user_id") or not _allowed():
        abort(403)
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("employee.index"))

    existing_user = db.execute("SELECT * FROM users WHERE employee_id=?", (employee_id,)).fetchone()
    if existing_user:
        flash(f"Employee already has user account '{existing_user['username']}'.", "info")
        return redirect(url_for("employee.index"))

    desired_username = request.form.get("username", "").strip() or _generate_unique_username(db, emp["full_name"], emp["employee_code"])
    raw_password = request.form.get("password", "").strip() or f"{emp['employee_code']}@123"
    role_id = request.form.get("role_id", type=int)
    if not role_id:
        r = db.execute("SELECT id FROM roles WHERE name='employee'").fetchone()
        role_id = r["id"] if r else 4

    try:
        db.execute("""INSERT INTO users(username, email, password_hash, role_id, employee_id, division_id, active)
                      VALUES(?,?,?,?,?,?,1)""",
                   (desired_username, emp["email"], generate_password_hash(raw_password), role_id, employee_id, emp["division_id"]))
        db.commit()
        log_activity("CREATE", "user", None, f"Created account for employee {employee_id}")
        db.commit()
        flash(f"Login account created! Username: <strong>{desired_username}</strong> | Password: <strong>{raw_password}</strong>", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not create account: {exc}", "danger")
    return redirect(url_for("employee.index"))
