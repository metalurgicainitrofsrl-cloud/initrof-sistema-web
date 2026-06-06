const state = {
  clients: [],
  budgets: [],
  delivery: [],
  orders: [],
  printables: [],
  company: {},
  selected: { client: null, budget: null, delivery: null, order: null, print: null },
};

const $ = (id) => document.getElementById(id);

function money(value) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(Number(value || 0));
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2400);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 401) location.href = "/login";
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function setView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  document.querySelectorAll(".sidebar nav button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
  const titles = {
    dashboard: ["Panel", "Gestion centralizada accesible desde cualquier computadora."],
    clients: ["Clientes", "Alta, modificacion y consulta de clientes."],
    budgets: ["Presupuestos", "Generacion de presupuestos, PDF y conversion a remito."],
    delivery: ["Remitos", "Carga y reimpresion sobre remito preimpreso."],
    orders: ["Ordenes de trabajo", "Seguimiento de tareas, responsables y materiales."],
    printing: ["Impresion", "Vista previa, PDF y reimpresion historica."],
    settings: ["Configuracion", "Datos fiscales, logo, offsets de remito y clave."],
  };
  $("view-title").textContent = titles[name][0];
  $("view-hint").textContent = titles[name][1];
}

function table(el, headers, rows, selectedId, onClick) {
  el.innerHTML = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody></tbody>`;
  const tbody = el.querySelector("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.dataset.id = row.id;
    if (String(row.id) === String(selectedId)) tr.classList.add("selected");
    tr.innerHTML = headers.map((h) => `<td>${row[h] ?? ""}</td>`).join("");
    tr.addEventListener("click", () => onClick(row.id));
    tbody.appendChild(tr);
  });
}

function input(name, label, value = "", type = "text", cls = "") {
  return `<div class="${cls}"><label>${label}</label><input name="${name}" type="${type}" value="${String(value ?? "").replaceAll('"', "&quot;")}"></div>`;
}

function textarea(name, label, value = "", cls = "full") {
  return `<div class="${cls}"><label>${label}</label><textarea name="${name}">${String(value ?? "")}</textarea></div>`;
}

function select(name, label, options, value = "", cls = "") {
  return `<div class="${cls}"><label>${label}</label><select name="${name}">${options.map((opt) => `<option value="${opt.value}" ${String(opt.value) === String(value) ? "selected" : ""}>${opt.label}</option>`).join("")}</select></div>`;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function loadAll() {
  const data = await api("/api/bootstrap");
  Object.assign(state, {
    clients: data.clients,
    budgets: data.budgets,
    delivery: data.delivery_notes,
    orders: data.orders,
    printables: data.printables,
    company: data.company,
  });
  renderAll();
}

function renderAll() {
  renderDashboard();
  renderClients();
  renderDocuments("Presupuesto");
  renderDocuments("Remito");
  renderOrders();
  renderPrinting();
  renderCompany();
}

function renderDashboard() {
  const labels = [
    ["budgets_month", "Presupuestos del mes"],
    ["delivery_notes", "Remitos emitidos"],
    ["open_orders", "Ordenes abiertas"],
    ["active_clients", "Clientes activos"],
    ["budget_amount", "Importe presupuestado"],
  ];
  api("/api/bootstrap").then((data) => {
    $("stats").innerHTML = labels.map(([key, label]) => `<div class="stat"><span>${label}</span><strong>${key === "budget_amount" ? money(data.stats[key]) : data.stats[key]}</strong></div>`).join("");
    miniList($("dash-budgets"), data.budgets, "Presupuesto");
    miniList($("dash-delivery"), data.delivery_notes, "Remito");
  });
}

function miniList(el, rows, type) {
  el.innerHTML = rows.length ? rows.map((r) => `<p><strong>${r.number}</strong> ${r.client_name} <span class="hint">${money(r.total)}</span></p>`).join("") : `<p class="hint">Sin ${type.toLowerCase()}s cargados.</p>`;
}

function renderClients() {
  table($("clients-table"), ["ID", "Razon social", "CUIT", "Telefono", "Correo"], state.clients.map((c) => ({
    id: c.id, ID: c.id, "Razon social": c.business_name, CUIT: c.cuit || "", Telefono: c.phone || "", Correo: c.email || "",
  })), state.selected.client, selectClient);
  renderClientForm(state.clients.find((c) => c.id === state.selected.client) || {});
}

function renderClientForm(client) {
  $("client-form").innerHTML = [
    input("business_name", "Razon social", client.business_name),
    input("trade_name", "Nombre comercial", client.trade_name),
    input("cuit", "CUIT", client.cuit),
    input("contact_name", "Contacto", client.contact_name),
    input("address", "Direccion", client.address, "text", "full"),
    input("city", "Localidad", client.city),
    input("province", "Provincia", client.province),
    input("phone", "Telefono", client.phone),
    input("whatsapp", "WhatsApp", client.whatsapp),
    input("email", "Correo", client.email, "email", "full"),
    textarea("notes", "Observaciones / condicion IVA", client.notes),
    `<div class="full"><button>Guardar cliente</button> <button type="button" class="secondary" id="clear-client">Limpiar</button></div>`,
  ].join("");
  $("client-form").onsubmit = saveClient;
  $("clear-client").onclick = () => { state.selected.client = null; renderClients(); };
}

async function selectClient(id) {
  state.selected.client = id;
  renderClients();
}

async function saveClient(event) {
  event.preventDefault();
  const data = formData(event.target);
  if (!data.business_name.trim()) return toast("La razon social es obligatoria.");
  data.id = state.selected.client;
  await api("/api/clients", { method: "POST", body: JSON.stringify(data) });
  state.clients = await api("/api/clients");
  state.selected.client = null;
  renderClients();
  toast("Cliente guardado.");
}

function clientOptions() {
  return state.clients.map((c) => ({ value: c.id, label: c.business_name }));
}

function renderDocuments(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const rows = type === "Presupuesto" ? state.budgets : state.delivery;
  table($(`${key}s-table`) || $(`${key}-table`), ["ID", "Numero", "Fecha", "Cliente", "Estado", "Total"], rows.map((d) => ({
    id: d.id, ID: d.id, Numero: d.number, Fecha: d.date, Cliente: d.client_name, Estado: d.status, Total: money(d.total),
  })), state.selected[key], (id) => selectDocument(type, id));
  renderDocumentForm(type, rows.find((d) => d.id === state.selected[key]));
}

async function selectDocument(type, id) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  state.selected[key] = id;
  const payload = await api(`/api/documents/${id}`);
  state[`${key}Detail`] = payload;
  renderDocumentForm(type, payload.document, payload.items);
  renderDocuments(type);
}

function renderDocumentForm(type, doc = {}, items = null) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const statuses = type === "Presupuesto"
    ? ["Borrador", "Enviado", "Aprobado", "Rechazado"]
    : ["Pendiente", "Entregado", "Facturado", "Anulado"];
  const currentItems = items || [{ quantity: 1, description: "", unit: "u", unit_price: 0 }];
  $(`${key}-form`).innerHTML = [
    `<div class="form-grid">`,
    input("number", "Numero", doc.number || "Se asigna al guardar"),
    input("date", "Fecha", doc.date || window.INITROF_TODAY, "date"),
    select("client_id", "Cliente", clientOptions(), doc.client_id),
    select("status", "Estado", statuses.map((s) => ({ value: s, label: s })), doc.status || statuses[0]),
    input("contact", "Contacto", doc.contact),
    input("phone", "Telefono", doc.phone),
    input("address", "Direccion", doc.address, "text", "full"),
    `</div>`,
    `<label>Items</label><div class="item-actions"><button type="button" id="${key}-add-item">Agregar item</button><button type="button" class="secondary" id="${key}-remove-item">Quitar ultimo</button></div>`,
    `<table class="items" id="${key}-items"><thead><tr><th>Cant.</th><th>Descripcion</th><th>Unidad</th><th>P. unitario</th><th>Subtotal</th></tr></thead><tbody>${currentItems.map(itemRow).join("")}</tbody></table>`,
    `<div class="totals" id="${key}-total"></div>`,
    textarea("observations", "Observaciones", doc.observations || ""),
    `<button>Guardar ${type.toLowerCase()}</button> <button type="button" class="secondary" id="${key}-clear">Limpiar</button>`,
  ].join("");
  $(`${key}-form`).onsubmit = (event) => saveDocument(event, type);
  $(`${key}-add-item`).onclick = () => { $(`${key}-items`).querySelector("tbody").insertAdjacentHTML("beforeend", itemRow({ quantity: 1, unit: "u", unit_price: 0 })); bindItemTotals(key); };
  $(`${key}-remove-item`).onclick = () => { const tbody = $(`${key}-items`).querySelector("tbody"); if (tbody.children.length > 1) tbody.lastElementChild.remove(); updateTotals(key); };
  $(`${key}-clear`).onclick = () => { state.selected[key] = null; renderDocumentForm(type); renderDocuments(type); };
  bindItemTotals(key);
}

function itemRow(item = {}) {
  return `<tr>
    <td><input name="quantity" type="number" step="0.01" value="${item.quantity ?? 1}"></td>
    <td><input name="description" value="${item.description || ""}"></td>
    <td><input name="unit" value="${item.unit || "u"}"></td>
    <td><input name="unit_price" type="number" step="0.01" value="${item.unit_price ?? 0}"></td>
    <td class="line-total">${money((item.quantity || 0) * (item.unit_price || 0))}</td>
  </tr>`;
}

function bindItemTotals(key) {
  $(`${key}-items`).querySelectorAll("input").forEach((inputEl) => inputEl.addEventListener("input", () => updateTotals(key)));
  updateTotals(key);
}

function collectItems(key) {
  return [...$(`${key}-items`).querySelectorAll("tbody tr")].map((tr) => {
    const fields = tr.querySelectorAll("input");
    return {
      quantity: Number(fields[0].value || 0),
      description: fields[1].value.trim(),
      unit: fields[2].value.trim() || "u",
      unit_price: Number(fields[3].value || 0),
    };
  }).filter((item) => item.description);
}

function updateTotals(key) {
  let total = 0;
  $(`${key}-items`).querySelectorAll("tbody tr").forEach((tr) => {
    const fields = tr.querySelectorAll("input");
    const subtotal = Number(fields[0].value || 0) * Number(fields[3].value || 0);
    tr.querySelector(".line-total").textContent = money(subtotal);
    total += subtotal * 1.21;
  });
  $(`${key}-total`).textContent = `Total estimado con IVA: ${money(total)}`;
}

async function saveDocument(event, type) {
  event.preventDefault();
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const data = formData(event.target);
  const items = collectItems(key);
  if (!data.client_id || !items.length) return toast("Complete cliente y al menos un item.");
  const payload = {
    document: {
      id: state.selected[key],
      doc_type: type,
      number: data.number,
      date: data.date,
      client_id: Number(data.client_id),
      contact: data.contact,
      address: data.address,
      phone: data.phone,
      status: data.status,
      observations: data.observations,
      source_document_id: null,
    },
    items,
  };
  const saved = await api("/api/documents", { method: "POST", body: JSON.stringify(payload) });
  state.selected[key] = saved.document.id;
  await refreshLists();
  await selectDocument(type, saved.document.id);
  toast(`${type} guardado.`);
}

async function refreshLists() {
  state.clients = await api("/api/clients");
  state.budgets = await api("/api/documents?doc_type=Presupuesto");
  state.delivery = await api("/api/documents?doc_type=Remito");
  state.orders = await api("/api/orders");
  state.printables = (await api("/api/bootstrap")).printables;
  renderAll();
}

function openSelectedPdf(type) {
  const key = type === "Presupuesto" ? "budget" : type === "Remito" ? "delivery" : "order";
  const id = state.selected[key];
  if (!id) return toast("Seleccione un registro primero.");
  window.open(type === "Orden" ? `/pdf/order/${id}` : `/pdf/document/${id}`, "_blank");
}

async function convertSelectedBudget() {
  if (!state.selected.budget) return toast("Seleccione un presupuesto.");
  const saved = await api(`/api/documents/${state.selected.budget}/convert-to-remito`, { method: "POST" });
  state.selected.delivery = saved.document.id;
  await refreshLists();
  setView("delivery");
  toast("Remito generado con numeracion consecutiva.");
}

function renderOrders() {
  table($("orders-table"), ["ID", "Numero", "Cliente", "Responsable", "Inicio", "Estado"], state.orders.map((o) => ({
    id: o.id, ID: o.id, Numero: o.number, Cliente: o.client_name, Responsable: o.responsible || "", Inicio: o.start_date, Estado: o.status,
  })), state.selected.order, selectOrder);
  renderOrderForm();
}

async function selectOrder(id) {
  state.selected.order = id;
  state.orderDetail = await api(`/api/orders/${id}`);
  renderOrders();
  renderOrderForm(state.orderDetail);
}

function renderOrderForm(order = {}) {
  $("order-form").innerHTML = [
    input("number", "Numero", order.number || "Se asigna al guardar"),
    select("client_id", "Cliente", clientOptions(), order.client_id),
    input("responsible", "Responsable", order.responsible),
    input("start_date", "Fecha inicio", order.start_date || window.INITROF_TODAY, "date"),
    input("due_date", "Fecha entrega", order.due_date || window.INITROF_TODAY, "date"),
    select("status", "Estado", ["Pendiente", "En Proceso", "Finalizado", "Entregado"].map((s) => ({ value: s, label: s })), order.status || "Pendiente", "full"),
    textarea("requested_work", "Trabajo solicitado", order.requested_work),
    textarea("materials", "Materiales", order.materials),
    textarea("observations", "Observaciones", order.observations),
    `<div class="full"><button>Guardar orden</button> <button type="button" class="secondary" id="clear-order">Limpiar</button></div>`,
  ].join("");
  $("order-form").onsubmit = saveOrder;
  $("clear-order").onclick = () => { state.selected.order = null; renderOrderForm(); renderOrders(); };
}

async function saveOrder(event) {
  event.preventDefault();
  const data = formData(event.target);
  data.id = state.selected.order;
  data.client_id = Number(data.client_id);
  if (!data.client_id) return toast("Seleccione cliente.");
  const saved = await api("/api/orders", { method: "POST", body: JSON.stringify(data) });
  state.selected.order = saved.id;
  await refreshLists();
  toast("Orden guardada.");
}

function renderPrinting() {
  table($("print-table"), ["ID", "Tipo", "Numero", "Fecha", "Cliente", "Estado", "Total"], state.printables.map((p) => ({
    id: `${p.item_type}:${p.id}`, ID: p.id, Tipo: p.item_type, Numero: p.number, Fecha: p.date, Cliente: p.client_name, Estado: p.status, Total: p.total ? money(p.total) : "-",
  })), state.selected.print, (id) => { state.selected.print = id; renderPrinting(); });
}

function openPrintable() {
  if (!state.selected.print) return toast("Seleccione un documento.");
  const [type, id] = String(state.selected.print).split(":");
  window.open(type === "Orden de Trabajo" ? `/pdf/order/${id}` : `/pdf/document/${id}`, "_blank");
}

function renderCompany() {
  const c = state.company || {};
  $("company-form").innerHTML = [
    input("name", "Nombre", c.name),
    input("subtitle", "Rubro", c.subtitle),
    input("cuit", "CUIT", c.cuit),
    input("iva_condition", "IVA", c.iva_condition),
    input("gross_income", "Ingresos brutos", c.gross_income),
    input("activity_start", "Inicio actividad", c.activity_start),
    input("address", "Direccion", c.address, "text", "full"),
    input("phone", "Telefono", c.phone),
    input("whatsapp", "WhatsApp", c.whatsapp),
    input("email", "Correo", c.email, "email"),
    input("website", "Web", c.website),
    input("remito_cai", "CAI remito", c.remito_cai),
    input("remito_cai_due", "Vencimiento CAI", c.remito_cai_due),
    input("remito_offset_x_mm", "Ajuste remito X mm", c.remito_offset_x_mm, "number"),
    input("remito_offset_y_mm", "Ajuste remito Y mm", c.remito_offset_y_mm, "number"),
    input("sale_conditions", "Condiciones de venta", c.sale_conditions, "text", "full"),
    textarea("legal_notes", "Notas legales", c.legal_notes),
    `<input type="hidden" name="logo_path" value="${c.logo_path || ""}"><div class="full"><button>Guardar configuracion</button></div>`,
  ].join("");
  $("company-form").onsubmit = saveCompany;
}

async function saveCompany(event) {
  event.preventDefault();
  state.company = await api("/api/company", { method: "POST", body: JSON.stringify(formData(event.target)) });
  toast("Configuracion guardada.");
}

async function uploadLogo(event) {
  event.preventDefault();
  const response = await fetch("/api/company/logo", { method: "POST", body: new FormData(event.target) });
  if (!response.ok) return toast("No se pudo subir el logo.");
  toast("Logo actualizado.");
  setTimeout(() => location.reload(), 800);
}

async function savePassword() {
  const password = $("new-password").value;
  if (password.length < 8) return toast("La clave debe tener al menos 8 caracteres.");
  await api("/api/password", { method: "POST", body: JSON.stringify({ password }) });
  $("new-password").value = "";
  toast("Clave actualizada.");
}

function bindEvents() {
  document.querySelectorAll(".sidebar nav button").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
  $("new-client").onclick = () => { state.selected.client = null; renderClients(); };
  $("new-budget").onclick = () => { state.selected.budget = null; renderDocumentForm("Presupuesto"); };
  $("new-delivery").onclick = () => { state.selected.delivery = null; renderDocumentForm("Remito"); };
  $("new-order").onclick = () => { state.selected.order = null; renderOrderForm(); };
  $("budget-pdf").onclick = () => openSelectedPdf("Presupuesto");
  $("delivery-pdf").onclick = () => openSelectedPdf("Remito");
  $("order-pdf").onclick = () => openSelectedPdf("Orden");
  $("budget-convert").onclick = convertSelectedBudget;
  $("print-open").onclick = openPrintable;
  $("logo-form").onsubmit = uploadLogo;
  $("save-password").onclick = savePassword;
  $("client-search").addEventListener("input", async (event) => { state.clients = await api(`/api/clients?search=${encodeURIComponent(event.target.value)}`); renderClients(); });
  $("budget-search").addEventListener("input", async (event) => { state.budgets = await api(`/api/documents?doc_type=Presupuesto&search=${encodeURIComponent(event.target.value)}`); renderDocuments("Presupuesto"); });
  $("delivery-search").addEventListener("input", async (event) => { state.delivery = await api(`/api/documents?doc_type=Remito&search=${encodeURIComponent(event.target.value)}`); renderDocuments("Remito"); });
  $("order-search").addEventListener("input", async (event) => { state.orders = await api(`/api/orders?search=${encodeURIComponent(event.target.value)}`); renderOrders(); });
  $("print-search").addEventListener("input", async (event) => { state.printables = (await api(`/api/bootstrap`)).printables.filter((p) => JSON.stringify(p).toLowerCase().includes(event.target.value.toLowerCase())); renderPrinting(); });
}

bindEvents();
loadAll().catch((error) => toast(error.message));
