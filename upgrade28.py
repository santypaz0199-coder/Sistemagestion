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
    print(f"[upgrade28] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade28] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    if 'vendedor_id' not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN vendedor_id INTEGER")
        print("[upgrade28] + clientes.vendedor_id")
        # Asignar clientes existentes al admin (primer admin)
        admin = conn.execute("SELECT id FROM usuarios WHERE rol='admin' AND activo=1 ORDER BY id LIMIT 1").fetchone()
        if admin:
            conn.execute("UPDATE clientes SET vendedor_id=? WHERE vendedor_id IS NULL", (admin[0],))
            print(f"[upgrade28] clientes existentes asignados al admin (id={admin[0]})")

    conn.commit(); conn.close()


APP28_PY = r'''
import re, urllib.parse
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app27 import app
from app import permiso_required, admin_required, generar_numero_orden
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


def _puede_ver_cliente(cliente, usuario):
    """Verifica si el usuario puede ver/editar este cliente."""
    if not cliente:
        return False
    if usuario.es_admin:
        return True
    return cliente['vendedor_id'] == usuario.id


# ===== Lista de clientes con filtro por vendedor =====
def clientes_lista_v3():
    q = request.args.get('q', '').strip()
    filtro_tipo = request.args.get('tipo', '')
    provincia_id = request.args.get('provincia_id', '').strip()
    localidad_id = request.args.get('localidad_id', '').strip()
    vendedor_filtro = request.args.get('vendedor', '').strip()

    conn = get_db()
    sql = """SELECT c.*,
             p.nombre as provincia_nombre,
             l.nombre as localidad_nombre,
             v.nombre as vendedor_nombre,
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
             LEFT JOIN usuarios v ON v.id = c.vendedor_id
             WHERE c.activo=1"""
    params = []

    # Vendedor solo ve sus propios clientes
    if not current_user.es_admin:
        sql += " AND c.vendedor_id = ?"
        params.append(current_user.id)
    elif vendedor_filtro:
        sql += " AND c.vendedor_id = ?"
        params.append(int(vendedor_filtro))

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

    # Vendedores para el filtro (solo admin)
    vendedores = []
    if current_user.es_admin:
        vendedores = conn.execute(
            "SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre"
        ).fetchall()

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
                           stats=stats, vendedores=vendedores, vendedor_filtro=vendedor_filtro)


app.view_functions['clientes_lista'] = clientes_lista_v3


# ===== Nuevo cliente (auto-asigna vendedor) =====
def _datos_cliente_form():
    try:
        provincia_id = int(request.form.get('provincia_id') or 0) or None
    except ValueError:
        provincia_id = None
    try:
        localidad_id = int(request.form.get('localidad_id') or 0) or None
    except ValueError:
        localidad_id = None
    try:
        vendedor_id = int(request.form.get('vendedor_id') or 0) or None
    except ValueError:
        vendedor_id = None
    return {
        'nombre_completo': request.form.get('nombre_completo', '').strip(),
        'tipo_doc': request.form.get('tipo_doc', '').strip(),
        'nro_doc': request.form.get('nro_doc', '').strip(),
        'provincia_id': provincia_id,
        'localidad_id': localidad_id,
        'codigo_postal': request.form.get('codigo_postal', '').strip(),
        'email': request.form.get('email', '').strip(),
        'telefono': request.form.get('telefono', '').strip(),
        'es_minorista': 1 if request.form.get('es_minorista') else 0,
        'es_mayorista': 1 if request.form.get('es_mayorista') else 0,
        'notas': request.form.get('notas', '').strip(),
        'vendedor_id': vendedor_id,
    }


def _render_form_cliente(conn, cliente, valores):
    from app21 import _provincias, _localidades_por_provincia
    provincias = _provincias(conn)
    locs = _localidades_por_provincia(conn)
    vendedores = conn.execute(
        "SELECT id, nombre, rol FROM usuarios WHERE activo=1 ORDER BY nombre"
    ).fetchall()
    return render_template('clientes/form.html', cliente=cliente, valores=valores,
                           provincias=provincias, localidades_por_provincia=locs,
                           vendedores=vendedores)


def clientes_nuevo_v3():
    conn = get_db()
    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form_cliente(get_db(), None, d)
        # Si es vendedor, se auto-asigna
        if not current_user.es_admin:
            d['vendedor_id'] = current_user.id
        # Si es admin y no eligio, se asigna a si mismo
        if current_user.es_admin and not d['vendedor_id']:
            d['vendedor_id'] = current_user.id
        conn2 = get_db()
        conn2.execute("""INSERT INTO clientes
            (nombre_completo, tipo_doc, nro_doc, provincia_id, localidad_id, codigo_postal,
             email, telefono, es_minorista, es_mayorista, notas, vendedor_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'],
             d['notas'], d['vendedor_id']))
        conn2.commit(); conn2.close()
        conn.close()
        flash('Cliente creado.', 'success')
        return redirect(url_for('clientes_lista'))
    conn.close()
    return _render_form_cliente(get_db(), None, {})


def clientes_editar_v4(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))
    cliente = dict(row)
    # Verificar permiso
    if not current_user.es_admin and cliente.get('vendedor_id') != current_user.id:
        conn.close(); flash('Ese cliente no te pertenece.', 'error')
        return redirect(url_for('clientes_lista'))

    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form_cliente(get_db(), cliente, d)
        # Vendedor no puede reasignar a otro vendedor
        if not current_user.es_admin:
            d['vendedor_id'] = cliente['vendedor_id']
        # Admin sin seleccion: mantiene el actual
        if current_user.es_admin and not d['vendedor_id']:
            d['vendedor_id'] = cliente['vendedor_id']
        conn.execute("""UPDATE clientes SET
            nombre_completo=?, tipo_doc=?, nro_doc=?, provincia_id=?, localidad_id=?, codigo_postal=?,
            email=?, telefono=?, es_minorista=?, es_mayorista=?, notas=?, vendedor_id=? WHERE id=?""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'],
             d['notas'], d['vendedor_id'], id))
        conn.commit(); conn.close()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('clientes_lista'))

    conn.close()
    return _render_form_cliente(get_db(), cliente, {})


app.view_functions['clientes_nuevo'] = clientes_nuevo_v3
app.view_functions['clientes_editar'] = clientes_editar_v4


# ===== Nueva venta con filtro de clientes =====
def ventas_nueva_v4():
    conn = get_db()
    if request.method == 'POST':
        try:
            cliente_id = int(request.form['cliente_id'])
            tipo = request.form['tipo']
            canal_id = int(request.form['canal_id']) if request.form.get('canal_id') else None
            fecha = request.form.get('fecha') or date.today().isoformat()
            descuento = float(request.form.get('descuento') or 0)
            notas = request.form.get('notas', '').strip()
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            precios = request.form.getlist('precio')
        except (ValueError, KeyError):
            conn.close(); flash('Revisa los datos.', 'error')
            return redirect(url_for('ventas_nueva'))

        # Verificar que el cliente pertenece al vendedor (si no es admin)
        cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
        if not cliente:
            conn.close(); flash('Cliente no encontrado.', 'error')
            return redirect(url_for('ventas_nueva'))
        if not current_user.es_admin and cliente['vendedor_id'] != current_user.id:
            conn.close(); flash('Ese cliente no te pertenece.', 'error')
            return redirect(url_for('ventas_nueva'))

        items = []
        for pid, cant, prec in zip(pids, cants, precios):
            if not pid or not cant: continue
            try:
                cant_f = float(cant); prec_f = float(prec)
            except ValueError: continue
            if cant_f <= 0: continue
            items.append({'producto_id': int(pid), 'cantidad': cant_f, 'precio': prec_f, 'subtotal': cant_f * prec_f})
        if not items:
            conn.close(); flash('Agrega productos.', 'error')
            return redirect(url_for('ventas_nueva'))
        subtotal = sum(i['subtotal'] for i in items)
        total = max(0, subtotal - descuento)
        numero = generar_numero_orden(conn)
        cur = conn.execute("""INSERT INTO ordenes_venta
            (numero_interno,cliente_id,usuario_id,canal_id,tipo,fecha,estado,estado_facturacion,subtotal,descuento,total,notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, cliente_id, current_user.id, canal_id, tipo, fecha, 'pendiente_pago',
             'no_requiere', subtotal, descuento, total, notas))
        oid = cur.lastrowid
        for it in items:
            conn.execute("""INSERT INTO orden_items (orden_id,producto_id,cantidad,precio_unitario,subtotal)
                VALUES (?,?,?,?,?)""",
                         (oid, it['producto_id'], it['cantidad'], it['precio'], it['subtotal']))
        conn.commit(); conn.close()
        flash(f'Orden {numero} creada.', 'success')
        return redirect(url_for('ventas_detalle', id=oid))

    # GET: filtrar clientes
    if current_user.es_admin:
        clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 ORDER BY nombre_completo").fetchall()
    else:
        clientes = conn.execute(
            "SELECT * FROM clientes WHERE activo=1 AND vendedor_id=? ORDER BY nombre_completo",
            (current_user.id,)).fetchall()
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('ventas/form.html', clientes=clientes, productos=productos,
                           canales=canales, hoy=date.today().isoformat())


app.view_functions['ventas_nueva'] = ventas_nueva_v4


# ===== Borrar cliente con verificacion =====
def clientes_borrar_v3(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not cliente:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))
    if not current_user.es_admin and cliente['vendedor_id'] != current_user.id:
        conn.close(); flash('Ese cliente no te pertenece.', 'error')
        return redirect(url_for('clientes_lista'))

    if current_user.es_admin:
        conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Cliente desactivado.', 'success')
        return redirect(url_for('clientes_lista'))

    # Vendedor: crear solicitud
    from app12 import _crear_solicitud
    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'cliente', id, cliente['nombre_completo'], motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para este cliente.', 'error')
    return redirect(url_for('clientes_lista'))


app.view_functions['clientes_borrar_v2'] = clientes_borrar_v3


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
<div class="col-md-2">
<label class="form-label small text-muted">Provincia</label>
<select name="provincia_id" id="filtro-provincia" class="form-select form-select-sm">
<option value="">Todas</option>
{% for p in provincias %}
<option value="{{ p.id }}" {% if provincia_id==p.id|string %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-2">
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
{% if current_user.es_admin %}
<div class="col-md-2">
<label class="form-label small text-muted">Vendedor</label>
<select name="vendedor" class="form-select form-select-sm">
<option value="">Todos</option>
{% for v in vendedores %}
<option value="{{ v.id }}" {% if vendedor_filtro==v.id|string %}selected{% endif %}>{{ v.nombre }}</option>
{% endfor %}
</select>
</div>
{% endif %}
<div class="col-md-1">
<button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i></button>
</div>
</div>
</form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Nombre</th><th>Doc</th><th>Ciudad / Provincia</th><th>Contacto</th>
{% if current_user.es_admin %}<th>Vendedor</th>{% endif %}
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
{% if current_user.es_admin %}
<td class="small"><span class="badge bg-secondary">{{ c.vendedor_nombre or '—' }}</span></td>
{% endif %}
<td class="text-nowrap">
{% if c.es_minorista %}<span class="badge bg-info text-dark">Minorista</span>{% endif %}
{% if c.es_mayorista %}<span class="badge bg-warning text-dark">Mayorista</span>{% endif %}
</td>
<td class="text-end">
{% if c.total_compras > 0 %}
<div class="fw-semibold">${{ '{:,.0f}'.format(c.total_compras).replace(',', '.') }}</div>
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
<tr><td colspan="8" class="text-center text-muted py-4">Sin clientes con esos filtros.</td></tr>
{% endfor %}
</tbody></table></div></div>

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


CLIENTES_FORM = r'''{% extends "base.html" %}
{% block title %}Cliente{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if cliente else 'Nuevo' }} cliente</h4>
<a href="{{ url_for('clientes_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (cliente if cliente else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Nombre completo *</label>
<input name="nombre_completo" class="form-control" required value="{{ v.get('nombre_completo') or '' }}">
</div>
<div class="col-md-3">
<label class="form-label">Tipo doc</label>
<select name="tipo_doc" class="form-select">
<option value="">--</option>
{% for t in ['CUIT','CUIL','DNI'] %}
<option value="{{ t }}" {% if v.get('tipo_doc') == t %}selected{% endif %}>{{ t }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3">
<label class="form-label">Numero</label>
<input name="nro_doc" class="form-control" value="{{ v.get('nro_doc') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Email</label>
<input type="email" name="email" class="form-control" value="{{ v.get('email') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Telefono</label>
<input name="telefono" class="form-control" value="{{ v.get('telefono') or '' }}">
</div>

<div class="col-md-6">
<label class="form-label">Provincia</label>
<select name="provincia_id" id="provincia-select" class="form-select">
<option value="">— Sin provincia —</option>
{% for p in provincias %}
<option value="{{ p.id }}" {% if v.get('provincia_id') == p.id %}selected{% endif %}>{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-6">
<label class="form-label">Localidad</label>
<div class="input-group">
<select name="localidad_id" id="localidad-select" class="form-select" {% if not v.get('provincia_id') %}disabled{% endif %}>
<option value="">— Sin localidad —</option>
{% if v.get('provincia_id') and localidades_por_provincia.get(v.get('provincia_id')) %}
{% for l in localidades_por_provincia[v.get('provincia_id')] %}
<option value="{{ l.id }}" {% if v.get('localidad_id') == l.id %}selected{% endif %}>{{ l.nombre }}</option>
{% endfor %}
{% endif %}
</select>
<button type="button" class="btn btn-outline-secondary" id="btn-add-localidad" onclick="abrirAgregarLocalidad()" title="Agregar localidad que falta"><i class="bi bi-plus-lg"></i></button>
</div>
<div class="form-text">¿No esta tu localidad? Click en +</div>
</div>

<div class="col-md-4">
<label class="form-label">Codigo postal</label>
<input name="codigo_postal" class="form-control" value="{{ v.get('codigo_postal') or '' }}">
</div>

{% if current_user.es_admin %}
<div class="col-md-8">
<label class="form-label">Vendedor (dueño de la cartera)</label>
<select name="vendedor_id" class="form-select">
<option value="">— Asignar a mi (admin) —</option>
{% for u in vendedores %}
<option value="{{ u.id }}" {% if v.get('vendedor_id') == u.id %}selected{% endif %}>{{ u.nombre }} ({{ u.rol }})</option>
{% endfor %}
</select>
<div class="form-text">Solo el admin puede reasignar clientes entre vendedores.</div>
</div>
{% else %}
<input type="hidden" name="vendedor_id" value="{{ current_user.id }}">
<div class="col-md-8">
<label class="form-label">Vendedor</label>
<div class="form-control-plaintext"><span class="badge bg-secondary">{{ current_user.nombre }}</span></div>
<div class="form-text">Tu eres el dueño de este cliente.</div>
</div>
{% endif %}

<div class="col-md-12">
<label class="form-label d-block">Tags *</label>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_minorista" id="es_minorista" {% if v.get('es_minorista') %}checked{% endif %}>
<label class="form-check-label" for="es_minorista">Minorista</label>
</div>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_mayorista" id="es_mayorista" {% if v.get('es_mayorista') %}checked{% endif %}>
<label class="form-check-label" for="es_mayorista">Mayorista</label>
</div>
<div class="form-text">Un cliente puede ser ambos a la vez.</div>
</div>
<div class="col-12">
<label class="form-label">Notas</label>
<textarea name="notas" class="form-control" rows="2">{{ v.get('notas') or '' }}</textarea>
</div>
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>

<div class="modal fade" id="addLocalidadModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Agregar nueva localidad</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<p class="text-muted small">Se agrega a la provincia seleccionada y queda disponible para todos.</p>
<div class="mb-2">
<label class="form-label">Provincia</label>
<input id="add-prov-nombre" class="form-control" disabled>
</div>
<div class="mb-2">
<label class="form-label">Nombre de la localidad *</label>
<input id="add-loc-nombre" class="form-control" placeholder="Ej: Villa Nueva" required>
</div>
<div id="add-loc-error" class="alert alert-danger py-2 small d-none"></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="button" class="btn btn-primary" onclick="guardarLocalidad()">Agregar</button>
</div>
</div></div></div>

<script>
const LOCALIDADES = {{ localidades_por_provincia|tojson }};
const provSelect = document.getElementById('provincia-select');
const locSelect = document.getElementById('localidad-select');
const btnAdd = document.getElementById('btn-add-localidad');

function actualizarLocalidades() {
  const pid = provSelect.value;
  locSelect.innerHTML = '<option value="">— Sin localidad —</option>';
  if (!pid) { locSelect.disabled = true; btnAdd.disabled = true; return; }
  locSelect.disabled = false; btnAdd.disabled = false;
  (LOCALIDADES[pid] || []).forEach(function(l) {
    const opt = document.createElement('option');
    opt.value = l.id; opt.textContent = l.nombre;
    locSelect.appendChild(opt);
  });
}
provSelect.addEventListener('change', actualizarLocalidades);
if (!provSelect.value) btnAdd.disabled = true;
if (provSelect.value) {
  const currentLoc = locSelect.value;
  actualizarLocalidades();
  if (currentLoc) locSelect.value = currentLoc;
}
function abrirAgregarLocalidad() {
  const pid = provSelect.value;
  if (!pid) return;
  document.getElementById('add-prov-nombre').value = provSelect.options[provSelect.selectedIndex].text;
  document.getElementById('add-loc-nombre').value = '';
  document.getElementById('add-loc-error').classList.add('d-none');
  new bootstrap.Modal(document.getElementById('addLocalidadModal')).show();
}
async function guardarLocalidad() {
  const nombre = document.getElementById('add-loc-nombre').value.trim();
  const pid = provSelect.value;
  const errEl = document.getElementById('add-loc-error');
  errEl.classList.add('d-none');
  if (!nombre) {
    errEl.textContent = 'Escribi el nombre de la localidad';
    errEl.classList.remove('d-none');
    return;
  }
  try {
    const resp = await fetch('/api/localidades/agregar', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({nombre: nombre, provincia_id: parseInt(pid)})
    });
    const data = await resp.json();
    if (!data.ok) {
      errEl.textContent = data.error || 'Error al guardar';
      errEl.classList.remove('d-none');
      return;
    }
    if (!LOCALIDADES[pid]) LOCALIDADES[pid] = [];
    if (!LOCALIDADES[pid].some(l => l.id === data.id)) LOCALIDADES[pid].push({id: data.id, nombre: data.nombre});
    actualizarLocalidades();
    locSelect.value = data.id;
    bootstrap.Modal.getInstance(document.getElementById('addLocalidadModal')).hide();
  } catch (e) {
    errEl.textContent = 'Error de conexion: ' + e.message;
    errEl.classList.remove('d-none');
  }
}
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app28; app28.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 28: Clientes por vendedor (ownership) ===")
    migrar()
    escribir('app28.py', APP28_PY)
    escribir('templates/clientes/lista.html', CLIENTES_LISTA)
    escribir('templates/clientes/form.html', CLIENTES_FORM)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app28.py)")
    print("")
    print("NOTA: los clientes existentes quedaron asignados al admin.")
    print("      Editalos si queres reasignarlos a un vendedor especifico.")


if __name__ == '__main__':
    main()