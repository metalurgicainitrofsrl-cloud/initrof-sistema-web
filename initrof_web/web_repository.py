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


def get_client(client_id: int) -> dict | None:
    with session() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None


def delete_document(document_id: int) -> bool:
    with session() as conn:
        row = conn.execute("SELECT doc_type, number FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, 'Eliminar', ?)",
            (row["doc_type"], document_id, row["number"]),
        )
        return True


def delete_test_delivery_notes(max_number: int = 200) -> int:
    with session() as conn:
        rows = conn.execute("SELECT id, number FROM documents WHERE doc_type = 'Remito'").fetchall()
        ids_to_delete = []
        for row in rows:
            digits = "".join(ch for ch in str(row["number"]) if ch.isdigit())
            number = int(digits[-6:]) if digits else 0
            if 0 < number <= max_number:
                ids_to_delete.append(row["id"])
        if not ids_to_delete:
            return 0
        conn.executemany("DELETE FROM documents WHERE id = ?", [(doc_id,) for doc_id in ids_to_delete])
        conn.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES ('Remito', 0, 'Eliminar remitos de prueba', ?)",
            (f"Eliminados {len(ids_to_delete)} remitos hasta numero {max_number}",),
        )
        return len(ids_to_delete)


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
        "clients": repo.list_clients(),
        "budgets": repo.list_documents("Presupuesto")[:8],
        "delivery_notes": repo.list_documents("Remito")[:8],
        "orders": repo.list_work_orders()[:8],
    }
