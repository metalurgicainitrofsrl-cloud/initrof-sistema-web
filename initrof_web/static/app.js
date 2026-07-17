const state = {
  clients: [],
  budgets: [],
  delivery: [],
  orders: [],
  printables: [],
  company: {},
  selected: { client: null, budget: null, delivery: null, order: null, print: null },
  orderDetail: null,
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value = "") {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function money(value) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(Number(value || 0));
}

function toast(message, type = "info") {
  const el = $("toast");
  el.textContent = message;
  el.className = type;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2400);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 401) location.href = "/login";
  if (!response.ok) {
    let message = await response.text();
    try {
      const payload = JSON.parse(message);
      message = payload.detail || payload.message || message;
    } catch (_) {
      message = message || "No se pudo completar la operacion.";
    }
    throw new Error(message);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

async function guard(action) {
  try {
    return await action();
  } catch (error) {
    console.error(error);
    toast(error.message || "Ocurrio un error inesperado.", "error");
    return null;
  }
}

function on(id, event, handler) {
  const el = $(id);
  if (!el) {
    console.warn(`Elemento no encontrado: ${id}`);
    return;
  }
  el.addEventListener(event, handler);
}

function setView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  document.querySelectorAll(".sidebar nav button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
  const titles = {
    dashboard: ["Panel", "Gestion centralizada accesible desde cualquier computadora."],
    clients: ["Clientes", "Alta, modificacion y consulta de clientes."],
    budgets: ["Presupuestos", "Generacion de presupuestos, PDF y conversion a remito."],
    delivery: ["Remitos", "Carga, PDF e impresion completa en hoja A4 blanca."],
    orders: ["Ordenes de trabajo", "Seguimiento de tareas, responsables y materiales."],
    printing: ["Impresion", "Vista previa, PDF y reimpresion historica."],
    settings: ["Configuracion", "Datos fiscales, logo, CAI de remito y clave."],
  };
  $("view-title").textContent = titles[name][0];
  $("view-hint").textContent = titles[name][1];
}

function table(el, headers, rows, selectedId, onClick) {
  el.innerHTML = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody></tbody>`;
  const tbody = el.querySelector("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${headers.length}" class="empty">Sin registros para mostrar.</td></tr>`;
    return;
  }
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.dataset.id = row.id;
    if (row.Estado) tr.classList.add("status-row", `status-${statusSlug(row.Estado)}`);
    if (String(row.id) === String(selectedId)) tr.classList.add("selected");
    tr.innerHTML = headers.map((h) => `<td>${cellHtml(h, row[h])}</td>`).join("");
    tr.addEventListener("click", () => onClick(row.id));
    tbody.appendChild(tr);
  });
}

function statusSlug(status) {
  return String(status || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, "-");
}

function cellHtml(header, value) {
  if (header === "Estado") {
    const label = escapeHtml(value ?? "");
    return `<span class="status-badge status-${statusSlug(value)}">${label}</span>`;
  }
  return escapeHtml(value ?? "");
}

function input(name, label, value = "", type = "text", cls = "", attrs = "") {
  return `<div class="${cls}"><label>${escapeHtml(label)}</label><input name="${escapeHtml(name)}" type="${escapeHtml(type)}" value="${escapeHtml(value)}" ${attrs}></div>`;
}

function textarea(name, label, value = "", cls = "full") {
  return `<div class="${cls}"><label>${escapeHtml(label)}</label><textarea name="${escapeHtml(name)}">${escapeHtml(value)}</textarea></div>`;
}

function select(name, label, options, value = "", cls = "") {
  return `<div class="${cls}"><label>${escapeHtml(label)}</label><select name="${escapeHtml(name)}">${options.map((opt) => `<option value="${escapeHtml(opt.value)}" ${String(opt.value) === String(value) ? "selected" : ""}>${escapeHtml(opt.label)}</option>`).join("")}</select></div>`;
}

function checkbox(name, label, checked = false, cls = "full") {
  return `<div class="${cls} checkbox-row"><label><input name="${escapeHtml(name)}" type="checkbox" value="1" ${checked ? "checked" : ""}> ${escapeHtml(label)}</label></div>`;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function documentShowsIva(doc = {}) {
  return doc.show_iva === undefined || doc.show_iva === null || String(doc.show_iva) !== "0";
}

function documentClientRespInscripto(doc = {}) {
  return doc.client_resp_inscripto === undefined || doc.client_resp_inscripto === null || String(doc.client_resp_inscripto) !== "0";
}

function clientDefaultRespInscripto(client = {}) {
  const notes = String(client.notes || "").toLowerCase();
  if (notes.includes("monotrib") || notes.includes("exento") || notes.includes("final")) return false;
  return true;
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
  }).catch((error) => toast(error.message, "error"));
}

function miniList(el, rows, type) {
  el.innerHTML = rows.length ? rows.map((r) => `<p><strong>${escapeHtml(r.number)}</strong> ${escapeHtml(r.client_name)} <span class="hint">${money(r.total)}</span></p>`).join("") : `<p class="hint">Sin ${type.toLowerCase()}s cargados.</p>`;
}

function renderClients() {
  table($("clients-table"), ["ID", "Razon social", "CUIT", "Telefono", "Correo"], state.clients.map((c) => ({
    id: c.id, ID: c.id, "Razon social": c.business_name, CUIT: c.cuit || "", Telefono: c.phone || "", Correo: c.email || "",
  })), state.selected.client, selectClient);
  renderClientForm(state.clients.find((c) => c.id === state.selected.client) || {});
}

function renderClientForm(client) {
  const deleteButton = client.id ? `<button type="button" class="danger" id="delete-client">Eliminar cliente</button>` : "";
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
    `<div class="full"><button>Guardar cliente</button> <button type="button" class="secondary" id="clear-client">Limpiar</button> ${deleteButton}</div>`,
  ].join("");
  $("client-form").onsubmit = saveClient;
  $("clear-client").onclick = () => { state.selected.client = null; renderClients(); };
  if ($("delete-client")) $("delete-client").onclick = deleteSelectedClient;
}

async function selectClient(id) {
  state.selected.client = id;
  renderClients();
}

async function saveClient(event) {
  event.preventDefault();
  const data = formData(event.target);
  if (!data.business_name.trim()) return toast("La razon social es obligatoria.", "error");
  await guard(async () => {
    data.id = state.selected.client;
    await api("/api/clients", { method: "POST", body: JSON.stringify(data) });
    state.clients = await api("/api/clients");
    state.selected.client = null;
    renderClients();
    toast("Cliente guardado.", "success");
  });
}

async function deleteSelectedClient() {
  if (!state.selected.client) return toast("Seleccione un cliente.", "error");
  if (!confirm("Desea eliminar este cliente? No aparecera en nuevas operaciones.")) return;
  await guard(async () => {
    await api(`/api/clients/${state.selected.client}`, { method: "DELETE" });
    state.clients = await api("/api/clients");
    state.selected.client = null;
    renderClients();
    toast("Cliente eliminado.", "success");
  });
}

function clientOptions() {
  return [{ value: "", label: "Seleccione cliente" }, ...state.clients.map((c) => ({ value: c.id, label: c.business_name }))];
}

function clientById(id) {
  return state.clients.find((client) => String(client.id) === String(id));
}

function rememberClient(client) {
  if (!client || !client.id) return;
  const index = state.clients.findIndex((row) => String(row.id) === String(client.id));
  if (index >= 0) {
    state.clients[index] = client;
  } else {
    state.clients.push(client);
  }
}

async function fetchClientDetail(id) {
  if (!id) return null;
  try {
    const client = await api(`/api/clients/${id}`);
    rememberClient(client);
    return client;
  } catch (error) {
    console.warn("No se pudo cargar la ficha completa del cliente.", error);
    return clientById(id) || null;
  }
}

async function fillDocumentClientFields(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const form = $(`${key}-form`);
  const selectedClientId = form.elements.client_id.value;
  if (!selectedClientId) {
    form.elements.contact.value = "";
    form.elements.address.value = "";
    form.elements.phone.value = "";
    return;
  }
  const client = await fetchClientDetail(selectedClientId);
  if (!client) return;
  if (!form.isConnected || String(form.elements.client_id.value) !== String(selectedClientId)) return;
  form.elements.contact.value = client.contact_name || client.business_name || "";
  form.elements.address.value = client.address || "";
  form.elements.phone.value = client.phone || client.whatsapp || "";
  if (key === "delivery" && form.elements.client_resp_inscripto) {
    form.elements.client_resp_inscripto.checked = clientDefaultRespInscripto(client);
  }
}

function renderDocuments(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const rows = type === "Presupuesto" ? state.budgets : state.delivery;
  table($(`${key}s-table`) || $(`${key}-table`), ["ID", "Numero", "Fecha", "Cliente", "Estado", "Total"], rows.map((d) => ({
    id: d.id, ID: d.id, Numero: d.number, Fecha: d.date, Cliente: d.client_name, Estado: d.status, Total: money(d.total),
  })), state.selected[key], (id) => selectDocument(type, id));
  const detail = state[`${key}Detail`];
  const hasDetail = detail && String(detail.document.id) === String(state.selected[key]);
  renderDocumentForm(type, hasDetail ? detail.document : rows.find((d) => d.id === state.selected[key]), hasDetail ? detail.items : null);
}

async function selectDocument(type, id) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  state.selected[key] = id;
  await guard(async () => {
    state[`${key}Detail`] = await api(`/api/documents/${id}`);
    renderDocuments(type);
  });
}

function renderDocumentForm(type, doc = {}, items = null) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const statuses = type === "Presupuesto"
    ? ["Borrador", "Enviado", "Aprobado", "Aprobado parcial", "Rechazado", "Anulado"]
    : ["Pendiente", "Entregado", "Facturado", "Anulado"];
  const currentItems = items || [{ quantity: 1, description: "", unit: "u", unit_price: 0 }];
  const voidButton = state.selected[key] ? `<button type="button" class="danger" id="${key}-void">Anular ${type.toLowerCase()}</button>` : "";
  const deleteButton = state.selected[key] ? `<button type="button" class="danger" id="${key}-delete">Eliminar ${type.toLowerCase()}</button>` : "";
  $(`${key}-form`).innerHTML = [
    `<div class="form-grid">`,
    input("number", "Numero", doc.number || "Se asigna al guardar", "text", "", "readonly"),
    input("date", "Fecha", doc.date || window.INITROF_TODAY, "date"),
    select("client_id", "Cliente", clientOptions(), doc.client_id),
    select("status", "Estado", statuses.map((s) => ({ value: s, label: s })), doc.status || statuses[0]),
    type === "Presupuesto" ? checkbox("show_iva", "Mostrar IVA 21% discriminado", documentShowsIva(doc)) : "",
    input("contact", "Contacto", doc.contact),
    input("phone", "Telefono", doc.phone),
    type === "Remito" ? input("invoice_number", "Factura nro", doc.invoice_number) : "",
    type === "Remito" ? checkbox("client_resp_inscripto", "Cliente Resp. Inscripto", documentClientRespInscripto(doc)) : "",
    input("address", "Direccion", doc.address, "text", "full"),
    `</div>`,
    `<label>Items</label><div class="item-actions"><button type="button" id="${key}-add-item">Agregar item</button><button type="button" class="secondary" id="${key}-remove-item">Quitar ultimo</button></div>`,
    `<table class="items" id="${key}-items"><thead><tr><th>Cant.</th><th>Descripcion</th><th>Unidad</th><th>P. unitario</th><th>Subtotal</th></tr></thead><tbody>${currentItems.map(itemRow).join("")}</tbody></table>`,
    `<div class="totals" id="${key}-total"></div>`,
    textarea("observations", "Observaciones", doc.observations || ""),
    `<button>Guardar ${type.toLowerCase()}</button> <button type="button" class="secondary" id="${key}-clear">Limpiar</button> ${voidButton} ${deleteButton}`,
  ].join("");
  $(`${key}-form`).onsubmit = (event) => saveDocument(event, type);
  $(`${key}-form`).elements.client_id.onchange = () => guard(async () => fillDocumentClientFields(type));
  $(`${key}-add-item`).onclick = () => { $(`${key}-items`).querySelector("tbody").insertAdjacentHTML("beforeend", itemRow({ quantity: 1, unit: "u", unit_price: 0 })); bindItemTotals(key); };
  $(`${key}-remove-item`).onclick = () => { const tbody = $(`${key}-items`).querySelector("tbody"); if (tbody.children.length > 1) tbody.lastElementChild.remove(); updateTotals(key); };
  $(`${key}-clear`).onclick = () => newDocument(type);
  if ($(`${key}-void`)) $(`${key}-void`).onclick = () => voidSelectedDocument(type);
  if ($(`${key}-delete`)) $(`${key}-delete`).onclick = () => deleteSelectedDocument(type);
  bindItemTotals(key);
}

function newDocument(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  state.selected[key] = null;
  state[`${key}Detail`] = null;
  renderDocuments(type);
  toast(`Nuevo ${type.toLowerCase()} listo para cargar.`, "success");
}

function itemRow(item = {}) {
  return `<tr>
    <td><input name="quantity" type="number" min="0.01" step="0.01" value="${escapeHtml(item.quantity ?? 1)}"></td>
    <td><input name="description" value="${escapeHtml(item.description || "")}"></td>
    <td><input name="unit" value="${escapeHtml(item.unit || "u")}"></td>
    <td><input name="unit_price" type="number" min="0" step="0.01" value="${escapeHtml(item.unit_price ?? 0)}"></td>
    <td class="line-total">${money((item.quantity || 0) * (item.unit_price || 0))}</td>
  </tr>`;
}

function bindItemTotals(key) {
  $(`${key}-items`).querySelectorAll("input").forEach((inputEl) => { inputEl.oninput = () => updateTotals(key); });
  const ivaToggle = $(`${key}-form`).elements.show_iva;
  if (ivaToggle) ivaToggle.onchange = () => updateTotals(key);
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
  let subtotalTotal = 0;
  $(`${key}-items`).querySelectorAll("tbody tr").forEach((tr) => {
    const fields = tr.querySelectorAll("input");
    const subtotal = Number(fields[0].value || 0) * Number(fields[3].value || 0);
    tr.querySelector(".line-total").textContent = money(subtotal);
    subtotalTotal += subtotal;
  });
  const showIva = key !== "budget" || Boolean($(`${key}-form`).elements.show_iva?.checked);
  const total = showIva ? subtotalTotal * 1.21 : subtotalTotal;
  $(`${key}-total`).textContent = showIva ? `Total estimado con IVA: ${money(total)}` : `Total estimado: ${money(total)}`;
}

async function saveDocument(event, type) {
  event.preventDefault();
  const key = type === "Presupuesto" ? "budget" : "delivery";
  const data = formData(event.target);
  const items = collectItems(key);
  const currentDoc = state[`${key}Detail`]?.document || {};
  const invalidItem = items.find((item) => item.quantity <= 0 || item.unit_price < 0);
  if (!data.client_id) return toast("Seleccione cliente.", "error");
  if (!data.date) return toast("La fecha es obligatoria.", "error");
  if (!items.length) return toast("Agregue al menos un item con descripcion.", "error");
  if (invalidItem) return toast("Revise cantidades y precios de los items.", "error");
  await guard(async () => {
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
        show_iva: type === "Presupuesto" ? (data.show_iva === "1" ? 1 : 0) : (documentShowsIva(currentDoc) ? 1 : 0),
        client_resp_inscripto: type === "Remito" ? (data.client_resp_inscripto === "1" ? 1 : 0) : (documentClientRespInscripto(currentDoc) ? 1 : 0),
        observations: data.observations,
        invoice_number: data.invoice_number || "",
        source_document_id: null,
      },
      items,
    };
    const saved = await api("/api/documents", { method: "POST", body: JSON.stringify(payload) });
    state.selected[key] = saved.document.id;
    state[`${key}Detail`] = saved;
    await refreshLists();
    await selectDocument(type, saved.document.id);
    toast(`${type} guardado.`, "success");
  });
}

async function voidSelectedDocument(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  if (!state.selected[key]) return toast("Seleccione un documento.", "error");
  if (!confirm(`Desea anular este ${type.toLowerCase()}?`)) return;
  await guard(async () => {
    const payload = await api(`/api/documents/${state.selected[key]}/void`, { method: "POST" });
    state[`${key}Detail`] = payload;
    await refreshLists();
    await selectDocument(type, state.selected[key]);
    toast(`${type} anulado.`, "success");
  });
}

async function deleteSelectedDocument(type) {
  const key = type === "Presupuesto" ? "budget" : "delivery";
  if (!state.selected[key]) return toast("Seleccione un documento.", "error");
  const label = type === "Remito" ? "remito" : "presupuesto";
  if (!confirm(`Eliminar definitivamente este ${label}? Esta accion no se puede deshacer.`)) return;
  await guard(async () => {
    await api(`/api/documents/${state.selected[key]}`, { method: "DELETE" });
    state.selected[key] = null;
    state[`${key}Detail`] = null;
    await refreshLists();
    toast(`${type} eliminado.`, "success");
  });
}

async function deleteTestDeliveryNotes() {
  if (!confirm("Eliminar definitivamente todos los remitos de prueba anteriores al 201? No se tocaran los remitos 201 a 300.")) return;
  await guard(async () => {
    const result = await api("/api/documents/remitos/delete-test", { method: "POST" });
    state.selected.delivery = null;
    state.deliveryDetail = null;
    await refreshLists();
    toast(`Remitos de prueba eliminados: ${result.deleted}.`, "success");
  });
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
  if (!id) return toast("Seleccione un registro primero.", "error");
  const cacheBust = Date.now();
  window.open(type === "Orden" ? `/pdf/order/${id}?v=${cacheBust}` : `/pdf/document/${id}?v=${cacheBust}`, "_blank");
}

async function convertSelectedBudget() {
  if (!state.selected.budget) return toast("Seleccione un presupuesto.", "error");
  await guard(async () => {
    const saved = await api(`/api/documents/${state.selected.budget}/convert-to-remito`, { method: "POST" });
    state.selected.delivery = saved.document.id;
    state.deliveryDetail = saved;
    await refreshLists();
    setView("delivery");
    toast("Remito generado con numeracion consecutiva.", "success");
  });
}

async function generateOrderFromSelectedBudget() {
  if (!state.selected.budget) return toast("Seleccione un presupuesto.", "error");
  await guard(async () => {
    const payload = await api(`/api/documents/${state.selected.budget}/convert-to-order`, { method: "POST" });
    await refreshLists();
    state.selected.order = payload.order.id;
    state.orderDetail = payload.order;
    setView("orders");
    renderOrders();
    toast(payload.created ? "Orden de trabajo generada desde el presupuesto." : "Este presupuesto ya tenia una orden generada.", "success");
  });
}

function renderOrders() {
  table($("orders-table"), ["ID", "Numero", "Cliente", "Responsable", "Inicio", "Estado"], state.orders.map((o) => ({
    id: o.id, ID: o.id, Numero: o.number, Cliente: o.client_name, Responsable: o.responsible || "", Inicio: o.start_date, Estado: o.status,
  })), state.selected.order, selectOrder);
  renderOrderForm(selectedOrderForForm());
}

function selectedOrderForForm() {
  if (!state.selected.order) return {};
  if (state.orderDetail && String(state.orderDetail.id) === String(state.selected.order)) return state.orderDetail;
  return state.orders.find((order) => String(order.id) === String(state.selected.order)) || {};
}

async function selectOrder(id) {
  state.selected.order = id;
  await guard(async () => {
    state.orderDetail = await api(`/api/orders/${id}`);
    renderOrders();
  });
}

function renderOrderForm(order = {}) {
  const editing = Boolean(order.id);
  $("order-form").innerHTML = [
    `<div class="full form-note">${editing ? `Editando ${escapeHtml(order.number)}. Modifique los campos necesarios y presione Guardar orden.` : "Nueva orden lista para cargar."}</div>`,
    input("number", "Numero", order.number || "Se asigna al guardar", "text", "", "readonly"),
    order.source_budget_number ? input("source_budget_number", "Presupuesto origen", order.source_budget_number, "text", "", "readonly") : "",
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
  $("clear-order").onclick = () => { state.selected.order = null; state.orderDetail = null; renderOrders(); };
}

async function saveOrder(event) {
  event.preventDefault();
  const data = formData(event.target);
  const wasEditing = Boolean(state.selected.order);
  data.id = state.selected.order;
  data.client_id = Number(data.client_id);
  if (!data.client_id) return toast("Seleccione cliente.", "error");
  if (!data.start_date) return toast("La fecha de inicio es obligatoria.", "error");
  if (!data.requested_work.trim()) return toast("Complete el trabajo solicitado.", "error");
  await guard(async () => {
    const saved = await api("/api/orders", { method: "POST", body: JSON.stringify(data) });
    state.selected.order = saved.id;
    state.orderDetail = saved;
    await refreshLists();
    toast(wasEditing ? "Orden actualizada correctamente." : "Orden guardada.", "success");
  });
}

function renderPrinting() {
  table($("print-table"), ["ID", "Tipo", "Numero", "Fecha", "Cliente", "Estado", "Total"], state.printables.map((p) => ({
    id: `${p.item_type}:${p.id}`, ID: p.id, Tipo: p.item_type, Numero: p.number, Fecha: p.date, Cliente: p.client_name, Estado: p.status, Total: p.total ? money(p.total) : "-",
  })), state.selected.print, (id) => { state.selected.print = id; renderPrinting(); });
}

function openPrintable() {
  if (!state.selected.print) return toast("Seleccione un documento.", "error");
  const [type, id] = String(state.selected.print).split(":");
  const cacheBust = Date.now();
  window.open(type === "Orden de Trabajo" ? `/pdf/order/${id}?v=${cacheBust}` : `/pdf/document/${id}?v=${cacheBust}`, "_blank");
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
  await guard(async () => {
    state.company = await api("/api/company", { method: "POST", body: JSON.stringify(formData(event.target)) });
    toast("Configuracion guardada.", "success");
  });
}

async function uploadLogo(event) {
  event.preventDefault();
  const response = await fetch("/api/company/logo", { method: "POST", body: new FormData(event.target) });
  if (!response.ok) return toast("No se pudo subir el logo.", "error");
  toast("Logo actualizado.", "success");
  setTimeout(() => location.reload(), 800);
}

async function savePassword() {
  const password = $("new-password").value;
  if (password.length < 8) return toast("La clave debe tener al menos 8 caracteres.", "error");
  await guard(async () => {
    await api("/api/password", { method: "POST", body: JSON.stringify({ password }) });
    $("new-password").value = "";
    toast("Clave actualizada.", "success");
  });
}

function bindEvents() {
  document.querySelectorAll(".sidebar nav button").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
  on("new-client", "click", () => { state.selected.client = null; renderClients(); toast("Nuevo cliente listo para cargar.", "success"); });
  on("new-budget", "click", () => newDocument("Presupuesto"));
  on("new-delivery", "click", () => newDocument("Remito"));
  on("delete-test-delivery", "click", deleteTestDeliveryNotes);
  on("new-order", "click", () => { state.selected.order = null; state.orderDetail = null; renderOrderForm(); renderOrders(); toast("Nueva orden lista para cargar.", "success"); });
  on("edit-order", "click", () => {
    if (!state.selected.order) return toast("Seleccione una orden de la lista para editar.", "error");
    selectOrder(state.selected.order);
  });
  on("budget-pdf", "click", () => openSelectedPdf("Presupuesto"));
  on("delivery-pdf", "click", () => openSelectedPdf("Remito"));
  on("order-pdf", "click", () => openSelectedPdf("Orden"));
  on("budget-convert", "click", convertSelectedBudget);
  on("budget-order", "click", generateOrderFromSelectedBudget);
  on("print-open", "click", openPrintable);
  $("logo-form").onsubmit = uploadLogo;
  on("save-password", "click", savePassword);
  on("client-search", "input", (event) => guard(async () => { state.clients = await api(`/api/clients?search=${encodeURIComponent(event.target.value)}`); renderClients(); }));
  on("budget-search", "input", (event) => guard(async () => { state.budgets = await api(`/api/documents?doc_type=Presupuesto&search=${encodeURIComponent(event.target.value)}`); renderDocuments("Presupuesto"); }));
  on("delivery-search", "input", (event) => guard(async () => { state.delivery = await api(`/api/documents?doc_type=Remito&search=${encodeURIComponent(event.target.value)}`); renderDocuments("Remito"); }));
  on("order-search", "input", (event) => guard(async () => { state.orders = await api(`/api/orders?search=${encodeURIComponent(event.target.value)}`); renderOrders(); }));
  on("print-search", "input", (event) => guard(async () => { state.printables = (await api(`/api/bootstrap`)).printables.filter((p) => JSON.stringify(p).toLowerCase().includes(event.target.value.toLowerCase())); renderPrinting(); }));
}

bindEvents();
loadAll().catch((error) => toast(error.message, "error"));
