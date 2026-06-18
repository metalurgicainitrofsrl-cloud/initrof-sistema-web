from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from initrof_app.core.paths import db_path, default_logo_path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    subtitle TEXT NOT NULL,
    cuit TEXT,
    address TEXT,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    website TEXT,
    iva_condition TEXT,
    gross_income TEXT,
    activity_start TEXT,
    remito_cai TEXT,
    remito_cai_due TEXT,
    remito_offset_x_mm REAL NOT NULL DEFAULT 0,
    remito_offset_y_mm REAL NOT NULL DEFAULT 0,
    sale_conditions TEXT,
    legal_notes TEXT,
    logo_path TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('Administrador','Operador')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    trade_name TEXT,
    cuit TEXT,
    address TEXT,
    city TEXT,
    province TEXT,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    contact_name TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('Presupuesto','Remito')),
    number TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    contact TEXT,
    address TEXT,
    phone TEXT,
    status TEXT NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0,
    iva REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    show_iva INTEGER NOT NULL DEFAULT 1,
    observations TEXT,
    invoice_number TEXT,
    source_document_id INTEGER REFERENCES documents(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    quantity REAL NOT NULL,
    description TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'u',
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL UNIQUE,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    source_document_id INTEGER REFERENCES documents(id),
    responsible TEXT,
    start_date TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL CHECK(status IN ('Pendiente','En Proceso','Finalizado','Entregado')),
    requested_work TEXT,
    materials TEXT,
    observations TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS number_sequences (
    key TEXT PRIMARY KEY,
    prefix TEXT NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        seed(conn)


def migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(company)").fetchall()}
    additions = {
        "iva_condition": "TEXT",
        "gross_income": "TEXT",
        "activity_start": "TEXT",
        "remito_cai": "TEXT",
        "remito_cai_due": "TEXT",
        "remito_offset_x_mm": "REAL NOT NULL DEFAULT 0",
        "remito_offset_y_mm": "REAL NOT NULL DEFAULT 0",
        "sale_conditions": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE company ADD COLUMN {name} {sql_type}")
    conn.execute(
        """
        UPDATE company SET
            iva_condition = COALESCE(iva_condition, 'Responsable Inscripto'),
            gross_income = COALESCE(gross_income, ''),
            activity_start = COALESCE(activity_start, ''),
            remito_cai = COALESCE(remito_cai, ''),
            remito_cai_due = COALESCE(remito_cai_due, ''),
            remito_offset_x_mm = COALESCE(remito_offset_x_mm, 0),
            remito_offset_y_mm = COALESCE(remito_offset_y_mm, 0),
            sale_conditions = COALESCE(sale_conditions, 'Contado / Cta. Cte.')
        WHERE id = 1
        """
    )
    conn.executemany(
        "INSERT OR IGNORE INTO number_sequences(key, prefix, last_number) VALUES (?, ?, 0)",
        [("Presupuesto", "P"), ("Remito", "R"), ("Orden", "OT")],
    )
    document_columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "invoice_number" not in document_columns:
        conn.execute("ALTER TABLE documents ADD COLUMN invoice_number TEXT")
    if "show_iva" not in document_columns:
        conn.execute("ALTER TABLE documents ADD COLUMN show_iva INTEGER NOT NULL DEFAULT 1")
    sync_sequence(conn, "Presupuesto", "documents", "doc_type = 'Presupuesto'")
    sync_sequence(conn, "Remito", "documents", "doc_type = 'Remito'")
    sync_sequence(conn, "Orden", "work_orders", "1 = 1")
    conn.execute("UPDATE number_sequences SET last_number = MAX(last_number, 183) WHERE key = 'Remito'")
    work_order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(work_orders)").fetchall()}
    if "source_document_id" not in work_order_columns:
        conn.execute("ALTER TABLE work_orders ADD COLUMN source_document_id INTEGER REFERENCES documents(id)")


def sync_sequence(conn: sqlite3.Connection, key: str, table: str, where: str) -> None:
    rows = conn.execute(f"SELECT number FROM {table} WHERE {where}").fetchall()
    max_value = 0
    for row in rows:
        digits = "".join(ch for ch in str(row["number"]) if ch.isdigit())
        if digits:
            max_value = max(max_value, int(digits[-6:]))
    conn.execute("UPDATE number_sequences SET last_number = MAX(last_number, ?) WHERE key = ?", (max_value, key))


def seed(conn: sqlite3.Connection) -> None:
    company_exists = conn.execute("SELECT COUNT(*) FROM company").fetchone()[0]
    if not company_exists:
        conn.execute(
            """
            INSERT INTO company
            (id, name, subtitle, cuit, address, phone, whatsapp, email, website,
             iva_condition, gross_income, activity_start, remito_cai, remito_cai_due,
             remito_offset_x_mm, remito_offset_y_mm, sale_conditions, legal_notes, logo_path)
            VALUES (1, 'INITROF SRL', 'METALURGICA', '30-00000000-0',
                    'Parque industrial - Argentina', '+54 000 000000',
                    '+54 9 000 000000', 'administracion@initrof.com.ar',
                    'www.initrof.com.ar', 'Responsable Inscripto', '',
                    '', '', '', 0, 0, 'Contado / Cta. Cte.',
                    'Documento generado digitalmente.', ?)
            """,
            (str(default_logo_path()),),
        )
    user_exists = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if not user_exists:
        conn.executemany(
            "INSERT INTO users(username, full_name, role) VALUES (?, ?, ?)",
            [("admin", "Administrador INITROF", "Administrador"), ("operador", "Operador", "Operador")],
        )
