
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
