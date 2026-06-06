from __future__ import annotations

import subprocess
import sys
import os
from datetime import date
from pathlib import Path

from initrof_app.core.database import initialize_database
from initrof_app.core import repository as repo
from initrof_app.core.paths import data_dir, default_logo_path, set_configured_data_dir
from initrof_app.services.backup import create_backup, restore_backup
from initrof_app.services.pdf import export_document_pdf, export_work_order_pdf

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
        QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit,
        QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
    )
    from PySide6.QtCore import QUrl
    from PySide6.QtPrintSupport import QPrintDialog, QPrinter
    from PySide6.QtPdf import QPdfDocument
except ModuleNotFoundError as exc:  # pragma: no cover - user-facing startup guard
    raise SystemExit(
        "PySide6 no esta instalado. Ejecute: pip install -r requirements.txt\n"
        "Luego inicie nuevamente con: python -m initrof_app"
    ) from exc


APP_QSS = """
* { font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow { background: #F5F7FA; }
QFrame#Sidebar { background: #111827; }
QLabel#Brand { color: white; font-size: 20pt; font-weight: 800; }
QLabel#Subtitle { color: #AAB4C0; font-size: 8pt; letter-spacing: 0; }
QLabel#LogoPane { background: transparent; }
QPushButton#NavButton {
    color: #D7DEE8; background: transparent; border: 0; text-align: left;
    padding: 12px 14px; border-radius: 6px; font-weight: 600;
}
QPushButton#NavButton:hover { background: #1F2937; color: white; }
QPushButton#NavButton:checked { background: #0E4C92; color: white; }
QLabel#Title { color: #111827; font-size: 22pt; font-weight: 800; }
QLabel#Hint { color: #6B7280; }
QFrame#Card { background: white; border: 1px solid #E5E7EB; border-radius: 8px; }
QLabel#CardLabel { color: #64748B; font-weight: 600; }
QLabel#CardValue { color: #111827; font-size: 20pt; font-weight: 800; }
QPushButton {
    background: #0E4C92; color: white; border: 0; border-radius: 6px;
    padding: 9px 13px; font-weight: 700;
}
QPushButton:hover { background: #0B3D75; }
QPushButton#Danger { background: #D72638; }
QPushButton#Ghost { color: #1F2937; background: #E7ECF2; }
QLineEdit, QComboBox, QPlainTextEdit {
    background: white; border: 1px solid #CDD6E1; border-radius: 6px; padding: 8px;
}
QTableWidget {
    background: white; border: 1px solid #E5E7EB; border-radius: 8px; gridline-color: #EEF2F6;
    selection-background-color: #DCEBFA; selection-color: #111827;
}
QHeaderView::section {
    background: #1F2933; color: white; border: 0; padding: 8px; font-weight: 700;
}
QGroupBox { font-weight: 800; color: #111827; border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 10px; padding: 14px; background: white; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
"""


def format_money(value: float) -> str:
    return f"$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class BarChart(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.values: list[tuple[str, float]] = []
        self.setMinimumHeight(220)

    def set_values(self, values: list[tuple[str, float]]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(16, 14, -16, -18)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(rect.left(), rect.top(), self.title)
        chart = rect.adjusted(0, 30, 0, -10)
        max_value = max([value for _, value in self.values] or [1])
        bar_w = max(24, int(chart.width() / max(len(self.values), 1) * 0.56))
        gap = int((chart.width() - bar_w * max(len(self.values), 1)) / max(len(self.values) + 1, 2))
        for idx, (label, value) in enumerate(self.values):
            x = chart.left() + gap + idx * (bar_w + gap)
            h = int((chart.height() - 30) * (value / max_value)) if max_value else 0
            y = chart.bottom() - 22 - h
            painter.setBrush(QColor("#0E4C92"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_w, h, 5, 5)
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(x - 12, chart.bottom() - 14, bar_w + 24, 14, Qt.AlignCenter, label[-7:])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("INITROF SRL - Gestion Comercial")
        self.resize(1360, 820)
        self.current_client_id: int | None = None
        self.current_doc_id: int | None = None
        self.current_order_id: int | None = None
        self.pages: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        self.build_shell()
        self.refresh_all()

    def build_shell(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        logo = QLabel()
        logo.setObjectName("LogoPane")
        logo.setFixedHeight(78)
        logo.setPixmap(QPixmap(str(default_logo_path())).scaled(190, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand = QLabel("INITROF")
        brand.setObjectName("Brand")
        subtitle = QLabel("SRL  |  METALURGICA")
        subtitle.setObjectName("Subtitle")
        side.addWidget(logo)
        side.addWidget(brand)
        side.addWidget(subtitle)
        side.addSpacing(20)
        for key, label in [
            ("dashboard", "Panel principal"),
            ("clients", "Clientes"),
            ("budgets", "Presupuestos"),
            ("delivery", "Remitos"),
            ("orders", "Ordenes de trabajo"),
            ("printing", "Impresion"),
            ("search", "Buscar documentos"),
            ("settings", "Configuracion"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self.show_page(k))
            side.addWidget(btn)
            self.nav_buttons[key] = btn
        side.addStretch()
        self.stack = QStackedWidget()
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        builders = {
            "dashboard": self.build_dashboard,
            "clients": self.build_clients,
            "budgets": lambda: self.build_documents("Presupuesto"),
            "delivery": lambda: self.build_documents("Remito"),
            "orders": self.build_orders,
            "printing": self.build_printing,
            "search": self.build_search,
            "settings": self.build_settings,
        }
        for key, builder in builders.items():
            page = builder()
            self.pages[key] = page
            self.stack.addWidget(page)
        self.show_page("dashboard")

    def page_layout(self, title: str, hint: str):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        hint_label = QLabel(hint)
        hint_label.setObjectName("Hint")
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return page, layout

    def build_dashboard(self):
        page, layout = self.page_layout("Panel principal", "Indicadores comerciales y operativos de INITROF SRL.")
        logo_row = QHBoxLayout()
        dash_logo = QLabel()
        dash_logo.setPixmap(QPixmap(str(default_logo_path())).scaled(300, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_row.addWidget(dash_logo)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        grid = QGridLayout()
        self.stat_labels = {}
        for idx, (key, title) in enumerate([
            ("budgets_month", "Presupuestos del mes"),
            ("delivery_notes", "Remitos emitidos"),
            ("open_orders", "Ordenes abiertas"),
            ("active_clients", "Clientes activos"),
            ("budget_amount", "Importe presupuestado"),
        ]):
            card = QFrame()
            card.setObjectName("Card")
            box = QVBoxLayout(card)
            label = QLabel(title)
            label.setObjectName("CardLabel")
            value = QLabel("0")
            value.setObjectName("CardValue")
            box.addWidget(label)
            box.addWidget(value)
            self.stat_labels[key] = value
            grid.addWidget(card, idx // 3, idx % 3)
        layout.addLayout(grid)
        charts = QHBoxLayout()
        self.month_chart = BarChart("Presupuestos por mes")
        self.client_chart = BarChart("Clientes principales")
        for chart in (self.month_chart, self.client_chart):
            frame = QFrame()
            frame.setObjectName("Card")
            box = QVBoxLayout(frame)
            box.addWidget(chart)
            charts.addWidget(frame)
        layout.addLayout(charts, 1)
        return page

    def build_clients(self):
        page, layout = self.page_layout("Clientes", "Alta, modificacion, busqueda e historial comercial.")
        top = QHBoxLayout()
        self.client_search = QLineEdit()
        self.client_search.setPlaceholderText("Buscar por razon social, CUIT o contacto")
        self.client_search.textChanged.connect(self.refresh_clients)
        new_btn = QPushButton("Nuevo cliente")
        new_btn.clicked.connect(self.clear_client_form)
        del_btn = QPushButton("Eliminar")
        del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self.delete_selected_client)
        top.addWidget(self.client_search, 1)
        top.addWidget(new_btn)
        top.addWidget(del_btn)
        layout.addLayout(top)
        body = QHBoxLayout()
        self.clients_table = self.table(["ID", "Razon social", "CUIT", "Telefono", "Correo", "Contacto"])
        self.clients_table.cellClicked.connect(self.load_client_from_table)
        body.addWidget(self.clients_table, 2)
        form_box = QGroupBox("Ficha del cliente")
        form = QFormLayout(form_box)
        self.client_fields = {name: QLineEdit() for name in ["business_name", "trade_name", "cuit", "address", "city", "province", "phone", "whatsapp", "email", "contact_name"]}
        labels = ["Razon social", "Nombre comercial", "CUIT", "Direccion", "Localidad", "Provincia", "Telefono", "WhatsApp", "Correo", "Contacto"]
        for label, field in zip(labels, self.client_fields.values()):
            form.addRow(label, field)
        self.client_notes = QPlainTextEdit()
        form.addRow("Observaciones", self.client_notes)
        save = QPushButton("Guardar cliente")
        save.clicked.connect(self.save_client)
        form.addRow(save)
        body.addWidget(form_box, 1)
        layout.addLayout(body, 1)
        return page

    def build_documents(self, doc_type: str):
        page, layout = self.page_layout(doc_type + "s", "Generacion, reimpresion, PDF y seguimiento de estados.")
        prefix = "budget" if doc_type == "Presupuesto" else "delivery"
        top = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText(f"Buscar {doc_type.lower()} por numero, cliente o estado")
        setattr(self, f"{prefix}_search", search)
        search.textChanged.connect(lambda: self.refresh_documents(doc_type))
        new_btn = QPushButton(f"Nuevo {doc_type.lower()}")
        new_btn.clicked.connect(lambda: self.clear_doc_form(doc_type))
        pdf_btn = QPushButton("Exportar PDF")
        pdf_btn.clicked.connect(self.export_selected_pdf)
        preview_btn = QPushButton("Vista previa")
        preview_btn.setObjectName("Ghost")
        preview_btn.clicked.connect(self.preview_selected_item)
        print_btn = QPushButton("Imprimir")
        print_btn.setObjectName("Ghost")
        print_btn.clicked.connect(self.print_selected_item)
        mail_btn = QPushButton("Enviar correo")
        mail_btn.setObjectName("Ghost")
        mail_btn.clicked.connect(self.email_selected_document)
        top.addWidget(search, 1)
        top.addWidget(new_btn)
        top.addWidget(preview_btn)
        top.addWidget(print_btn)
        top.addWidget(pdf_btn)
        top.addWidget(mail_btn)
        if doc_type == "Presupuesto":
            convert = QPushButton("Convertir a remito")
            convert.clicked.connect(self.convert_budget_to_delivery)
            top.addWidget(convert)
        layout.addLayout(top)
        body = QHBoxLayout()
        table = self.table(["ID", "Numero", "Fecha", "Cliente", "Estado", "Total"])
        setattr(self, f"{prefix}_table", table)
        table.cellClicked.connect(lambda row, _: self.load_doc_from_table(doc_type, row))
        body.addWidget(table, 2)
        form_box = QGroupBox(f"Editor de {doc_type.lower()}")
        form_layout = QVBoxLayout(form_box)
        self.doc_type = doc_type
        form = QFormLayout()
        number = QLineEdit()
        date_edit = QLineEdit(date.today().isoformat())
        client = QComboBox()
        status = QComboBox()
        status.addItems(["Borrador", "Enviado", "Aprobado", "Rechazado"] if doc_type == "Presupuesto" else ["Pendiente", "Entregado", "Facturado", "Anulado"])
        contact = QLineEdit()
        address = QLineEdit()
        phone = QLineEdit()
        setattr(self, f"{prefix}_fields", {"number": number, "date": date_edit, "client": client, "status": status, "contact": contact, "address": address, "phone": phone})
        for label, widget in [("Numero", number), ("Fecha", date_edit), ("Cliente", client), ("Estado", status), ("Contacto", contact), ("Direccion", address), ("Telefono", phone)]:
            form.addRow(label, widget)
        form_layout.addLayout(form)
        items = self.table(["Cant.", "Descripcion", "Unidad", "P. unit.", "Subtotal"])
        items.setMinimumWidth(620)
        items.setMinimumHeight(150)
        items.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for col, width in enumerate([78, 250, 80, 105, 105]):
            items.setColumnWidth(col, width)
        items.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        items.setRowCount(4)
        setattr(self, f"{prefix}_items", items)
        form_layout.addWidget(items)
        item_buttons = QHBoxLayout()
        add_item = QPushButton("Agregar item")
        add_item.clicked.connect(lambda: items.insertRow(items.rowCount()))
        remove_item = QPushButton("Quitar item")
        remove_item.setObjectName("Ghost")
        remove_item.clicked.connect(lambda: items.removeRow(max(items.currentRow(), 0)))
        item_buttons.addWidget(add_item)
        item_buttons.addWidget(remove_item)
        form_layout.addLayout(item_buttons)
        observations = QPlainTextEdit()
        setattr(self, f"{prefix}_observations", observations)
        form_layout.addWidget(QLabel("Observaciones"))
        form_layout.addWidget(observations)
        save = QPushButton(f"Guardar {doc_type.lower()}")
        save.clicked.connect(lambda: self.save_document(doc_type))
        form_layout.addWidget(save)
        form_box.setMinimumWidth(680)
        body.addWidget(form_box, 2)
        layout.addLayout(body, 1)
        return page

    def build_printing(self):
        page, layout = self.page_layout("Impresion profesional", "Vista previa, impresion directa, PDF y reimpresion historica en formato A4.")
        actions = QHBoxLayout()
        self.print_search = QLineEdit()
        self.print_search.setPlaceholderText("Buscar documento u orden por numero, cliente o estado")
        self.print_search.textChanged.connect(self.refresh_printing)
        preview = QPushButton("Vista previa")
        preview.clicked.connect(self.preview_selected_item)
        print_btn = QPushButton("Imprimir directo")
        print_btn.clicked.connect(self.print_selected_item)
        pdf = QPushButton("Exportar PDF")
        pdf.setObjectName("Ghost")
        pdf.clicked.connect(self.export_selected_pdf)
        actions.addWidget(self.print_search, 1)
        actions.addWidget(preview)
        actions.addWidget(print_btn)
        actions.addWidget(pdf)
        layout.addLayout(actions)
        self.print_table = self.table(["ID", "Tipo", "Numero", "Fecha", "Cliente", "Estado", "Total"])
        layout.addWidget(self.print_table, 1)
        note = QLabel("Presupuestos y ordenes se imprimen completos en A4. Los remitos imprimen solo datos variables sobre el papel preimpreso.")
        note.setObjectName("Hint")
        layout.addWidget(note)
        return page

    def build_orders(self):
        page, layout = self.page_layout("Ordenes de trabajo", "Seguimiento de produccion, responsables, materiales y entregas.")
        top = QHBoxLayout()
        self.order_search = QLineEdit()
        self.order_search.setPlaceholderText("Buscar orden por numero, cliente o estado")
        self.order_search.textChanged.connect(self.refresh_orders)
        new_btn = QPushButton("Nueva orden")
        new_btn.clicked.connect(self.clear_order_form)
        top.addWidget(self.order_search, 1)
        top.addWidget(new_btn)
        layout.addLayout(top)
        body = QHBoxLayout()
        self.orders_table = self.table(["ID", "Numero", "Cliente", "Responsable", "Inicio", "Entrega", "Estado"])
        self.orders_table.cellClicked.connect(self.load_order_from_table)
        body.addWidget(self.orders_table, 2)
        box = QGroupBox("Editor de orden")
        form = QFormLayout(box)
        self.order_fields = {
            "number": QLineEdit(),
            "client": QComboBox(),
            "responsible": QLineEdit(),
            "start_date": QLineEdit(date.today().isoformat()),
            "due_date": QLineEdit(date.today().isoformat()),
            "status": QComboBox(),
        }
        self.order_fields["status"].addItems(["Pendiente", "En Proceso", "Finalizado", "Entregado"])
        for label, key in [("Numero", "number"), ("Cliente", "client"), ("Responsable", "responsible"), ("Fecha inicio", "start_date"), ("Fecha entrega", "due_date"), ("Estado", "status")]:
            form.addRow(label, self.order_fields[key])
        self.order_work = QPlainTextEdit()
        self.order_materials = QPlainTextEdit()
        self.order_observations = QPlainTextEdit()
        form.addRow("Trabajo solicitado", self.order_work)
        form.addRow("Materiales", self.order_materials)
        form.addRow("Observaciones", self.order_observations)
        save = QPushButton("Guardar orden")
        save.clicked.connect(self.save_order)
        form.addRow(save)
        body.addWidget(box, 1)
        layout.addLayout(body, 1)
        return page

    def build_search(self):
        page, layout = self.page_layout("Buscar documentos", "Consulta rapida para reimprimir, exportar o revisar historial.")
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Buscar por numero, cliente o estado")
        self.global_search.textChanged.connect(self.refresh_search)
        self.search_table = self.table(["ID", "Tipo", "Numero", "Fecha", "Cliente", "Estado", "Total"])
        pdf = QPushButton("Exportar PDF seleccionado")
        pdf.clicked.connect(self.export_selected_pdf)
        mail = QPushButton("Enviar correo")
        mail.setObjectName("Ghost")
        mail.clicked.connect(self.email_selected_document)
        layout.addWidget(self.global_search)
        layout.addWidget(self.search_table, 1)
        actions = QHBoxLayout()
        actions.addWidget(pdf)
        actions.addWidget(mail)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def build_settings(self):
        page, layout = self.page_layout("Configuracion", "Datos corporativos, logo, backups y restauracion.")
        box = QGroupBox("Empresa")
        form = QFormLayout(box)
        self.company_fields = {key: QLineEdit() for key in [
            "name", "subtitle", "cuit", "address", "phone", "whatsapp", "email", "website",
            "iva_condition", "gross_income", "activity_start", "remito_cai", "remito_cai_due",
            "remito_offset_x_mm", "remito_offset_y_mm", "sale_conditions", "logo_path",
        ]}
        for label, key in [
            ("Razon social", "name"), ("Subtitulo", "subtitle"), ("CUIT", "cuit"),
            ("Direccion", "address"), ("Telefonos", "phone"), ("WhatsApp", "whatsapp"),
            ("Correo", "email"), ("Web", "website"), ("Condicion IVA", "iva_condition"),
            ("Ingresos brutos", "gross_income"), ("Inicio actividades", "activity_start"),
            ("CAI remito", "remito_cai"), ("Vencimiento CAI", "remito_cai_due"),
            ("Ajuste remito X mm", "remito_offset_x_mm"), ("Ajuste remito Y mm", "remito_offset_y_mm"),
            ("Condiciones de venta", "sale_conditions"), ("Logo", "logo_path"),
        ]:
            form.addRow(label, self.company_fields[key])
        pick_logo = QPushButton("Seleccionar logo")
        pick_logo.clicked.connect(self.pick_logo)
        self.company_notes = QPlainTextEdit()
        form.addRow(pick_logo)
        form.addRow("Leyendas legales", self.company_notes)
        save = QPushButton("Guardar configuracion")
        save.clicked.connect(self.save_company)
        form.addRow(save)
        layout.addWidget(box)
        backup_box = QGroupBox("Backups")
        backup_layout = QHBoxLayout(backup_box)
        make = QPushButton("Crear backup")
        make.clicked.connect(self.make_backup)
        restore = QPushButton("Restaurar backup")
        restore.setObjectName("Ghost")
        restore.clicked.connect(self.restore_backup)
        backup_layout.addWidget(make)
        backup_layout.addWidget(restore)
        backup_layout.addStretch()
        layout.addWidget(backup_box)
        network_box = QGroupBox("Uso en varias computadoras")
        network_layout = QFormLayout(network_box)
        self.data_dir_field = QLineEdit(str(data_dir()))
        choose_data = QPushButton("Elegir carpeta compartida")
        choose_data.clicked.connect(self.pick_data_dir)
        network_layout.addRow("Base de datos actual", self.data_dir_field)
        network_layout.addRow(choose_data)
        layout.addWidget(network_box)
        layout.addStretch()
        return page

    def table(self, headers):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        return table

    def show_page(self, key: str):
        self.stack.setCurrentWidget(self.pages[key])
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        self.refresh_all()

    def refresh_all(self):
        self.refresh_clients()
        self.refresh_documents("Presupuesto")
        self.refresh_documents("Remito")
        self.refresh_orders()
        self.refresh_search()
        self.refresh_printing()
        self.refresh_dashboard()
        self.refresh_company()
        self.populate_client_combos()

    def populate(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(value)))

    def refresh_dashboard(self):
        stats = repo.dashboard_stats()
        for key, label in self.stat_labels.items():
            value = stats[key]
            label.setText(format_money(value) if key == "budget_amount" else str(value))
        self.month_chart.set_values([(row["month"], row["amount"] or 0) for row in stats["monthly"]])
        self.client_chart.set_values([(row["business_name"][:12], row["amount"] or 0) for row in stats["top_clients"]])

    def refresh_clients(self):
        if not hasattr(self, "clients_table"):
            return
        rows = repo.list_clients(self.client_search.text() if hasattr(self, "client_search") else "")
        self.populate(self.clients_table, [[r["id"], r["business_name"], r.get("cuit") or "", r.get("phone") or "", r.get("email") or "", r.get("contact_name") or ""] for r in rows])

    def clear_client_form(self):
        self.current_client_id = None
        for field in self.client_fields.values():
            field.clear()
        self.client_notes.clear()

    def load_client_from_table(self, row, _):
        client_id = int(self.clients_table.item(row, 0).text())
        data = next(c for c in repo.list_clients() if c["id"] == client_id)
        self.current_client_id = client_id
        for key, field in self.client_fields.items():
            field.setText(str(data.get(key) or ""))
        self.client_notes.setPlainText(data.get("notes") or "")

    def save_client(self):
        data = {key: field.text().strip() for key, field in self.client_fields.items()}
        if not data["business_name"]:
            QMessageBox.warning(self, "Cliente", "La razon social es obligatoria.")
            return
        data["id"] = self.current_client_id
        data["notes"] = self.client_notes.toPlainText()
        self.current_client_id = repo.save_client(data)
        self.refresh_all()
        QMessageBox.information(self, "Cliente", "Cliente guardado correctamente.")

    def delete_selected_client(self):
        row = self.clients_table.currentRow()
        if row < 0:
            return
        client_id = int(self.clients_table.item(row, 0).text())
        if QMessageBox.question(self, "Eliminar", "Desea eliminar el cliente seleccionado?") == QMessageBox.Yes:
            repo.delete_client(client_id)
            self.clear_client_form()
            self.refresh_all()

    def populate_client_combos(self):
        clients = repo.list_clients()
        for combo in [getattr(self, "budget_fields", {}).get("client"), getattr(self, "delivery_fields", {}).get("client"), getattr(self, "order_fields", {}).get("client")]:
            if not combo:
                continue
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for client in clients:
                combo.addItem(client["business_name"], client["id"])
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def refresh_documents(self, doc_type: str):
        prefix = "budget" if doc_type == "Presupuesto" else "delivery"
        table = getattr(self, f"{prefix}_table", None)
        if table is None:
            return
        search = getattr(self, f"{prefix}_search").text()
        rows = repo.list_documents(doc_type, search)
        self.populate(table, [[r["id"], r["number"], r["date"], r["client_name"], r["status"], format_money(r["total"])] for r in rows])

    def clear_doc_form(self, doc_type: str):
        self.current_doc_id = None
        prefix = "budget" if doc_type == "Presupuesto" else "delivery"
        fields = getattr(self, f"{prefix}_fields")
        fields["number"].setText("Se asigna al guardar")
        fields["date"].setText(date.today().isoformat())
        fields["contact"].clear()
        fields["address"].clear()
        fields["phone"].clear()
        getattr(self, f"{prefix}_observations").clear()
        items = getattr(self, f"{prefix}_items")
        items.setRowCount(4)
        for r in range(items.rowCount()):
            for c in range(items.columnCount()):
                items.setItem(r, c, QTableWidgetItem(""))

    def load_doc_from_table(self, doc_type: str, row: int):
        prefix = "budget" if doc_type == "Presupuesto" else "delivery"
        table = getattr(self, f"{prefix}_table")
        doc_id = int(table.item(row, 0).text())
        doc, items = repo.get_document(doc_id)
        self.current_doc_id = doc_id
        fields = getattr(self, f"{prefix}_fields")
        for key in ["number", "date", "contact", "address", "phone"]:
            fields[key].setText(str(doc.get(key) or ""))
        fields["status"].setCurrentText(doc["status"])
        idx = fields["client"].findData(doc["client_id"])
        if idx >= 0:
            fields["client"].setCurrentIndex(idx)
        table_items = getattr(self, f"{prefix}_items")
        table_items.setRowCount(max(len(items), 1))
        for r, item in enumerate(items):
            for c, key in enumerate(["quantity", "description", "unit", "unit_price", "subtotal"]):
                table_items.setItem(r, c, QTableWidgetItem(str(item[key])))
        getattr(self, f"{prefix}_observations").setPlainText(doc.get("observations") or "")

    def collect_items(self, table):
        items = []
        for row in range(table.rowCount()):
            vals = [table.item(row, col).text().strip() if table.item(row, col) else "" for col in range(4)]
            if not any(vals):
                continue
            quantity = float(vals[0].replace(",", ".") or 0)
            description = vals[1]
            unit = vals[2] or "u"
            price = float(vals[3].replace(",", ".") or 0)
            if description:
                items.append({"quantity": quantity, "description": description, "unit": unit, "unit_price": price})
        return items

    def save_document(self, doc_type: str):
        prefix = "budget" if doc_type == "Presupuesto" else "delivery"
        fields = getattr(self, f"{prefix}_fields")
        items = self.collect_items(getattr(self, f"{prefix}_items"))
        if not fields["number"].text().strip() or not fields["client"].currentData() or not items:
            QMessageBox.warning(self, doc_type, "Complete cliente y al menos un item.")
            return
        doc = {
            "id": self.current_doc_id,
            "doc_type": doc_type,
            "number": fields["number"].text().strip(),
            "date": fields["date"].text().strip(),
            "client_id": fields["client"].currentData(),
            "contact": fields["contact"].text().strip(),
            "address": fields["address"].text().strip(),
            "phone": fields["phone"].text().strip(),
            "status": fields["status"].currentText(),
            "observations": getattr(self, f"{prefix}_observations").toPlainText(),
            "source_document_id": None,
        }
        self.current_doc_id = repo.save_document(doc, items)
        saved_doc, _ = repo.get_document(self.current_doc_id)
        fields["number"].setText(saved_doc["number"])
        self.refresh_all()
        QMessageBox.information(self, doc_type, f"{doc_type} guardado correctamente.")

    def selected_document_id(self):
        page = self.stack.currentWidget()
        tables = [getattr(self, name, None) for name in ["budget_table", "delivery_table", "search_table"]]
        for table in tables:
            if table and table.isVisible() and table.currentRow() >= 0:
                return int(table.item(table.currentRow(), 0).text())
        return self.current_doc_id

    def selected_print_item(self):
        if hasattr(self, "print_table") and self.print_table.isVisible() and self.print_table.currentRow() >= 0:
            row = self.print_table.currentRow()
            return self.print_table.item(row, 1).text(), int(self.print_table.item(row, 0).text())
        page_tables = [
            ("Presupuesto", getattr(self, "budget_table", None)),
            ("Remito", getattr(self, "delivery_table", None)),
            ("Documento", getattr(self, "search_table", None)),
            ("Orden de Trabajo", getattr(self, "orders_table", None)),
        ]
        for item_type, table in page_tables:
            if table and table.isVisible() and table.currentRow() >= 0:
                if item_type == "Documento":
                    item_type = table.item(table.currentRow(), 1).text()
                return item_type, int(table.item(table.currentRow(), 0).text())
        if self.current_doc_id:
            return "Documento", self.current_doc_id
        if self.current_order_id:
            return "Orden de Trabajo", self.current_order_id
        return None

    def export_item_pdf(self, item_type: str, item_id: int) -> Path:
        if item_type == "Orden de Trabajo":
            return export_work_order_pdf(item_id)
        return export_document_pdf(item_id)

    def export_selected_pdf(self):
        selected = self.selected_print_item()
        if not selected:
            QMessageBox.warning(self, "PDF", "Seleccione o guarde un documento primero.")
            return
        path = self.export_item_pdf(*selected)
        QMessageBox.information(self, "PDF", f"PDF generado:\n{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def preview_selected_item(self):
        selected = self.selected_print_item()
        if not selected:
            QMessageBox.warning(self, "Vista previa", "Seleccione un documento u orden primero.")
            return
        path = self.export_item_pdf(*selected)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def print_selected_item(self):
        selected = self.selected_print_item()
        if not selected:
            QMessageBox.warning(self, "Impresion", "Seleccione un documento u orden primero.")
            return
        path = self.export_item_pdf(*selected)
        if self.print_pdf_with_dialog(path):
            QMessageBox.information(self, "Impresion", "Documento enviado a impresion.")
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            QMessageBox.warning(self, "Impresion", "No se pudo imprimir desde el dialogo interno. Se abrio la vista previa del PDF.")

    def print_pdf_with_dialog(self, path: Path) -> bool:
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPrinter.A4)
        printer.setFullPage(False)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.Accepted:
            return True
        doc = QPdfDocument(self)
        if doc.load(str(path)) != QPdfDocument.Error.None_:
            return False
        painter = QPainter(printer)
        if not painter.isActive():
            return False
        try:
            for page in range(doc.pageCount()):
                if page:
                    printer.newPage()
                rect = painter.viewport()
                image = doc.render(page, rect.size())
                if image.isNull():
                    return False
                painter.drawImage(rect, image)
            return True
        finally:
            painter.end()

    def email_selected_document(self):
        doc_id = self.selected_document_id()
        if not doc_id:
            QMessageBox.warning(self, "Correo", "Seleccione un documento primero.")
            return
        doc, _ = repo.get_document(doc_id)
        path = export_document_pdf(doc_id)
        subject = f"{doc['doc_type']} {doc['number']} - INITROF SRL"
        body = (
            f"Estimado/a,\n\nAdjuntamos {doc['doc_type'].lower()} {doc['number']} de INITROF SRL.\n"
            f"PDF generado en: {path}\n\nSaludos."
        )
        url = QUrl()
        url.setScheme("mailto")
        url.setPath(doc.get("client_email") or "")
        url.setQuery(f"subject={subject}&body={body}")
        QDesktopServices.openUrl(url)
        QMessageBox.information(self, "Correo", "Se abrio el cliente de correo predeterminado. Adjunte el PDF generado si su cliente no lo agrega automaticamente.")

    def convert_budget_to_delivery(self):
        row = self.budget_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Remito", "Seleccione un presupuesto aprobado o enviado.")
            return
        source_id = int(self.budget_table.item(row, 0).text())
        doc, items = repo.get_document(source_id)
        new_doc = {
            "doc_type": "Remito",
            "number": repo.next_number("Remito"),
            "date": date.today().isoformat(),
            "client_id": doc["client_id"],
            "contact": doc.get("contact"),
            "address": doc.get("address"),
            "phone": doc.get("phone"),
            "status": "Pendiente",
            "observations": f"Generado desde presupuesto {doc['number']}",
            "source_document_id": source_id,
        }
        repo.save_document(new_doc, items)
        self.refresh_all()
        self.show_page("delivery")

    def refresh_orders(self):
        if not hasattr(self, "orders_table"):
            return
        rows = repo.list_work_orders(self.order_search.text() if hasattr(self, "order_search") else "")
        self.populate(self.orders_table, [[r["id"], r["number"], r["client_name"], r.get("responsible") or "", r["start_date"], r.get("due_date") or "", r["status"]] for r in rows])

    def refresh_printing(self):
        if not hasattr(self, "print_table"):
            return
        rows = repo.list_printables(self.print_search.text() if hasattr(self, "print_search") else "")
        self.populate(self.print_table, [[r["id"], r["item_type"], r["number"], r["date"], r["client_name"], r["status"], format_money(r["total"]) if r["total"] else "-"] for r in rows])

    def clear_order_form(self):
        self.current_order_id = None
        self.order_fields["number"].setText("Se asigna al guardar")
        self.order_fields["start_date"].setText(date.today().isoformat())
        self.order_fields["due_date"].setText(date.today().isoformat())
        self.order_fields["responsible"].clear()
        self.order_work.clear()
        self.order_materials.clear()
        self.order_observations.clear()

    def load_order_from_table(self, row, _):
        order_id = int(self.orders_table.item(row, 0).text())
        order = next(o for o in repo.list_work_orders() if o["id"] == order_id)
        self.current_order_id = order_id
        for key in ["number", "responsible", "start_date", "due_date"]:
            self.order_fields[key].setText(str(order.get(key) or ""))
        self.order_fields["status"].setCurrentText(order["status"])
        idx = self.order_fields["client"].findData(order["client_id"])
        if idx >= 0:
            self.order_fields["client"].setCurrentIndex(idx)
        self.order_work.setPlainText(order.get("requested_work") or "")
        self.order_materials.setPlainText(order.get("materials") or "")
        self.order_observations.setPlainText(order.get("observations") or "")

    def save_order(self):
        data = {
            "id": self.current_order_id,
            "number": self.order_fields["number"].text().strip(),
            "client_id": self.order_fields["client"].currentData(),
            "responsible": self.order_fields["responsible"].text().strip(),
            "start_date": self.order_fields["start_date"].text().strip(),
            "due_date": self.order_fields["due_date"].text().strip(),
            "status": self.order_fields["status"].currentText(),
            "requested_work": self.order_work.toPlainText(),
            "materials": self.order_materials.toPlainText(),
            "observations": self.order_observations.toPlainText(),
        }
        if not data["number"] or not data["client_id"]:
            QMessageBox.warning(self, "Orden", "Complete cliente.")
            return
        self.current_order_id = repo.save_work_order(data)
        self.order_fields["number"].setText(next(o["number"] for o in repo.list_work_orders() if o["id"] == self.current_order_id))
        self.refresh_all()
        QMessageBox.information(self, "Orden", "Orden guardada correctamente.")

    def refresh_search(self):
        if not hasattr(self, "search_table"):
            return
        rows = repo.list_documents(None, self.global_search.text() if hasattr(self, "global_search") else "")
        self.populate(self.search_table, [[r["id"], r["doc_type"], r["number"], r["date"], r["client_name"], r["status"], format_money(r["total"])] for r in rows])

    def refresh_company(self):
        if not hasattr(self, "company_fields"):
            return
        company = repo.fetch_company()
        for key, field in self.company_fields.items():
            field.setText(str(company.get(key) or ""))
        self.company_notes.setPlainText(company.get("legal_notes") or "")

    def pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar logo", "", "Imagenes (*.png *.jpg *.jpeg)")
        if path:
            self.company_fields["logo_path"].setText(path)

    def save_company(self):
        data = {key: field.text().strip() for key, field in self.company_fields.items()}
        data["legal_notes"] = self.company_notes.toPlainText()
        repo.update_company(data)
        QMessageBox.information(self, "Configuracion", "Configuracion guardada.")

    def pick_data_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta compartida para la base", str(data_dir()))
        if not folder:
            return
        set_configured_data_dir(Path(folder))
        self.data_dir_field.setText(folder)
        QMessageBox.information(
            self,
            "Base compartida",
            "Carpeta configurada. Reinicie la aplicacion en esta PC y configure la misma carpeta en las demas computadoras.",
        )

    def make_backup(self):
        path = create_backup()
        QMessageBox.information(self, "Backup", f"Backup creado:\n{path}")

    def restore_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restaurar backup", "", "SQLite (*.sqlite *.db)")
        if path and QMessageBox.question(self, "Restaurar", "La base actual sera reemplazada. Continuar?") == QMessageBox.Yes:
            restore_backup(Path(path))
            self.refresh_all()
            QMessageBox.information(self, "Backup", "Backup restaurado correctamente.")


def main() -> int:
    initialize_database()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = MainWindow()
    window.show()
    return app.exec()
