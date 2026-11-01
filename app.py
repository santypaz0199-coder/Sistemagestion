
import os
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave-local-cambiar-luego')

login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id, nombre, email, rol):
        self.id = id
        self.nombre = nombre
        self.email = email
        self.rol = rol

    @property
    def es_admin(self):
        return self.rol == 'admin'

    def puede(self, modulo):
        if self.rol == 'admin':
            return True
        permitidos = {'vendedor': ['dashboard', 'clientes', 'ventas', 'emails']}
        return modulo in permitidos.get(self.rol, [])


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row['id'], row['nombre'], row['email'], row['rol'])
    return None


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not current_user.is_authenticated or not current_user.es_admin:
            flash('No tenes permiso.', 'error')
            return redirect(url_for('dashboard'))
        return f(*a, **k)
    return w


def permiso_required(modulo):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not current_user.puede(modulo):
                flash('No tenes permiso.', 'error')
                return redirect(url_for('dashboard'))
            return f(*a, **k)
        return w
    return deco


def generar_numero_orden(conn):
    n = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM ordenes_venta").fetchone()[0]
    return f"ORD-{n:06d}"


def aplicar_descuento_stock(conn, orden_id, usuario_id):
    items = conn.execute("SELECT * FROM orden_items WHERE orden_id=?", (orden_id,)).fetchall()
    for it in items:
        conn.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id=?",
                     (it['cantidad'], it['producto_id']))
        conn.execute("""INSERT INTO movimientos_stock
            (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?,?,?,?,?)""",
                     (it['producto_id'], 'salida', it['cantidad'], f'Orden #{orden_id}', usuario_id))
    conn.execute("UPDATE ordenes_venta SET stock_descontado=1 WHERE id=?", (orden_id,))


def revertir_stock(conn, orden_id, usuario_id):
    items = conn.execute("SELECT * FROM orden_items WHERE orden_id=?", (orden_id,)).fetchall()
    for it in items:
        conn.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id=?",
                     (it['cantidad'], it['producto_id']))
        conn.execute("""INSERT INTO movimientos_stock
            (producto_id, tipo, cantidad, referencia, usuario_id) VALUES (?,?,?,?,?)""",
                     (it['producto_id'], 'entrada', it['cantidad'], f'Cancelacion #{orden_id}', usuario_id))
    conn.execute("UPDATE ordenes_venta SET stock_descontado=0 WHERE id=?", (orden_id,))


def productos_en_negativo(conn):
    return conn.execute("SELECT nombre FROM productos WHERE activo=1 AND stock_actual<0").fetchall()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE lower(email)=? AND activo=1", (email,)).fetchone()
        conn.close()
        if row and check_password_hash(row['password_hash'], pw):
            login_user(User(row['id'], row['nombre'], row['email'], row['rol']))
            return redirect(url_for('dashboard'))
        flash('Email o contrasena incorrectos', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    hoy = date.today().isoformat()
    inicio_mes = date.today().replace(day=1).isoformat()
    data = {}
    if current_user.es_admin:
        data['total_clientes'] = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
        data['total_productos'] = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0]
        data['stock_total'] = conn.execute("SELECT COALESCE(SUM(stock_actual),0) FROM productos WHERE activo=1").fetchone()[0]
        data['bajo_stock'] = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_actual<=stock_minimo AND stock_minimo>0").fetchone()[0]
        data['ventas_mes'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM ordenes_venta WHERE date(fecha)>=? AND estado IN ('pagado_sin_enviar','pagado_enviado')", (inicio_mes,)).fetchone()[0]
        data['ordenes_mes'] = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE date(fecha)>=?", (inicio_mes,)).fetchone()[0]
    else:
        data['total_clientes'] = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
        data['mis_ventas_hoy'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM ordenes_venta WHERE usuario_id=? AND date(fecha)=? AND estado IN ('pagado_sin_enviar','pagado_enviado')", (current_user.id, hoy)).fetchone()[0]
        data['mis_ventas_mes'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM ordenes_venta WHERE usuario_id=? AND date(fecha)>=? AND estado IN ('pagado_sin_enviar','pagado_enviado')", (current_user.id, inicio_mes)).fetchone()[0]
        data['mis_ordenes_mes'] = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE usuario_id=? AND date(fecha)>=?", (current_user.id, inicio_mes)).fetchone()[0]
        data['mis_ordenes_pendientes'] = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE usuario_id=? AND estado='pendiente_pago'", (current_user.id,)).fetchone()[0]
    conn.close()
    return render_template('dashboard.html', **data)


@app.route('/mi-cuenta', methods=['GET', 'POST'])
@login_required
def mi_cuenta():
    if request.method == 'POST':
        actual = request.form.get('actual', '')
        nueva = request.form.get('nueva', '')
        confirmar = request.form.get('confirmar', '')
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if not check_password_hash(row['password_hash'], actual):
            conn.close(); flash('Contrasena actual incorrecta.', 'error')
            return redirect(url_for('mi_cuenta'))
        if len(nueva) < 6 or nueva != confirmar:
            conn.close(); flash('Revisa la nueva contrasena.', 'error')
            return redirect(url_for('mi_cuenta'))
        conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?", (generate_password_hash(nueva), current_user.id))
        conn.commit(); conn.close()
        flash('Contrasena actualizada.', 'success')
        return redirect(url_for('mi_cuenta'))
    return render_template('mi_cuenta.html')


@app.route('/usuarios')
@login_required
@admin_required
def usuarios_lista():
    conn = get_db()
    usuarios = conn.execute("SELECT * FROM usuarios ORDER BY creado DESC").fetchall()
    conn.close()
    return render_template('usuarios/lista.html', usuarios=usuarios)


@app.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def usuarios_nuevo():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        rol = request.form['rol']
        if not nombre or not email or not password:
            flash('Completa todos los campos.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form)
        conn = get_db()
        if conn.execute("SELECT id FROM usuarios WHERE lower(email)=?", (email,)).fetchone():
            conn.close(); flash('Email ya existe.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form)
        conn.execute("INSERT INTO usuarios (nombre,email,password_hash,rol) VALUES (?,?,?,?)",
                     (nombre, email, generate_password_hash(password), rol))
        conn.commit(); conn.close()
        flash('Usuario creado.', 'success')
        return redirect(url_for('usuarios_lista'))
    return render_template('usuarios/form.html', usuario=None, valores={})


@app.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def usuarios_editar(id):
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
    if not usuario:
        conn.close(); return redirect(url_for('usuarios_lista'))
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        email = request.form['email'].strip().lower()
        rol = request.form['rol']
        password = request.form.get('password', '').strip()
        activo = 1 if request.form.get('activo') else 0
        if password:
            conn.execute("UPDATE usuarios SET nombre=?,email=?,rol=?,activo=?,password_hash=? WHERE id=?",
                         (nombre, email, rol, activo, generate_password_hash(password), id))
        else:
            conn.execute("UPDATE usuarios SET nombre=?,email=?,rol=?,activo=? WHERE id=?",
                         (nombre, email, rol, activo, id))
        conn.commit(); conn.close()
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('usuarios_lista'))
    conn.close()
    return render_template('usuarios/form.html', usuario=usuario, valores={})


@app.route('/usuarios/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def usuarios_eliminar(id):
    if id == current_user.id:
        flash('No podes eliminarte.', 'error')
        return redirect(url_for('usuarios_lista'))
    conn = get_db()
    conn.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('usuarios_lista'))


def _datos_cliente():
    return {
        'nombre_completo': request.form.get('nombre_completo', '').strip(),
        'tipo_doc': request.form.get('tipo_doc', '').strip(),
        'nro_doc': request.form.get('nro_doc', '').strip(),
        'provincia': request.form.get('provincia', '').strip(),
        'localidad': request.form.get('localidad', '').strip(),
        'codigo_postal': request.form.get('codigo_postal', '').strip(),
        'email': request.form.get('email', '').strip(),
        'telefono': request.form.get('telefono', '').strip(),
        'es_minorista': 1 if request.form.get('es_minorista') else 0,
        'es_mayorista': 1 if request.form.get('es_mayorista') else 0,
        'notas': request.form.get('notas', '').strip(),
    }


@app.route('/clientes')
@login_required
@permiso_required('clientes')
def clientes_lista():
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '')
    provincia = request.args.get('provincia', '').strip()
    conn = get_db()
    sql = "SELECT * FROM clientes WHERE activo=1"
    params = []
    if q:
        sql += " AND (nombre_completo LIKE ? OR nro_doc LIKE ? OR email LIKE ?)"
        params += [f'%{q}%'] * 3
    if tipo == 'minorista':
        sql += " AND es_minorista=1"
    elif tipo == 'mayorista':
        sql += " AND es_mayorista=1"
    if provincia:
        sql += " AND provincia=?"; params.append(provincia)
    sql += " ORDER BY nombre_completo"
    clientes = conn.execute(sql, params).fetchall()
    provincias = [r[0] for r in conn.execute("SELECT DISTINCT provincia FROM clientes WHERE provincia!='' ORDER BY provincia").fetchall()]
    conn.close()
    return render_template('clientes/lista.html', clientes=clientes, q=q, filtro_tipo=tipo, provincia=provincia, provincias=provincias)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_nuevo():
    if request.method == 'POST':
        d = _datos_cliente()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            return render_template('clientes/form.html', cliente=None, valores=d)
        conn = get_db()
        conn.execute("""INSERT INTO clientes (nombre_completo,tipo_doc,nro_doc,provincia,localidad,codigo_postal,email,telefono,es_minorista,es_mayorista,notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (d['nombre_completo'],d['tipo_doc'],d['nro_doc'],d['provincia'],d['localidad'],
             d['codigo_postal'],d['email'],d['telefono'],d['es_minorista'],d['es_mayorista'],d['notas']))
        conn.commit(); conn.close()
        flash('Cliente creado.', 'success')
        return redirect(url_for('clientes_lista'))
    return render_template('clientes/form.html', cliente=None, valores={})


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_editar(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not cliente:
        conn.close(); return redirect(url_for('clientes_lista'))
    if request.method == 'POST':
        d = _datos_cliente()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            return render_template('clientes/form.html', cliente=cliente, valores=d)
        conn.execute("""UPDATE clientes SET nombre_completo=?,tipo_doc=?,nro_doc=?,provincia=?,localidad=?,codigo_postal=?,email=?,telefono=?,es_minorista=?,es_mayorista=?,notas=? WHERE id=?""",
            (d['nombre_completo'],d['tipo_doc'],d['nro_doc'],d['provincia'],d['localidad'],
             d['codigo_postal'],d['email'],d['telefono'],d['es_minorista'],d['es_mayorista'],d['notas'],id))
        conn.commit(); conn.close()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('clientes_lista'))
    conn.close()
    return render_template('clientes/form.html', cliente=cliente, valores={})


@app.route('/clientes/<int:id>/eliminar', methods=['POST'])
@login_required
@permiso_required('clientes')
def clientes_eliminar(id):
    conn = get_db()
    conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Cliente desactivado.', 'success')
    return redirect(url_for('clientes_lista'))


@app.route('/productos')
@login_required
@permiso_required('productos')
def productos_lista():
    q = request.args.get('q', '').strip()
    conn = get_db()
    sql = "SELECT * FROM productos WHERE activo=1"
    params = []
    if q:
        sql += " AND (nombre LIKE ? OR sku LIKE ?)"; params += [f'%{q}%'] * 2
    sql += " ORDER BY nombre"
    productos = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template('productos/lista.html', productos=productos, q=q)


@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_nuevo():
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_actual = float(request.form.get('stock_actual') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
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
        cur = conn.execute("INSERT INTO productos (sku,nombre,costo,precio,stock_actual,stock_minimo) VALUES (?,?,?,?,?,?)",
                           (sku, nombre, costo, precio, stock_actual, stock_minimo))
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
def productos_editar(id):
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
        except ValueError:
            flash('Revisa los numeros.', 'error')
            return render_template('productos/form.html', producto=producto, valores=request.form)
        conn.execute("UPDATE productos SET sku=?,nombre=?,costo=?,precio=?,stock_minimo=? WHERE id=?",
                     (sku, nombre, costo, precio, stock_minimo, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={})


@app.route('/productos/<int:id>/eliminar', methods=['POST'])
@login_required
@permiso_required('productos')
def productos_eliminar(id):
    conn = get_db()
    conn.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Producto desactivado.', 'success')
    return redirect(url_for('productos_lista'))


@app.route('/ventas')
@login_required
@permiso_required('ventas')
def ventas_lista():
    conn = get_db()
    q = request.args.get('q', '').strip()
    estado = request.args.get('estado', '')
    canal = request.args.get('canal', '')
    tipo = request.args.get('tipo', '')
    vendedor = request.args.get('vendedor', '')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    sql = """SELECT o.*, c.nombre_completo as cliente_nombre, u.nombre as vendedor_nombre, cv.nombre as canal_nombre
             FROM ordenes_venta o
             JOIN clientes c ON c.id=o.cliente_id
             JOIN usuarios u ON u.id=o.usuario_id
             LEFT JOIN canales_venta cv ON cv.id=o.canal_id WHERE 1=1"""
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
    ventas = conn.execute(sql, params).fetchall()
    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT * FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall() if current_user.es_admin else []
    conn.close()
    return render_template('ventas/lista.html', ventas=ventas, q=q, estado=estado, canal=canal,
                           tipo=tipo, vendedor=vendedor, desde=desde, hasta=hasta,
                           canales=canales, vendedores=vendedores)


@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
@permiso_required('ventas')
def ventas_nueva():
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
            (numero, cliente_id, current_user.id, canal_id, tipo, fecha, 'pendiente_pago', 'no_requiere', subtotal, descuento, total, notas))
        oid = cur.lastrowid
        for it in items:
            conn.execute("INSERT INTO orden_items (orden_id,producto_id,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",
                         (oid, it['producto_id'], it['cantidad'], it['precio'], it['subtotal']))
        conn.commit(); conn.close()
        flash(f'Orden {numero} creada.', 'success')
        return redirect(url_for('ventas_detalle', id=oid))
    clientes = conn.execute("SELECT * FROM clientes WHERE activo=1 ORDER BY nombre_completo").fetchall()
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('ventas/form.html', clientes=clientes, productos=productos, canales=canales, hoy=date.today().isoformat())


@app.route('/ventas/<int:id>')
@login_required
@permiso_required('ventas')
def ventas_detalle(id):
    conn = get_db()
    orden = conn.execute("""SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email,
        c.telefono as cliente_telefono, c.provincia as cliente_provincia, c.localidad as cliente_localidad,
        c.nro_doc as cliente_doc, c.tipo_doc as cliente_tipo_doc,
        u.nombre as vendedor_nombre, cv.nombre as canal_nombre, t.nombre as transportista_nombre
        FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id JOIN usuarios u ON u.id=o.usuario_id
        LEFT JOIN canales_venta cv ON cv.id=o.canal_id LEFT JOIN transportistas t ON t.id=o.transportista_id
        WHERE o.id=?""", (id,)).fetchone()
    if not orden:
        conn.close(); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))
    items = conn.execute("SELECT oi.*, p.nombre as producto_nombre, p.sku FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
    pagos = conn.execute("SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=? ORDER BY pg.id", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1 ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas)


@app.route('/ventas/<int:id>/pago', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_pago(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden or (not current_user.es_admin and orden['usuario_id'] != current_user.id):
        conn.close(); return redirect(url_for('ventas_lista'))
    if orden['estado'] == 'cancelado':
        conn.close(); flash('Orden cancelada.', 'error'); return redirect(url_for('ventas_detalle', id=id))
    try:
        monto = float(request.form['monto'])
        comision = float(request.form.get('comision') or 0)
    except (ValueError, KeyError):
        conn.close(); flash('Monto invalido.', 'error'); return redirect(url_for('ventas_detalle', id=id))
    medio_id = int(request.form['medio_pago_id']) if request.form.get('medio_pago_id') else None
    fecha = request.form.get('fecha') or date.today().isoformat()
    conn.execute("INSERT INTO pagos (orden_id,fecha,medio_pago_id,monto,comision,monto_neto,usuario_id) VALUES (?,?,?,?,?,?,?)",
                 (id, fecha, medio_id, monto, comision, monto - comision, current_user.id))
    total_pagado = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (id,)).fetchone()[0]
    if total_pagado >= orden['total'] and orden['estado'] == 'pendiente_pago':
        aplicar_descuento_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
        conn.commit()
        neg = productos_en_negativo(conn)
        conn.close()
        if neg:
            flash('Pago completo. ATENCION stock negativo: ' + ', '.join([p['nombre'] for p in neg]), 'error')
        else:
            flash('Pago completo. Stock descontado.', 'success')
        return redirect(url_for('ventas_detalle', id=id))
    conn.commit(); conn.close()
    flash('Pago registrado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/pago/<int:pago_id>/eliminar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_pago_eliminar(id, pago_id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden or (not current_user.es_admin and orden['usuario_id'] != current_user.id):
        conn.close(); return redirect(url_for('ventas_lista'))
    if orden['estado'] != 'pendiente_pago':
        conn.close(); flash('Solo en pendientes.', 'error'); return redirect(url_for('ventas_detalle', id=id))
    conn.execute("DELETE FROM pagos WHERE id=? AND orden_id=?", (pago_id, id))
    conn.commit(); conn.close()
    flash('Pago eliminado.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/estado', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_estado(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden or (not current_user.es_admin and orden['usuario_id'] != current_user.id):
        conn.close(); return redirect(url_for('ventas_lista'))
    nuevo = request.form['estado']
    actual = orden['estado']
    trans = {'pendiente_pago': ['pagado_sin_enviar', 'cancelado'],
             'pagado_sin_enviar': ['pagado_enviado', 'cancelado'],
             'pagado_enviado': ['cancelado'], 'cancelado': []}
    if nuevo not in trans.get(actual, []):
        conn.close(); flash('Transicion no permitida.', 'error'); return redirect(url_for('ventas_detalle', id=id))
    if nuevo == 'cancelado':
        if orden['stock_descontado']:
            revertir_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
    elif nuevo == 'pagado_sin_enviar' and not orden['stock_descontado']:
        aplicar_descuento_stock(conn, id, current_user.id)
        conn.execute("UPDATE ordenes_venta SET estado='pagado_sin_enviar' WHERE id=?", (id,))
    else:
        conn.execute("UPDATE ordenes_venta SET estado=? WHERE id=?", (nuevo, id))
    conn.commit(); conn.close()
    flash(f'Estado actualizado a {nuevo}.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/envio', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_envio(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden or (not current_user.es_admin and orden['usuario_id'] != current_user.id):
        conn.close(); return redirect(url_for('ventas_lista'))
    trans = request.form.get('transportista_id') or None
    conn.execute("""UPDATE ordenes_venta SET transportista_id=?, nro_guia=?,
        destinatario_nombre=?, destinatario_provincia=?, destinatario_localidad=?,
        destinatario_cp=?, destinatario_calle=?, destinatario_detalles=? WHERE id=?""",
        (int(trans) if trans else None,
         request.form.get('nro_guia', '').strip() or None,
         request.form.get('destinatario_nombre', '').strip() or None,
         request.form.get('destinatario_provincia', '').strip() or None,
         request.form.get('destinatario_localidad', '').strip() or None,
         request.form.get('destinatario_cp', '').strip() or None,
         request.form.get('destinatario_calle', '').strip() or None,
         request.form.get('destinatario_detalles', '').strip() or None, id))
    conn.commit(); conn.close()
    flash('Datos de envio guardados.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


@app.route('/ventas/<int:id>/factura', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_factura(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden or (not current_user.es_admin and orden['usuario_id'] != current_user.id):
        conn.close(); return redirect(url_for('ventas_lista'))
    est = request.form.get('estado_facturacion', 'no_requiere')
    if est == 'facturada':
        nro = request.form.get('nro_factura_arca', '').strip()
        fecha = request.form.get('fecha_factura', '').strip() or date.today().isoformat()
        if not nro:
            conn.close(); flash('Ingresa Nro ARCA.', 'error'); return redirect(url_for('ventas_detalle', id=id))
        conn.execute("UPDATE ordenes_venta SET estado_facturacion='facturada', nro_factura_arca=?, fecha_factura=? WHERE id=?", (nro, fecha, id))
    else:
        conn.execute("UPDATE ordenes_venta SET estado_facturacion=?, nro_factura_arca=NULL, fecha_factura=NULL WHERE id=?", (est, id))
    conn.commit(); conn.close()
    flash('Facturacion actualizada.', 'success')
    return redirect(url_for('ventas_detalle', id=id))


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)

