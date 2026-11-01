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
    print(f"[upgrade22] escrito: {relpath}")


APP22_PY = r'''
import re, urllib.parse
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app21 import app
from app import permiso_required
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


@app.route('/clientes')
@login_required
@permiso_required('clientes')
def clientes_lista_v2():
    q = request.args.get('q', '').strip()
    filtro_tipo = request.args.get('tipo', '')
    provincia_id = request.args.get('provincia_id', '').strip()
    localidad_id = request.args.get('localidad_id', '').strip()

    conn = get_db()
    sql = """SELECT c.*,
             p.nombre as provincia_nombre,
             l.nombre as localidad_nombre,
             COALESCE((
                 SELECT SUM(o.total) FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
             ), 0) as total_compras,
             COALESCE((
                 SELECT COUNT(*) FROM ordenes_venta o WHERE o.cliente_id = c.id
             ), 0) as num_ordenes
             FROM clientes c
             LEFT JOIN provincias p ON p.id = c.provincia_id
             LEFT JOIN localidades l ON l.id = c.localidad_id
             WHERE c.activo=1"""
    params = []
    if q:
        sql += " AND (c.nombre_completo LIKE ? OR c.nro_doc LIKE ? OR c.email LIKE ? OR c.telefono LIKE ?)"
        params += [f'%{q}%'] * 4
    if filtro_tipo == 'minorista':
        sql += " AND c.es_minorista=1"
    elif filtro_tipo == 'mayorista':
        sql += " AND c.es_mayorista=1"
    if provincia_id:
        sql += " AND c.provincia_id=?"
        params.append(int(provincia_id))
    if localidad_id:
        sql += " AND c.localidad_id=?"
        params.append(int(localidad_id))
    sql += " ORDER BY c.nombre_completo"
    rows = conn.execute(sql, params).fetchall()

    clientes = []
    for r in rows:
        d = dict(r)
        tel = _limpiar_tel(r['telefono'])
        if tel:
            nombre_corto = (r['nombre_completo'] or '').split()[0] if r['nombre_completo'] else 'cliente'
            msg = f"Hola {nombre_corto}! Te escribimos de Familia Zaragoza ® ¿En que te podemos ayudar?"
            d['wa_url'] = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
        else:
            d['wa_url'] = None
        d['mailto_url'] = None
        if r['email'] and '@' in r['email']:
            asunto = urllib.parse.quote('Consulta - Familia Zaragoza ®')
            d['mailto_url'] = f"mailto:{r['email']}?subject={asunto}"
        clientes.append(d)

    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    stats = {
        'total': len(clientes),
        'minoristas': sum(1 for c in clientes if c['es_minorista']),
        'mayoristas': sum(1 for c in clientes if c['es_mayorista']),
    }
    conn.close()
    return render_template('clientes/lista.html', clientes=clientes, q=q,
                           filtro_tipo=filtro_tipo, provincia_id=provincia_id,
                           localidad_id=localidad_id, provincias=provincias,
                           localidades_por_provincia=localidades_por_provincia,
                           stats=stats)


@app.route('/clientes/top')
@login_required
@permiso_required('clientes')
def clientes_top():
    tab = request.args.get('tab', 'facturacion')
    periodo = request.args.get('periodo', 'todo')
    conn = get_db()

    # Rango de fechas segun periodo
    hoy = date.today()
    if periodo == 'mes':
        ini = hoy.replace(day=1).isoformat()
    elif periodo == 'trimestre':
        ini = (hoy - timedelta(days=90)).isoformat()
    elif periodo == 'anio':
        ini = hoy.replace(month=1, day=1).isoformat()
    else:
        ini = '2000-01-01'
    fin = hoy.isoformat()

    if tab == 'facturacion':
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COALESCE(SUM(o.total),0) as metrica,
                   COUNT(DISTINCT o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Facturado'

    elif tab == 'ordenes':
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COUNT(o.id) as metrica,
                   COUNT(o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Ordenes'

    else:  # kilos
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COALESCE(SUM(
                       CASE WHEN prod.peso_unidad = 'g'
                            THEN (oi.cantidad * prod.peso_valor) / 1000.0
                            ELSE oi.cantidad * COALESCE(prod.peso_valor, 0)
                       END
                   ), 0) as metrica,
                   COUNT(DISTINCT o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            LEFT JOIN orden_items oi ON oi.orden_id = o.id
            LEFT JOIN productos prod ON prod.id = oi.producto_id
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Kilos'

    conn.close()
    return render_template('clientes/top.html', ranking=ranking, tab=tab,
                           periodo=periodo, metrica_label=metrica_label,
                           ini=ini, fin=fin)


app.view_functions['clientes_lista'] = clientes_lista_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


CLIENTES_LISTA = r'''{% extends "base.html" %}
{% block title %}Clientes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Clientes</h4>
<div class="d-flex gap-2">
<a href="{{ url_for('clientes_top') }}" class="btn btn-outline-primary btn-sm"><i class="bi bi-trophy"></i> Top clientes</a>
<a href="{{ url_for('clientes_nuevo') }}" class="btn btn-dark btn-sm"><i class="bi bi-plus-lg"></i> Nuevo cliente</a>
</div>
</div>

<!-- Contadores -->
<div class="row row-cols-3 g-2 mb-3">
<div class="col"><div class="card-kpi"><div class="kpi-label">Total</div><div class="kpi-value">{{ stats.total }}</div></div></div>
<div class="col"><div class="card-kpi" style="border-left:3px solid #06b6d4;"><div class="kpi-label">Minoristas</div><div class="kpi-value">{{ stats.minoristas }}</div></div></div>
<div class="col"><div class="card-kpi" style="border-left:3px solid #f59e0b;"><div class="kpi-label">Mayoristas</div><div class="kpi-value">{{ stats.mayoristas }}</div></div></div>
</div>

<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Buscar</label>
<input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Nombre, doc, email, tel">
</div>
<div class="col-md-2">
<label class="form-label small text-muted">Tag</label>
<select name="tipo" class="form-select form-select-sm">
<option value="">Todos</option>
<option value="minorista" {% if filtro_tipo=='minorista' %}selected{% endif %}>Minorista</option>
<option value="mayorista" {% if filtro_tipo=='mayorista' %}selected{% endif %}>Mayorista</option>
</select>
</div>
<div class="col-md-3">
<label class="form-label small text-muted">Provincia</label>
<select name="provincia_id" id="filtro-provincia" class="form-select form-select-sm">
<option value="">Todas</option>
{% for p in provincias %}
<option value="{{ p.id }}" {% if provincia_id==p.id|string %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3">
<label class="form-label small text-muted">Localidad</label>
<select name="localidad_id" id="filtro-localidad" class="form-select form-select-sm" {% if not provincia_id %}disabled{% endif %}>
<option value="">Todas</option>
{% if provincia_id and localidades_por_provincia.get(provincia_id|int) %}
{% for l in localidades_por_provincia[provincia_id|int] %}
<option value="{{ l.id }}" {% if localidad_id==l.id|string %}selected{% endif %}>{{ l.nombre }}</option>
{% endfor %}
{% endif %}
</select>
</div>
<div class="col-md-1">
<button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i></button>
</div>
</div>
</form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th>Doc</th><th>Ciudad / Provincia</th><th>Contacto</th>
<th>Tags</th><th class="text-end">Compras</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for c in clientes %}
<tr>
<td><a href="{{ url_for('clientes_editar', id=c.id) }}" class="text-decoration-none fw-semibold">{{ c.nombre_completo }}</a></td>
<td class="small text-muted text-nowrap">{{ c.tipo_doc or '' }} {{ c.nro_doc or '' }}</td>
<td class="small">
{% if c.localidad_nombre %}{{ c.localidad_nombre }}{% endif %}
{% if c.localidad_nombre and c.provincia_nombre %} · {% endif %}
{% if c.provincia_nombre %}<span class="text-muted">{{ c.provincia_nombre }}</span>{% endif %}
{% if not c.localidad_nombre and not c.provincia_nombre %}—{% endif %}
</td>
<td class="small">
{% if c.email %}<div class="text-truncate" style="max-width:180px;"><i class="bi bi-envelope text-muted"></i> {{ c.email }}</div>{% endif %}
{% if c.telefono %}<div><i class="bi bi-telephone text-muted"></i> {{ c.telefono }}</div>{% endif %}
{% if not c.email and not c.telefono %}<span class="text-muted">—</span>{% endif %}
</td>
<td class="text-nowrap">
{% if c.es_minorista %}<span class="badge bg-info text-dark">Minorista</span>{% endif %}
{% if c.es_mayorista %}<span class="badge bg-warning text-dark">Mayorista</span>{% endif %}
</td>
<td class="text-end">
{% if c.total_compras > 0 %}
<div class="fw-semibold">${{ '%.0f'|format(c.total_compras).replace(',','.') }}</div>
<div class="small text-muted">{{ c.num_ordenes }} orden{{ 'es' if c.num_ordenes != 1 else '' }}</div>
{% else %}
<span class="text-muted small">Sin compras</span>
{% endif %}
</td>
<td class="text-end text-nowrap">
{% if c.wa_url %}
<a href="{{ c.wa_url }}" target="_blank" class="btn btn-sm btn-outline-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
{% else %}
<button class="btn btn-sm btn-outline-secondary" disabled title="Sin telefono"><i class="bi bi-whatsapp"></i></button>
{% endif %}
{% if c.mailto_url %}
<a href="{{ c.mailto_url }}" class="btn btn-sm btn-outline-primary" title="Enviar email"><i class="bi bi-envelope"></i></a>
{% else %}
<button class="btn btn-sm btn-outline-secondary" disabled title="Sin email"><i class="bi bi-envelope"></i></button>
{% endif %}
<a href="{{ url_for('ventas_nueva') }}?cliente_id={{ c.id }}" class="btn btn-sm btn-outline-dark" title="Crear orden"><i class="bi bi-cart-plus"></i></a>
<a href="{{ url_for('clientes_editar', id=c.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarCliente({{ c.id }}, {{ c.nombre_completo|tojson }})" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="7" class="text-center text-muted py-4">Sin clientes con esos filtros.</td></tr>
{% endfor %}
</tbody></table></div></div>

<!-- Modal borrar -->
<div class="modal fade" id="borrarClienteModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-cliente-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar cliente <span id="borrar-cliente-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, el cliente se desactiva inmediatamente.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label><textarea name="motivo" class="form-control" rows="2"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<script>
const LOCS = {{ localidades_por_provincia|tojson }};
const provSel = document.getElementById('filtro-provincia');
const locSel = document.getElementById('filtro-localidad');

function actualizarLocFiltro() {
  const pid = provSel.value;
  locSel.innerHTML = '<option value="">Todas</option>';
  if (!pid) { locSel.disabled = true; return; }
  locSel.disabled = false;
  (LOCS[pid] || []).forEach(function(l){
    const o = document.createElement('option');
    o.value = l.id; o.textContent = l.nombre;
    locSel.appendChild(o);
  });
}
provSel.addEventListener('change', actualizarLocFiltro);

function openBorrarCliente(id, nombre) {
  document.getElementById('borrar-cliente-form').action = '/clientes/' + id + '/borrar';
  document.getElementById('borrar-cliente-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('borrarClienteModal')).show();
}
</script>
{% endblock %}
'''


CLIENTES_TOP = r'''{% extends "base.html" %}
{% block title %}Top clientes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Top clientes</h4>
<div class="text-muted small">{{ ini }} al {{ fin }}</div>
</div>
<a href="{{ url_for('clientes_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<!-- Tabs -->
<ul class="nav nav-pills mb-3">
<li class="nav-item"><a class="nav-link {% if tab=='facturacion' %}active{% endif %}" href="{{ url_for('clientes_top', tab='facturacion', periodo=periodo) }}"><i class="bi bi-currency-dollar"></i> Por facturacion</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='ordenes' %}active{% endif %}" href="{{ url_for('clientes_top', tab='ordenes', periodo=periodo) }}"><i class="bi bi-receipt"></i> Por ordenes</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='kilos' %}active{% endif %}" href="{{ url_for('clientes_top', tab='kilos', periodo=periodo) }}"><i class="bi bi-box-seam"></i> Por kilos</a></li>
</ul>

<!-- Filtro periodo -->
<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Periodo</label>
<select name="periodo" class="form-select form-select-sm" onchange="this.form.submit()">
<input type="hidden" name="tab" value="{{ tab }}">
<option value="mes" {% if periodo=='mes' %}selected{% endif %}>Este mes</option>
<option value="trimestre" {% if periodo=='trimestre' %}selected{% endif %}>Ultimos 90 dias</option>
<option value="anio" {% if periodo=='anio' %}selected{% endif %}>Este año</option>
<option value="todo" {% if periodo=='todo' %}selected{% endif %}>Todo el historial</option>
</select>
</div>
</div>
</form>

{% if ranking %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="60">#</th><th>Cliente</th><th>Provincia</th><th>Contacto</th>
<th class="text-end">{{ metrica_label }}</th><th class="text-end">Ordenes</th><th class="text-end"></th>
</tr></thead>
<tbody>
{% for c in ranking %}
<tr>
<td>
{% if loop.index == 1 %}<span class="badge" style="background:#fbbf24;color:#78350f;font-size:.9rem;">🥇 1</span>
{% elif loop.index == 2 %}<span class="badge" style="background:#d1d5db;color:#374151;font-size:.9rem;">🥈 2</span>
{% elif loop.index == 3 %}<span class="badge" style="background:#fbbf24;color:#78350f;font-size:.85rem;opacity:.85;">🥉 3</span>
{% else %}<span class="text-muted fw-semibold">{{ loop.index }}</span>{% endif %}
</td>
<td><a href="{{ url_for('clientes_editar', id=c.id) }}" class="text-decoration-none fw-semibold">{{ c.nombre_completo }}</a></td>
<td class="small">{{ c.provincia_nombre or '—' }}</td>
<td class="small">
{% if c.telefono %}<i class="bi bi-telephone text-muted"></i> {{ c.telefono }}{% endif %}
{% if c.email and c.telefono %} · {% endif %}
{% if c.email %}<span class="text-truncate">{{ c.email }}</span>{% endif %}
</td>
<td class="text-end fw-semibold">
{% if tab == 'facturacion' %}${{ '%.2f'|format(c.metrica) }}
{% elif tab == 'kilos' %}{{ '%.2f'|format(c.metrica) }} kg
{% else %}{{ c.metrica }}
{% endif %}
</td>
<td class="text-end text-muted">{{ c.num_ordenes }}</td>
<td class="text-end"><a href="{{ url_for('clientes_editar', id=c.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a></td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-people fs-1 text-muted"></i>
<h5 class="mt-3">Sin datos</h5>
<p class="text-muted mb-0">No hay clientes con compras en el periodo seleccionado.</p>
</div></div>
{% endif %}
{% endblock %}
'''


VENTAS_FORM = r'''{% extends "base.html" %}
{% block title %}Nueva orden{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Nueva orden de venta</h4>
<a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
<form method="post">
<div class="card shadow-sm mb-3"><div class="card-body"><div class="row g-3">
<div class="col-md-6"><label class="form-label">Cliente *</label><select name="cliente_id" id="cliente-select" class="form-select" required><option value="">-- Elegir --</option>{% for c in clientes %}<option value="{{ c.id }}">{{ c.nombre_completo }} ({{ c.provincia or '-' }})</option>{% endfor %}</select></div>
<div class="col-md-3"><label class="form-label">Tipo *</label><select name="tipo" class="form-select" required><option value="minorista">Minorista</option><option value="mayorista">Mayorista</option></select></div>
<div class="col-md-3"><label class="form-label">Canal</label><select name="canal_id" class="form-select"><option value="">--</option>{% for ch in canales %}<option value="{{ ch.id }}">{{ ch.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-3"><label class="form-label">Fecha</label><input type="date" name="fecha" class="form-control" value="{{ hoy }}"></div>
<div class="col-md-9"><label class="form-label">Notas</label><input name="notas" class="form-control" placeholder="Notas internas"></div>
</div></div></div>
<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2"><h6 class="mb-0">Productos</h6><button type="button" class="btn btn-sm btn-outline-secondary" onclick="addItem()"><i class="bi bi-plus-lg"></i> Agregar</button></div>
<table class="table table-sm align-middle mb-0"><thead><tr><th>Producto</th><th width="100">Cant.</th><th width="130">Precio</th><th width="110" class="text-end">Subtotal</th><th width="40"></th></tr></thead><tbody id="items-body"></tbody></table>
</div></div>
<div class="card shadow-sm mb-3"><div class="card-body"><div class="row"><div class="col-md-6 offset-md-6">
<table class="table table-sm mb-0">
<tr><td>Subtotal:</td><td class="text-end" id="subtotal-view">$0.00</td></tr>
<tr><td>Descuento:</td><td><input type="number" step="0.01" min="0" name="descuento" id="descuento" value="0" class="form-control form-control-sm text-end" onchange="updateTotals()"></td></tr>
<tr class="fw-bold"><td>Total:</td><td class="text-end" id="total-view">$0.00</td></tr>
</table></div></div></div></div>
<button class="btn btn-dark btn-lg">Crear orden</button>
</form>
<template id="item-template"><tr class="item-row">
<td><select name="producto_id" class="form-select form-select-sm" onchange="onProductChange(this)" required><option value="">--</option>{% for p in productos %}<option value="{{ p.id }}" data-precio="{{ p.precio }}">{{ p.nombre }} (stock: {{ '%g'|format(p.stock_actual) }})</option>{% endfor %}</select></td>
<td><input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" onchange="updateTotals()" required></td>
<td><input type="number" step="0.01" min="0" name="precio" class="form-control form-control-sm" value="0" onchange="updateTotals()" required></td>
<td class="text-end subtotal">$0.00</td>
<td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(this)"><i class="bi bi-trash"></i></button></td>
</tr></template>
<script>
function addItem(){const t=document.getElementById('item-template');document.getElementById('items-body').appendChild(t.content.cloneNode(true));}
function removeItem(b){b.closest('tr').remove();updateTotals();}
function onProductChange(s){const o=s.options[s.selectedIndex];const p=o.dataset.precio||0;s.closest('tr').querySelector('[name="precio"]').value=p;updateTotals();}
function updateTotals(){let sub=0;document.querySelectorAll('.item-row').forEach(r=>{const c=parseFloat(r.querySelector('[name="cantidad"]').value)||0;const p=parseFloat(r.querySelector('[name="precio"]').value)||0;const s=c*p;r.querySelector('.subtotal').textContent='$'+s.toFixed(2);sub+=s;});
const d=parseFloat(document.getElementById('descuento').value)||0;document.getElementById('subtotal-view').textContent='$'+sub.toFixed(2);document.getElementById('total-view').textContent='$'+Math.max(0,sub-d).toFixed(2);}
document.addEventListener('DOMContentLoaded',()=>{
  addItem();
  const params = new URLSearchParams(window.location.search);
  const cid = params.get('cliente_id');
  if (cid) {
    const sel = document.getElementById('cliente-select');
    if (sel) { sel.value = cid; }
  }
});
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app22; app22.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 22: Lista clientes rediseñada + Top clientes (F4.2) ===")
    escribir('app22.py', APP22_PY)
    escribir('templates/clientes/lista.html', CLIENTES_LISTA)
    escribir('templates/clientes/top.html', CLIENTES_TOP)
    escribir('templates/ventas/form.html', VENTAS_FORM)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app22.py)")


if __name__ == '__main__':
    main()