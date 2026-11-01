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
    print(f"[upgrade17] escrito: {relpath}")


APP17_PY = r'''
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app16 import app, _categorias_arbol, _stats_productos
from app import permiso_required, admin_required
from database import get_db


def _stats_reservados(conn):
    return conn.execute("""
        SELECT COUNT(DISTINCT oi.producto_id) FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        WHERE o.estado = 'pendiente_pago'
    """).fetchone()[0]


@app.route('/productos')
@login_required
@permiso_required('productos')
def productos_lista_v3():
    conn = get_db()
    q = request.args.get('q', '').strip()
    categoria_id = request.args.get('categoria', '').strip()
    alerta = request.args.get('alerta', '').strip()

    sql = """SELECT p.*, c.nombre as categoria_nombre, cp.nombre as parent_nombre
             FROM productos p
             LEFT JOIN categorias_productos c ON c.id = p.categoria_id
             LEFT JOIN categorias_productos cp ON cp.id = c.parent_id
             WHERE p.activo=1"""
    params = []
    if q:
        sql += " AND (p.nombre LIKE ? OR p.sku LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if categoria_id:
        sql += " AND (p.categoria_id=? OR c.parent_id=?)"
        params += [int(categoria_id), int(categoria_id)]
    if alerta == 'sin_foto':
        sql += " AND (p.foto IS NULL OR p.foto='')"
    elif alerta == 'sin_precio':
        sql += " AND (p.precio IS NULL OR p.precio=0)"
    elif alerta == 'agotado':
        sql += " AND p.stock_actual <= 0"
    elif alerta == 'bajo_stock':
        sql += " AND p.stock_minimo > 0 AND p.stock_actual <= p.stock_minimo AND p.stock_actual > 0"
    elif alerta == 'reservado':
        sql += " AND p.id IN (SELECT oi.producto_id FROM orden_items oi JOIN ordenes_venta o ON o.id=oi.orden_id WHERE o.estado='pendiente_pago')"
    sql += " ORDER BY p.nombre"
    productos = conn.execute(sql, params).fetchall()

    stats = _stats_productos(conn)
    stats['reservados'] = _stats_reservados(conn)
    padres, hijos = _categorias_arbol(conn)
    conn.close()
    return render_template('productos/lista.html',
                           productos=productos, q=q, categoria_id=categoria_id,
                           alerta=alerta, stats=stats, padres=padres, hijos=hijos)


@app.route('/productos/reservados')
@login_required
@permiso_required('productos')
def productos_reservados():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id as producto_id, p.nombre as producto_nombre, p.sku as producto_sku,
               p.foto as producto_foto, p.stock_actual,
               SUM(oi.cantidad) as cantidad_reservada,
               COUNT(DISTINCT o.id) as num_ordenes
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE o.estado = 'pendiente_pago'
        GROUP BY p.id
        ORDER BY cantidad_reservada DESC
    """).fetchall()

    reservas = []
    for r in rows:
        d = dict(r)
        d['ordenes'] = conn.execute("""
            SELECT o.id as orden_id, o.numero_interno, o.fecha, oi.cantidad, oi.subtotal,
                   c.nombre_completo as cliente_nombre, c.id as cliente_id,
                   u.nombre as vendedor_nombre
            FROM orden_items oi
            JOIN ordenes_venta o ON o.id = oi.orden_id
            JOIN clientes c ON c.id = o.cliente_id
            JOIN usuarios u ON u.id = o.usuario_id
            WHERE oi.producto_id = ? AND o.estado = 'pendiente_pago'
            ORDER BY o.fecha ASC
        """, (r['producto_id'],)).fetchall()
        reservas.append(d)
    conn.close()
    return render_template('productos/reservados.html', reservas=reservas)


@app.route('/productos/ranking')
@login_required
@permiso_required('productos')
def productos_ranking():
    conn = get_db()
    periodo = request.args.get('periodo', 'mes')
    hoy = date.today()
    if periodo == 'mes':
        ini = hoy.replace(day=1)
    elif periodo == 'trimestre':
        ini = hoy - timedelta(days=90)
    elif periodo == 'anio':
        ini = hoy.replace(month=1, day=1)
    else:
        ini = date(2000, 1, 1)

    ranking = conn.execute("""
        SELECT p.id, p.nombre, p.sku, p.foto,
               SUM(oi.cantidad) as cant_vendida,
               SUM(oi.subtotal) as total_vendido,
               COUNT(DISTINCT o.id) as num_ordenes
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
          AND date(o.fecha) BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY cant_vendida DESC
        LIMIT 50
    """, (ini.isoformat(), hoy.isoformat())).fetchall()
    conn.close()
    return render_template('productos/ranking.html', ranking=ranking, periodo=periodo,
                           ini=ini, fin=hoy)


@app.route('/productos/<int:id>/ajuste', methods=['GET', 'POST'])
@login_required
@admin_required
def productos_ajuste(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))

    if request.method == 'POST':
        try:
            nuevo = float(request.form['nuevo_stock'])
        except (ValueError, KeyError):
            flash('Numero invalido.', 'error')
            conn.close()
            return redirect(url_for('productos_ajuste', id=id))
        motivo = request.form.get('motivo', '').strip()
        if not motivo:
            flash('El motivo es obligatorio.', 'error')
            conn.close()
            return redirect(url_for('productos_ajuste', id=id))
        anterior = producto['stock_actual']
        diferencia = nuevo - anterior
        conn.execute("UPDATE productos SET stock_actual=?, actualizado=datetime('now') WHERE id=?",
                     (nuevo, id))
        conn.execute("""INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id)
            VALUES (?, 'ajuste', ?, ?, ?)""",
            (id, diferencia,
             f'Ajuste manual: {motivo} (antes: {anterior:g}, ahora: {nuevo:g})',
             current_user.id))
        conn.commit(); conn.close()
        flash(f'Stock ajustado: {anterior:g} → {nuevo:g}. Motivo registrado.', 'success')
        return redirect(url_for('productos_lista'))

    movimientos = conn.execute("""SELECT m.*, u.nombre as usuario_nombre FROM movimientos_stock m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        WHERE m.producto_id = ? ORDER BY m.fecha DESC, m.id DESC LIMIT 30""", (id,)).fetchall()
    conn.close()
    return render_template('productos/ajuste.html', producto=producto, movimientos=movimientos)


app.view_functions['productos_lista'] = productos_lista_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


PRODUCTOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Productos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Productos</h4>
<div class="d-flex gap-2 flex-wrap">
<a href="{{ url_for('productos_ranking') }}" class="btn btn-outline-primary btn-sm"><i class="bi bi-trophy"></i> Ranking</a>
<a href="{{ url_for('productos_reservados') }}" class="btn btn-outline-warning btn-sm"><i class="bi bi-hourglass-split"></i> Reservados</a>
<a href="{{ url_for('productos_categorias') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-tags"></i> Categorias</a>
<a href="{{ url_for('productos_nuevo') }}" class="btn btn-dark btn-sm"><i class="bi bi-plus-lg"></i> Nuevo producto</a>
</div>
</div>

<div class="row row-cols-2 row-cols-md-5 g-2 mb-3">
<div class="col"><div class="card-kpi"><div class="kpi-label">Total productos</div><div class="kpi-value">{{ stats.total }}</div></div></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='sin_foto') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #f59e0b;"><div class="kpi-label">Sin foto</div><div class="kpi-value">{{ stats.sin_foto }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='sin_precio') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #ef4444;"><div class="kpi-label">Sin precio</div><div class="kpi-value">{{ stats.sin_precio }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_lista', alerta='agotado') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #6b7280;"><div class="kpi-label">Agotados</div><div class="kpi-value">{{ stats.agotados }}</div></div></a></div>
<div class="col"><a href="{{ url_for('productos_reservados') }}" class="text-decoration-none text-reset"><div class="card-kpi" style="border-left:3px solid #06b6d4;"><div class="kpi-label">Reservados</div><div class="kpi-value">{{ stats.reservados }}</div></div></a></div>
</div>

<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-4"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="SKU o nombre"></div>
<div class="col-md-3"><label class="form-label small text-muted">Categoria</label>
<select name="categoria" class="form-select form-select-sm">
<option value="">Todas</option>
{% for p in padres %}
<option value="{{ p.id }}" {% if categoria_id==p.id|string %}selected{% endif %}>{{ p.nombre }}</option>
{% for h in hijos.get(p.id, []) %}
<option value="{{ h.id }}" {% if categoria_id==h.id|string %}selected{% endif %}>&nbsp;&nbsp;— {{ h.nombre }}</option>
{% endfor %}
{% endfor %}
</select></div>
<div class="col-md-3"><label class="form-label small text-muted">Alerta</label>
<select name="alerta" class="form-select form-select-sm">
<option value="">Todas</option>
<option value="sin_foto" {% if alerta=='sin_foto' %}selected{% endif %}>Sin foto</option>
<option value="sin_precio" {% if alerta=='sin_precio' %}selected{% endif %}>Sin precio</option>
<option value="agotado" {% if alerta=='agotado' %}selected{% endif %}>Agotados</option>
<option value="bajo_stock" {% if alerta=='bajo_stock' %}selected{% endif %}>Bajo stock</option>
<option value="reservado" {% if alerta=='reservado' %}selected{% endif %}>Reservados</option>
</select></div>
<div class="col-md-2"><button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i> Filtrar</button></div>
</div></form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="60">Foto</th><th>SKU</th><th>Nombre</th><th>Categoria</th>
<th class="text-end">Precio</th><th class="text-end">Stock</th><th>Estado</th>
<th class="text-muted small">Creado</th><th class="text-end">Acciones</th>
</tr></thead>
<tbody>
{% for p in productos %}
<tr>
<td>
{% if p.foto %}
<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" style="width:44px;height:44px;object-fit:cover;border-radius:8px;">
{% else %}
<div style="width:44px;height:44px;border-radius:8px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;color:#9ca3af;"><i class="bi bi-image"></i></div>
{% endif %}
</td>
<td class="text-muted small">{{ p.sku or '' }}</td>
<td class="fw-semibold">{{ p.nombre }}</td>
<td class="small">{% if p.parent_nombre %}{{ p.parent_nombre }} › {% endif %}{{ p.categoria_nombre or '—' }}</td>
<td class="text-end">{% if p.precio and p.precio > 0 %}${{ '%.2f'|format(p.precio) }}{% else %}<span class="text-danger small">Sin precio</span>{% endif %}</td>
<td class="text-end">
{% if p.stock_actual <= 0 %}<span class="badge bg-secondary">Agotado</span>
{% elif p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo %}<span class="badge bg-danger">{{ '%g'|format(p.stock_actual) }}</span>
{% else %}<span class="badge bg-success">{{ '%g'|format(p.stock_actual) }}</span>{% endif %}
</td>
<td class="small text-muted">
{% if not p.foto %}<span class="badge bg-warning text-dark">Sin foto</span>{% endif %}
{% if not p.precio or p.precio == 0 %}<span class="badge bg-danger">Sin precio</span>{% endif %}
</td>
<td class="small text-muted">{{ p.creado[:10] if p.creado else '' }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('productos_editar', id=p.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
{% if current_user.es_admin %}
<a href="{{ url_for('productos_ajuste', id=p.id) }}" class="btn btn-sm btn-outline-primary" title="Ajustar stock"><i class="bi bi-sliders"></i></a>
{% endif %}
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarProducto({{ p.id }}, '{{ p.nombre }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="9" class="text-center text-muted py-4">Sin productos.</td></tr>
{% endfor %}
</tbody></table></div></div>

<div class="modal fade" id="borrarProductoModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-producto-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar producto <span id="borrar-producto-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, el producto se desactiva inmediatamente.</div>
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
function openBorrarProducto(id, nombre) {
  document.getElementById('borrar-producto-form').action = '/productos/' + id + '/borrar';
  document.getElementById('borrar-producto-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('borrarProductoModal')).show();
}
</script>
{% endblock %}
'''


RESERVADOS_HTML = r'''{% extends "base.html" %}
{% block title %}Productos reservados{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Productos reservados</h4>
<div class="text-muted small">Productos comprometidos en ordenes pendientes de pago. El stock se descuenta cuando la orden pasa a Pagado.</div>
</div>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

{% if reservas %}
<div class="row g-3">
{% for r in reservas %}
<div class="col-12">
<div class="card shadow-sm">
<div class="card-body">
<div class="d-flex align-items-start gap-3 mb-3">
{% if r.producto_foto %}
<img src="{{ url_for('productos_ver_foto', nombre=r.producto_foto) }}" style="width:60px;height:60px;object-fit:cover;border-radius:10px;">
{% else %}
<div style="width:60px;height:60px;border-radius:10px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;color:#9ca3af;"><i class="bi bi-image fs-4"></i></div>
{% endif %}
<div class="flex-grow-1">
<div class="fw-semibold">{{ r.producto_nombre }} {% if r.producto_sku %}<small class="text-muted">({{ r.producto_sku }})</small>{% endif %}</div>
<div class="small text-muted">Stock actual: <strong>{{ '%g'|format(r.stock_actual) }}</strong> · Reservado: <strong class="text-warning">{{ '%g'|format(r.cantidad_reservada) }}</strong> · {{ r.num_ordenes }} orden(es)</div>
</div>
<a href="{{ url_for('productos_editar', id=r.producto_id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a>
</div>

<table class="table table-sm mb-0">
<thead class="table-light">
<tr><th>Orden</th><th>Fecha</th><th>Cliente</th><th>Vendedor</th><th class="text-end">Cantidad</th><th class="text-end">Subtotal</th><th></th></tr>
</thead>
<tbody>
{% for o in r.ordenes %}
<tr>
<td class="fw-semibold small">{{ o.numero_interno }}</td>
<td class="small text-muted">{{ o.fecha }}</td>
<td class="small"><a href="{{ url_for('clientes_editar', id=o.cliente_id) }}" class="text-decoration-none">{{ o.cliente_nombre }}</a></td>
<td class="small">{{ o.vendedor_nombre }}</td>
<td class="text-end">{{ '%g'|format(o.cantidad) }}</td>
<td class="text-end">${{ '%.2f'|format(o.subtotal) }}</td>
<td class="text-end"><a href="{{ url_for('ventas_detalle', id=o.orden_id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-eye"></i></a></td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</div>
{% endfor %}
</div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-check-circle fs-1 text-success"></i>
<h5 class="mt-3">Sin reservas</h5>
<p class="text-muted mb-0">Ningun producto esta comprometido en ordenes pendientes de pago.</p>
</div></div>
{% endif %}
{% endblock %}
'''


RANKING_HTML = r'''{% extends "base.html" %}
{% block title %}Ranking productos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Ranking de productos mas vendidos</h4>
<div class="text-muted small">{{ ini.strftime('%d/%m/%Y') }} al {{ fin.strftime('%d/%m/%Y') }}</div>
</div>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Periodo</label>
<select name="periodo" class="form-select form-select-sm" onchange="this.form.submit()">
<option value="mes" {% if periodo=='mes' %}selected{% endif %}>Este mes</option>
<option value="trimestre" {% if periodo=='trimestre' %}selected{% endif %}>Ultimos 90 dias</option>
<option value="anio" {% if periodo=='anio' %}selected{% endif %}>Este año</option>
<option value="todo" {% if periodo=='todo' %}selected{% endif %}>Todo el historial</option>
</select></div>
</div></form>

{% if ranking %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th width="60">#</th><th width="60">Foto</th><th>Producto</th><th>SKU</th>
<th class="text-end">Unidades</th><th class="text-end">Total $</th><th class="text-end">Ordenes</th>
</tr></thead>
<tbody>
{% for p in ranking %}
<tr>
<td>
{% if loop.index == 1 %}<span class="badge" style="background:#fbbf24;color:#78350f;font-size:.9rem;">🥇 1</span>
{% elif loop.index == 2 %}<span class="badge" style="background:#d1d5db;color:#374151;font-size:.9rem;">🥈 2</span>
{% elif loop.index == 3 %}<span class="badge" style="background:#fbbf24;color:#78350f;font-size:.85rem;opacity:.85;">🥉 3</span>
{% else %}<span class="text-muted fw-semibold">{{ loop.index }}</span>{% endif %}
</td>
<td>
{% if p.foto %}
<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" style="width:40px;height:40px;object-fit:cover;border-radius:8px;">
{% else %}
<div style="width:40px;height:40px;border-radius:8px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;color:#9ca3af;"><i class="bi bi-image"></i></div>
{% endif %}
</td>
<td class="fw-semibold">{{ p.nombre }}</td>
<td class="small text-muted">{{ p.sku or '' }}</td>
<td class="text-end fw-semibold">{{ '%g'|format(p.cant_vendida) }}</td>
<td class="text-end">${{ '%.2f'|format(p.total_vendido) }}</td>
<td class="text-end text-muted">{{ p.num_ordenes }}</td>
</tr>
{% endfor %}
</tbody></table></div></div>
{% else %}
<div class="card shadow-sm"><div class="card-body text-center py-5">
<i class="bi bi-trophy fs-1 text-muted"></i>
<h5 class="mt-3">Sin ventas en este periodo</h5>
<p class="text-muted mb-0">Cuando vendas productos (ordenes cobradas), apareceran aca.</p>
</div></div>
{% endif %}
{% endblock %}
'''


AJUSTE_HTML = r'''{% extends "base.html" %}
{% block title %}Ajustar stock{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Ajustar stock manualmente</h4>
<div class="text-muted small">{{ producto.nombre }}{% if producto.sku %} · SKU {{ producto.sku }}{% endif %}</div>
</div>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-5">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3">Nuevo valor de stock</h6>
<div class="alert alert-light border mb-3 py-2">
Stock actual: <strong class="fs-5">{{ '%g'|format(producto.stock_actual) }}</strong>
</div>
<form method="post">
<div class="mb-3">
<label class="form-label">Nuevo stock *</label>
<input type="number" step="0.01" name="nuevo_stock" class="form-control" required value="{{ producto.stock_actual }}">
</div>
<div class="mb-3">
<label class="form-label">Motivo * (queda en el historial)</label>
<textarea name="motivo" class="form-control" rows="3" required placeholder="Ej: rotura de mercaderia, conteo fisico, error de carga previo, merma..."></textarea>
<div class="form-text">Obligatorio. Se guarda en el historial de movimientos.</div>
</div>
<div class="alert alert-warning py-2 small"><i class="bi bi-exclamation-triangle"></i> Este ajuste queda registrado como movimiento y afecta el stock del producto.</div>
<button class="btn btn-primary">Guardar ajuste</button>
</form>
</div></div>
</div>

<div class="col-md-7">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3">Historial de movimientos</h6>
{% if movimientos %}
<table class="table table-sm mb-0">
<thead class="table-light"><tr><th>Fecha</th><th>Tipo</th><th class="text-end">Cant.</th><th>Referencia</th><th>Usuario</th></tr></thead>
<tbody>
{% for m in movimientos %}
<tr>
<td class="small text-muted text-nowrap">{{ m.fecha[:16] if m.fecha else '' }}</td>
<td>
{% if m.tipo == 'entrada' %}<span class="badge bg-success">Entrada</span>
{% elif m.tipo == 'salida' %}<span class="badge bg-danger">Salida</span>
{% elif m.tipo == 'ajuste' %}<span class="badge bg-warning text-dark">Ajuste</span>
{% elif m.tipo == 'ajuste_inicial' %}<span class="badge bg-info text-dark">Inicial</span>
{% else %}<span class="badge bg-secondary">{{ m.tipo }}</span>{% endif %}
</td>
<td class="text-end fw-semibold {% if m.tipo in ('entrada','ajuste_inicial') %}text-success{% elif m.tipo == 'salida' %}text-danger{% endif %}">
{% if m.tipo in ('entrada','ajuste_inicial') %}+{% endif %}{{ '%g'|format(m.cantidad) }}
</td>
<td class="small">{{ m.referencia or '' }}</td>
<td class="small text-muted">{{ m.usuario_nombre or '' }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}
<p class="text-muted small mb-0">Sin movimientos registrados.</p>
{% endif %}
</div></div>
</div>
</div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app17; app17.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 17: Ajuste stock + Reservados + Ranking (F3.2) ===")
    escribir('app17.py', APP17_PY)
    escribir('templates/productos/lista.html', PRODUCTOS_LISTA)
    escribir('templates/productos/reservados.html', RESERVADOS_HTML)
    escribir('templates/productos/ranking.html', RANKING_HTML)
    escribir('templates/productos/ajuste.html', AJUSTE_HTML)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app17.py)")


if __name__ == '__main__':
    main()