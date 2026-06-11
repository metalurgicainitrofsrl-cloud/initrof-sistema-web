from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from initrof_app.core.database import initialize_database
from initrof_app.core import repository as repo
from initrof_app.core.paths import data_dir, default_logo_path
from initrof_app.services.pdf import export_document_pdf, export_work_order_pdf
from initrof_web.security import app_secret, read_session, sign_session
from initrof_web import web_repository as web_repo


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="INITROF Gestion Web")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    web_repo.ensure_web_schema()


def current_user(request: Request) -> dict:
    payload = read_session(request.cookies.get("initrof_session"), app_secret())
    if not payload:
        raise HTTPException(status_code=401)
    return payload


def require_user(request: Request) -> dict:
    try:
        return current_user(request)
    except HTTPException:
        raise HTTPException(status_code=303, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    user = web_repo.authenticate(username, password)
    if not user:
        return RedirectResponse("/login?error=Usuario%20o%20clave%20incorrectos", status_code=303)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "initrof_session",
        sign_session({"uid": user["id"], "name": user["full_name"], "role": user["role"], "exp": int(time.time()) + 60 * 60 * 12}, app_secret()),
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("initrof_session")
    return response


@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: dict = Depends(require_user)):
    company = repo.fetch_company()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "company": company,
            "today": date.today().isoformat(),
            "logo_url": "/logo",
        },
    )


@app.get("/logo")
def logo():
    company = repo.fetch_company()
    path = Path(company.get("logo_path") or default_logo_path())
    if not path.exists():
        path = default_logo_path()
    return FileResponse(path)


@app.get("/api/bootstrap")
def bootstrap(user: dict = Depends(require_user)):
    return {
        **web_repo.dashboard_payload(),
        "company": repo.fetch_company(),
        "printables": repo.list_printables(),
    }


@app.get("/api/clients")
def clients(search: str = "", user: dict = Depends(require_user)):
    return repo.list_clients(search)


@app.post("/api/clients")
async def save_client(request: Request, user: dict = Depends(require_user)):
    data = await request.json()
    if not str(data.get("business_name") or "").strip():
        raise HTTPException(400, "La razon social es obligatoria")
    client_id = repo.save_client(data)
    return web_repo.get_client(client_id)


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int, user: dict = Depends(require_user)):
    repo.delete_client(client_id)
    return {"ok": True}


@app.get("/api/documents")
def documents(doc_type: str | None = None, search: str = "", user: dict = Depends(require_user)):
    return repo.list_documents(doc_type, search)


@app.get("/api/documents/{document_id}")
def document(document_id: int, user: dict = Depends(require_user)):
    doc, items = repo.get_document(document_id)
    return {"document": doc, "items": items}


@app.post("/api/documents")
async def save_document(request: Request, user: dict = Depends(require_user)):
    payload = await request.json()
    validate_document_payload(payload)
    doc_id = repo.save_document(payload["document"], payload["items"])
    doc, items = repo.get_document(doc_id)
    return {"document": doc, "items": items}


@app.post("/api/documents/{document_id}/void")
def void_document(document_id: int, user: dict = Depends(require_user)):
    if not web_repo.void_document(document_id):
        raise HTTPException(404, "Documento no encontrado")
    doc, items = repo.get_document(document_id)
    return {"document": doc, "items": items}


@app.post("/api/documents/{document_id}/convert-to-remito")
def convert_to_remito(document_id: int, user: dict = Depends(require_user)):
    doc, items = repo.get_document(document_id)
    if doc["doc_type"] != "Presupuesto":
        raise HTTPException(400, "Solo se puede convertir un presupuesto")
    new_doc = {
        "doc_type": "Remito",
        "number": "",
        "date": date.today().isoformat(),
        "client_id": doc["client_id"],
        "contact": doc.get("contact"),
        "address": doc.get("address"),
        "phone": doc.get("phone"),
        "status": "Pendiente",
        "observations": f"Generado desde presupuesto {doc['number']}",
        "source_document_id": document_id,
    }
    remito_id = repo.save_document(new_doc, items)
    remito, remito_items = repo.get_document(remito_id)
    return {"document": remito, "items": remito_items}


@app.get("/api/orders")
def orders(search: str = "", user: dict = Depends(require_user)):
    return repo.list_work_orders(search)


@app.get("/api/orders/{order_id}")
def order(order_id: int, user: dict = Depends(require_user)):
    return repo.get_work_order(order_id)


@app.post("/api/orders")
async def save_order(request: Request, user: dict = Depends(require_user)):
    payload = await request.json()
    if not int(payload.get("client_id") or 0):
        raise HTTPException(400, "Seleccione cliente")
    if not str(payload.get("start_date") or "").strip():
        raise HTTPException(400, "La fecha de inicio es obligatoria")
    order_id = repo.save_work_order(payload)
    return repo.get_work_order(order_id)


@app.post("/api/company")
async def save_company(request: Request, user: dict = Depends(require_user)):
    data = await request.json()
    repo.update_company(data)
    return repo.fetch_company()


@app.post("/api/company/logo")
async def upload_logo(file: UploadFile, user: dict = Depends(require_user)):
    suffix = Path(file.filename or "logo.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, "Formato de logo no admitido")
    target = data_dir() / f"logo_initrof{suffix}"
    target.write_bytes(await file.read())
    company = repo.fetch_company()
    company["logo_path"] = str(target)
    repo.update_company(company)
    return {"logo_path": str(target)}


@app.post("/api/password")
async def password(request: Request, user: dict = Depends(require_user)):
    data = await request.json()
    if len(data.get("password", "")) < 8:
        raise HTTPException(400, "La clave debe tener al menos 8 caracteres")
    web_repo.change_password(user["uid"], data["password"])
    return {"ok": True}


@app.get("/pdf/document/{document_id}")
def document_pdf(document_id: int, user: dict = Depends(require_user)):
    return FileResponse(export_document_pdf(document_id), media_type="application/pdf")


@app.get("/pdf/order/{order_id}")
def order_pdf(order_id: int, user: dict = Depends(require_user)):
    return FileResponse(export_work_order_pdf(order_id), media_type="application/pdf")


@app.get("/health")
def health():
    return {"ok": True, "data_dir": str(data_dir())}


def validate_document_payload(payload: dict) -> None:
    document = payload.get("document") or {}
    items = payload.get("items") or []
    doc_type = document.get("doc_type")
    if doc_type not in {"Presupuesto", "Remito"}:
        raise HTTPException(400, "Tipo de documento invalido")
    if not str(document.get("date") or "").strip():
        raise HTTPException(400, "La fecha es obligatoria")
    if not int(document.get("client_id") or 0):
        raise HTTPException(400, "Seleccione cliente")
    clean_items = []
    for idx, item in enumerate(items, start=1):
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        try:
            quantity = float(item.get("quantity") or 0)
            unit_price = float(item.get("unit_price") or 0)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Item {idx}: cantidad o precio invalido")
        if quantity <= 0:
            raise HTTPException(400, f"Item {idx}: la cantidad debe ser mayor a cero")
        if unit_price < 0:
            raise HTTPException(400, f"Item {idx}: el precio no puede ser negativo")
        clean_items.append(
            {
                "quantity": quantity,
                "description": description,
                "unit": str(item.get("unit") or "u").strip() or "u",
                "unit_price": unit_price,
            }
        )
    if not clean_items:
        raise HTTPException(400, "Agregue al menos un item con descripcion")
    payload["items"] = clean_items
