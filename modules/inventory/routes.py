from flask import Blueprint, render_template, request, redirect, url_for, session, abort, flash
from database.db import get_db, log_activity

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    db = get_db()
    role = session.get("role")
    if request.method == "POST":
        if role not in ("owner", "manager", "accountant"):
            abort(403)
        name = request.form["name"].strip()
        div = int(request.form["division_id"])
        qty = float(request.form.get("quantity", 0))
        price = float(request.form.get("unit_price", 0))
        gst = float(request.form.get("gst_percent", 0))
        reorder_level = float(request.form.get("reorder_level", 0))
        if qty <= 0 or price < 0 or gst < 0:
            abort(400)
        try:
            db.execute("INSERT OR IGNORE INTO materials(division_id,name,category,unit,reorder_level) VALUES(?,?,?,?,?)",
                       (div, name, request.form.get("category"), request.form.get("unit", "Nos"), reorder_level))
            material = db.execute("SELECT id FROM materials WHERE division_id=? AND name=?", (div, name)).fetchone()
            gst_amount = qty * price * gst / 100
            total = qty * price + gst_amount
            db.execute("""INSERT INTO material_purchases(division_id,material_id,quantity,unit_price,gst_percent,gst_amount,total_amount,purchase_date,invoice_number,created_by)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (div, material["id"], qty, price, gst, gst_amount, total,
                        request.form["purchase_date"], request.form.get("invoice_number"), session["user_id"]))
            db.execute("UPDATE materials SET current_stock=current_stock+?, reorder_level=MAX(reorder_level, ?) WHERE id=?",
                       (qty, reorder_level, material["id"]))
            db.execute("""INSERT INTO inventory_transactions(division_id,material_id,transaction_type,quantity,reference,created_by)
                          VALUES(?,?,'PURCHASE',?,?,?)""",
                       (div, material["id"], qty, request.form.get("invoice_number"), session["user_id"]))
            db.commit()
            log_activity("PURCHASE", "material", material["id"], f"qty={qty},total={total}")
            db.commit()
            flash(f"Purchase recorded. Added {qty} units of {name}. Total ₹{total:,.2f}", "success")
        except Exception as e:
            db.rollback()
            flash(f"Purchase failed: {e}", "danger")
        return redirect(url_for("inventory.index"))

    active_division = session.get("active_division_id") or session.get("division_id")
    materials = db.execute("SELECT m.*, b.name division_name FROM materials m JOIN business_divisions b ON b.id=m.division_id" +
                           (" WHERE m.division_id=?" if active_division else "") + " ORDER BY m.name",
                           (active_division,) if active_division else ()).fetchall()
    divisions = db.execute("SELECT * FROM business_divisions WHERE active=1 ORDER BY name").fetchall()
    projects = db.execute("SELECT id, name, division_id FROM projects" +
                          (" WHERE division_id=?" if active_division else "") + " ORDER BY name",
                          (active_division,) if active_division else ()).fetchall()
    return render_template("inventory.html", materials=materials, divisions=divisions, projects=projects,
                           can_edit=role in ("owner", "manager", "accountant"))


@inventory_bp.post("/issue")
def issue():
    if session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    mid = int(request.form["material_id"])
    qty = float(request.form["quantity"])
    try:
        db.execute("BEGIN IMMEDIATE")
        m = db.execute("SELECT * FROM materials WHERE id=?", (mid,)).fetchone()
        if not m or qty <= 0 or m["current_stock"] < qty:
            raise ValueError(f"Insufficient stock (Available: {m['current_stock'] if m else 0}) or invalid quantity.")
        db.execute("UPDATE materials SET current_stock=current_stock-? WHERE id=?", (qty, mid))
        db.execute("""INSERT INTO inventory_transactions(division_id,material_id,project_id,transaction_type,quantity,notes,created_by)
                      VALUES(?,?,?,'ISSUE',?,?,?)""",
                   (m["division_id"], mid, request.form.get("project_id") or None, qty, request.form.get("notes"), session["user_id"]))
        db.commit()
        log_activity("ISSUE", "material", mid, f"qty={qty}")
        db.commit()
        flash(f"Stock of {qty} units issued successfully.", "success")
    except Exception as e:
        db.rollback()
        flash(str(e), "danger")
    return redirect(url_for("inventory.index"))


@inventory_bp.post("/<int:material_id>/edit")
def edit_material(material_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager", "accountant"):
        abort(403)
    db = get_db()
    mat = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    if not mat:
        flash("Material not found.", "danger")
        return redirect(url_for("inventory.index"))

    name = request.form.get("name", "").strip()
    div_id = request.form.get("division_id", type=int)
    category = request.form.get("category", "").strip()
    unit = request.form.get("unit", "Nos").strip()
    reorder_level = float(request.form.get("reorder_level") or 0)
    current_stock = float(request.form.get("current_stock") or mat["current_stock"])

    if not name or not div_id:
        flash("Material name and workspace are required.", "danger")
        return redirect(url_for("inventory.index"))

    try:
        db.execute("""UPDATE materials SET division_id=?, name=?, category=?, unit=?,
                      reorder_level=?, current_stock=? WHERE id=?""",
                   (div_id, name, category or None, unit, reorder_level, current_stock, material_id))
        db.commit()
        log_activity("UPDATE", "material", material_id, f"Edited {name}")
        db.commit()
        flash(f"Material '{name}' updated successfully.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not update material: {exc}", "danger")
    return redirect(url_for("inventory.index"))


@inventory_bp.post("/<int:material_id>/delete")
def delete_material(material_id):
    if not session.get("user_id") or session.get("role") not in ("owner", "manager"):
        abort(403)
    db = get_db()
    mat = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    if not mat:
        flash("Material not found.", "danger")
        return redirect(url_for("inventory.index"))

    try:
        # Check transaction history
        tx_count = db.execute("SELECT COUNT(*) FROM inventory_transactions WHERE material_id=?", (material_id,)).fetchone()[0]
        if tx_count > 0:
            flash(f"Cannot delete '{mat['name']}' because it has {tx_count} recorded transactions.", "warning")
        else:
            db.execute("DELETE FROM materials WHERE id=?", (material_id,))
            db.commit()
            log_activity("DELETE", "material", material_id, f"Deleted {mat['name']}")
            db.commit()
            flash(f"Material '{mat['name']}' was deleted.", "success")
    except Exception as exc:
        db.rollback()
        flash(f"Could not delete material: {exc}", "danger")
    return redirect(url_for("inventory.index"))
