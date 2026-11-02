from getpass import getpass
from app import app
from modules.owner.setup import create_owner

with app.app_context():
    username = input("Owner username: ").strip()
    email = input("Owner email (optional): ").strip() or None
    password = getpass("Owner password (min 12 characters): ")
    confirm = getpass("Confirm password: ")
    if len(password) < 12 or password != confirm:
        raise SystemExit("Passwords must match and contain at least 12 characters.")
    create_owner(username, password, email)
    print("Owner account created. You can now sign in.")
