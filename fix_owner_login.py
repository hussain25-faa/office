"""Create the first owner account or reset an existing owner's password.

Uses the same DATABASE_PATH as the Flask application. Does not delete or
recreate the SQLite database or any business records.
"""
from getpass import getpass
from app import app
from database.db import get_db
from werkzeug.security import generate_password_hash


def main():
    with app.app_context():
        db = get_db()
        db.execute("PRAGMA foreign_keys = ON")
        db_path = app.config["DATABASE_PATH"]
        print(f"Using database: {db_path}")

        owner_role = db.execute(
            "SELECT id FROM roles WHERE name = 'owner'"
        ).fetchone()
        if owner_role is None:
            raise SystemExit(
                "Owner role is missing. Run: python database/init_db.py"
            )

        existing = db.execute(
            "SELECT id, username, role_id FROM users ORDER BY id"
        ).fetchall()
        if existing:
            print("Existing login accounts:")
            for row in existing:
                role = db.execute(
                    "SELECT name FROM roles WHERE id = ?", (row["role_id"],)
                ).fetchone()
                print(f" - {row['username']} ({role['name'] if role else 'unknown'})")
        else:
            print("No login accounts exist in this database yet.")

        username = input("Owner username to create or repair: ").strip()
        if not username:
            raise SystemExit("Username cannot be empty.")

        password = getpass("New owner password (minimum 12 characters): ")
        confirm = getpass("Confirm new password: ")
        if len(password) < 12:
            raise SystemExit("Password must contain at least 12 characters.")
        if password != confirm:
            raise SystemExit("Passwords do not match. No changes were made.")

        user = db.execute(
            "SELECT id, role_id FROM users WHERE username = ?", (username,)
        ).fetchone()
        password_hash = generate_password_hash(password)

        try:
            if user:
                if user["role_id"] != owner_role["id"]:
                    raise SystemExit(
                        "That username belongs to a non-owner account. "
                        "Choose a different username. No changes were made."
                    )
                db.execute(
                    "UPDATE users SET password_hash = ?, active = 1 WHERE id = ?",
                    (password_hash, user["id"]),
                )
                message = "Existing owner password updated and account activated."
            else:
                db.execute(
                    "INSERT INTO users (username, password_hash, role_id, active) "
                    "VALUES (?, ?, ?, 1)",
                    (username, password_hash, owner_role["id"]),
                )
                message = "Owner account created successfully."
            db.commit()
        except Exception:
            db.rollback()
            raise

        print(message)
        print("Now run: python app.py")
        print("Then sign in using the owner username and new password.")


if __name__ == "__main__":
    main()
