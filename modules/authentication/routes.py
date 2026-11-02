from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database.db import get_db, log_activity

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = get_db().execute("""
            SELECT u.*, r.name AS role_name, e.full_name
            FROM users u JOIN roles r ON r.id=u.role_id
            LEFT JOIN employees e ON e.id=u.employee_id
            WHERE u.username=? AND u.active=1
        """,(username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role_name"]
            session["division_id"] = user["division_id"]
            session["active_division_id"] = user["division_id"]
            session["employee_id"] = user["employee_id"]
            log_activity("LOGIN","user",user["id"])
            return redirect(url_for("owner.dashboard"))
        flash("Invalid username or password.","danger")
    return render_template("login.html")

@auth_bp.route("/logout", methods=["POST"])
def logout():
    log_activity("LOGOUT","user",session.get("user_id"))
    session.clear()
    flash("You have been logged out.","success")
    return redirect(url_for("auth.login"))
