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
    print(f"[upgrade13] escrito: {relpath}")


APP13_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app12 import app, _cargar_orden
from app import permiso_required
from database import get_db


def _config(clave, default=''):
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return (row['valor'] if row and row['valor'] else default)


@app.route('/ventas/<int:id>/imprimir')
@login_required
@permiso_required('ventas')
def ventas_imprimir(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error'); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku,
        p.peso_valor, p.peso_unidad FROM orden_items oi
        JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?""", (id,)).fetchall()
    pagos = conn.execute("""SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg
        LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=?""", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    conn.close()

    kilos_total = 0.0
    for it in items:
        pv = it['peso_valor'] or 0
        if it['peso_unidad'] == 'g':
            kilos_total += (it['cantidad'] * pv) / 1000.0
        else:
            kilos_total += it['cantidad'] * pv

    empresa = {
        'nombre': _config('empresa_nombre', 'Familia Zaragoza'),
        'telefono': _config('empresa_telefono', ''),
        'web': _config('empresa_web', ''),
        'email': _config('smtp_remitente_email', ''),
    }
    return render_template('ventas/imprimir.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, kilos_total=kilos_total, empresa=empresa)


@app.route('/ventas/<int:id>/compartir', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_compartir(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); return jsonify({'ok': False, 'error': 'No encontrada'}), 404
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); return jsonify({'ok': False, 'error': 'Sin permiso'}), 403
    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre FROM orden_items oi
        JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?""", (id,)).fetchall()
    conn.close()

    estado = {'pendiente_pago': 'Pendiente de pago', 'pagado_sin_enviar': 'Pagado / Sin enviar',
              'pagado_enviado': 'Pagado / Enviado', 'cancelado': 'Cancelado'}.get(orden['estado'], orden['estado'])
    lineas = [f"*Pedido {orden['numero_interno']}*",
              f"Fecha: {orden['fecha']}",
              f"Cliente: {orden['cliente_nombre']}",
              f"Estado: {estado}",
              ""]
    for it in items:
        lineas.append(f"- {it['producto_nombre']} x {it['cantidad']:g} = ${it['subtotal']:.2f}")
    lineas.append("")
    lineas.append(f"*Total: ${orden['total']:.2f}*")
    if orden['nro_guia']:
        lineas.append(f"Guia: {orden['nro_guia']}")
    texto = "\n".join(lineas)
    link = url_for('ventas_detalle', id=id, _external=False)
    return jsonify({'ok': True, 'texto': texto, 'link': link, 'numero': orden['numero_interno']})


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


IMPRIMIR_HTML = r'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<title>{{ orden.numero_interno }} - {{ empresa.nombre }}</title>
<style>
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 40px; font-size: 13px; max-width: 800px; margin-left: auto; margin-right: auto; }
.header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1f2937; padding-bottom: 16px; margin-bottom: 24px; }
.header .empresa h1 { margin: 0 0 4px 0; font-size: 22px; letter-spacing: -.02em; }
.header .empresa .info { font-size: 11px; color: #6b7280; line-height: 1.6; }
.header .orden-box { text-align: right; }
.header .orden-box .num { font-size: 20px; font-weight: 700; }
.header .orden-box .fecha { color: #6b7280; font-size: 12px; margin-top: 2px; }
.header .orden-box .estado { display: inline-block; margin-top: 6px; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; }
.estado-pendiente_pago { background: #fef3c7; color: #92400e; }
.estado-pagado_sin_enviar { background: #cffafe; color: #155e75; }
.estado-pagado_enviado { background: #d1fae5; color: #065f46; }
.estado-cancelado { background: #e5e7eb; color: #4b5563; }
.row { display: flex; gap: 24px; margin-bottom: 20px; }
.col { flex: 1; }
.box { border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; }
.box h3 { margin: 0 0 8px 0; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.box p { margin: 2px 0; line-height: 1.5; }
.box .strong { font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; }
table th { background: #f9fafb; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
table td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; }
table .num { text-align: right; }
.totales { margin-top: 20px; display: flex; justify-content: flex-end; }
.totales table { width: 280px; }
.totales .total-row td { font-size: 15px; font-weight: 700; border-top: 2px solid #1f2937; padding-top: 10px; }
.totales .saldo { color: #dc2626; }
.totales .pagado { color: #059669; }
.firma { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 11px; line-height: 1.6; }
.acciones { position: fixed; top: 20px; right: 20px; display: flex; gap: 8px; }
.btn-accion { padding: 8px 16px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.btn-imprimir { background: #3b5bdb; color: #fff; }
.btn-cerrar { background: #e5e7eb; color: #1f2937; }
.btn-accion:hover { opacity: .88; }
@media print {
  body { padding: 0; }
  .acciones { display: none; }
  .box { border: none; padding: 0; }
  .header { border-bottom-width: 2px; }
}
</style></head>
<body>

<div class="acciones">
<button class="btn-accion btn-imprimir" onclick="window.print()">🖨️ Imprimir / Guardar PDF</button>
<button class="btn-accion btn-cerrar" onclick="window.close()">✕ Cerrar</button>
</div>

<div class="header">
<div class="empresa">
<h1>{{ empresa.nombre }}</h1>
<div class="info">
{% if empresa.telefono %}📞 {{ empresa.telefono }}<br>{% endif %}
{% if empresa.email %}✉ {{ empresa.email }}<br>{% endif %}
{% if empresa.web %}🌐 {{ empresa.web }}{% endif %}
</div>
</div>
<div class="orden-box">
<div class="num">{{ orden.numero_interno }}</div>
<div class="fecha">{{ orden.fecha }}</div>
<div class="estado estado-{{ orden.estado }}">
{{ {'pendiente_pago':'Pendiente pago','pagado_sin_enviar':'Pagado / Sin enviar','pagado_enviado':'Pagado / Enviado','cancelado':'Cancelado'}.get(orden.estado, orden.estado) }}
</div>
</div>
</div>

<div class="row">
<div class="col"><div class="box">
<h3>Cliente</h3>
<p class="strong">{{ orden.cliente_nombre }}</p>
{% if orden.cliente_doc %}<p>{{ orden.cliente_tipo_doc or '' }} {{ orden.cliente_doc }}</p>{% endif %}
{% if orden.cliente_email %}<p>{{ orden.cliente_email }}</p>{% endif %}
{% if orden.cliente_telefono %}<p>{{ orden.cliente_telefono }}</p>{% endif %}
<p>{{ orden.cliente_provincia or '' }}{% if orden.cliente_localidad %}, {{ orden.cliente_localidad }}{% endif %}</p>
</div></div>
<div class="col"><div class="box">
<h3>Datos del pedido</h3>
<p><strong>Tipo:</strong> {{ orden.tipo|capitalize }}</p>
<p><strong>Vendedor:</strong> {{ orden.vendedor_nombre }}</p>
<p><strong>Canal:</strong> {{ orden.canal_nombre or '—' }}</p>
<p><strong>Kilos totales:</strong> {{ '%.2f'|format(kilos_total) }} kg</p>
</div></div>
</div>

{% if orden.destinatario_nombre or orden.nro_guia %}
<div class="box" style="margin-bottom:20px;">
<h3>Datos de envio</h3>
{% if orden.destinatario_nombre %}<p><strong>Destinatario:</strong> {{ orden.destinatario_nombre }}</p>{% endif %}
{% if orden.destinatario_calle %}<p><strong>Direccion:</strong> {{ orden.destinatario_calle }}{% if orden.destinatario_localidad %}, {{ orden.destinatario_localidad }}{% endif %}{% if orden.destinatario_provincia %} ({{ orden.destinatario_provincia }}){% endif %}{% if orden.destinatario_cp %} CP {{ orden.destinatario_cp }}{% endif %}</p>{% endif %}
{% if orden.transportista_nombre %}<p><strong>Transportista:</strong> {{ orden.transportista_nombre }}</p>{% endif %}
{% if orden.nro_guia %}<p><strong>Nro guia:</strong> {{ orden.nro_guia }}</p>{% endif %}
{% if orden.destinatario_detalles %}<p><strong>Detalles:</strong> {{ orden.destinatario_detalles }}</p>{% endif %}
</div>
{% endif %}

<div class="box">
<h3>Productos</h3>
<table>
<thead><tr><th>Producto</th><th class="num">Cant.</th><th class="num">Precio</th><th class="num">Subtotal</th></tr></thead>
<tbody>
{% for it in items %}
<tr>
<td>{{ it.producto_nombre }}{% if it.sku %} <span style="color:#9ca3af; font-size:11px;">({{ it.sku }})</span>{% endif %}</td>
<td class="num">{{ '%g'|format(it.cantidad) }}</td>
<td class="num">${{ '%.2f'|format(it.precio_unitario) }}</td>
<td class="num">${{ '%.2f'|format(it.subtotal) }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>

<div class="totales">
<table>
<tr><td>Subtotal:</td><td class="num">${{ '%.2f'|format(orden.subtotal) }}</td></tr>
{% if orden.descuento > 0 %}<tr><td>Descuento:</td><td class="num">-${{ '%.2f'|format(orden.descuento) }}</td></tr>{% endif %}
<tr class="total-row"><td>Total:</td><td class="num">${{ '%.2f'|format(orden.total) }}</td></tr>
{% if pagos %}
<tr><td>Pagado:</td><td class="num pagado">${{ '%.2f'|format(total_pagado) }}</td></tr>
<tr><td>Saldo:</td><td class="num {% if total_pagado < orden.total %}saldo{% else %}pagado{% endif %}">${{ '%.2f'|format(orden.total - total_pagado) }}</td></tr>
{% endif %}
</table>
</div>

{% if pagos %}
<div class="box" style="margin-top:20px;">
<h3>Pagos registrados</h3>
<table>
<thead><tr><th>Fecha</th><th>Medio</th><th class="num">Monto</th></tr></thead>
<tbody>
{% for p in pagos %}
<tr><td>{{ p.fecha }}</td><td>{{ p.medio_nombre or '—' }}</td><td class="num">${{ '%.2f'|format(p.monto) }}</td></tr>
{% endfor %}
</tbody>
</table>
</div>
{% endif %}

{% if orden.notas %}
<div class="box" style="margin-top:20px;">
<h3>Notas</h3>
<p>{{ orden.notas }}</p>
</div>
{% endif %}

<div class="firma">
{{ empresa.nombre }}<br>
Gracias por elegirnos
</div>

</body></html>
'''


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
<button type="button" class="btn btn-sm btn-outline-danger" onclick="bulkSubmit('cancelar', 'Cancelar las ordenes seleccionadas?')"><i class="bi bi-x-lg"></i> Cancelar</button>
<button type="button" class="btn btn-sm btn-outline-success" onclick="bulkSubmit('enviado', 'Marcar las seleccionadas como enviadas?')"><i class="bi bi-truck"></i> Enviado</button>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="bulkSubmit('notificar', 'Enviar email Envio en camino?')"><i class="bi bi-envelope"></i> Notificar</button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openBulkFacturar()"><i class="bi bi-receipt"></i> Facturar</button>
</div>
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="30"><input type="checkbox" id="check-all" onchange="toggleAll(this)"></th>
<th>Fecha</th><th>ID</th><th>Estado</th><th>Cliente</th><th class="text-end">Kilos</th><th>Tipo</th><th>Facturacion</th><th class="text-end">Total</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for v in ventas %}
<tr>
<td><input type="checkbox" class="check-row" name="ordenes_ids" value="{{ v.id }}" onchange="updateToolbar()"></td>
<td class="small text-muted text-nowrap">{{ v.fecha }}</td>
<td class="fw-semibold text-nowrap">{{ v.numero_interno }}</td>
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
<td class="text-end text-nowrap">
<a href="{{ url_for('ventas_detalle', id=v.id) }}" class="btn btn-sm btn-outline-secondary" title="Ver / Editar"><i class="bi bi-eye"></i></a>
<a href="{{ url_for('ventas_imprimir', id=v.id) }}" target="_blank" class="btn btn-sm btn-outline-dark" title="Imprimir / PDF"><i class="bi bi-printer"></i></a>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openCompartir({{ v.id }})" title="Compartir"><i class="bi bi-share"></i></button>
{% if v.wa_url %}<a href="{{ v.wa_url }}" target="_blank" class="btn btn-sm btn-outline-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
{% else %}<button class="btn btn-sm btn-outline-secondary" disabled title="Sin telefono"><i class="bi bi-whatsapp"></i></button>{% endif %}
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openEmail({{ v.id }})" title="Email"><i class="bi bi-envelope"></i></button>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrar({{ v.id }}, '{{ v.numero_interno }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="10" class="text-center text-muted py-4">No hay ventas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</form>

<!-- Modales -->
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


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app13; app13.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 13: Imprimir + PDF + Compartir (F2.2b) ===")
    escribir('app13.py', APP13_PY)
    escribir('templates/ventas/imprimir.html', IMPRIMIR_HTML)
    escribir('templates/ventas/lista.html', VENTAS_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app13.py)")


if __name__ == '__main__':
    main()