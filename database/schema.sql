PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS business_divisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    employee_id INTEGER,
    division_id INTEGER REFERENCES business_divisions(id),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL UNIQUE,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    full_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    aadhaar_number TEXT,
    date_of_birth TEXT,
    gender TEXT,
    address TEXT,
    designation TEXT,
    department TEXT,
    employee_type TEXT DEFAULT 'Permanent',
    salary_type TEXT DEFAULT 'Monthly',
    monthly_salary REAL NOT NULL DEFAULT 0 CHECK(monthly_salary >= 0),
    daily_wage REAL NOT NULL DEFAULT 0 CHECK(daily_wage >= 0),
    joining_date TEXT,
    emergency_contact TEXT,
    bank_name TEXT,
    bank_account TEXT,
    ifsc_code TEXT,
    photo_filename TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employee_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    document_type TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    original_filename TEXT,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    project_id INTEGER,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Present','Absent','Half-day','Leave')),
    check_in TEXT,
    check_out TEXT,
    overtime_hours REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    title TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    assigned_to INTEGER REFERENCES employees(id),
    assigned_by INTEGER REFERENCES users(id),
    project_id INTEGER REFERENCES projects(id),
    priority TEXT NOT NULL DEFAULT 'Normal',
    status TEXT NOT NULL DEFAULT 'Pending'
      CHECK(status IN ('Pending','In Progress','Completed','Under Review','Rejected')),
    start_date TEXT,
    due_date TEXT,
    estimated_hours REAL NOT NULL DEFAULT 0,
    actual_hours REAL NOT NULL DEFAULT 0,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    employee_notes TEXT,
    batch_no INTEGER NOT NULL DEFAULT 1,
    queue_order INTEGER NOT NULL DEFAULT 0,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    approved_by INTEGER REFERENCES users(id),
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    stored_filename TEXT NOT NULL,
    original_filename TEXT,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    name TEXT NOT NULL,
    phone TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    client_id INTEGER REFERENCES clients(id),
    project_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    site_address TEXT,
    start_date TEXT,
    expected_end_date TEXT,
    budget REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Planning'
      CHECK(status IN ('Planning','Active','On Hold','Completed','Cancelled')),
    manager_user_id INTEGER REFERENCES users(id),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT NOT NULL DEFAULT 'Nos',
    current_stock REAL NOT NULL DEFAULT 0,
    reorder_level REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(division_id, name)
);

CREATE TABLE IF NOT EXISTS material_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    material_id INTEGER NOT NULL REFERENCES materials(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    project_id INTEGER REFERENCES projects(id),
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    gst_percent REAL NOT NULL DEFAULT 0,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL,
    invoice_number TEXT,
    purchase_date TEXT NOT NULL,
    bill_filename TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    material_id INTEGER NOT NULL REFERENCES materials(id),
    project_id INTEGER REFERENCES projects(id),
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('PURCHASE','ISSUE','ADJUSTMENT','REVERSAL')),
    quantity REAL NOT NULL CHECK(quantity > 0),
    reference TEXT,
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS salary_advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    amount REAL NOT NULL CHECK(amount > 0),
    payment_date TEXT NOT NULL,
    note TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS salary_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    period_month TEXT NOT NULL,
    gross_amount REAL NOT NULL,
    deductions REAL NOT NULL DEFAULT 0,
    overtime_amount REAL NOT NULL DEFAULT 0,
    advance_deducted REAL NOT NULL DEFAULT 0,
    net_amount REAL NOT NULL,
    payment_date TEXT NOT NULL,
    payment_method TEXT,
    reference TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    project_id INTEGER REFERENCES projects(id),
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    expense_date TEXT NOT NULL,
    description TEXT,
    payment_method TEXT,
    receipt_filename TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES business_divisions(id),
    client_id INTEGER REFERENCES clients(id),
    project_id INTEGER REFERENCES projects(id),
    invoice_number TEXT NOT NULL UNIQUE,
    invoice_date TEXT NOT NULL,
    subtotal REAL NOT NULL,
    gst_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL,
    amount_paid REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Unpaid',
    notes TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount REAL NOT NULL CHECK(amount > 0),
    payment_date TEXT NOT NULL,
    payment_method TEXT,
    reference TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id),
    module_name TEXT NOT NULL,
    can_view INTEGER NOT NULL DEFAULT 1,
    can_manage INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(role_id, module_name)
);

CREATE INDEX IF NOT EXISTS idx_employee_division ON employees(division_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee_status ON tasks(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_projects_division ON projects(division_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date_division ON expenses(division_id, expense_date);
CREATE INDEX IF NOT EXISTS idx_inventory_material ON inventory_transactions(material_id, created_at);
CREATE INDEX IF NOT EXISTS idx_salary_employee_period ON salary_payments(employee_id, period_month);

INSERT OR IGNORE INTO business_divisions(name, code) VALUES
 ('Furniture Management','FURNITURE'),
 ('Civil Engineering','CIVIL');

INSERT OR IGNORE INTO roles(name) VALUES
 ('owner'),('manager'),('accountant'),('employee');
