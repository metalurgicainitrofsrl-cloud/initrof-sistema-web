from __future__ import annotations

import os

from initrof_app.core.database import session
from initrof_app.core import repository as repo
from initrof_web.security import hash_password, verify_password


def ensure_web_schema() -> None:
    initial_password = os.environ.get("INITROF_ADMIN_PASSWORD", "admin123")
    with session() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not admin:
            conn.execute(
                "INSERT INTO users(username, full_name, role, active, password_hash) VALUES (?, ?, ?, 1, ?)",
                ("admin", "Administrador INITROF", "Administrador", hash_password(initial_password)),
            )
        else:
            conn.execute(
                "UPDATE users SET password_hash = COALESCE(password_hash, ?) WHERE username = 'admin'",
                (hash_password(initial_password),),
            )


def authenticate(username: str, password: str) -> dict | None:
    with session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username.strip(),),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return dict(row)
    return None


def change_password(user_id: int, password: str) -> None:
    with session() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))


def get_client(client_id: int) -> dict:
    with session() as conn:
        return dict(conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone())


def delete_document(document_id: int) -> None:
    with session() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def void_document(document_id: int) -> bool:
    with session() as conn:
        row = conn.execute("SELECT doc_type, number FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE documents SET status = 'Anulado', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (document_id,),
        )
        conn.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, 'Anular', ?)",
            (row["doc_type"], document_id, row["number"]),
        )
        return True


def dashboard_payload() -> dict:
    stats = repo.dashboard_stats()
    return {
        "stats": stats,
        "clients": repo.list_clients()[:8],
        "budgets": repo.list_documents("Presupuesto")[:8],
        "delivery_notes": repo.list_documents("Remito")[:8],
        "orders": repo.list_work_orders()[:8],
    }
