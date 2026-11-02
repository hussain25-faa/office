from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@expenses_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ("owner", "manager", "accountant"):
            abort(403)
        amount = float(request.form.get("amount") or 0)
        category = request.form.get("category", "").strip()
        expense_date = request.form.get("expense_date")
        div_id = int(request.form["division_id"])

        if amount <= 0 or not category or not expense_date:
            flash("Category, positive amount, and date are required.", "danger")
            return redirect(url_for("expenses.index"))

        try:
            db.execute("""INSERT INTO expenses(division_id,project_id,category,amount,expense_date,description,payment_method,created_by)
                          VALUES(?,?,?,?,?,?,?,?)""",
                       (div_id, request.form.get("project_id") or None, category, amount,
                        expense_date, request.form.get("description"), request.form.get("payment_method", "Cash"), session["user_id"]))
            exp_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()
            log_activity("CREATE", "expense", exp_id, f"₹{amount} for {category}")
            db.commit()
            flash(f"Expense of ₹{amount:,.2f} recorded.", "success")
        except Exception as exc:
            db.rollback()
            flash(f"Could not record expense: {exc}", "danger")
        return redirect(url_for("expenses.index"))

    active_division = session.get("active_division_id") or session.get("division_id")
    rows = db.execute("SELECT x.*, b.name division_name, p.name project_name FROM expenses x JOIN business_divisions b ON b.id=x.division_id LEFT JOIN projects p ON p.id=x.project_id" +
                      (" WHERE x.division_id=?" if active_division else "") + " ORDER BY expense_date DESC, x.id DESC",
                      (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    projects = db.execute("SELECT * FROM projects" + (" WHERE division_id=?" if active_division else "") + " ORDER BY name",
                          (active_division,) if active_division else ()).fetchall()
    return render_template("expenses.html", rows=rows, divisions=divisions, projects=projects,
                           can_edit=role in ("owner", "manager", "accountant"))


@expenses_bp.post("/<int:expense_id>/edit")
def edit_expense(expense_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager", "accountant"):
        abort(403)
    db = get_db()
    exp = db.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
    if not exp:
        flash("Expense not found.", "danger")
        return redirect(url_for("expenses.index"))

    amount = float(request.form.get("amount") or 0)
    category = request.form.get("category", "").strip()
    expense_date = request.form.get("expense_date")
    div_id = request.form.get("division_id", type=int)

    if amount <= 0 or not category or not expense_date or not div_id:
        flash("Division, category, date, and positive amount are required.", "danger")
        return redirect(url_for("expenses.index"))

    try:
        db.execute("""UPDATE expenses SET division_id=?, project_id=?, category=?,
                      amount=?, expense_date=?, description=?, payment_method=? WHERE id=?""",
                   (div_id, request.form.get("project_id") or None, category, amount,
                    expense_date, request.form.get("description") or None,
                    request.form.get("payment_method", "Cash"), expense_id))
        db.commit()
        log_activity("UPDATE", "expense", expense_id, f"Edited ₹{amount}")
        db.commit()
        flash("Expense updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update expense: {exc}", "danger")
    return redirect(url_for("expenses.index"))


@expenses_bp.post("/<int:expense_id>/delete")
def delete_expense(expense_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager", "accountant"):
        abort(403)
    db = get_db()
    exp = db.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
    if not exp:
        flash("Expense not found.", "danger")
        return redirect(url_for("expenses.index"))

    try:
        db.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        db.commit()
        log_activity("DELETE", "expense", expense_id, f"Deleted ₹{exp['amount']}")
        db.commit()
        flash("Expense record deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete expense: {exc}", "danger")
    return redirect(url_for("expenses.index"))
