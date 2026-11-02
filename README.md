# Integrated Furniture & Civil Engineering ERP — Flask + SQLite

This source code uses **one local SQLite database** for both business divisions:
`database/business_erp.sqlite3`. It does not use Supabase, Firebase, PostgreSQL, MySQL, or a cloud database.

## 1. Requirements

- Python 3.10+
- Windows, macOS, or Linux
- Optional: DB Browser for SQLite

## 2. Setup on Windows

Open the project folder in VS Code terminal:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`. Generate a secret key with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value after `SECRET_KEY=` in `.env`.

Initialize the database (safe to rerun; it uses `CREATE TABLE IF NOT EXISTS` and does not delete records):

```powershell
python database/init_db.py
```

## 3. Create the first owner

```powershell
python create_owner.py
```

Enter the owner username, email and password when prompted. Do not share the credentials.

## Login troubleshooting

If the login page says `Invalid username or password`, first confirm that you are using the project folder and database path shown by the application. Run:

```powershell
python fix_owner_login.py
```

This helper prints the exact SQLite database path, lists existing usernames and roles, and lets you create the first owner or reset an existing owner password. It does not delete or recreate the database or business records. Use a username that belongs to the owner role.

## 4. Run

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## 5. Database ownership

Open `database/business_erp.sqlite3` with DB Browser for SQLite. The same file contains Furniture and Civil Engineering data, separated by `division_id`.

## 6. Backup and restore

Create a backup:

```powershell
python backup_db.py
```

Backups are saved under `backups/`. Stop the Flask server before manually replacing a database during a restore. Verify the backup first and keep a second copy of the current database.

## 7. Important implementation notes

This is a functional starter codebase with a working authentication foundation, shared schema, dashboards, and initial CRUD workflows for attendance, tasks, inventory purchases/issues, projects, expenses, salary advances, invoices and reports.

Before real production use, complete and test the remaining workflows: employee/user provisioning and editing, manager-to-division scoping on every query, accountant-specific permissions, project/client/supplier CRUD, task-batch release and approval logic, complete salary payroll/payment posting, customer payment reconciliation, PDF/Excel exports, private file upload/download routes, notifications, and audit review. Sensitive employee identity documents and bank details are intentionally not exposed by this starter.

The schema includes foreign keys, unique constraints, indexes, parameterized SQL, CSRF protection, password hashing, session cookie flags, activity logs, and SQLite WAL/busy timeout. Do a security review and role-by-role test before using with live financial or employee data.

## 8. Data safety

- Never delete `database/business_erp.sqlite3` to fix an application issue.
- Back up before applying a migration.
- Put schema changes in `database/migrations/`.
- Do not commit `.env`, database files, uploads or backups to GitHub.
- The included `schema.sql` is for initial creation; do not use destructive schema resets on a live database.
