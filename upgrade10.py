# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade10] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade10] sin DB."); return
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'peso_valor' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN peso_valor REAL DEFAULT 0")
        print("[upgrade10] + productos.peso_valor")
    if 'peso_unidad' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN peso_unidad TEXT DEFAULT 'kg'")
        print("[upgrade10] + productos.peso_unidad")
    conn.commit(); conn.close()


APP10_PY = r'''
import re, urllib.parse
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app8 import app
from app import permiso_required
from database import get_db


def _estado_humano(e):
    return {'pendiente_pago': 'Pendiente de pago', 'pagado_sin_enviar': 'Pagado / Sin enviar',
            'pagado_enviado': 'Pagado / Enviado', 'cancelado': 'Cancelado'}.get(e, e)


def _limpiar_tel(t):
    if not t: return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'): n = '54' + n
    return n


# ==== Ventas (lista nueva) ====
@app.route('/ventas')
@login_required
@permiso_required('ventas')
def ventas_lista_v2():
    conn = get_db()
    q = request.args.get('q', '').strip()
    estado = request.args.get('estado', '')
    canal = request.args.get('canal', '')
    tipo = request.args.get('tipo', '')
    vendedor = request.args.get('vendedor', '')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')

    sql = """SELECT o.*, c.nombre_completo as cliente_nombre, c.telefono as cliente_telefono,
             u.nombre as vendedor_nombre, cv.nombre as canal_nombre,
             (SELECT COALESCE(SUM(
                CASE WHEN p.peso_unidad = 'g' THEN (oi.cantidad * p.peso_valor) / 1000.0
                     ELSE oi.cantidad * COALESCE(p.peso_valor, 0) END
             ), 0)
              FROM orden_items oi
              LEFT JOIN productos p ON p.id = oi.producto_id
              WHERE oi.orden_id = o.id) as kilos
             FROM ordenes_venta o
             JOIN clientes c ON c.id = o.cliente_id
             JOIN usuarios u ON u.id = o.usuario_id
             LEFT JOIN canales_venta cv ON cv.id = o.canal_id
             WHERE 1=1"""
    params = []
    if not current_user.es_admin:
        sql += " AND o.usuario_id=?"; params.append(current_user.id)
    elif vendedor:
        sql += " AND o.usuario_id=?"; params.append(int(vendedor))
    if q:
        sql += " AND (o.numero_interno LIKE ? OR c.nombre_completo LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if estado:
        sql += " AND o.estado=?"; params.append(estado)
    if canal:
        sql += " AND o.canal_id=?"; params.append(int(canal))
    if tipo:
        sql += " AND o.tipo=?"; params.append(tipo)
    if desde:
        sql += " AND date(o.fecha)>=?"; params.append(desde)
    if hasta:
        sql += " AND date(o.fecha)<=?"; params.append(hasta)
    sql += " ORDER BY o.id DESC"
    rows = conn.execute(sql, params).fetchall()

    ventas = []
    for r in rows:
        d = dict(r)
        tel = _limpiar_tel(r['cliente_telefono'])
        if tel:
            msg = (f"Hola {r['cliente_nombre']}!\n"
                   f"Te paso el resumen de tu pedido {r['numero_interno']}:\n"
                   f"Total: ${r['total']:.2f}\n"
                   f"Estado: {_estado_humano(r['estado'])}")
            d['wa_url'] = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
        else:
            d['wa_url'] = None
        ventas.append(d)

    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT * FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall() if current_user.es_admin else []
    conn.close()
    return render_template('ventas/lista.html', ventas=ventas, q=q, estado=estado, canal=canal,
                           tipo=tipo, vendedor=vendedor, desde=desde, hasta=hasta,
                           canales=canales, vendedores=vendedores)


app.view_functions['ventas_lista'] = ventas_lista_v2


# ==== Productos (con peso) ====
@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_nuevo_v2():
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_actual = float(request.form.get('stock_actual') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
        except ValueError:
            flash('Revisa los numeros.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        conn = get_db()
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            conn.close(); flash('SKU ya existe.', 'error')
            return render_template('productos/form.html', producto=None, valores=request.form)
        cur = conn.execute("""INSERT INTO productos (sku,nombre,costo,precio,stock_actual,stock_minimo,peso_valor,peso_unidad)
            VALUES (?,?,?,?,?,?,?,?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad))
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    return render_template('productos/form.html', producto=None, valores={})


@app.route('/productos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_editar_v2(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); return redirect(url_for('productos_lista'))
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
        except ValueError:
            flash('Revisa los numeros.', 'error')
            return render_template('productos/form.html', producto=producto, valores=request.form)
        conn.execute("""UPDATE productos SET sku=?,nombre=?,costo=?,precio=?,stock_minimo=?,peso_valor=?,peso_unidad=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={})


app.view_functions['productos_nuevo'] = productos_nuevo_v2
app.view_functions['productos_editar'] = productos_editar_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


PRODUCTOS_FORM = r'''{% extends "base.html" %}
{% block title %}Producto{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if producto else 'Nuevo' }} producto</h4>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (producto if producto else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-4"><label class="form-label">SKU</label><input name="sku" class="form-control" value="{{ v['sku'] if 'sku' in v and v['sku'] else '' }}"></div>
<div class="col-md-8"><label class="form-label">Nombre *</label><input name="nombre" class="form-control" required value="{{ v['nombre'] if 'nombre' in v else '' }}"></div>
<div class="col-md-4"><label class="form-label">Costo</label><input type="number" step="0.01" name="costo" class="form-control" value="{{ v['costo'] if 'costo' in v else 0 }}"></div>
<div class="col-md-4"><label class="form-label">Precio</label><input type="number" step="0.01" name="precio" class="form-control" value="{{ v['precio'] if 'precio' in v else 0 }}"></div>
<div class="col-md-4"><label class="form-label">Stock minimo</label><input type="number" step="0.01" name="stock_minimo" class="form-control" value="{{ v['stock_minimo'] if 'stock_minimo' in v else 0 }}"></div>
{% if not producto %}<div class="col-md-4"><label class="form-label">Stock inicial</label><input type="number" step="0.01" name="stock_actual" class="form-control" value="0"><div class="form-text">Solo al crear.</div></div>{% endif %}
<div class="col-md-4"><label class="form-label">Peso del producto</label>
<div class="input-group">
<input type="number" step="0.01" min="0" name="peso_valor" class="form-control" value="{{ v['peso_valor'] if 'peso_valor' in v and v['peso_valor'] is not none else 0 }}">
<select name="peso_unidad" class="form-select" style="max-width:80px;">
<option value="kg" {% if ('peso_unidad' in v and v['peso_unidad']=='kg') or 'peso_unidad' not in v %}selected{% endif %}>kg</option>
<option value="g" {% if 'peso_unidad' in v and v['peso_unidad']=='g' %}selected{% endif %}>g</option>
</select>
</div>
<div class="form-text">Se usa para calcular kilos por pedido.</div>
</div>
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
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
<button type="button" class="btn btn-sm btn-outline-danger" onclick="bulkSubmit('cancelar', 'Cancelar las ordenes seleccionadas? Se devuelve stock si corresponde.')"><i class="bi bi-x-lg"></i> Cancelar</button>
<button type="button" class="btn btn-sm btn-outline-success" onclick="bulkSubmit('enviado', 'Marcar las seleccionadas como enviadas?')"><i class="bi bi-truck"></i> Enviado</button>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="bulkSubmit('notificar', 'Enviar email Envio en camino a los clientes con email?')"><i class="bi bi-envelope"></i> Notificar</button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openBulkFacturar()"><i class="bi bi-receipt"></i> Facturar</button>
</div>
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="30"><input type="checkbox" id="check-all" onchange="toggleAll(this)"></th>
<th>Fecha</th>
<th>ID</th>
<th>Estado</th>
<th>Cliente</th>
<th class="text-end">Kilos</th>
<th>Tipo</th>
<th>Facturacion</th>
<th class="text-end">Total</th>
<th class="text-end">Acciones</th>
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
{% if v.wa_url %}<a href="{{ v.wa_url }}" target="_blank" class="btn btn-sm btn-outline-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
{% else %}<button class="btn btn-sm btn-outline-secondary" disabled title="Sin telefono"><i class="bi bi-whatsapp"></i></button>{% endif %}
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openEmail({{ v.id }})" title="Enviar por email"><i class="bi bi-envelope"></i></button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openMas({{ v.id }})" title="Mas acciones"><i class="bi bi-three-dots"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="10" class="text-center text-muted py-4">No hay ventas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</form>

<!-- Modal: cambiar estado -->
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
<div class="form-text mt-2">Si pasas a "Pagado / Sin enviar" se descuenta stock. Si cancelas, se devuelve.</div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cerrar</button>
<button type="submit" class="btn btn-primary btn-sm">Guardar</button>
</div>
</form></div></div></div>

<!-- Modal: factura -->
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

<!-- Modal: email -->
<div class="modal fade" id="emailModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Enviar email al cliente</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="text-muted small mb-3">Se envia al email cargado en la ficha del cliente. Si no tiene, editalo primero en Clientes.</p>
<form id="email-form" method="post">
<div class="d-grid gap-2">
<button type="submit" formaction="" class="btn btn-outline-primary" onclick="this.form.action=this.form.getAttribute('data-url')+'/confirmacion'"><i class="bi bi-file-text"></i> Enviar orden</button>
<button type="submit" formaction="" class="btn btn-outline-success" onclick="this.form.action=this.form.getAttribute('data-url')+'/pago'"><i class="bi bi-cash-coin"></i> Notificar pago</button>
<button type="submit" formaction="" class="btn btn-outline-info" onclick="this.form.action=this.form.getAttribute('data-url')+'/envio'"><i class="bi bi-truck"></i> Notificar envio</button>
<button type="submit" formaction="" class="btn btn-outline-secondary" onclick="this.form.action=this.form.getAttribute('data-url')+'/entrega'"><i class="bi bi-box-seam"></i> Notificar entrega</button>
<button type="submit" formaction="" class="btn btn-outline-dark" onclick="this.form.action=this.form.getAttribute('data-url')+'/factura'"><i class="bi bi-file-earmark-pdf"></i> Enviar factura</button>
</div>
</form>
</div>
</div></div></div>

<!-- Modal: mas acciones -->
<div class="modal fade" id="masModal" tabindex="-1">
<div class="modal-dialog modal-sm"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Mas acciones</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="text-muted small mb-2">Proximamente:</p>
<button class="btn btn-outline-secondary w-100 mb-2" disabled><i class="bi bi-file-earmark-pdf"></i> Descargar PDF</button>
<button class="btn btn-outline-secondary w-100 mb-2" disabled><i class="bi bi-printer"></i> Imprimir</button>
<button class="btn btn-outline-secondary w-100" disabled><i class="bi bi-share"></i> Compartir</button>
</div>
</div></div></div>

<!-- Modal: bulk facturar -->
<div class="modal fade" id="bulkFacturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Marcar seleccionadas como facturadas</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2"><label class="form-label">Nro ARCA base (opcional)</label><input id="bulk-factura-nro" class="form-control">
<div class="form-text">Se aplica a todas. Si necesitas distintos, dejanlo vacio y editalos uno por uno.</div></div>
<p class="text-muted small mb-0">Se marcaran <strong><span id="bulk-factura-count">0</span></strong> ordenes como facturadas.</p>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-primary" onclick="confirmBulkFacturar()">Confirmar</button>
</div>
</div></div></div>

<script>
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
function openMas(id) { new bootstrap.Modal(document.getElementById('masModal')).show(); }
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
python -c "import app10; app10.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 10: Peso productos + Lista nueva ventas (F2.1) ===")
    migrar()
    escribir('app10.py', APP10_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('templates/ventas/lista.html', VENTAS_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app10.py)")


if __name__ == '__main__':
    main()