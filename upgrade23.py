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
    print(f"[upgrade23] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade23] sin DB."); return
    conn = sqlite3.connect(db)

    # 1. Recrear compra_items con descripcion y producto_id nullable
    cols_ci = [r[1] for r in conn.execute("PRAGMA table_info(compra_items)").fetchall()]
    if 'descripcion' not in cols_ci:
        conn.execute("ALTER TABLE compra_items RENAME TO compra_items_bak")
        conn.execute("""
            CREATE TABLE compra_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id INTEGER NOT NULL,
                producto_id INTEGER,
                descripcion TEXT,
                cantidad REAL NOT NULL,
                costo_unitario REAL NOT NULL,
                FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        """)
        conn.execute("""INSERT INTO compra_items (id, compra_id, producto_id, cantidad, costo_unitario)
                        SELECT id, compra_id, producto_id, cantidad, costo_unitario FROM compra_items_bak""")
        conn.execute("DROP TABLE compra_items_bak")
        print("[upgrade23] compra_items recreada con descripcion")

    # 2. Tipo y categoria_id en compras
    cols_c = [r[1] for r in conn.execute("PRAGMA table_info(compras)").fetchall()]
    if 'tipo' not in cols_c:
        conn.execute("ALTER TABLE compras ADD COLUMN tipo TEXT DEFAULT 'stock'")
        print("[upgrade23] + compras.tipo")
    if 'categoria_id' not in cols_c:
        conn.execute("ALTER TABLE compras ADD COLUMN categoria_id INTEGER")
        print("[upgrade23] + compras.categoria_id")

    # 3. Tabla N:N productos-proveedores
    conn.execute("""
        CREATE TABLE IF NOT EXISTS productos_proveedores (
            producto_id INTEGER NOT NULL,
            proveedor_id INTEGER NOT NULL,
            PRIMARY KEY (producto_id, proveedor_id),
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade23] tabla productos_proveedores OK")

    conn.commit(); conn.close()


APP23_PY = r'''
import os
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app22 import app
from app import permiso_required, admin_required
from database import get_db


def _mes_ant(hoy):
    if hoy.month == 1:
        return date(hoy.year-1, 12, 1), date(hoy.year-1, 12, 31)
    ini = date(hoy.year, hoy.month-1, 1)
    ult = date(hoy.year, hoy.month, 1) - timedelta(days=1)
    return ini, ult


def _var(curr, prev):
    if prev == 0:
        return None if curr == 0 else 100.0
    return ((curr - prev) / prev) * 100


def gastos_unificado():
    tab = request.args.get('tab', 'gastos')
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()
    ini_ant, fin_ant = _mes_ant(hoy)
    ini_ant_s, fin_ant_s = ini_ant.isoformat(), fin_ant.isoformat()

    gastos_mes = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=?", (ini_mes,)).fetchone()[0]
    gastos_ant = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ?", (ini_ant_s, fin_ant_s)).fetchone()[0]
    compras_mes = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras WHERE date(fecha)>=?", (ini_mes,)).fetchone()[0]
    compras_ant = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras WHERE date(fecha) BETWEEN ? AND ?", (ini_ant_s, fin_ant_s)).fetchone()[0]

    stats = {
        'gastos_mes': gastos_mes, 'gastos_ant': gastos_ant,
        'compras_mes': compras_mes, 'compras_ant': compras_ant,
        'total_mes': gastos_mes + compras_mes,
        'total_ant': gastos_ant + compras_ant,
        'var_gastos': _var(gastos_mes, gastos_ant),
        'var_compras': _var(compras_mes, compras_ant),
        'var_total': _var(gastos_mes + compras_mes, gastos_ant + compras_ant),
    }

    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    proveedores_lista = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()

    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    cat_filtro = request.args.get('categoria', '')
    prov_filtro = request.args.get('proveedor', '')

    gastos = compras = proveedores = []
    if tab == 'gastos':
        sql = """SELECT g.*, cg.nombre as categoria_nombre, u.nombre as usuario_nombre
                 FROM gastos g LEFT JOIN categorias_gastos cg ON cg.id=g.categoria_id
                 LEFT JOIN usuarios u ON u.id=g.usuario_id WHERE 1=1"""
        params = []
        if desde: sql += " AND date(g.fecha)>=?"; params.append(desde)
        if hasta: sql += " AND date(g.fecha)<=?"; params.append(hasta)
        if cat_filtro: sql += " AND g.categoria_id=?"; params.append(int(cat_filtro))
        sql += " ORDER BY g.fecha DESC, g.id DESC"
        gastos = conn.execute(sql, params).fetchall()
    elif tab == 'compras':
        sql = """SELECT c.*, p.nombre as proveedor_nombre, u.nombre as usuario_nombre
                 FROM compras c LEFT JOIN proveedores p ON p.id=c.proveedor_id
                 LEFT JOIN usuarios u ON u.id=c.usuario_id WHERE 1=1"""
        params = []
        if desde: sql += " AND date(c.fecha)>=?"; params.append(desde)
        if hasta: sql += " AND date(c.fecha)<=?"; params.append(hasta)
        if prov_filtro: sql += " AND c.proveedor_id=?"; params.append(int(prov_filtro))
        sql += " ORDER BY c.id DESC"
        compras = conn.execute(sql, params).fetchall()
    else:
        proveedores = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()

    conn.close()
    return render_template('gastos/lista.html',
        tab=tab, stats=stats, gastos=gastos, compras=compras, proveedores=proveedores,
        categorias=categorias, proveedores_lista=proveedores_lista,
        desde=desde, hasta=hasta, cat_filtro=cat_filtro, prov_filtro=prov_filtro)


# Redirects compatibilidad
def compras_redirect():
    return redirect(url_for('gastos_lista', tab='compras'))

def proveedores_redirect():
    return redirect(url_for('gastos_lista', tab='proveedores'))

app.view_functions['gastos_lista'] = gastos_unificado
app.view_functions['compras_lista'] = compras_redirect
app.view_functions['proveedores_lista'] = proveedores_redirect


@app.route('/api/productos-por-proveedor/<int:pid>')
@login_required
def api_productos_por_proveedor(pid):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.nombre, p.sku, p.costo, p.stock_actual
        FROM productos p
        JOIN productos_proveedores pp ON pp.producto_id = p.id
        WHERE pp.proveedor_id = ? AND p.activo = 1
        ORDER BY p.nombre
    """, (pid,)).fetchall()
    conn.close()
    return jsonify([{'id': r['id'], 'nombre': r['nombre'], 'sku': r['sku'],
                     'costo': r['costo'], 'stock_actual': r['stock_actual']} for r in rows])


# === Proveedores ===
@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def proveedores_nuevo():
    conn = get_db()
    productos_lista = conn.execute("SELECT id, nombre, sku FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('proveedores/form.html', proveedor=None, valores=request.form,
                                   productos_lista=productos_lista, productos_seleccionados=[])
        cur = conn.execute("INSERT INTO proveedores (nombre,cuit,contacto,telefono,email) VALUES (?,?,?,?,?)",
                     (nombre, request.form.get('cuit','').strip(), request.form.get('contacto','').strip(),
                      request.form.get('telefono','').strip(), request.form.get('email','').strip()))
        pid = cur.lastrowid
        for prod_id in request.form.getlist('productos'):
            try:
                conn.execute("INSERT OR IGNORE INTO productos_proveedores (producto_id, proveedor_id) VALUES (?, ?)",
                             (int(prod_id), pid))
            except: pass
        conn.commit(); conn.close()
        flash('Proveedor creado.', 'success')
        return redirect(url_for('gastos_lista', tab='proveedores'))
    conn.close()
    return render_template('proveedores/form.html', proveedor=None, valores={},
                           productos_lista=productos_lista, productos_seleccionados=[])


@app.route('/proveedores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def proveedores_editar(id):
    conn = get_db()
    prov = conn.execute("SELECT * FROM proveedores WHERE id=?", (id,)).fetchone()
    if not prov:
        conn.close(); return redirect(url_for('gastos_lista', tab='proveedores'))
    productos_lista = conn.execute("SELECT id, nombre, sku FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    prod_sel = [r[0] for r in conn.execute("SELECT producto_id FROM productos_proveedores WHERE proveedor_id=?", (id,)).fetchall()]

    if request.method == 'POST':
        conn.execute("UPDATE proveedores SET nombre=?,cuit=?,contacto=?,telefono=?,email=? WHERE id=?",
                     (request.form['nombre'].strip(), request.form.get('cuit','').strip(),
                      request.form.get('contacto','').strip(), request.form.get('telefono','').strip(),
                      request.form.get('email','').strip(), id))
        conn.execute("DELETE FROM productos_proveedores WHERE proveedor_id=?", (id,))
        for prod_id in request.form.getlist('productos'):
            try:
                conn.execute("INSERT OR IGNORE INTO productos_proveedores (producto_id, proveedor_id) VALUES (?, ?)",
                             (int(prod_id), id))
            except: pass
        conn.commit(); conn.close()
        flash('Proveedor actualizado.', 'success')
        return redirect(url_for('gastos_lista', tab='proveedores'))

    conn.close()
    return render_template('proveedores/form.html', proveedor=dict(prov), valores={},
                           productos_lista=productos_lista, productos_seleccionados=prod_sel)


@app.route('/proveedores/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def proveedores_eliminar(id):
    conn = get_db()
    conn.execute("UPDATE proveedores SET activo=0 WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Proveedor desactivado.', 'success')
    return redirect(url_for('gastos_lista', tab='proveedores'))


# === Compras ===
def compras_nueva_v2():
    conn = get_db()
    if request.method == 'POST':
        tipo = request.form.get('tipo', 'stock')
        prov_id = int(request.form['proveedor_id']) if request.form.get('proveedor_id') else None
        fecha = request.form.get('fecha') or date.today().isoformat()
        notas = request.form.get('notas', '').strip()
        cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None

        if tipo == 'stock':
            pids = request.form.getlist('producto_id')
            cants = request.form.getlist('cantidad')
            costos = request.form.getlist('costo')
            items = []
            for pid, c, co in zip(pids, cants, costos):
                if not pid or not c: continue
                try:
                    cf = float(c); cof = float(co)
                except ValueError: continue
                if cf <= 0: continue
                items.append({'pid': int(pid), 'cantidad': cf, 'costo': cof, 'sub': cf*cof})
            if not items:
                conn.close(); flash('Agrega productos de stock.', 'error')
                return redirect(url_for('compras_nueva'))
            total = sum(i['sub'] for i in items)
            cur = conn.execute("INSERT INTO compras (proveedor_id,fecha,total,usuario_id,notas,tipo,categoria_id) VALUES (?,?,?,?,?,?,?)",
                               (prov_id, fecha, total, current_user.id, notas, 'stock', cat_id))
            cid = cur.lastrowid
            for it in items:
                conn.execute("INSERT INTO compra_items (compra_id,producto_id,cantidad,costo_unitario) VALUES (?,?,?,?)",
                             (cid, it['pid'], it['cantidad'], it['costo']))
                conn.execute("UPDATE productos SET stock_actual=stock_actual+?, costo=? WHERE id=?",
                             (it['cantidad'], it['costo'], it['pid']))
                conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                             (it['pid'], 'entrada', it['cantidad'], f'Compra #{cid}', current_user.id))
            conn.commit(); conn.close()
            flash(f'Compra de stock #{cid} registrada. Stock actualizado.', 'success')
            return redirect(url_for('gastos_lista', tab='compras'))
        else:
            desc = request.form.get('descripcion', '').strip()
            try:
                monto = float(request.form.get('monto_insumo') or 0)
            except ValueError:
                monto = 0
            if not desc or monto <= 0:
                conn.close(); flash('Descripcion y monto obligatorios para insumo.', 'error')
                return redirect(url_for('compras_nueva'))
            cur = conn.execute("INSERT INTO compras (proveedor_id,fecha,total,usuario_id,notas,tipo,categoria_id) VALUES (?,?,?,?,?,?,?)",
                               (prov_id, fecha, monto, current_user.id, notas, 'insumo', cat_id))
            cid = cur.lastrowid
            conn.execute("INSERT INTO compra_items (compra_id,producto_id,descripcion,cantidad,costo_unitario) VALUES (?,?,?,?,?)",
                         (cid, None, desc, 1, monto))
            conn.commit(); conn.close()
            flash(f'Insumo #{cid} registrado.', 'success')
            return redirect(url_for('gastos_lista', tab='compras'))

    proveedores_lista = conn.execute("SELECT * FROM proveedores WHERE activo=1 ORDER BY nombre").fetchall()
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('compras/nueva.html', proveedores=proveedores_lista,
                           categorias=categorias, hoy=date.today().isoformat())

app.view_functions['compras_nueva'] = compras_nueva_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


BASE_HTML = r'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><title>{% block title %}Sistema FZ{% endblock %}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --fz-bg:#f4f6fb; --fz-card:#ffffff; --fz-text:#1f2937; --fz-muted:#6b7280;
  --fz-border:#e8ecf3; --fz-primary:#3b5bdb; --fz-primary-soft:#eef2ff;
  --fz-success:#10b981; --fz-success-soft:#ecfdf5;
  --fz-danger:#ef4444; --fz-danger-soft:#fef2f2;
  --fz-warning:#f59e0b; --fz-warning-soft:#fffbeb;
  --fz-shadow:0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04);
  --fz-shadow-md:0 4px 12px rgba(16,24,40,.08);
  --fz-radius:14px;
}
*{ -webkit-font-smoothing:antialiased; }
body{ background:var(--fz-bg); color:var(--fz-text); margin:0; font-family:'Inter',system-ui,-apple-system,sans-serif; font-size:.94rem; }
.sidebar{ width:245px; min-height:100vh; position:fixed; top:0; left:0;
  background:#111827; color:#e5e7eb; padding:1.25rem 0; display:flex; flex-direction:column; }
.sidebar .brand{ padding:0 1.5rem 1.25rem; font-weight:700; color:#fff;
  border-bottom:1px solid rgba(255,255,255,.08); margin-bottom:.75rem; font-size:1.05rem; letter-spacing:-.01em; }
.sidebar a{ color:#9ca3af; text-decoration:none; padding:.62rem 1.5rem;
  display:flex; align-items:center; gap:.7rem; font-size:.9rem; font-weight:500; transition:background .15s; }
.sidebar a:hover{ background:rgba(255,255,255,.05); color:#fff; }
.sidebar a.active{ background:var(--fz-primary); color:#fff; }
.sidebar a i{ font-size:1.08rem; }
.sidebar .user-info{ margin-top:auto; padding:1.25rem 1.5rem; border-top:1px solid rgba(255,255,255,.08); font-size:.82rem; }
.content{ margin-left:245px; padding:1.75rem 2.25rem; }
.content.sin-sidebar{ margin-left:0; padding-top:4rem; }
.card{ border:none; border-radius:var(--fz-radius); box-shadow:var(--fz-shadow); background:var(--fz-card); }
.card-body{ padding:1.25rem 1.5rem; }
.card-kpi{ background:var(--fz-card); border-radius:var(--fz-radius); box-shadow:var(--fz-shadow);
  padding:1.35rem 1.5rem; height:100%; position:relative; }
.card-kpi:hover{ box-shadow:var(--fz-shadow-md); }
.kpi-icon{ width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:1.15rem; margin-bottom:.9rem; }
.kpi-icon-primary{ background:var(--fz-primary-soft); color:var(--fz-primary); }
.kpi-icon-success{ background:var(--fz-success-soft); color:var(--fz-success); }
.kpi-icon-danger{ background:var(--fz-danger-soft); color:var(--fz-danger); }
.kpi-icon-warning{ background:var(--fz-warning-soft); color:var(--fz-warning); }
.kpi-label{ color:var(--fz-muted); font-size:.82rem; font-weight:500; margin-bottom:.35rem; }
.kpi-value{ font-size:1.65rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; }
.kpi-delta{ font-size:.78rem; margin-top:.5rem; display:flex; align-items:center; gap:.25rem; }
.kpi-delta i{ font-size:.9rem; }
.btn-primary{ background:var(--fz-primary); border-color:var(--fz-primary); }
.btn-primary:hover{ background:#2f4bbf; border-color:#2f4bbf; }
.btn-outline-primary{ color:var(--fz-primary); border-color:var(--fz-primary); }
.btn-outline-primary:hover{ background:var(--fz-primary); border-color:var(--fz-primary); }
.btn-dark{ background:#111827; border-color:#111827; }
.btn-dark:hover{ background:#1f2937; border-color:#1f2937; }
.badge-soft-primary{ background:var(--fz-primary-soft); color:var(--fz-primary); padding:.4rem .8rem; border-radius:8px; font-weight:600; font-size:.8rem; }
.badge-soft-success{ background:var(--fz-success-soft); color:var(--fz-success); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }
.badge-soft-danger{ background:var(--fz-danger-soft); color:var(--fz-danger); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }
.badge-soft-warning{ background:var(--fz-warning-soft); color:var(--fz-warning); padding:.35rem .65rem; border-radius:6px; font-weight:600; font-size:.78rem; }
.table thead th{ font-weight:600; font-size:.8rem; text-transform:uppercase; letter-spacing:.02em; color:var(--fz-muted); border-bottom:1px solid var(--fz-border); }
.table>:not(caption)>*>*{ border-color:var(--fz-border); }
.form-control, .form-select{ border-radius:9px; border-color:var(--fz-border); }
.form-control:focus, .form-select:focus{ border-color:var(--fz-primary); box-shadow:0 0 0 3px rgba(59,91,219,.12); }
.alert{ border-radius:10px; border:none; }
h4, h5, h6{ font-weight:600; letter-spacing:-.01em; }
h4{ font-size:1.35rem; }
.nav-pills .nav-link{ color:var(--fz-muted); border-radius:8px; padding:.5rem 1rem; font-weight:500; font-size:.9rem; }
.nav-pills .nav-link:hover{ background:var(--fz-primary-soft); color:var(--fz-primary); }
.nav-pills .nav-link.active{ background:var(--fz-primary); color:#fff; }
</style></head><body>
{% if current_user.is_authenticated %}
<aside class="sidebar">
<div class="brand">Familia Zaragoza ®</div>
<a href="{{ url_for('dashboard') }}" class="{% if request.endpoint=='dashboard' %}active{% endif %}"><i class="bi bi-speedometer2"></i> Dashboard</a>
{% if current_user.puede('clientes') %}<a href="{{ url_for('clientes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('clientes') %}active{% endif %}"><i class="bi bi-people"></i> Clientes</a>{% endif %}
{% if current_user.puede('ventas') %}<a href="{{ url_for('ventas_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('ventas') %}active{% endif %}"><i class="bi bi-cart"></i> Ventas</a>{% endif %}
{% if current_user.es_admin %}
<a href="{{ url_for('gastos_lista') }}" class="{% if request.endpoint and (request.endpoint.startswith('gastos') or request.endpoint.startswith('compras') or request.endpoint.startswith('proveedores')) %}active{% endif %}"><i class="bi bi-cash-coin"></i> Gastos</a>
<a href="{{ url_for('reportes') }}" class="{% if request.endpoint and request.endpoint.startswith('reportes') %}active{% endif %}"><i class="bi bi-graph-up"></i> Reportes</a>
<a href="{{ url_for('emails_historial') }}" class="{% if request.endpoint and request.endpoint.startswith('emails') %}active{% endif %}"><i class="bi bi-envelope"></i> Emails</a>
<a href="{{ url_for('solicitudes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('solicitudes') %}active{% endif %}"><i class="bi bi-inbox"></i> Solicitudes</a>
{% endif %}
{% if current_user.puede('productos') %}<a href="{{ url_for('productos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('productos') %}active{% endif %}"><i class="bi bi-box-seam"></i> Productos</a>{% endif %}
{% if current_user.es_admin %}<a href="{{ url_for('usuarios_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('usuarios') %}active{% endif %}"><i class="bi bi-person-badge"></i> Usuarios</a>
<a href="{{ url_for('configuracion') }}" class="{% if request.endpoint and request.endpoint.startswith('configuracion') %}active{% endif %}"><i class="bi bi-gear"></i> Configuracion</a>{% endif %}
<div class="user-info">
<div class="d-flex align-items-center gap-2 mb-2"><i class="bi bi-person-circle fs-5 text-secondary"></i><div><div class="text-white">{{ current_user.nombre }}</div><small class="text-secondary">{{ 'Admin' if current_user.es_admin else 'Vendedor' }}</small></div></div>
<a href="{{ url_for('mi_cuenta') }}" class="btn btn-outline-light btn-sm w-100 mb-1" style="border-color:rgba(255,255,255,.15);"><i class="bi bi-key"></i> Mi cuenta</a>
<a href="{{ url_for('logout') }}" class="btn btn-outline-danger btn-sm w-100" style="border-color:rgba(239,68,68,.4);"><i class="bi bi-box-arrow-right"></i> Salir</a>
</div></aside>
{% endif %}
<main class="content {% if not current_user.is_authenticated %}sin-sidebar{% endif %}">
{% with messages = get_flashed_messages(with_categories=true) %}{% for cat, msg in messages %}
<div class="alert alert-{{ 'danger' if cat=='error' else ('success' if cat=='success' else 'info') }} alert-dismissible fade show">{{ msg }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
{% endfor %}{% endwith %}
{% block content %}{% endblock %}
</main>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>

{% if alertas_popup %}
<div class="modal fade" id="alertasModal" tabindex="-1" data-bs-backdrop="static">
<div class="modal-dialog modal-lg"><div class="modal-content">
<div class="modal-header">
<h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill text-warning"></i> Alertas importantes</h5>
<button type="button" class="btn-close" data-bs-dismiss="modal" onclick="dismissAlertas()"></button>
</div>
<div class="modal-body">
{% if alertas_popup.productos_agotados %}
<div class="alert alert-danger py-2 px-3 mb-3" style="border-left:4px solid #ef4444;">
<div class="fw-semibold mb-2"><i class="bi bi-x-octagon-fill"></i> {{ alertas_popup.productos_agotados|length }} producto(s) agotado(s)</div>
<ul class="mb-0 ps-3 small">
{% for p in alertas_popup.productos_agotados %}
<li>{{ p.nombre }}{% if p.sku %} <span class="text-muted">({{ p.sku }})</span>{% endif %}</li>
{% endfor %}
</ul>
</div>
{% endif %}
{% if alertas_popup.productos_bajos %}
<div class="alert alert-warning py-2 px-3 mb-3" style="border-left:4px solid #f59e0b;">
<div class="fw-semibold mb-2"><i class="bi bi-exclamation-triangle-fill"></i> {{ alertas_popup.productos_bajos|length }} producto(s) con bajo stock</div>
<ul class="mb-0 ps-3 small">
{% for p in alertas_popup.productos_bajos %}
<li>{{ p.nombre }} — stock <strong>{{ '%g'|format(p.stock_actual) }}</strong> (mínimo {{ '%g'|format(p.stock_minimo) }})</li>
{% endfor %}
</ul>
</div>
{% endif %}
{% if alertas_popup.ordenes_viejas %}
<div class="alert alert-info py-2 px-3 mb-3" style="border-left:4px solid #06b6d4;">
<div class="fw-semibold mb-2"><i class="bi bi-clock-history"></i> {{ alertas_popup.ordenes_viejas|length }} orden(es) pagada(s) sin despachar hace más de {{ alertas_popup.horas_limite }}hs</div>
<ul class="mb-0 ps-3 small">
{% for o in alertas_popup.ordenes_viejas %}
<li><a href="{{ url_for('ventas_detalle', id=o.id) }}" class="text-decoration-none fw-semibold">{{ o.numero_interno }}</a> — {{ o.cliente_nombre }} <span class="text-muted">({{ o.horas_esperando }}hs esperando)</span></li>
{% endfor %}
</ul>
</div>
{% endif %}
</div>
<div class="modal-footer flex-wrap gap-2">
{% if alertas_popup.productos_agotados or alertas_popup.productos_bajos %}
<a href="{{ url_for('productos_lista', alerta='agotado') }}" class="btn btn-outline-danger btn-sm" onclick="dismissAlertas()"><i class="bi bi-box-seam"></i> Ver productos</a>
{% endif %}
{% if alertas_popup.ordenes_viejas %}
<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="btn btn-outline-primary btn-sm" onclick="dismissAlertas()"><i class="bi bi-truck"></i> Ver pendientes</a>
{% endif %}
<button type="button" class="btn btn-dark btn-sm" data-bs-dismiss="modal" onclick="dismissAlertas()">Entendido</button>
</div>
</div></div>
</div>
<script>
(function(){
  const COOLDOWN_HORAS = 4;
  const key = 'fz_alertas_last_dismissed';
  try {
    const last = localStorage.getItem(key);
    if (last) {
      const diff = Date.now() - parseInt(last);
      if (diff < COOLDOWN_HORAS * 3600 * 1000) return;
    }
  } catch(e) { }
  const modalEl = document.getElementById('alertasModal');
  if (!modalEl) return;
  new bootstrap.Modal(modalEl).show();
})();
function dismissAlertas() {
  try { localStorage.setItem('fz_alertas_last_dismissed', Date.now().toString()); } catch(e) {}
}
</script>
{% endif %}

</body></html>
'''


GASTOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Gastos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Gastos</h4>
<div class="d-flex gap-2">
<a href="{{ url_for('gastos_nuevo') }}" class="btn btn-dark btn-sm"><i class="bi bi-plus-lg"></i> Nuevo gasto</a>
<a href="{{ url_for('compras_nueva') }}" class="btn btn-dark btn-sm"><i class="bi bi-plus-lg"></i> Nueva compra</a>
<a href="{{ url_for('proveedores_nuevo') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-plus-lg"></i> Nuevo proveedor</a>
</div>
</div>

<!-- Stats mes actual vs mes anterior -->
<div class="row row-cols-2 row-cols-md-3 g-2 mb-3">
<div class="col">
<div class="card-kpi" style="border-left:3px solid #ef4444;">
<div class="kpi-label">Gastos del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.gastos_mes).replace(',','.') }}</div>
{% if stats.var_gastos is not none %}
<div class="kpi-delta {% if stats.var_gastos > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_gastos > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_gastos|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #f59e0b;">
<div class="kpi-label">Compras del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.compras_mes).replace(',','.') }}</div>
{% if stats.var_compras is not none %}
<div class="kpi-delta {% if stats.var_compras > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_compras > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_compras|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #1f2937;">
<div class="kpi-label">Total egresos del mes</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.total_mes).replace(',','.') }}</div>
{% if stats.var_total is not none %}
<div class="kpi-delta {% if stats.var_total > 0 %}text-danger{% else %}text-success{% endif %}">
<i class="bi bi-arrow-{% if stats.var_total > 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.var_total|abs) }}% vs mes anterior
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
</div>

<!-- Tabs -->
<ul class="nav nav-pills mb-3">
<li class="nav-item"><a class="nav-link {% if tab=='gastos' %}active{% endif %}" href="{{ url_for('gastos_lista', tab='gastos') }}"><i class="bi bi-receipt"></i> Gastos generales</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='compras' %}active{% endif %}" href="{{ url_for('gastos_lista', tab='compras') }}"><i class="bi bi-bag"></i> Compras de stock</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='proveedores' %}active{% endif %}" href="{{ url_for('gastos_lista', tab='proveedores') }}"><i class="bi bi-people"></i> Proveedores</a></li>
</ul>

{% if tab == 'gastos' %}
<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Desde</label><input type="date" name="desde" value="{{ desde }}" class="form-control form-control-sm"></div>
<div class="col-md-3"><label class="form-label small text-muted">Hasta</label><input type="date" name="hasta" value="{{ hasta }}" class="form-control form-control-sm"></div>
<div class="col-md-4"><label class="form-label small text-muted">Categoria</label><select name="categoria" class="form-select form-select-sm"><option value="">Todas</option>{% for c in categorias %}<option value="{{ c.id }}" {% if cat_filtro==c.id|string %}selected{% endif %}>{{ c.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-2"><button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i> Filtrar</button></div>
<input type="hidden" name="tab" value="gastos">
</div></form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr><th>Fecha</th><th>Categoria</th><th>Descripcion</th><th>Usuario</th><th class="text-end">Monto</th><th class="text-end"></th></tr></thead>
<tbody>
{% for g in gastos %}
<tr>
<td class="small">{{ g.fecha }}</td>
<td>{{ g.categoria_nombre or '-' }}</td>
<td>{{ g.descripcion or '' }}</td>
<td class="small">{{ g.usuario_nombre }}</td>
<td class="text-end">${{ '%.2f'|format(g.monto) }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('gastos_editar', id=g.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a>
<form method="post" action="{{ url_for('gastos_eliminar', id=g.id) }}" class="d-inline" onsubmit="return confirm('Eliminar?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
</td>
</tr>
{% else %}<tr><td colspan="6" class="text-center text-muted py-4">Sin gastos.</td></tr>{% endfor %}
</tbody></table></div></div>

{% elif tab == 'compras' %}
<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Desde</label><input type="date" name="desde" value="{{ desde }}" class="form-control form-control-sm"></div>
<div class="col-md-3"><label class="form-label small text-muted">Hasta</label><input type="date" name="hasta" value="{{ hasta }}" class="form-control form-control-sm"></div>
<div class="col-md-4"><label class="form-label small text-muted">Proveedor</label><select name="proveedor" class="form-select form-select-sm"><option value="">Todos</option>{% for p in proveedores_lista %}<option value="{{ p.id }}" {% if prov_filtro==p.id|string %}selected{% endif %}>{{ p.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-2"><button class="btn btn-outline-secondary btn-sm w-100"><i class="bi bi-search"></i> Filtrar</button></div>
<input type="hidden" name="tab" value="compras">
</div></form>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr><th>#</th><th>Fecha</th><th>Tipo</th><th>Proveedor</th><th>Usuario</th><th class="text-end">Total</th></tr></thead>
<tbody>
{% for c in compras %}
<tr>
<td class="fw-semibold">{{ c.id }}</td>
<td class="small">{{ c.fecha }}</td>
<td>{% if c.tipo == 'insumo' %}<span class="badge bg-secondary">Insumo</span>{% else %}<span class="badge bg-success">Stock</span>{% endif %}</td>
<td>{{ c.proveedor_nombre or '—' }}</td>
<td class="small">{{ c.usuario_nombre }}</td>
<td class="text-end">${{ '%.2f'|format(c.total) }}</td>
</tr>
{% else %}<tr><td colspan="6" class="text-center text-muted py-4">Sin compras.</td></tr>{% endfor %}
</tbody></table></div></div>

{% else %}
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr><th>Nombre</th><th>CUIT</th><th>Contacto</th><th>Telefono</th><th>Email</th><th class="text-end">Acciones</th></tr></thead>
<tbody>
{% for p in proveedores %}
<tr>
<td class="fw-semibold">{{ p.nombre }}</td>
<td class="small">{{ p.cuit or '' }}</td>
<td>{{ p.contacto or '' }}</td>
<td>{{ p.telefono or '' }}</td>
<td class="small">{{ p.email or '' }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('proveedores_editar', id=p.id) }}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-pencil"></i></a>
<form method="post" action="{{ url_for('proveedores_eliminar', id=p.id) }}" class="d-inline" onsubmit="return confirm('Desactivar?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
</td>
</tr>
{% else %}<tr><td colspan="6" class="text-center text-muted py-4">Sin proveedores.</td></tr>{% endfor %}
</tbody></table></div></div>
{% endif %}
{% endblock %}
'''


PROVEEDORES_FORM = r'''{% extends "base.html" %}
{% block title %}Proveedor{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if proveedor else 'Nuevo' }} proveedor</h4>
<a href="{{ url_for('gastos_lista', tab='proveedores') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (proveedor if proveedor else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6"><label class="form-label">Nombre *</label><input name="nombre" class="form-control" required value="{{ v.get('nombre') or '' }}"></div>
<div class="col-md-6"><label class="form-label">CUIT</label><input name="cuit" class="form-control" value="{{ v.get('cuit') or '' }}"></div>
<div class="col-md-4"><label class="form-label">Contacto</label><input name="contacto" class="form-control" value="{{ v.get('contacto') or '' }}"></div>
<div class="col-md-4"><label class="form-label">Telefono</label><input name="telefono" class="form-control" value="{{ v.get('telefono') or '' }}"></div>
<div class="col-md-4"><label class="form-label">Email</label><input type="email" name="email" class="form-control" value="{{ v.get('email') or '' }}"></div>
</div>

<div class="mt-4 mb-2">
<label class="form-label fw-semibold">Productos que le compras a este proveedor</label>
<div class="form-text mb-2">Marcá los productos. Cuando crees una compra a este proveedor, vas a ver solo estos productos disponibles.</div>
</div>
<div class="border rounded p-2" style="max-height:300px; overflow-y:auto;">
{% if productos_lista %}
{% for p in productos_lista %}
<div class="form-check">
<input class="form-check-input" type="checkbox" name="productos" value="{{ p.id }}" id="prod-{{ p.id }}" {% if p.id in productos_seleccionados %}checked{% endif %}>
<label class="form-check-label small" for="prod-{{ p.id }}">
{{ p.nombre }}{% if p.sku %} <span class="text-muted">({{ p.sku }})</span>{% endif %}
</label>
</div>
{% endfor %}
{% else %}
<p class="text-muted small mb-0">No hay productos cargados en el sistema.</p>
{% endif %}
</div>

<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
'''


COMPRAS_NUEVA = r'''{% extends "base.html" %}
{% block title %}Nueva compra{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Nueva compra</h4>
<a href="{{ url_for('gastos_lista', tab='compras') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
<form method="post">
<div class="card shadow-sm mb-3"><div class="card-body"><div class="row g-3">
<div class="col-md-6">
<label class="form-label">Tipo de compra *</label>
<select name="tipo" id="tipo-select" class="form-select" onchange="cambiarTipo()">
<option value="stock">Compra de stock (suma inventario)</option>
<option value="insumo">Compra de insumo / gasto (no suma inventario)</option>
</select>
</div>
<div class="col-md-6">
<label class="form-label">Proveedor</label>
<select name="proveedor_id" id="proveedor-select" class="form-select" onchange="cargarProductosProveedor()">
<option value="">— Sin proveedor —</option>
{% for p in proveedores %}
<option value="{{ p.id }}">{{ p.nombre }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3"><label class="form-label">Fecha</label><input type="date" name="fecha" class="form-control" value="{{ hoy }}"></div>
<div class="col-md-9"><label class="form-label">Notas</label><input name="notas" class="form-control"></div>
</div></div></div>

<div id="bloque-stock">
<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2">
<h6 class="mb-0">Productos</h6>
<button type="button" class="btn btn-sm btn-outline-secondary" onclick="addItem()"><i class="bi bi-plus-lg"></i> Agregar producto</button>
</div>
<div class="alert alert-info py-2 small" id="aviso-proveedor" style="display:none;">
<i class="bi bi-info-circle"></i> Elegí un proveedor para cargar automaticamente sus productos, o agrega manualmente.
</div>
<table class="table table-sm align-middle mb-0">
<thead><tr><th>Producto</th><th width="100">Cantidad</th><th width="130">Costo unit.</th><th width="120" class="text-end">Subtotal</th><th width="40"></th></tr></thead>
<tbody id="items-body"></tbody>
</table>
</div></div>
<div class="card shadow-sm mb-3"><div class="card-body">
<table class="table table-sm mb-0"><tr class="fw-bold"><td>Total:</td><td class="text-end" id="total-view">$0.00</td></tr></table>
</div></div>
</div>

<div id="bloque-insumo" style="display:none;">
<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-3">Detalle del insumo / gasto</h6>
<div class="row g-2">
<div class="col-md-6"><label class="form-label">Descripcion *</label><input name="descripcion" class="form-control" placeholder="Ej: 20kg de azucar para produccion"></div>
<div class="col-md-3"><label class="form-label">Monto total *</label><input type="number" step="0.01" min="0" name="monto_insumo" class="form-control"></div>
<div class="col-md-3"><label class="form-label">Categoria de gasto</label>
<select name="categoria_id" class="form-select">
<option value="">— Sin categoria —</option>
{% for c in categorias %}
<option value="{{ c.id }}">{{ c.nombre }}</option>
{% endfor %}
</select>
</div>
</div>
<p class="text-muted small mt-2 mb-0"><i class="bi bi-info-circle"></i> Los insumos no suman stock, se registran como egreso en compras.</p>
</div></div>
</div>

<button class="btn btn-dark btn-lg">Registrar compra</button>
</form>

<script>
const PRODUCTOS_POR_PROV = {};
const TODOS_PRODS = [
{% for p in productos_todos or [] %}
{id: {{ p.id }}, nombre: {{ p.nombre|tojson }}, sku: {{ (p.sku or '')|tojson }}, costo: {{ p.costo or 0 }}},
{% endfor %}
];

function cambiarTipo() {
  const t = document.getElementById('tipo-select').value;
  document.getElementById('bloque-stock').style.display = (t === 'stock') ? 'block' : 'none';
  document.getElementById('bloque-insumo').style.display = (t === 'insumo') ? 'block' : 'none';
}

async function cargarProductosProveedor() {
  const pid = document.getElementById('proveedor-select').value;
  const aviso = document.getElementById('aviso-proveedor');
  if (!pid) {
    aviso.style.display = 'none';
    return;
  }
  try {
    const r = await fetch('/api/productos-por-proveedor/' + pid);
    const prods = await r.json();
    if (prods.length === 0) {
      aviso.style.display = 'block';
      aviso.textContent = 'Este proveedor no tiene productos asignados. Editalo en Proveedores o agrega manualmente.';
    } else {
      aviso.style.display = 'none';
    }
    // Reemplazar las opciones de los selects existentes
    document.querySelectorAll('select[name="producto_id"]').forEach(sel => {
      const actual = sel.value;
      sel.innerHTML = '<option value="">--</option>';
      prods.forEach(p => {
        const o = document.createElement('option');
        o.value = p.id;
        o.textContent = p.nombre + (p.sku ? ' ('+p.sku+')' : '');
        o.dataset.costo = p.costo;
        sel.appendChild(o);
      });
      sel.value = actual;
    });
    if (prods.length > 0 && document.querySelectorAll('.item-row').length === 0) {
      addItem();
    }
  } catch (e) {
    console.error(e);
  }
}

async function addItem() {
  const tbody = document.getElementById('items-body');
  const row = document.createElement('tr');
  row.className = 'item-row';
  const pid = document.getElementById('proveedor-select').value;
  const prods = pid ? (await (await fetch('/api/productos-por-proveedor/' + pid)).json()) : TODOS_PRODS;
  let opts = '<option value="">--</option>';
  prods.forEach(p => {
    opts += '<option value="' + p.id + '" data-costo="' + p.costo + '">' + p.nombre + '</option>';
  });
  row.innerHTML = '<td><select name="producto_id" class="form-select form-select-sm" onchange="onProdChange(this)">' + opts + '</select></td>' +
    '<td><input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" onchange="updateTotals()"></td>' +
    '<td><input type="number" step="0.01" min="0" name="costo" class="form-control form-control-sm" value="0" onchange="updateTotals()"></td>' +
    '<td class="text-end subtotal">$0.00</td>' +
    '<td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(this)"><i class="bi bi-trash"></i></button></td>';
  tbody.appendChild(row);
}
function removeItem(b) { b.closest('tr').remove(); updateTotals(); }
function onProdChange(s) {
  const o = s.options[s.selectedIndex];
  s.closest('tr').querySelector('[name="costo"]').value = o.dataset.costo || 0;
  updateTotals();
}
function updateTotals() {
  let sub = 0;
  document.querySelectorAll('.item-row').forEach(r => {
    const c = parseFloat(r.querySelector('[name="cantidad"]').value) || 0;
    const co = parseFloat(r.querySelector('[name="costo"]').value) || 0;
    const s = c * co;
    r.querySelector('.subtotal').textContent = '$' + s.toFixed(2);
    sub += s;
  });
  document.getElementById('total-view').textContent = '$' + sub.toFixed(2);
}
document.addEventListener('DOMContentLoaded', () => {
  addItem();
});
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app23; app23.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 23: Gastos unificado + Proveedores-Productos + Compras con tipo (F5.1) ===")
    migrar()
    escribir('app23.py', APP23_PY)
    escribir('templates/base.html', BASE_HTML)
    escribir('templates/gastos/lista.html', GASTOS_LISTA)
    escribir('templates/proveedores/form.html', PROVEEDORES_FORM)
    escribir('templates/compras/nueva.html', COMPRAS_NUEVA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app23.py)")


if __name__ == '__main__':
    main()