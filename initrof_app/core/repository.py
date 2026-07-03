from __future__ import annotations

import secrets
from datetime import date

from initrof_app.core.database import session


def fetch_company():
    with session() as conn:
        return dict(conn.execute("SELECT * FROM company WHERE id = 1").fetchone())


def update_company(data: dict) -> None:
    fields = [
        "name", "subtitle", "cuit", "address", "phone", "whatsapp", "email", "website",
        "iva_condition", "gross_income", "activity_start", "remito_cai", "remito_cai_due",
        "remito_offset_x_mm", "remito_offset_y_mm", "sale_conditions", "legal_notes", "logo_path",
    ]
    values = [data.get(field) for field in fields]
    with session() as conn:
        conn.execute(
            f"UPDATE company SET {', '.join(f'{field} = ?' for field in fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            values,
        )


def list_clients(search: str = ""):
    with session() as conn:
        pattern = f"%{search}%"
        rows = conn.execute(
            """
            SELECT * FROM clients
            WHERE active = 1 AND (business_name LIKE ? OR trade_name LIKE ? OR cuit LIKE ? OR contact_name LIKE ?)
            ORDER BY business_name
            """,
            (pattern, pattern, pattern, pattern),
        ).fetchall()
        return [dict(row) for row in rows]


def save_client(data: dict) -> int:
    fields = ["business_name", "trade_name", "cuit", "address", "city", "province", "phone", "whatsapp", "email", "contact_name", "notes"]
    with session() as conn:
        if data.get("id"):
            conn.execute(
                f"UPDATE clients SET {', '.join(f'{f} = ?' for f in fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [data.get(f) for f in fields] + [data["id"]],
            )
            client_id = data["id"]
        else:
            cur = conn.execute(
                f"INSERT INTO clients ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                [data.get(f) for f in fields],
            )
            client_id = cur.lastrowid
        conn.execute("INSERT INTO history(entity_type, entity_id, action, detail) VALUES ('Cliente', ?, 'Guardar', ?)", (client_id, data.get("business_name")))
        return client_id


def delete_client(client_id: int) -> None:
    with session() as conn:
        conn.execute("UPDATE clients SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (client_id,))
        conn.execute("INSERT INTO history(entity_type, entity_id, action) VALUES ('Cliente', ?, 'Eliminar')", (client_id,))


def next_number(doc_type: str) -> str:
    key = sequence_key(doc_type)
    with session() as conn:
        row = conn.execute("SELECT prefix, last_number FROM number_sequences WHERE key = ?", (key,)).fetchone()
        return format_number(row["prefix"], row["last_number"] + 1)


def sequence_key(doc_type: str) -> str:
    return "Orden" if doc_type in ("Orden", "Orden de Trabajo") else doc_type


def format_number(prefix: str, value: int) -> str:
    return f"{prefix}-{value:06d}"


def reserve_number(conn, doc_type: str) -> str:
    key = sequence_key(doc_type)
    row = conn.execute("SELECT prefix, last_number FROM number_sequences WHERE key = ?", (key,)).fetchone()
    next_value = int(row["last_number"]) + 1
    conn.execute("UPDATE number_sequences SET last_number = ? WHERE key = ?", (next_value, key))
    return format_number(row["prefix"], next_value)


def save_document(doc: dict, items: list[dict]) -> int:
    subtotal = sum(float(item["quantity"]) * float(item["unit_price"]) for item in items)
    show_iva = 0 if str(doc.get("show_iva", 1)).lower() in {"0", "false", "no", "off"} else 1
    client_resp_inscripto = 0 if str(doc.get("client_resp_inscripto", 1)).lower() in {"0", "false", "no", "off"} else 1
    iva = round(subtotal * 0.21, 2) if show_iva else 0
    total = round(subtotal + iva, 2)
    doc["subtotal"], doc["iva"], doc["total"], doc["show_iva"], doc["client_resp_inscripto"] = subtotal, iva, total, show_iva, client_resp_inscripto
    fields = ["doc_type", "number", "date", "client_id", "contact", "address", "phone", "status", "subtotal", "iva", "total", "show_iva", "client_resp_inscripto", "observations", "invoice_number", "source_document_id"]
    with session() as conn:
        apply_client_document_defaults(conn, doc)
        if doc.get("id"):
            existing = conn.execute("SELECT number FROM documents WHERE id = ?", (doc["id"],)).fetchone()
            if existing:
                doc["number"] = existing["number"]
            conn.execute(
                f"UPDATE documents SET {', '.join(f'{f} = ?' for f in fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [doc.get(f) for f in fields] + [doc["id"]],
            )
            doc_id = doc["id"]
            conn.execute("DELETE FROM document_items WHERE document_id = ?", (doc_id,))
        else:
            conn.execute("BEGIN IMMEDIATE")
            doc["number"] = reserve_number(conn, doc["doc_type"])
            cur = conn.execute(
                f"INSERT INTO documents ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                [doc.get(f) for f in fields],
            )
            doc_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO document_items(document_id, quantity, description, unit, unit_price, subtotal) VALUES (?, ?, ?, ?, ?, ?)",
            [(doc_id, item["quantity"], item["description"], item["unit"], item["unit_price"], float(item["quantity"]) * float(item["unit_price"])) for item in items],
        )
        conn.execute("INSERT INTO history(entity_type, entity_id, action, detail) VALUES (?, ?, 'Guardar', ?)", (doc["doc_type"], doc_id, doc["number"]))
        return doc_id


def apply_client_document_defaults(conn, doc: dict) -> None:
    client_id = doc.get("client_id")
    if not client_id:
        return
    client = conn.execute("SELECT business_name, contact_name, address, phone, whatsapp FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        return
    doc["contact"] = (doc.get("contact") or client["contact_name"] or client["business_name"] or "").strip()
    doc["address"] = (doc.get("address") or client["address"] or "").strip()
    doc["phone"] = (doc.get("phone") or client["phone"] or client["whatsapp"] or "").strip()


def list_documents(doc_type: str | None = None, search: str = ""):
    where = []
    params = []
    if doc_type:
        where.append("d.doc_type = ?")
        params.append(doc_type)
    if search:
        where.append("(d.number LIKE ? OR c.business_name LIKE ? OR d.status LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    sql_where = "WHERE " + " AND ".join(where) if where else ""
    with session() as conn:
        rows = conn.execute(
            f"""
            SELECT d.*, c.business_name AS client_name, c.email AS client_email
            FROM documents d JOIN clients c ON c.id = d.client_id
            {sql_where}
            ORDER BY d.date DESC, d.id DESC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def list_printables(search: str = ""):
    pattern = f"%{search}%"
    with session() as conn:
        docs = [dict(row) for row in conn.execute(
            """
            SELECT d.id, d.doc_type AS item_type, d.number, d.date, c.business_name AS client_name, d.status, d.total
            FROM documents d JOIN clients c ON c.id = d.client_id
            WHERE d.number LIKE ? OR c.business_name LIKE ? OR d.status LIKE ?
            """,
            (pattern, pattern, pattern),
        ).fetchall()]
        orders = [dict(row) for row in conn.execute(
            """
            SELECT w.id, 'Orden de Trabajo' AS item_type, w.number, w.start_date AS date,
                   c.business_name AS client_name, w.status, 0 AS total
            FROM work_orders w JOIN clients c ON c.id = w.client_id
            WHERE w.number LIKE ? OR c.business_name LIKE ? OR w.status LIKE ?
            """,
            (pattern, pattern, pattern),
        ).fetchall()]
    return sorted(docs + orders, key=lambda row: (row["date"], row["id"]), reverse=True)


def get_document(document_id: int):
    with session() as conn:
        doc = dict(conn.execute(
            """
            SELECT d.*, c.business_name AS client_name, c.email AS client_email,
                   c.cuit AS client_cuit, c.notes AS client_notes
            FROM documents d JOIN clients c ON c.id = d.client_id
            WHERE d.id = ?
            """,
            (document_id,),
        ).fetchone())
        items = [dict(row) for row in conn.execute("SELECT * FROM document_items WHERE document_id = ? ORDER BY id", (document_id,)).fetchall()]
        return doc, items


def get_or_create_validation_token(document_id: int) -> str:
    with session() as conn:
        doc = conn.execute("SELECT doc_type FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            raise ValueError("El documento no existe")
        if doc["doc_type"] != "Presupuesto":
            raise ValueError("Solo los presupuestos tienen validacion digital")
        existing = conn.execute("SELECT token FROM document_validation_tokens WHERE document_id = ?", (document_id,)).fetchone()
        if existing:
            return existing["token"]
        while True:
            token = secrets.token_urlsafe(24)
            try:
                conn.execute(
                    "INSERT INTO document_validation_tokens(document_id, token) VALUES (?, ?)",
                    (document_id, token),
                )
                return token
            except Exception:
                if conn.execute("SELECT 1 FROM document_validation_tokens WHERE token = ?", (token,)).fetchone():
                    continue
                raise


def get_document_by_validation_token(token: str):
    with session() as conn:
        token_row = conn.execute(
            """
            SELECT dvt.token, dvt.created_at AS token_created_at, d.*
            FROM document_validation_tokens dvt
            JOIN documents d ON d.id = dvt.document_id
            WHERE dvt.token = ? AND d.doc_type = 'Presupuesto'
            """,
            (token,),
        ).fetchone()
        if not token_row:
            return None, []
        doc = dict(token_row)
        client = conn.execute("SELECT business_name, cuit, email, phone FROM clients WHERE id = ?", (doc["client_id"],)).fetchone()
        if client:
            doc.update(
                {
                    "client_name": client["business_name"],
                    "client_cuit": client["cuit"],
                    "client_email": client["email"],
                    "client_phone": client["phone"],
                }
            )
        items = [dict(row) for row in conn.execute("SELECT * FROM document_items WHERE document_id = ? ORDER BY id", (doc["id"],)).fetchall()]
        decision = conn.execute(
            "SELECT * FROM document_validation_events WHERE document_id = ? ORDER BY id DESC LIMIT 1",
            (doc["id"],),
        ).fetchone()
        doc["validation_event"] = dict(decision) if decision else None
        return doc, items


def record_document_validation_decision(token: str, data: dict) -> dict | None:
    decision = "Aprobado" if data.get("decision") == "Aprobado" else "Rechazado"
    document_id = None
    with session() as conn:
        row = conn.execute(
            """
            SELECT d.id, d.number, d.status
            FROM document_validation_tokens dvt
            JOIN documents d ON d.id = dvt.document_id
            WHERE dvt.token = ? AND d.doc_type = 'Presupuesto'
            """,
            (token,),
        ).fetchone()
        if not row:
            return None
        document_id = row["id"]
        if row["status"] != "Anulado":
            conn.execute(
                "UPDATE documents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (decision, document_id),
            )
        conn.execute(
            """
            INSERT INTO document_validation_events
            (document_id, token, decision, signer_name, signer_identifier, signer_email, comments, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                token,
                decision,
                data.get("signer_name"),
                data.get("signer_identifier"),
                data.get("signer_email"),
                data.get("comments"),
                data.get("ip_address"),
                data.get("user_agent"),
            ),
        )
        conn.execute(
            "INSERT INTO history(entity_type, entity_id, action, detail) VALUES ('Presupuesto', ?, ?, ?)",
            (document_id, f"Validacion digital: {decision}", row["number"]),
        )
    doc, items = get_document_by_validation_token(token)
    return {"document": doc, "items": items}


def save_work_order(data: dict) -> int:
    fields = ["number", "client_id", "source_document_id", "responsible", "start_date", "due_date", "status", "requested_work", "materials", "observations"]
    with session() as conn:
        if data.get("id"):
            existing = conn.execute("SELECT number, source_document_id FROM work_orders WHERE id = ?", (data["id"],)).fetchone()
            if not existing:
                raise ValueError("La orden de trabajo no existe")
            data["number"] = existing["number"]
            if "source_document_id" not in data:
                data["source_document_id"] = existing["source_document_id"]
            conn.execute(
                f"UPDATE work_orders SET {', '.join(f'{f} = ?' for f in fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [data.get(f) for f in fields] + [data["id"]],
            )
            order_id = data["id"]
        else:
            conn.execute("BEGIN IMMEDIATE")
            data["number"] = reserve_number(conn, "Orden")
            cur = conn.execute(
                f"INSERT INTO work_orders ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                [data.get(f) for f in fields],
            )
            order_id = cur.lastrowid
        conn.execute("INSERT INTO history(entity_type, entity_id, action, detail) VALUES ('Orden de Trabajo', ?, 'Guardar', ?)", (order_id, data.get("number")))
        return order_id


def get_work_order_by_source_document(document_id: int) -> dict | None:
    with session() as conn:
        row = conn.execute(
            """
            SELECT w.*, c.business_name AS client_name, d.number AS source_budget_number
            FROM work_orders w
            JOIN clients c ON c.id = w.client_id
            LEFT JOIN documents d ON d.id = w.source_document_id
            WHERE w.source_document_id = ?
            ORDER BY w.id DESC
            LIMIT 1
            """,
            (document_id,),
        ).fetchone()
        return dict(row) if row else None


def list_work_orders(search: str = ""):
    with session() as conn:
        rows = conn.execute(
            """
            SELECT w.*, c.business_name AS client_name, d.number AS source_budget_number
            FROM work_orders w
            JOIN clients c ON c.id = w.client_id
            LEFT JOIN documents d ON d.id = w.source_document_id
            WHERE w.number LIKE ? OR c.business_name LIKE ? OR w.status LIKE ? OR d.number LIKE ?
            ORDER BY w.start_date DESC, w.id DESC
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"),
        ).fetchall()
        return [dict(row) for row in rows]


def get_work_order(order_id: int):
    with session() as conn:
        row = conn.execute(
            """
            SELECT w.*, c.business_name AS client_name, c.email AS client_email,
                   c.address AS client_address, c.phone AS client_phone,
                   d.number AS source_budget_number
            FROM work_orders w
            JOIN clients c ON c.id = w.client_id
            LEFT JOIN documents d ON d.id = w.source_document_id
            WHERE w.id = ?
            """,
            (order_id,),
        ).fetchone()
        return dict(row)


def dashboard_stats():
    month_prefix = date.today().strftime("%Y-%m")
    with session() as conn:
        return {
            "budgets_month": conn.execute("SELECT COUNT(*) FROM documents WHERE doc_type='Presupuesto' AND date LIKE ?", (f"{month_prefix}%",)).fetchone()[0],
            "delivery_notes": conn.execute("SELECT COUNT(*) FROM documents WHERE doc_type='Remito'").fetchone()[0],
            "open_orders": conn.execute("SELECT COUNT(*) FROM work_orders WHERE status IN ('Pendiente','En Proceso')").fetchone()[0],
            "active_clients": conn.execute("SELECT COUNT(*) FROM clients WHERE active=1").fetchone()[0],
            "budget_amount": conn.execute("SELECT COALESCE(SUM(total),0) FROM documents WHERE doc_type='Presupuesto' AND date LIKE ?", (f"{month_prefix}%",)).fetchone()[0],
            "monthly": [dict(row) for row in conn.execute(
                """
                SELECT substr(date,1,7) AS month, SUM(total) AS amount
                FROM documents WHERE doc_type='Presupuesto'
                GROUP BY substr(date,1,7) ORDER BY month LIMIT 12
                """
            ).fetchall()],
            "top_clients": [dict(row) for row in conn.execute(
                """
                SELECT c.business_name, SUM(d.total) AS amount
                FROM documents d JOIN clients c ON c.id=d.client_id
                GROUP BY c.id ORDER BY amount DESC LIMIT 5
                """
            ).fetchall()],
        }
