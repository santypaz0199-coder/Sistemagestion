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
    print(f"[upgrade9] escrito: {relpath}")


VENTAS_LISTA = r'''{% extends "base.html" %}
{% block title %}Ventas{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Ventas</h4>
<a href="{{ url_for('ventas_nueva') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nueva orden</a>
</div>

<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
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
<button type="button" class="btn btn-sm btn-outline-danger" onclick="bulkSubmit('cancelar', 'Cancelar las ordenes seleccionadas? Se devuelve stock si corresponde.')"><i class="bi bi-x-lg"></i> Cancelar</button>
<button type="button" class="btn btn-sm btn-outline-success" onclick="bulkSubmit('enviado', 'Marcar las seleccionadas como enviadas?')"><i class="bi bi-truck"></i> Enviado</button>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="bulkSubmit('notificar', 'Enviar email Envio en camino a los clientes con email? Las que no tengan email se saltean.')"><i class="bi bi-envelope"></i> Notificar</button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openBulkFacturar()"><i class="bi bi-receipt"></i> Facturar</button>
</div>
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="30"><input type="checkbox" id="check-all" onchange="toggleAll(this)"></th>
<th>Nro</th><th>Fecha</th><th>Cliente</th><th>Vendedor</th>
<th>Canal</th><th>Tipo</th><th>Estado</th><th>Facturacion</th>
<th class="text-end">Total</th><th></th>
</tr></thead>
<tbody>
{% for v in ventas %}
<tr>
<td><input type="checkbox" class="check-row" name="ordenes_ids" value="{{ v.id }}" onchange="updateToolbar()"></td>
<td class="fw-semibold">{{ v.numero_interno }}</td>
<td class="small text-muted">{{ v.fecha }}</td>
<td>{{ v.cliente_nombre }}</td>
<td class="small">{{ v.vendedor_nombre }}</td>
<td class="small">{{ v.canal_nombre or '-' }}</td>
<td><span class="badge bg-{{ 'info text-dark' if v.tipo=='minorista' else 'warning text-dark' }}">{{ v.tipo }}</span></td>
<td>
{% if v.estado == 'pendiente_pago' %}<span class="badge bg-warning text-dark">Pendiente pago</span>
{% elif v.estado == 'pagado_sin_enviar' %}<span class="badge bg-info text-dark">Pagado / Sin enviar</span>
{% elif v.estado == 'pagado_enviado' %}<span class="badge bg-success">Pagado / Enviado</span>
{% else %}<span class="badge bg-secondary">Cancelado</span>{% endif %}
</td>
<td>
<button type="button" class="btn btn-sm p-1 border-0" onclick="openFactura({{ v.id }}, {{ (v.estado_facturacion or 'no_requiere')|tojson }}, {{ (v.nro_factura_arca or '')|tojson }})">
{% if v.estado_facturacion=='facturada' %}<span class="badge bg-success">Facturada</span>
{% elif v.estado_facturacion=='pendiente' %}<span class="badge bg-warning text-dark">Sin facturar</span>
{% else %}<span class="badge bg-light text-dark border">No requiere</span>{% endif %}
</button>
</td>
<td class="text-end">${{ '%.2f'|format(v.total) }}</td>
<td class="text-end"><a href="{{ url_for('ventas_detalle', id=v.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a></td>
</tr>
{% else %}
<tr><td colspan="11" class="text-center text-muted py-4">No hay ventas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</form>

<div class="modal fade" id="facturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="factura-form" method="post">
<div class="modal-header"><h6 class="modal-title">Cambiar estado de facturacion</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2">
<label class="form-label">Estado</label>
<select name="estado_facturacion" class="form-select" id="fact-estado">
<option value="no_requiere">No requiere</option>
<option value="pendiente">Sin facturar (pendiente)</option>
<option value="facturada">Facturada</option>
</select>
</div>
<div class="mb-2">
<label class="form-label">Nro ARCA (solo si facturada)</label>
<input name="nro_factura_arca" class="form-control" id="fact-nro">
</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-primary">Guardar</button>
</div>
</form>
</div></div>
</div>

<div class="modal fade" id="bulkFacturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Marcar seleccionadas como facturadas</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2">
<label class="form-label">Nro ARCA base (opcional)</label>
<input id="bulk-factura-nro" class="form-control">
<div class="form-text">Se aplica el mismo numero a todas. Si necesitas distintos, dejanlo vacio y editalos uno por uno despues.</div>
</div>
<p class="text-muted small mb-0">Se marcaran <strong><span id="bulk-factura-count">0</span></strong> ordenes como facturadas.</p>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-primary" onclick="confirmBulkFacturar()">Confirmar</button>
</div>
</div></div>
</div>

<script>
function toggleAll(cb) {
  document.querySelectorAll('.check-row').forEach(r => r.checked = cb.checked);
  updateToolbar();
}
function updateToolbar() {
  const checked = document.querySelectorAll('.check-row:checked').length;
  const total = document.querySelectorAll('.check-row').length;
  document.getElementById('count-selected').textContent = checked;
  const toolbar = document.getElementById('bulk-toolbar');
  if (checked > 0) { toolbar.classList.remove('d-none'); }
  else { toolbar.classList.add('d-none'); }
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
function openFactura(id, estado, nro) {
  document.getElementById('factura-form').action = '/ventas/' + id + '/facturacion';
  document.getElementById('fact-estado').value = estado || 'no_requiere';
  document.getElementById('fact-nro').value = nro || '';
  new bootstrap.Modal(document.getElementById('facturaModal')).show();
}
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app8; app8.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 9: Toolbar de acciones masivas horizontal ===")
    escribir('templates/ventas/lista.html', VENTAS_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()