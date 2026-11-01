# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade70] escrito: {relpath}")


VENTAS_LISTA = r'''{% extends "base.html" %}
{% block title %}Ventas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Ventas</h4>
<a href="{{ url_for('ventas_nueva') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nueva orden</a>
</div>

<!-- Stats compactas -->
<style>
.stats-compact-ventas{ display:flex; gap:8px; margin-bottom:1rem; flex-wrap:wrap; }
.stats-compact-ventas .stat-pill{ display:flex; align-items:center; gap:8px; padding:8px 14px; background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(16,24,40,.06); text-decoration:none; color:inherit; border-left:3px solid #6b7280; flex:1; min-width:150px; transition:box-shadow .15s; }
.stats-compact-ventas .stat-pill:hover{ box-shadow:0 4px 12px rgba(16,24,40,.08); color:inherit; }
.stats-compact-ventas .stat-icon{ width:28px; height:28px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:.85rem; flex-shrink:0; background:#f3f4f6; color:#6b7280; }
.stats-compact-ventas .stat-body{ display:flex; flex-direction:column; line-height:1.15; min-width:0; }
.stats-compact-ventas .stat-label{ font-size:.68rem; color:#6b7280; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stats-compact-ventas .stat-value{ font-size:1rem; font-weight:700; letter-spacing:-.01em; white-space:nowrap; }
.stats-compact-ventas .stat-pill.active{ background:#f0f4ff; border-left-width:3px; }
.stats-compact-ventas .p-primary{ border-left-color:#3b5bdb; } .stats-compact-ventas .p-primary .stat-icon{ background:#eef2ff; color:#3b5bdb; }
.stats-compact-ventas .p-warning{ border-left-color:#f59e0b; } .stats-compact-ventas .p-warning .stat-icon{ background:#fffbeb; color:#f59e0b; }
.stats-compact-ventas .p-info{ border-left-color:#06b6d4; } .stats-compact-ventas .p-info .stat-icon{ background:#ecfeff; color:#06b6d4; }
.stats-compact-ventas .p-danger{ border-left-color:#ef4444; } .stats-compact-ventas .p-danger .stat-icon{ background:#fef2f2; color:#ef4444; }
.stats-compact-ventas .p-success{ border-left-color:#10b981; } .stats-compact-ventas .p-success .stat-icon{ background:#ecfdf5; color:#10b981; }
.stats-compact-ventas .p-muted{ border-left-color:#6b7280; } .stats-compact-ventas .p-muted .stat-icon{ background:#f3f4f6; color:#6b7280; }
.stats-compact-ventas .stat-delta{ font-size:.65rem; font-weight:600; }
</style>

<div class="stats-compact-ventas">
<a href="{{ url_for('ventas_lista') }}" class="stat-pill p-primary {% if not estado and not con_saldo and not facturado %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-cart"></i></div>
<div class="stat-body">
<span class="stat-label">Ordenes mes</span>
<span class="stat-value">{{ stats.ordenes_mes }}
{% if stats.variacion_ordenes is not none %}
<span class="stat-delta {% if stats.variacion_ordenes >= 0 %}text-success{% else %}text-danger{% endif %}">{{ '%+.0f'|format(stats.variacion_ordenes) }}%</span>
{% endif %}
</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="stat-pill p-warning {% if estado=='pendiente_pago' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-hourglass-split"></i></div>
<div class="stat-body">
<span class="stat-label">Pendientes pago</span>
<span class="stat-value">{{ stats.pendientes }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="stat-pill p-info {% if estado=='pagado_sin_enviar' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-truck"></i></div>
<div class="stat-body">
<span class="stat-label">Sin despachar</span>
<span class="stat-value">{{ stats.sin_despachar }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', con_saldo='1') }}" class="stat-pill p-danger {% if con_saldo=='1' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-cash-coin"></i></div>
<div class="stat-body">
<span class="stat-label">A cobrar</span>
<span class="stat-value text-danger">${{ '{:,.0f}'.format(stats.a_cobrar).replace(',','.') }}</span>
</div>
</a>

<a href="{{ url_for('ventas_lista', facturado='1') }}" class="stat-pill p-success {% if facturado=='1' %}active{% endif %}">
<div class="stat-icon"><i class="bi bi-receipt"></i></div>
<div class="stat-body">
<span class="stat-label">Facturado mes</span>
<span class="stat-value">${{ '{:,.0f}'.format(stats.facturado_mes).replace(',','.') }}
{% if stats.variacion_facturado is not none %}
<span class="stat-delta {% if stats.variacion_facturado >= 0 %}text-success{% else %}text-danger{% endif %}">{{ '%+.0f'|format(stats.variacion_facturado) }}%</span>
{% endif %}
</span>
</div>
</a>

{% if con_saldo == '1' or facturado == '1' or estado or canal or tipo or q or desde or hasta %}
<a href="{{ url_for('ventas_lista') }}" class="stat-pill p-muted">
<div class="stat-icon"><i class="bi bi-x-lg"></i></div>
<div class="stat-body">
<span class="stat-label">Quitar filtros</span>
<span class="stat-value" style="font-size:.85rem;">Limpiar</span>
</div>
</a>
{% endif %}
</div>

<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Nro o cliente"></div>
<div class="col-md-2"><label class="form-label small text-muted">Estado</label><select name="estado" class="form-select form-select-sm"><option value="">Todos</option>
<option value="pendiente_pago" {% if estado=='pendiente_pago' %}selected{% endif %}>Pendiente pago</option>
<option value="pagado_sin_enviar" {% if estado=='pagado_sin_enviar' %}selected{% endif %}>Pagado/Sin enviar</option>
<option value="pagado_enviado" {% if estado=='pagado_enviado' %}selected{% endif %}>Pagado/Enviado</option>
<option value="cancelado" {% if estado=='cancelado' %}selected{% endif %}>Cancelado</option></select></div>
<div class="col-md-2"><label class="form-label small text-muted">Canal</label><select name="canal" class="form-select form-select-sm"><option value="">Todos</option>{% for c in canales %}<option value="{{ c.id }}" {% if canal==c.id|string %}selected{% endif %}>{{ c.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-1"><label class="form-label small text-muted">Tipo</label><select name="tipo" class="form-select form-select-sm"><option value="">-</option><option value="minorista" {% if tipo=='minorista' %}selected{% endif %}>Minor.</option><option value="mayorista" {% if tipo=='mayorista' %}selected{% endif %}>Mayor.</option></select></div>
{% if current_user.es_admin %}<div class="col-md-2"><label class="form-label small text-muted">Vendedor</label><select name="vendedor" class="form-select form-select-sm"><option value="">Todos</option>{% for v in vendedores %}<option value="{{ v.id }}" {% if vendedor==v.id|string %}selected{% endif %}>{{ v.nombre }}</option>{% endfor %}</select></div>{% endif %}
<div class="col-md-1"><label class="form-label small text-muted">Desde</label><input type="date" name="desde" value="{{ desde }}" class="form-control form-control-sm"></div>
<div class="col-md-1"><label class="form-label small text-muted">Hasta</label><input type="date" name="hasta" value="{{ hasta }}" class="form-control form-control-sm"></div>
</div>
<div class="mt-2"><button class="btn btn-outline-secondary btn-sm"><i class="bi bi-search"></i> Filtrar</button></div>
</form>

<form id="bulk-form" method="post" action="{{ url_for('ventas_masivo') }}">
<input type="hidden" name="accion" id="bulk-accion">
<input type="hidden" name="nro_arca" id="bulk-nro-arca">

<div class="card shadow-sm mb-3 d-none" id="bulk-toolbar" style="border-left:4px solid #3b5bdb;">
<div class="card-body py-2 px-3 d-flex flex-row flex-wrap align-items-center gap-2">
<span class="fw-semibold small me-2"><span id="count-selected">0</span> seleccionada(s)</span>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="bulkSubmit('cancelar', 'Cancelar las ordenes seleccionadas?')"><i class="bi bi-x-lg"></i> Cancelar</button>
<button type="button" class="btn btn-sm btn-outline-success" onclick="bulkSubmit('enviado', 'Marcar las seleccionadas como enviadas?')"><i class="bi bi-truck"></i> Enviado</button>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="bulkSubmit('notificar', 'Enviar email Envio en camino?')"><i class="bi bi-envelope"></i> Notificar</button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openBulkFacturar()"><i class="bi bi-receipt"></i> Facturar</button>
</div>
</div>

<!-- Tabla con scroll interno -->
<div class="card shadow-sm" style="max-height: calc(100vh - 320px); display: flex; flex-direction: column;">
<div class="table-responsive" style="overflow-y: auto; flex: 1;">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
<tr>
<th width="30"><input type="checkbox" id="check-all" onchange="toggleAll(this)"></th>
<th>Fecha</th><th>ID</th><th>Origen</th><th>Estado</th><th>Cliente</th><th class="text-end">Kilos</th><th>Tipo</th><th>Facturacion</th><th class="text-end">Total</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for v in ventas %}
<tr>
<td><input type="checkbox" class="check-row" name="ordenes_ids" value="{{ v.id }}" onchange="updateToolbar()"></td>
<td class="small text-muted text-nowrap">{{ v.fecha }}</td>
<td class="fw-semibold text-nowrap">{{ v.numero_interno }}</td>
<td>
{% if v.origen == 'catalogo' %}<span class="badge" style="background:#8b5cf6;color:#fff;" title="Pedido desde el catalogo publico"><i class="bi bi-globe"></i> Catalogo</span>
{% else %}<span class="badge bg-light text-dark border" style="font-size:.7rem;">Interno</span>{% endif %}
</td>
<td>
<button type="button" class="btn btn-sm p-0 border-0" onclick="openEstado({{ v.id }}, '{{ v.estado }}')">
{% if v.estado == 'pendiente_pago' %}<span class="badge bg-warning text-dark">Pendiente pago</span>
{% elif v.estado == 'pagado_sin_enviar' %}<span class="badge bg-info text-dark">Pagado / Sin enviar</span>
{% elif v.estado == 'pagado_enviado' %}<span class="badge bg-success">Pagado / Enviado</span>
{% else %}<span class="badge bg-secondary">Cancelado</span>{% endif %}
</button>
</td>
<td><a href="{{ url_for('clientes_editar', id=v.cliente_id) }}" class="text-decoration-none">{{ v.cliente_nombre }}</a></td>
<td class="text-end text-nowrap">{{ '%.2f'|format(v.kilos) }} kg</td>
<td><span class="badge bg-{{ 'info text-dark' if v.tipo=='minorista' else 'warning text-dark' }}">{{ v.tipo }}</span></td>
<td>
<button type="button" class="btn btn-sm p-1 border-0" onclick="openFactura({{ v.id }}, {{ (v.estado_facturacion or 'no_requiere')|tojson }}, {{ (v.nro_factura_arca or '')|tojson }})">
{% if v.estado_facturacion=='facturada' %}<span class="badge bg-success">Facturada</span>
{% elif v.estado_facturacion=='pendiente' %}<span class="badge bg-warning text-dark">Sin facturar</span>
{% else %}<span class="badge bg-light text-dark border">No requiere</span>{% endif %}
</button>
</td>
<td class="text-end fw-semibold text-nowrap">${{ '%.2f'|format(v.total) }}</td>
<td class="text-end text-nowrap dropdown-acciones">
<div class="dropdown">
<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown" aria-expanded="false" title="Acciones">
<i class="bi bi-three-dots-vertical"></i>
</button>
<ul class="dropdown-menu dropdown-menu-end">
<li><a class="dropdown-item" href="{{ url_for('ventas_detalle', id=v.id) }}"><i class="bi bi-eye text-secondary"></i> Ver / Editar</a></li>
<li><a class="dropdown-item" href="{{ url_for('ventas_imprimir', id=v.id) }}" target="_blank"><i class="bi bi-printer text-secondary"></i> Imprimir / PDF</a></li>
<li><a class="dropdown-item" href="#" onclick="openCompartir({{ v.id }}); return false;"><i class="bi bi-share text-secondary"></i> Compartir</a></li>
<li><hr class="dropdown-divider"></li>
{% if v.wa_url %}
<li><a class="dropdown-item" href="{{ v.wa_url }}" target="_blank"><i class="bi bi-whatsapp text-success"></i> WhatsApp</a></li>
{% else %}
<li><span class="dropdown-item text-muted disabled"><i class="bi bi-whatsapp"></i> WhatsApp (sin telefono)</span></li>
{% endif %}
<li><a class="dropdown-item" href="#" onclick="openEmail({{ v.id }}); return false;"><i class="bi bi-envelope text-primary"></i> Enviar email</a></li>
<li><hr class="dropdown-divider"></li>
<li><a class="dropdown-item text-danger" href="#" onclick="openBorrar({{ v.id }}, '{{ v.numero_interno }}'); return false;"><i class="bi bi-trash"></i> Borrar</a></li>
</ul>
</div>
</td>
</tr>
{% else %}
<tr><td colspan="11" class="text-center text-muted py-4">No hay ventas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</form>

<!-- MODALES -->
<div class="modal fade" id="estadoModal" tabindex="-1">
<div class="modal-dialog modal-sm"><div class="modal-content">
<form id="estado-form" method="post">
<div class="modal-header"><h6 class="modal-title">Cambiar estado</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<select name="estado" class="form-select" id="estado-select">
<option value="pendiente_pago">Pendiente pago</option>
<option value="pagado_sin_enviar">Pagado / Sin enviar</option>
<option value="pagado_enviado">Pagado / Enviado</option>
<option value="cancelado">Cancelado</option>
</select>
<div class="form-text mt-2">Al pasar a Pagado/Sin enviar se descuenta stock. Si cancelas, se devuelve.</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cerrar</button>
<button type="submit" class="btn btn-primary btn-sm">Guardar</button>
</div>
</form></div></div></div>

<div class="modal fade" id="facturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="factura-form" method="post">
<div class="modal-header"><h6 class="modal-title">Estado de facturacion</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2"><label class="form-label">Estado</label>
<select name="estado_facturacion" class="form-select" id="fact-estado">
<option value="no_requiere">No requiere</option>
<option value="pendiente">Sin facturar (pendiente)</option>
<option value="facturada">Facturada</option>
</select></div>
<div class="mb-2"><label class="form-label">Nro ARCA (solo si facturada)</label><input name="nro_factura_arca" class="form-control" id="fact-nro"></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-primary">Guardar</button>
</div>
</form></div></div></div>

<div class="modal fade" id="emailModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Enviar email al cliente</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<form id="email-form" method="post">
<div class="d-grid gap-2">
<button type="submit" class="btn btn-outline-primary" onclick="this.form.action=this.form.getAttribute('data-url')+'/confirmacion'"><i class="bi bi-file-text"></i> Enviar orden</button>
<button type="submit" class="btn btn-outline-success" onclick="this.form.action=this.form.getAttribute('data-url')+'/pago'"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button type="submit" class="btn btn-outline-info" onclick="this.form.action=this.form.getAttribute('data-url')+'/envio'"><i class="bi bi-truck"></i> Notificar envio</button>
<button type="submit" class="btn btn-outline-secondary" onclick="this.form.action=this.form.getAttribute('data-url')+'/entrega'"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button type="submit" class="btn btn-outline-dark" onclick="this.form.action=this.form.getAttribute('data-url')+'/factura'"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>
</form>
</div>
</div></div></div>

<div class="modal fade" id="compartirModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Compartir orden</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="text-muted small">Copia y pega en WhatsApp, email, lo que necesites:</p>
<div class="d-grid gap-2">
<button type="button" class="btn btn-outline-primary" onclick="copiarResumen()"><i class="bi bi-clipboard"></i> Copiar resumen del pedido</button>
<button type="button" class="btn btn-outline-secondary" onclick="copiarLink()"><i class="bi bi-link-45deg"></i> Copiar link</button>
<a id="btn-ver-orden" href="#" target="_blank" class="btn btn-outline-dark"><i class="bi bi-box-arrow-up-right"></i> Abrir orden</a>
</div>
<div id="compartir-resultado" class="alert alert-success py-2 small mt-3 mb-0 d-none"></div>
</div>
</div></div></div>

<div class="modal fade" id="borrarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar orden <span id="borrar-num"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, la orden se borra <strong>definitivamente</strong>.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="2"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<div class="modal fade" id="bulkFacturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Marcar seleccionadas como facturadas</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2"><label class="form-label">Nro ARCA base (opcional)</label><input id="bulk-factura-nro" class="form-control"></div>
<p class="text-muted small mb-0">Se marcaran <strong><span id="bulk-factura-count">0</span></strong> ordenes.</p>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-primary" onclick="confirmBulkFacturar()">Confirmar</button>
</div>
</div></div></div>

<script>
let _compartirActual = null;
const transiciones = {
  'pendiente_pago': ['pendiente_pago','pagado_sin_enviar','cancelado'],
  'pagado_sin_enviar': ['pagado_sin_enviar','pagado_enviado','cancelado'],
  'pagado_enviado': ['pagado_enviado','cancelado'],
  'cancelado': ['cancelado']
};
function openEstado(id, actual) {
  document.getElementById('estado-form').action = '/ventas/' + id + '/estado';
  const select = document.getElementById('estado-select');
  select.value = actual;
  const validas = transiciones[actual] || [];
  Array.from(select.options).forEach(opt => { opt.disabled = !validas.includes(opt.value); });
  new bootstrap.Modal(document.getElementById('estadoModal')).show();
}
function openFactura(id, estado, nro) {
  document.getElementById('factura-form').action = '/ventas/' + id + '/facturacion';
  document.getElementById('fact-estado').value = estado || 'no_requiere';
  document.getElementById('fact-nro').value = nro || '';
  new bootstrap.Modal(document.getElementById('facturaModal')).show();
}
function openEmail(id) {
  const form = document.getElementById('email-form');
  form.setAttribute('data-url', '/ventas/' + id + '/email');
  form.action = '/ventas/' + id + '/email/confirmacion';
  new bootstrap.Modal(document.getElementById('emailModal')).show();
}
function openCompartir(id) {
  _compartirActual = null;
  document.getElementById('compartir-resultado').classList.add('d-none');
  document.getElementById('btn-ver-orden').href = '/ventas/' + id;
  fetch('/ventas/' + id + '/compartir', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.ok) { _compartirActual = d; }
      else { alert('Error: ' + (d.error || 'desconocido')); }
    });
  new bootstrap.Modal(document.getElementById('compartirModal')).show();
}
function _mostrarResultado(msg) {
  const el = document.getElementById('compartir-resultado');
  el.textContent = msg;
  el.classList.remove('d-none');
  setTimeout(() => el.classList.add('d-none'), 2500);
}
function copiarResumen() {
  if (!_compartirActual) return;
  navigator.clipboard.writeText(_compartirActual.texto).then(() => _mostrarResultado('✅ Resumen copiado al portapapeles'));
}
function copiarLink() {
  if (!_compartirActual) return;
  const full = window.location.origin + _compartirActual.link;
  navigator.clipboard.writeText(full).then(() => _mostrarResultado('✅ Link copiado al portapapeles'));
}
function openBorrar(id, num) {
  document.getElementById('borrar-form').action = '/ventas/' + id + '/borrar';
  document.getElementById('borrar-num').textContent = num;
  new bootstrap.Modal(document.getElementById('borrarModal')).show();
}
function toggleAll(cb) { document.querySelectorAll('.check-row').forEach(r => r.checked = cb.checked); updateToolbar(); }
function updateToolbar() {
  const checked = document.querySelectorAll('.check-row:checked').length;
  const total = document.querySelectorAll('.check-row').length;
  document.getElementById('count-selected').textContent = checked;
  const toolbar = document.getElementById('bulk-toolbar');
  if (checked > 0) { toolbar.classList.remove('d-none'); } else { toolbar.classList.add('d-none'); }
  const all = document.getElementById('check-all');
  all.checked = checked > 0 && checked === total;
  all.indeterminate = checked > 0 && checked < total;
}
function bulkSubmit(accion, msg) {
  if (msg && !confirm(msg)) return;
  document.getElementById('bulk-accion').value = accion;
  document.getElementById('bulk-nro-arca').value = '';
  document.getElementById('bulk-form').submit();
}
function openBulkFacturar() {
  const checked = document.querySelectorAll('.check-row:checked').length;
  if (checked === 0) return;
  document.getElementById('bulk-factura-count').textContent = checked;
  document.getElementById('bulk-factura-nro').value = '';
  new bootstrap.Modal(document.getElementById('bulkFacturaModal')).show();
}
function confirmBulkFacturar() {
  document.getElementById('bulk-accion').value = 'facturar';
  document.getElementById('bulk-nro-arca').value = document.getElementById('bulk-factura-nro').value;
  document.getElementById('bulk-form').submit();
}
</script>
{% endblock %}
'''

def patch_base_scroll():
    """Asegura que el sidebar sea fixed y no se scrollee toda la página."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade70] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Eliminar el JS que guardaba el scroll (no lo necesitamos si el sidebar no scrollea)
    import re
    contenido = re.sub(r'<script>\s*/\* sidebar_scroll_preserve.*?</script>', '', contenido, flags=re.DOTALL)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade70] JS de scroll anterior eliminado")


def main():
    print("=== Upgrade 70: Fix layout (tabla con scroll interno) ===")
    escribir('templates/ventas/lista.html', VENTAS_LISTA)
    patch_base_scroll()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 para forzar recarga del CSS")


if __name__ == '__main__':
    main()