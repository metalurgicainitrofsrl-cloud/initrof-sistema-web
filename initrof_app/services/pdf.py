from __future__ import annotations

from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from initrof_app.core import repository as repo
from initrof_app.core.paths import default_logo_path, exports_dir, resource_path


BLUE = colors.HexColor("#0E4C92")
DARK = colors.HexColor("#1F2933")
RED = colors.HexColor("#D72638")
LIGHT = colors.HexColor("#F3F6F9")
MID = colors.HexColor("#D9E1EA")

REMITO_BASE_OFFSET_Y_MM = 42
SIGNATURE_IMAGE = "resources/firma_digital.png"


def money(value: float) -> str:
    return f"$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def export_document_pdf(document_id: int, include_qr: bool = True) -> Path:
    company = repo.fetch_company()
    doc, items = repo.get_document(document_id)
    filename = f"{doc['doc_type']}_{doc['number'].replace('-', '_')}.pdf"
    path = exports_dir() / filename
    c = canvas.Canvas(str(path), pagesize=A4)
    draw_document(c, company, doc, items, include_qr)
    c.save()
    return path


def export_work_order_pdf(order_id: int, include_qr: bool = True) -> Path:
    company = repo.fetch_company()
    order = repo.get_work_order(order_id)
    filename = f"Orden_Trabajo_{order['number'].replace('-', '_')}.pdf"
    path = exports_dir() / filename
    c = canvas.Canvas(str(path), pagesize=A4)
    draw_work_order(c, company, order, include_qr)
    c.save()
    return path


def draw_logo(c: canvas.Canvas, company: dict, x: float, y: float) -> None:
    logo_path = company.get("logo_path") or str(default_logo_path())
    if logo_path and Path(logo_path).exists():
        c.drawImage(logo_path, x, y - 18 * mm, width=42 * mm, height=18 * mm, preserveAspectRatio=True, mask="auto")
        return
    c.setFillColor(BLUE)
    c.roundRect(x, y - 18 * mm, 42 * mm, 18 * mm, 3 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 5 * mm, y - 11 * mm, "INITROF")
    c.setFillColor(RED)
    c.rect(x + 32 * mm, y - 18 * mm, 10 * mm, 18 * mm, fill=True, stroke=False)


def draw_document(c: canvas.Canvas, company: dict, doc: dict, items: list[dict], include_qr: bool) -> None:
    if doc["doc_type"] == "Remito":
        draw_delivery_note(c, company, doc, items, include_qr)
        return
    width, height = A4
    margin = 16 * mm
    y = height - margin

    c.setFillColor(DARK)
    c.rect(0, height - 34 * mm, width, 34 * mm, fill=True, stroke=False)
    draw_logo(c, company, margin, y - 2 * mm)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 48 * mm, y - 8 * mm, company["name"])
    c.setFont("Helvetica", 9)
    c.drawString(margin + 48 * mm, y - 14 * mm, company["subtitle"])
    c.drawString(margin + 48 * mm, y - 20 * mm, (company.get("address") or "")[:54])

    c.setFillColor(RED)
    c.roundRect(width - margin - 54 * mm, y - 24 * mm, 54 * mm, 22 * mm, 3 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width - margin - 27 * mm, y - 9 * mm, doc["doc_type"].upper())
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width - margin - 27 * mm, y - 15 * mm, doc["number"])
    c.setFont("Helvetica", 8)
    c.drawCentredString(width - margin - 27 * mm, y - 20 * mm, doc["date"])

    y -= 46 * mm
    section_title(c, margin, y, "Datos del cliente")
    y -= 8 * mm
    client_lines = [
        ("Razon social", doc["client_name"]),
        ("Contacto", doc.get("contact") or "-"),
        ("Direccion", doc.get("address") or "-"),
        ("Telefono", doc.get("phone") or "-"),
        ("Correo", doc.get("client_email") or "-"),
    ]
    c.setFillColor(LIGHT)
    c.roundRect(margin, y - 24 * mm, width - 2 * margin, 27 * mm, 2.5 * mm, fill=True, stroke=False)
    c.setFillColor(DARK)
    c.setFont("Helvetica", 8)
    x = margin + 6 * mm
    for idx, (label, value) in enumerate(client_lines):
        col_x = x + (idx % 2) * 82 * mm
        row_y = y - (idx // 2) * 8 * mm
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(BLUE)
        c.drawString(col_x, row_y, label.upper())
        c.setFont("Helvetica", 9)
        c.setFillColor(DARK)
        c.drawString(col_x, row_y - 4 * mm, str(value)[:48])

    y -= 36 * mm
    table_header(c, margin, y, width - 2 * margin)
    y -= 8 * mm
    for item in items:
        item_height = item_row_height(c, width - 2 * margin, item)
        if y - item_height < 64 * mm:
            footer(c, company, 1)
            c.showPage()
            y = height - margin
            table_header(c, margin, y, width - 2 * margin)
            y -= 8 * mm
        draw_item(c, margin, y, width - 2 * margin, item, item_height)
        y -= item_height + 2 * mm

    y -= 4 * mm
    totals_x = width - margin - 64 * mm
    c.setFillColor(LIGHT)
    c.roundRect(totals_x, y - 29 * mm, 64 * mm, 29 * mm, 2.5 * mm, fill=True, stroke=False)
    total_line(c, totals_x + 5 * mm, y - 7 * mm, "Subtotal", money(doc["subtotal"]), False)
    total_line(c, totals_x + 5 * mm, y - 15 * mm, "IVA 21%", money(doc["iva"]), False)
    c.setFillColor(RED)
    c.roundRect(totals_x + 3 * mm, y - 27 * mm, 58 * mm, 9 * mm, 2 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(totals_x + 6 * mm, y - 24 * mm, "TOTAL GENERAL")
    c.drawRightString(totals_x + 59 * mm, y - 24 * mm, money(doc["total"]))

    obs_y = y - 38 * mm
    section_title(c, margin, obs_y, "Observaciones")
    obs_lines = wrap_text(c, doc.get("observations") or "Sin observaciones.", "Helvetica", 9, width - 2 * margin - 10 * mm)
    obs_box_top = obs_y - 6 * mm
    obs_box_height = max(18 * mm, (len(obs_lines) * 5 + 6) * mm)
    c.setFillColor(LIGHT)
    c.roundRect(margin, obs_box_top - obs_box_height, width - 2 * margin, obs_box_height, 2.5 * mm, fill=True, stroke=False)
    c.setFillColor(DARK)
    c.setFont("Helvetica", 9)
    for idx, line in enumerate(obs_lines):
        c.drawString(margin + 5 * mm, obs_box_top - (7 + idx * 5) * mm, line)

    sig_y = obs_box_top - obs_box_height - 32 * mm
    draw_company_signature(c, margin, sig_y)
    c.setStrokeColor(MID)
    c.line(margin, sig_y, margin + 70 * mm, sig_y)
    c.line(width - margin - 70 * mm, sig_y, width - margin, sig_y)
    c.setFont("Helvetica", 8)
    c.setFillColor(DARK)
    c.drawString(margin, sig_y - 5 * mm, "Firma empresa / Aclaracion / Fecha")
    c.drawString(width - margin - 70 * mm, sig_y - 5 * mm, "Firma cliente / Aclaracion / Fecha")

    if include_qr:
        draw_validation_qr(c, width - margin - 28 * mm, sig_y - 22 * mm, doc)
    footer(c, company, 1)


def draw_delivery_note(c: canvas.Canvas, company: dict, doc: dict, items: list[dict], include_qr: bool) -> None:
    draw_preprinted_delivery_note(c, company, doc, items)


def draw_preprinted_delivery_note(c: canvas.Canvas, company: dict, doc: dict, items: list[dict]) -> None:
    """Print only variable fields over INITROF's preprinted remito form."""
    width, height = A4
    offset_x = float(company.get("remito_offset_x_mm") or 0) * mm
    offset_y = (REMITO_BASE_OFFSET_Y_MM + float(company.get("remito_offset_y_mm") or 0)) * mm

    def p(x_mm: float, y_from_top_mm: float) -> tuple[float, float]:
        return x_mm * mm + offset_x, height - y_from_top_mm * mm + offset_y

    def text(x_mm: float, y_top_mm: float, value: str, size: int = 9, bold: bool = False, max_chars: int | None = None) -> None:
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        value = str(value or "")
        if max_chars:
            value = value[:max_chars]
        c.drawString(*p(x_mm, y_top_mm), value)

    day, month, year = split_date(doc.get("date") or "")
    text(164, 72, day, 9, True)
    text(176, 72, month, 9, True)
    text(188, 72, year, 9, True)

    c.setFont("Helvetica", 9)
    text(22, 119, doc.get("client_name") or "", 9, False, 72)
    text(22, 128, doc.get("address") or "", 9, False, 78)
    text(140, 145, doc.get("client_cuit") or "", 9, False, 24)
    text(44, 163, company.get("sale_conditions") or "", 8, False, 30)

    iva_value = infer_client_iva(doc)
    if iva_value:
        text(27, 145, iva_value, 8, False, 28)

    c.setFont("Helvetica", 8)
    item_y = 184
    for item in items:
        if item_y > 255:
            break
        c.drawRightString(*p(18, item_y), f"{item['quantity']:g}")
        c.drawString(*p(29, item_y), str(item["description"])[:82])
        c.drawRightString(*p(193, item_y), money(item["subtotal"]))
        item_y += 8


def split_date(value: str) -> tuple[str, str, str]:
    parts = str(value).replace("/", "-").split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        return parts[2], parts[1], parts[0]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return "", "", ""


def infer_client_iva(doc: dict) -> str:
    notes = (doc.get("client_notes") or "").lower()
    if "monotrib" in notes:
        return "Monotributo"
    if "exento" in notes:
        return "Exento"
    if "final" in notes:
        return "Consumidor Final"
    return "Resp. Inscripto"


def draw_work_order(c: canvas.Canvas, company: dict, order: dict, include_qr: bool) -> None:
    width, height = A4
    margin = 16 * mm
    y = height - margin
    c.setFillColor(DARK)
    c.rect(0, height - 34 * mm, width, 34 * mm, fill=True, stroke=False)
    draw_logo(c, company, margin, y - 2 * mm)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 48 * mm, y - 8 * mm, company["name"])
    c.setFont("Helvetica", 9)
    c.drawString(margin + 48 * mm, y - 14 * mm, company["subtitle"])
    c.drawString(margin + 48 * mm, y - 20 * mm, company.get("address") or "")
    c.setFillColor(RED)
    c.roundRect(width - margin - 58 * mm, y - 24 * mm, 58 * mm, 22 * mm, 3 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width - margin - 29 * mm, y - 9 * mm, "ORDEN DE TRABAJO")
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width - margin - 29 * mm, y - 15 * mm, order["number"])
    c.setFont("Helvetica", 8)
    c.drawCentredString(width - margin - 29 * mm, y - 20 * mm, order["start_date"])

    y -= 46 * mm
    section_title(c, margin, y, "Datos de produccion")
    y -= 8 * mm
    c.setFillColor(LIGHT)
    c.roundRect(margin, y - 32 * mm, width - 2 * margin, 35 * mm, 2.5 * mm, fill=True, stroke=False)
    rows = [
        ("Cliente", order["client_name"]),
        ("Responsable", order.get("responsible") or "-"),
        ("Fecha inicio", order.get("start_date") or "-"),
        ("Fecha entrega", order.get("due_date") or "-"),
        ("Estado", order.get("status") or "-"),
        ("Telefono", order.get("client_phone") or "-"),
    ]
    for idx, (label, value) in enumerate(rows):
        col_x = margin + 6 * mm + (idx % 2) * 86 * mm
        row_y = y - (idx // 2) * 9 * mm
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(BLUE)
        c.drawString(col_x, row_y, label.upper())
        c.setFont("Helvetica", 9)
        c.setFillColor(DARK)
        c.drawString(col_x, row_y - 4 * mm, str(value)[:54])

    y -= 46 * mm
    for title, text, height_mm in [
        ("Trabajo solicitado", order.get("requested_work") or "Sin detalle.", 36),
        ("Materiales", order.get("materials") or "Sin materiales informados.", 32),
        ("Observaciones", order.get("observations") or "Sin observaciones.", 28),
    ]:
        section_title(c, margin, y, title)
        c.setFillColor(LIGHT)
        c.roundRect(margin, y - height_mm * mm, width - 2 * margin, (height_mm - 6) * mm, 2.5 * mm, fill=True, stroke=False)
        c.setFillColor(DARK)
        c.setFont("Helvetica", 9)
        draw_wrapped(c, margin + 6 * mm, y - 12 * mm, width - 44 * mm, text, 11 * mm)
        y -= (height_mm + 8) * mm

    c.setStrokeColor(MID)
    c.line(margin, 42 * mm, margin + 70 * mm, 42 * mm)
    c.line(width - margin - 70 * mm, 42 * mm, width - margin, 42 * mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(DARK)
    c.drawString(margin, 37 * mm, "Firma responsable / Aclaracion / Fecha")
    c.drawString(width - margin - 70 * mm, 37 * mm, "Firma cliente / Aclaracion / Fecha")
    if include_qr:
        draw_validation_qr(c, width - margin - 28 * mm, 18 * mm, {"doc_type": "Orden de Trabajo", "number": order["number"], "date": order["start_date"], "total": 0})
    footer(c, company, 1)


def draw_wrapped(c, x, y, width, text, leading):
    for line in wrap_text(c, text, "Helvetica", 9, width):
        c.drawString(x, y, line)
        y -= leading


def wrap_text(c, text, font_name: str, font_size: int, width: float) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font_name, font_size) <= width:
            line = trial
            continue
        if line:
            lines.append(line)
            line = ""
        while c.stringWidth(word, font_name, font_size) > width and len(word) > 1:
            cut = len(word)
            while cut > 1 and c.stringWidth(word[:cut], font_name, font_size) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    if line:
        lines.append(line)
    return lines or [""]


def section_title(c, x, y, text):
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, text.upper())
    c.setStrokeColor(RED)
    c.setLineWidth(1.2)
    c.line(x, y - 2 * mm, x + 26 * mm, y - 2 * mm)


def table_header(c, x, y, w):
    c.setFillColor(BLUE)
    c.roundRect(x, y - 7 * mm, w, 7 * mm, 2 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    columns = [(4, "Cant."), (22, "Descripcion"), (104, "Unidad"), (126, "P. Unitario"), (156, "Subtotal")]
    for dx, label in columns:
        c.drawString(x + dx * mm, y - 4.5 * mm, label)


def item_row_height(c, w, item) -> float:
    lines = wrap_text(c, item["description"], "Helvetica", 8, 78 * mm)
    return max(7 * mm, (len(lines) * 4 + 3) * mm)


def draw_item(c, x, y, w, item, row_height: float | None = None):
    row_height = row_height or item_row_height(c, w, item)
    description_lines = wrap_text(c, item["description"], "Helvetica", 8, 78 * mm)
    c.setFillColor(colors.white)
    c.setStrokeColor(MID)
    c.roundRect(x, y - row_height, w, row_height, 1.5 * mm, fill=True, stroke=True)
    c.setFillColor(DARK)
    c.setFont("Helvetica", 8)
    value_y = y - 4.5 * mm
    c.drawRightString(x + 14 * mm, value_y, f"{item['quantity']:g}")
    for idx, line in enumerate(description_lines):
        c.drawString(x + 22 * mm, value_y - idx * 4 * mm, line)
    c.drawString(x + 104 * mm, value_y, item["unit"])
    c.drawRightString(x + 149 * mm, value_y, money(item["unit_price"]))
    c.drawRightString(x + w - 4 * mm, value_y, money(item["subtotal"]))


def draw_company_signature(c, x: float, line_y: float) -> None:
    signature_path = resource_path(SIGNATURE_IMAGE)
    if signature_path.exists():
        c.drawImage(str(signature_path), x + 3 * mm, line_y + 2 * mm, width=64 * mm, height=28 * mm, mask="auto")


def total_line(c, x, y, label, value, bold):
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
    c.drawString(x, y, label)
    c.drawRightString(x + 54 * mm, y, value)


def draw_validation_qr(c, x, y, doc):
    payload = f"INITROF SRL | {doc['doc_type']} {doc['number']} | {doc['date']} | Total {doc['total']}"
    size = 24 * mm
    qr = QrCodeWidget(payload)
    bounds = qr.getBounds()
    drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, c, x, y)
    c.setFont("Helvetica", 6)
    c.drawCentredString(x + size / 2, y - 3 * mm, "Validacion digital")


def footer(c, company: dict, page: int):
    width, _ = A4
    c.setFillColor(DARK)
    c.rect(0, 0, width, 14 * mm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7)
    text = "  |  ".join(filter(None, [company.get("website"), company.get("email"), company.get("whatsapp"), company.get("address")]))
    c.drawCentredString(width / 2, 7 * mm, text)
    c.drawRightString(width - 10 * mm, 4 * mm, f"Pagina {page}")
