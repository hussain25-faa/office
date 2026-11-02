from app import app
from database.backup import backup_database
with app.app_context():
    path = backup_database(app.config["DATABASE_PATH"], "backups")
    print("Backup created:", path)
