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
    print(f"[upgrade26] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade26] sin DB."); return
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS objetivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            monto REAL NOT NULL,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado TEXT,
            UNIQUE(usuario_id, mes, anio),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade26] tabla objetivos OK")
    conn.commit(); conn.close()


APP26_PY = r'''
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app23 import app
from app import admin_required
from database import get_db


MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


def _get_objetivo(conn, usuario_id, mes, anio):
    if usuario_id is None:
        row = conn.execute("SELECT monto FROM objetivos WHERE usuario_id IS NULL AND mes=? AND anio=?",
                           (mes, anio)).fetchone()
    else:
        row = conn.execute("SELECT monto FROM objetivos WHERE usuario_id=? AND mes=? AND anio=?",
                           (usuario_id, mes, anio)).fetchone()
    return row['monto'] if row else 0


def _facturado(conn, usuario_id, mes, anio):
    if mes == 12:
        ini = date(anio, 12, 1).isoformat()
        fin = date(anio+1, 1, 1).isoformat()
    else:
        ini = date(anio, mes, 1).isoformat()
        fin = date(anio, mes+1, 1).isoformat()
    if usuario_id is None:
        total = conn.execute(
            """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
            WHERE date(fecha) >= ? AND date(fecha) < ?
            AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (ini, fin)).fetchone()[0]
    else:
        total = conn.execute(
            """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
            WHERE date(fecha) >= ? AND date(fecha) < ?
            AND usuario_id = ?
            AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (ini, fin, usuario_id)).fetchone()[0]
    return total


@app.context_processor
def _ctx_objetivo_sidebar():
    if not current_user.is_authenticated:
        return {}
    conn = get_db()
    try:
        hoy = date.today()
        if current_user.es_admin:
            objetivo = _get_objetivo(conn, None, hoy.month, hoy.year)
            facturado = _facturado(conn, None, hoy.month, hoy.year)
            return {'objetivo_sidebar': {
                'monto': objetivo,
                'facturado': facturado,
                'pct': (facturado / objetivo * 100) if objetivo > 0 else 0,
                'mes_label': MESES[hoy.month],
            }}
        else:
            objetivo = _get_objetivo(conn, current_user.id, hoy.month, hoy.year)
            if objetivo <= 0:
                return {}
            facturado = _facturado(conn, current_user.id, hoy.month, hoy.year)
            return {'objetivo_sidebar': {
                'monto': objetivo,
                'facturado': facturado,
                'pct': (facturado / objetivo * 100) if objetivo > 0 else 0,
                'mes_label': MESES[hoy.month],
            }}
    finally:
        conn.close()


@app.route('/objetivos')
@login_required
@admin_required
def objetivos_lista():
    conn = get_db()
    hoy = date.today()
    mes = request.args.get('mes', hoy.month, type=int)
    anio = request.args.get('anio', hoy.year, type=int)

    # Objetivo global
    objetivo_global = _get_objetivo(conn, None, mes, anio)
    facturado_global = _facturado(conn, None, mes, anio)

    # Objetivos por vendedor
    vendedores = conn.execute("SELECT id, nombre, email, rol FROM usuarios WHERE activo=1 AND rol='vendedor' ORDER BY nombre").fetchall()
    filas = []
    for v in vendedores:
        obj = _get_objetivo(conn, v['id'], mes, anio)
        fac = _facturado(conn, v['id'], mes, anio)
        filas.append({
            'usuario': v, 'objetivo': obj, 'facturado': fac,
            'pct': (fac / obj * 100) if obj > 0 else 0,
        })

    conn.close()
    return render_template('objetivos/lista.html',
                           mes=mes, anio=anio, mes_label=MESES[mes],
                           objetivo_global=objetivo_global, facturado_global=facturado_global,
                           pct_global=(facturado_global / objetivo_global * 100) if objetivo_global > 0 else 0,
                           filas=filas, MESES=MESES)


@app.route('/objetivos/global', methods=['POST'])
@login_required
@admin_required
def objetivos_global():
    mes = int(request.form['mes'])
    anio = int(request.form['anio'])
    try:
        monto = float(request.form['monto'] or 0)
    except ValueError:
        flash('Monto invalido.', 'error'); return redirect(url_for('objetivos_lista', mes=mes, anio=anio))
    conn = get_db()
    if monto > 0:
        conn.execute("""INSERT INTO objetivos (usuario_id, mes, anio, monto)
            VALUES (NULL, ?, ?, ?)
            ON CONFLICT(usuario_id, mes, anio) DO UPDATE SET monto=excluded.monto, actualizado=CURRENT_TIMESTAMP""",
            (mes, anio, monto))
        flash(f'Objetivo global de {MESES[mes]} {anio}: ${monto:,.0f}'.replace(',','.'), 'success')
    else:
        conn.execute("DELETE FROM objetivos WHERE usuario_id IS NULL AND mes=? AND anio=?", (mes, anio))
        flash('Objetivo global eliminado.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio))


@app.route('/objetivos/vendedor/<int:uid>', methods=['POST'])
@login_required
@admin_required
def objetivos_vendedor(uid):
    mes = int(request.form['mes'])
    anio = int(request.form['anio'])
    try:
        monto = float(request.form['monto'] or 0)
    except ValueError:
        flash('Monto invalido.', 'error'); return redirect(url_for('objetivos_lista', mes=mes, anio=anio))
    conn = get_db()
    if monto > 0:
        conn.execute("""INSERT INTO objetivos (usuario_id, mes, anio, monto)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(usuario_id, mes, anio) DO UPDATE SET monto=excluded.monto, actualizado=CURRENT_TIMESTAMP""",
            (uid, mes, anio, monto))
        flash('Objetivo del vendedor guardado.', 'success')
    else:
        conn.execute("DELETE FROM objetivos WHERE usuario_id=? AND mes=? AND anio=?", (uid, mes, anio))
        flash('Objetivo del vendedor eliminado.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio))


# ====== Dashboard con objetivos ======
@app.route('/')
@login_required
def dashboard_objetivos():
    # Reusar el dashboard original
    from app22 import ventas_lista_v2  # dummy import para asegurar carga
    from app17 import productos_lista_v3  # dummy
    # Ejecutar el dashboard real
    from app import app as app_base
    # Pero el dashboard real está en app7/app8 (dashboard_v3)
    # Lo llamamos manualmente
    from app7 import dashboard_v3
    result = dashboard_v3()
    # No podemos añadir al template desde aca sin modificar más
    # Por eso el objetivo se muestra en el sidebar (ya lo pusimos en _ctx_objetivo_sidebar)
    return result


# Reemplazar el dashboard original
from app7 import dashboard_v3
app.view_functions['dashboard'] = dashboard_v3


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
.sidebar-objetivo{ padding:.9rem 1.5rem; background:rgba(59,91,219,.15); border-top:1px solid rgba(255,255,255,.08); border-bottom:1px solid rgba(255,255,255,.08); }
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
.progress-fz{ height:8px; background:#e5e7eb; border-radius:20px; overflow:hidden; }
.progress-fz .progress-bar{ background:var(--fz-primary); transition:width .3s; }
.progress-fz.p-ok .progress-bar{ background:#10b981; }
.progress-fz.p-warn .progress-bar{ background:#f59e0b; }
.progress-fz.p-low .progress-bar{ background:#ef4444; }
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
<a href="{{ url_for('objetivos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('objetivos') %}active{% endif %}"><i class="bi bi-bullseye"></i> Objetivos</a>
<a href="{{ url_for('emails_historial') }}" class="{% if request.endpoint and request.endpoint.startswith('emails') %}active{% endif %}"><i class="bi bi-envelope"></i> Emails</a>
<a href="{{ url_for('solicitudes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('solicitudes') %}active{% endif %}"><i class="bi bi-inbox"></i> Solicitudes</a>
{% endif %}
{% if current_user.puede('productos') %}<a href="{{ url_for('productos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('productos') %}active{% endif %}"><i class="bi bi-box-seam"></i> Productos</a>{% endif %}
{% if current_user.es_admin %}<a href="{{ url_for('usuarios_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('usuarios') %}active{% endif %}"><i class="bi bi-person-badge"></i> Usuarios</a>
<a href="{{ url_for('configuracion') }}" class="{% if request.endpoint and request.endpoint.startswith('configuracion') %}active{% endif %}"><i class="bi bi-gear"></i> Configuracion</a>{% endif %}

{% if objetivo_sidebar is defined and objetivo_sidebar and objetivo_sidebar.monto > 0 %}
<div class="sidebar-objetivo">
<div class="d-flex justify-content-between mb-1" style="font-size:.75rem; color:#9ca3af;">
<span><i class="bi bi-bullseye"></i> Objetivo {{ objetivo_sidebar.mes_label }}</span>
<span class="fw-semibold" style="color:#fff;">{{ '%.0f'|format(objetivo_sidebar.pct) }}%</span>
</div>
<div class="progress-fz {% if objetivo_sidebar.pct >= 75 %}p-ok{% elif objetivo_sidebar.pct >= 50 %}p-warn{% else %}p-low{% endif %}" style="background:rgba(255,255,255,.15);">
<div class="progress-bar" style="width:{{ [objetivo_sidebar.pct, 100]|min }}%"></div>
</div>
<div class="mt-1" style="font-size:.72rem; color:#9ca3af;">
${{ '{:,.0f}'.format(objetivo_sidebar.facturado).replace(',', '.') }} / ${{ '{:,.0f}'.format(objetivo_sidebar.monto).replace(',', '.') }}
</div>
</div>
{% endif %}

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


OBJETIVOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Objetivos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Objetivos de venta</h4>
<div class="text-muted small">Metas por mes y por vendedor</div>
</div>
</div>

<!-- Selector mes/anio -->
<form class="card shadow-sm p-3 mb-3">
<div class="row g-2 align-items-end">
<div class="col-md-3">
<label class="form-label small text-muted">Mes</label>
<select name="mes" class="form-select form-select-sm" onchange="this.form.submit()">
{% for i in range(1, 13) %}
<option value="{{ i }}" {% if mes == i %}selected{% endif %}>{{ MESES[i] }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3">
<label class="form-label small text-muted">Año</label>
<select name="anio" class="form-select form-select-sm" onchange="this.form.submit()">
{% for a in range(2024, 2031) %}
<option value="{{ a }}" {% if anio == a %}selected{% endif %}>{{ a }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-6 text-md-end">
<span class="text-muted small">Periodo: <strong>{{ mes_label }} {{ anio }}</strong></span>
</div>
</div>
</form>

<!-- Objetivo global -->
<div class="card shadow-sm mb-3" style="border-left:4px solid #3b5bdb;">
<div class="card-body">
<div class="d-flex justify-content-between align-items-start mb-3">
<div>
<h6 class="mb-1"><i class="bi bi-globe"></i> Objetivo global del mes</h6>
<div class="text-muted small">Meta de facturación total de {{ mes_label }} {{ anio }}</div>
</div>
</div>
<div class="row g-3 align-items-center">
<div class="col-md-5">
<form method="post" action="{{ url_for('objetivos_global') }}" class="input-group">
<input type="hidden" name="mes" value="{{ mes }}">
<input type="hidden" name="anio" value="{{ anio }}">
<span class="input-group-text">$</span>
<input type="number" step="0.01" min="0" name="monto" class="form-control" value="{{ objetivo_global or '' }}" placeholder="0">
<button class="btn btn-dark">Guardar</button>
</form>
</div>
<div class="col-md-7">
{% if objetivo_global > 0 %}
<div class="d-flex justify-content-between mb-1">
<span class="small">Facturado: <strong>${{ '{:,.0f}'.format(facturado_global).replace(',', '.') }}</strong></span>
<span class="small fw-semibold">{{ '%.1f'|format(pct_global) }}%</span>
</div>
<div class="progress-fz {% if pct_global >= 75 %}p-ok{% elif pct_global >= 50 %}p-warn{% else %}p-low{% endif %}">
<div class="progress-bar" style="width:{{ [pct_global, 100]|min }}%"></div>
</div>
<div class="mt-1 small text-muted">
{% if pct_global >= 100 %}🎉 ¡Objetivo cumplido!
{% else %}Faltan <strong>${{ '{:,.0f}'.format(objetivo_global - facturado_global).replace(',', '.') }}</strong> para el objetivo
{% endif %}
</div>
{% else %}
<p class="text-muted small mb-0">Sin objetivo cargado para este mes</p>
{% endif %}
</div>
</div>
</div>
</div>

<!-- Objetivos por vendedor -->
<div class="card shadow-sm">
<div class="card-body">
<h6 class="mb-3"><i class="bi bi-people"></i> Objetivos por vendedor</h6>
{% if filas %}
<table class="table align-middle mb-0">
<thead class="table-light">
<tr>
<th>Vendedor</th><th style="width:220px;">Objetivo</th><th>Progreso</th><th class="text-end" style="width:120px;">Cumplimiento</th>
</tr>
</thead>
<tbody>
{% for f in filas %}
<tr>
<td>
<div class="fw-semibold">{{ f.usuario.nombre }}</div>
<div class="small text-muted">{{ f.usuario.email }}</div>
</td>
<td>
<form method="post" action="{{ url_for('objetivos_vendedor', uid=f.usuario.id) }}" class="input-group input-group-sm">
<input type="hidden" name="mes" value="{{ mes }}">
<input type="hidden" name="anio" value="{{ anio }}">
<span class="input-group-text">$</span>
<input type="number" step="0.01" min="0" name="monto" class="form-control" value="{{ f.objetivo or '' }}" placeholder="0">
<button class="btn btn-outline-dark">OK</button>
</form>
</td>
<td>
{% if f.objetivo > 0 %}
<div class="d-flex justify-content-between mb-1 small">
<span>${{ '{:,.0f}'.format(f.facturado).replace(',', '.') }} / ${{ '{:,.0f}'.format(f.objetivo).replace(',', '.') }}</span>
</div>
<div class="progress-fz {% if f.pct >= 75 %}p-ok{% elif f.pct >= 50 %}p-warn{% else %}p-low{% endif %}">
<div class="progress-bar" style="width:{{ [f.pct, 100]|min }}%"></div>
</div>
{% else %}
<span class="text-muted small">Sin objetivo asignado</span>
{% endif %}
</td>
<td class="text-end fw-semibold">
{% if f.objetivo > 0 %}
{{ '%.1f'|format(f.pct) }}%
{% else %}—{% endif %}
</td>
</tr>
{% endfor %}
</tbody>
</table>
{% else %}
<p class="text-muted small mb-0">No hay vendedores activos. Crea uno en Usuarios.</p>
{% endif %}
</div>
</div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app26; app26.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 26: Objetivos + barras de progreso (F5.2a) ===")
    migrar()
    escribir('app26.py', APP26_PY)
    escribir('templates/base.html', BASE_HTML)
    escribir('templates/objetivos/lista.html', OBJETIVOS_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app26.py)")


if __name__ == '__main__':
    main()