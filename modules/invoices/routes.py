from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")


@invoices_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ("owner", "accountant"):
            abort(403)
        quantity = float(request.form.get("quantity") or 1)
        unit_price = float(request.form.get("unit_price") or request.form.get("subtotal") or 0)
        subtotal = round(quantity * unit_price, 2)
        gst_percent = float(request.form.get("gst_percent") or 0)
        gst = round(subtotal * gst_percent / 100, 2)
        total = round(subtotal + gst, 2)
        if subtotal < 0 or gst < 0:
            abort(400)
        number = request.form["invoice_number"].strip()
        inv_date = request.form["invoice_date"]
        div_id = int(request.form["division_id"])

        if db.execute("SELECT 1 FROM invoices WHERE invoice_number=?", (number,)).fetchone():
            flash(f"Invoice number '{number}' already exists.", "danger")
            return redirect(url_for("invoices.index"))

        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT INTO invoices(division_id,invoice_number,invoice_date,subtotal,gst_amount,total_amount,status,notes,created_by)
                          VALUES(?,?,?,?,?,?,'Unpaid',?,?)""",
                       (div_id, number, inv_date, subtotal, gst, total, request.form.get("notes"), session["user_id"]))
            invoice_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("INSERT INTO invoice_items(invoice_id,description,quantity,unit_price,line_total) VALUES(?,?,?,?,?)",
                       (invoice_id, request.form.get("description", "Services / Materials"), quantity, unit_price, subtotal))

            # Deduct inventory if material selected
            material_id = request.form.get("material_id", type=int)
            if material_id:
                db.execute("UPDATE materials SET current_stock=current_stock-? WHERE id=?", (quantity, material_id))
                db.execute("""INSERT INTO inventory_transactions(division_id,material_id,transaction_type,quantity,reference,notes,created_by)
                              VALUES(?,?,'ISSUE',?,?,?,?)""",
                           (div_id, material_id, quantity, number, f"Sold on invoice {number}", session["user_id"]))

            db.commit()
            log_activity("CREATE", "invoice", invoice_id, f"Invoice {number} total ₹{total}")
            db.commit()
            flash(f"Invoice '{number}' created. Total: ₹{total:,.2f}", "success")
        except Exception as e:
            db.rollback()
            flash(f"Invoice could not be created: {e}", "danger")
        return redirect(url_for("invoices.index"))

    active_division = session.get("active_division_id") or session.get("division_id")
    rows = db.execute("SELECT i.*, b.name division_name FROM invoices i JOIN business_divisions b ON b.id=i.division_id" +
                      (" WHERE i.division_id=?" if active_division else "") + " ORDER BY invoice_date DESC, i.id DESC",
                      (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    materials = db.execute("SELECT id, name, current_stock, unit FROM materials" +
                           (" WHERE division_id=?" if active_division else "") + " ORDER BY name",
                           (active_division,) if active_division else ()).fetchall()
    return render_template("invoices.html", rows=rows, divisions=divisions, materials=materials,
                           can_edit=role in ("owner", "accountant"))


@invoices_bp.post("/<int:invoice_id>/payment")
def record_payment(invoice_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoices.index"))

    pay_amount = float(request.form.get("amount") or 0)
    pay_date = request.form.get("payment_date")
    method = request.form.get("payment_method", "Bank Transfer")
    ref = request.form.get("reference")

    if pay_amount <= 0 or not pay_date:
        flash("Valid payment amount and date are required.", "danger")
        return redirect(url_for("invoices.index"))

    new_paid = round(inv["amount_paid"] + pay_amount, 2)
    new_status = "Paid" if new_paid >= inv["total_amount"] else "Partial"

    try:
        db.execute("""INSERT INTO customer_payments(invoice_id,amount,payment_date,payment_method,reference,created_by)
                      VALUES(?,?,?,?,?,?)""",
                   (invoice_id, pay_amount, pay_date, method, ref, session["user_id"]))
        db.execute("UPDATE invoices SET amount_paid=?, status=? WHERE id=?", (new_paid, new_status, invoice_id))
        db.commit()
        log_activity("PAYMENT", "invoice", invoice_id, f"Received ₹{pay_amount}")
        db.commit()
        flash(f"Payment of ₹{pay_amount:,.2f} recorded. Status: {new_status}.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not record payment: {exc}", "danger")
    return redirect(url_for("invoices.index"))


@invoices_bp.post("/<int:invoice_id>/edit")
def edit_invoice(invoice_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoices.index"))

    number = request.form.get("invoice_number", "").strip()
    inv_date = request.form.get("invoice_date")
    div_id = request.form.get("division_id", type=int)
    subtotal = float(request.form.get("subtotal") or 0)
    gst_amount = float(request.form.get("gst_amount") or 0)
    total_amount = round(subtotal + gst_amount, 2)
    status = request.form.get("status", inv["status"])
    notes = request.form.get("notes")

    try:
        db.execute("""UPDATE invoices SET division_id=?, invoice_number=?, invoice_date=?,
                      subtotal=?, gst_amount=?, total_amount=?, status=?, notes=? WHERE id=?""",
                   (div_id, number, inv_date, subtotal, gst_amount, total_amount, status, notes, invoice_id))
        db.commit()
        log_activity("UPDATE", "invoice", invoice_id, f"Edited {number}")
        db.commit()
        flash(f"Invoice '{number}' updated.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update invoice: {exc}", "danger")
    return redirect(url_for("invoices.index"))


@invoices_bp.post("/<int:invoice_id>/delete")
def delete_invoice(invoice_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "accountant"):
        abort(403)
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        flash("Invoice not found.", "danger")
        return redirect(url_for("invoices.index"))

    try:
        db.execute("DELETE FROM customer_payments WHERE invoice_id=?", (invoice_id,))
        db.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
        db.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
        db.commit()
        log_activity("DELETE", "invoice", invoice_id, f"Deleted {inv['invoice_number']}")
        db.commit()
        flash(f"Invoice '{inv['invoice_number']}' deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete invoice: {exc}", "danger")
    return redirect(url_for("invoices.index"))
