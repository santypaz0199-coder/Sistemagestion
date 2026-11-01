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
    print(f"[upgrade12] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade12] sin DB."); return
    conn = sqlite3.connect(db)

    # Columna auto_cancelada en ordenes
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'auto_cancelada' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN auto_cancelada INTEGER DEFAULT 0")
        print("[upgrade12] + ordenes_venta.auto_cancelada")

    # Tabla solicitudes_borrado
    conn.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes_borrado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            entidad_id INTEGER NOT NULL,
            descripcion TEXT,
            motivo TEXT,
            usuario_id INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            resuelto_por INTEGER,
            resuelto_en TEXT,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (resuelto_por) REFERENCES usuarios(id)
        )
    """)
    print("[upgrade12] tabla solicitudes_borrado OK")

    # Plantilla de cancelacion automatica
    tipo_pl = 'cancelacion'
    asunto_k = f'plantilla_{tipo_pl}_asunto'
    cuerpo_k = f'plantilla_{tipo_pl}_cuerpo'
    if not conn.execute("SELECT clave FROM configuracion WHERE clave=?", (asunto_k,)).fetchone():
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
            (asunto_k, 'Tu pedido {{numero_orden}} fue cancelado'))
    if not conn.execute("SELECT clave FROM configuracion WHERE clave=?", (cuerpo_k,)).fetchone():
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
            (cuerpo_k, '''Hola {{cliente_nombre}},

Te avisamos que tu pedido {{numero_orden}} fue cancelado automaticamente luego de 24 hs sin registrar el pago.

Recorda que las ordenes estan sujetas a cambios de precios por la desregulacion del mercado en Argentina.

Si queres retomar la compra, podes responder este email y te ayudamos.

{{firma}}'''))

    conn.commit(); conn.close()


APP12_PY = r'''
import time
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app11 import app
from app import permiso_required, admin_required, revertir_stock
from database import get_db


_ultimo_chequeo_auto_cancel = 0
_INTERVALO_AUTO_CANCEL = 300  # 5 min


def _auto_cancelar():
    """Cancela ordenes pendiente_pago con mas de 24 hs y avisa por email."""
    global _ultimo_chequeo_auto_cancel
    ahora = time.time()
    if ahora - _ultimo_chequeo_auto_cancel < _INTERVALO_AUTO_CANCEL:
        return
    _ultimo_chequeo_auto_cancel = ahora

    conn = get_db()
    try:
        # ordenes pendiente_pago con mas de 24 hs
        candidatas = conn.execute("""
            SELECT * FROM ordenes_venta
            WHERE estado='pendiente_pago'
            AND auto_cancelada=0
            AND datetime(creado) < datetime('now', '-24 hours')
        """).fetchall()

        if not candidatas:
            return

        # Importar solo cuando hace falta
        try:
            from app4 import enviar_email, get_config, render_plantilla
        except Exception:
            enviar_email = None

        for orden in candidatas:
            # Revertir stock si estaba descontado (por seguridad)
            if orden['stock_descontado']:
                try:
                    revertir_stock(conn, orden['id'], 1)  # usuario=1 (sistema)
                except Exception:
                    pass

            conn.execute(
                "UPDATE ordenes_venta SET estado='cancelado', auto_cancelada=1 WHERE id=?",
                (orden['id'],)
            )

            # Enviar email al cliente
            if enviar_email:
                try:
                    c = conn.execute(
                        "SELECT email, nombre_completo FROM clientes WHERE id=?",
                        (orden['cliente_id'],)
                    ).fetchone()
                    if c and c['email']:
                        ctx = {
                            'cliente_nombre': c['nombre_completo'],
                            'numero_orden': orden['numero_interno'],
                            'fecha': orden['fecha'],
                            'total': f"{orden['total']:.2f}",
                            'firma': get_config('firma_email'),
                        }
                        asunto = render_plantilla(get_config('plantilla_cancelacion_asunto'), ctx)
                        cuerpo = render_plantilla(get_config('plantilla_cancelacion_cuerpo'), ctx)
                        ok, _msg = enviar_email(c['email'], asunto, cuerpo)
                        conn.execute("""INSERT INTO emails_enviados
                            (destinatario, asunto, tipo, orden_id, estado) VALUES (?,?,?,?,?)""",
                            (c['email'], asunto, 'cancelacion', orden['id'], 'ok' if ok else 'error'))
                except Exception as e:
                    print(f"[auto-cancel email] {e}")

        conn.commit()
        print(f"[auto-cancel] {len(candidatas)} orden(es) canceladas automaticamente")
    except Exception as e:
        print(f"[auto-cancel] error: {e}")
    finally:
        conn.close()


@app.before_request
def _hook_auto_cancelar():
    if request.endpoint in (None, 'static'):
        return
    if not current_user.is_authenticated:
        return
    try:
        _auto_cancelar()
    except Exception as e:
        print(f"[hook auto-cancel] {e}")


# ===== Solicitudes de borrado =====
def _crear_solicitud(conn, tipo, entidad_id, descripcion, motivo):
    ya = conn.execute("""SELECT id FROM solicitudes_borrado
        WHERE tipo=? AND entidad_id=? AND usuario_id=? AND estado='pendiente'""",
        (tipo, entidad_id, current_user.id)).fetchone()
    if ya:
        return False
    conn.execute("""INSERT INTO solicitudes_borrado
        (tipo, entidad_id, descripcion, motivo, usuario_id) VALUES (?,?,?,?,?)""",
        (tipo, entidad_id, descripcion, motivo, current_user.id))
    return True


def _borrar_entidad(conn, tipo, entidad_id):
    if tipo == 'orden':
        conn.execute("DELETE FROM ordenes_venta WHERE id=?", (entidad_id,))
    elif tipo == 'cliente':
        conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (entidad_id,))
    elif tipo == 'producto':
        conn.execute("UPDATE productos SET activo=0 WHERE id=?", (entidad_id,))


@app.route('/solicitudes')
@login_required
def solicitudes_lista():
    conn = get_db()
    if current_user.es_admin:
        solicitudes = conn.execute("""
            SELECT s.*, u.nombre as usuario_nombre, r.nombre as resuelto_por_nombre
            FROM solicitudes_borrado s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            LEFT JOIN usuarios r ON r.id = s.resuelto_por
            ORDER BY s.estado='pendiente' DESC, s.id DESC
        """).fetchall()
    else:
        solicitudes = conn.execute("""
            SELECT s.*, u.nombre as usuario_nombre, r.nombre as resuelto_por_nombre
            FROM solicitudes_borrado s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            LEFT JOIN usuarios r ON r.id = s.resuelto_por
            WHERE s.usuario_id=?
            ORDER BY s.id DESC
        """, (current_user.id,)).fetchall()
    pendientes = sum(1 for s in solicitudes if s['estado'] == 'pendiente' and current_user.es_admin)
    conn.close()
    return render_template('solicitudes/lista.html', solicitudes=solicitudes, pendientes=pendientes)


@app.route('/solicitudes/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def solicitudes_aprobar(id):
    conn = get_db()
    s = conn.execute("SELECT * FROM solicitudes_borrado WHERE id=? AND estado='pendiente'", (id,)).fetchone()
    if not s:
        conn.close(); flash('Solicitud no encontrada o ya resuelta.', 'error')
        return redirect(url_for('solicitudes_lista'))
    _borrar_entidad(conn, s['tipo'], s['entidad_id'])
    conn.execute("""UPDATE solicitudes_borrado SET estado='aprobada',
        resuelto_por=?, resuelto_en=datetime('now') WHERE id=?""",
        (current_user.id, id))
    conn.commit(); conn.close()
    flash(f'Solicitud aprobada. {s["tipo"].capitalize()} borrado.', 'success')
    return redirect(url_for('solicitudes_lista'))


@app.route('/solicitudes/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def solicitudes_rechazar(id):
    conn = get_db()
    conn.execute("""UPDATE solicitudes_borrado SET estado='rechazada',
        resuelto_por=?, resuelto_en=datetime('now') WHERE id=? AND estado='pendiente'""",
        (current_user.id, id))
    conn.commit(); conn.close()
    flash('Solicitud rechazada.', 'success')
    return redirect(url_for('solicitudes_lista'))


# ===== Borrar orden =====
@app.route('/ventas/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_borrar(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error')
        return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso sobre esta orden.', 'error')
        return redirect(url_for('ventas_lista'))

    # Si tiene stock descontado y no está cancelada, primero cancelar
    if orden['stock_descontado'] and orden['estado'] != 'cancelado':
        conn.close()
        flash('Antes de borrar tenes que cancelar la orden (para devolver el stock).', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    if current_user.es_admin:
        conn.execute("DELETE FROM ordenes_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Orden {orden["numero_interno"]} borrada.', 'success')
        return redirect(url_for('ventas_lista'))

    # Vendedor: crear solicitud
    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'orden', id,
                          f'Orden {orden["numero_interno"]} (${orden["total"]:.2f})', motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin para borrar esta orden. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para esta orden.', 'error')
    return redirect(url_for('ventas_lista'))


# ===== Borrar cliente =====
@app.route('/clientes/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('clientes')
def clientes_borrar_v2(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not cliente:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))

    if current_user.es_admin:
        conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Cliente {cliente["nombre_completo"]} desactivado.', 'success')
        return redirect(url_for('clientes_lista'))

    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'cliente', id, cliente['nombre_completo'], motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para este cliente.', 'error')
    return redirect(url_for('clientes_lista'))


# ===== Borrar producto =====
@app.route('/productos/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('productos')
def productos_borrar_v2(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))

    if current_user.es_admin:
        conn.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Producto {producto["nombre"]} desactivado.', 'success')
        return redirect(url_for('productos_lista'))

    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'producto', id, producto['nombre'], motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para este producto.', 'error')
    return redirect(url_for('productos_lista'))


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
</style></head><body>
{% if current_user.is_authenticated %}
<aside class="sidebar">
<div class="brand">Familia Zaragoza</div>
<a href="{{ url_for('dashboard') }}" class="{% if request.endpoint=='dashboard' %}active{% endif %}"><i class="bi bi-speedometer2"></i> Dashboard</a>
{% if current_user.puede('clientes') %}<a href="{{ url_for('clientes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('clientes') %}active{% endif %}"><i class="bi bi-people"></i> Clientes</a>{% endif %}
{% if current_user.puede('ventas') %}<a href="{{ url_for('ventas_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('ventas') %}active{% endif %}"><i class="bi bi-cart"></i> Ventas</a>{% endif %}
{% if current_user.es_admin %}
<a href="{{ url_for('compras_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('compras') %}active{% endif %}"><i class="bi bi-bag"></i> Compras</a>
<a href="{{ url_for('gastos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('gastos') %}active{% endif %}"><i class="bi bi-cash-coin"></i> Gastos</a>
<a href="{{ url_for('reportes') }}" class="{% if request.endpoint and request.endpoint.startswith('reportes') %}active{% endif %}"><i class="bi bi-graph-up"></i> Reportes</a>
<a href="{{ url_for('emails_historial') }}" class="{% if request.endpoint and request.endpoint.startswith('emails') %}active{% endif %}"><i class="bi bi-envelope"></i> Emails</a>
<a href="{{ url_for('solicitudes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('solicitudes') %}active{% endif %}">
  <i class="bi bi-inbox"></i> Solicitudes
  {% if solicitudes_pendientes_sidebar is defined and solicitudes_pendientes_sidebar > 0 %}
  <span class="badge bg-danger ms-auto" style="font-size:.7rem;">{{ solicitudes_pendientes_sidebar }}</span>
  {% endif %}
</a>
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
</body></html>
'''


SOLICITUDES_LISTA = r'''{% extends "base.html" %}
{% block title %}Solicitudes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Solicitudes de borrado</h4>
{% if current_user.es_admin and pendientes > 0 %}<span class="badge-soft-warning">{{ pendientes }} pendiente{{ 's' if pendientes != 1 else '' }}</span>{% endif %}
</div>

<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr>
<th>Fecha</th><th>Tipo</th><th>Descripcion</th><th>Solicitado por</th><th>Motivo</th><th>Estado</th><th>Resuelto por</th>{% if current_user.es_admin %}<th class="text-end">Acciones</th>{% endif %}
</tr></thead>
<tbody>
{% for s in solicitudes %}
<tr>
<td class="small text-muted text-nowrap">{{ s.creado[:16] if s.creado else '' }}</td>
<td><span class="badge bg-secondary">{{ s.tipo }}</span></td>
<td class="small">{{ s.descripcion or '' }}</td>
<td class="small">{{ s.usuario_nombre }}</td>
<td class="small text-muted">{{ s.motivo or '—' }}</td>
<td>
{% if s.estado == 'pendiente' %}<span class="badge bg-warning text-dark">Pendiente</span>
{% elif s.estado == 'aprobada' %}<span class="badge bg-success">Aprobada</span>
{% else %}<span class="badge bg-danger">Rechazada</span>{% endif %}
</td>
<td class="small text-muted">{{ s.resuelto_por_nombre or '—' }}</td>
{% if current_user.es_admin %}
<td class="text-end text-nowrap">
{% if s.estado == 'pendiente' %}
<form method="post" action="{{ url_for('solicitudes_aprobar', id=s.id) }}" class="d-inline" onsubmit="return confirm('Aprobar y borrar definitivamente?')"><button class="btn btn-sm btn-success"><i class="bi bi-check-lg"></i> Aprobar</button></form>
<form method="post" action="{{ url_for('solicitudes_rechazar', id=s.id) }}" class="d-inline ms-1" onsubmit="return confirm('Rechazar la solicitud?')"><button class="btn btn-sm btn-outline-danger"><i class="bi bi-x-lg"></i> Rechazar</button></form>
{% endif %}
</td>
{% endif %}
</tr>
{% else %}
<tr><td colspan="8" class="text-center text-muted py-4">No hay solicitudes.</td></tr>
{% endfor %}
</tbody>
</table></div></div>
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
<button type="button" class="btn btn-sm btn-outline-primary" onclick="bulkSubmit('notificar', 'Enviar email Envio en camino?')"><i class="bi bi-envelope"></i> Notificar</button>
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
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openEmail({{ v.id }})" title="Email"><i class="bi bi-envelope"></i></button>
<button type="button" class="btn btn-sm btn-outline-dark" onclick="openMas({{ v.id }})" title="Mas acciones"><i class="bi bi-three-dots"></i></button>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrar({{ v.id }}, '{{ v.numero_interno }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td>
</tr>
{% else %}
<tr><td colspan="10" class="text-center text-muted py-4">No hay ventas cargadas.</td></tr>
{% endfor %}
</tbody></table></div></div>
</form>

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
<p class="text-muted small mb-3">Se envia al email cargado en la ficha del cliente.</p>
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

<div class="modal fade" id="borrarModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar orden <span id="borrar-num"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, esta accion borra la orden <strong>definitivamente</strong>.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>. La orden se borra recien cuando la apruebe.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="2" placeholder="Ej: duplicada, error de carga, cliente desistio..."></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar definitivamente{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<div class="modal fade" id="bulkFacturaModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<div class="modal-header"><h6 class="modal-title">Marcar seleccionadas como facturadas</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
<div class="mb-2"><label class="form-label">Nro ARCA base (opcional)</label><input id="bulk-factura-nro" class="form-control"></div>
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


CLIENTES_LISTA = r'''{% extends "base.html" %}
{% block title %}Clientes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Clientes</h4>
<a href="{{ url_for('clientes_nuevo') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nuevo</a>
</div>
<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-5"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control" placeholder="Nombre, doc, email"></div>
<div class="col-md-3"><label class="form-label small text-muted">Tag</label><select name="tipo" class="form-select"><option value="">Todos</option><option value="minorista" {% if filtro_tipo=='minorista' %}selected{% endif %}>Minorista</option><option value="mayorista" {% if filtro_tipo=='mayorista' %}selected{% endif %}>Mayorista</option></select></div>
<div class="col-md-3"><label class="form-label small text-muted">Provincia</label><select name="provincia" class="form-select"><option value="">Todas</option>{% for p in provincias %}<option value="{{ p }}" {% if provincia==p %}selected{% endif %}>{{ p }}</option>{% endfor %}</select></div>
<div class="col-md-1"><button class="btn btn-outline-secondary w-100"><i class="bi bi-search"></i></button></div>
</div></form>
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr><th>Nombre</th><th>Doc</th><th>Provincia</th><th>Localidad</th><th>Email</th><th>Tags</th><th class="text-end">Acciones</th></tr></thead>
<tbody>
{% for c in clientes %}
<tr><td>{{ c.nombre_completo }}</td><td class="small text-muted">{{ c.tipo_doc or '' }} {{ c.nro_doc or '' }}</td>
<td>{{ c.provincia or '' }}</td><td>{{ c.localidad or '' }}</td><td class="small">{{ c.email or '' }}</td>
<td>{% if c.es_minorista %}<span class="badge bg-info text-dark">Minorista</span>{% endif %}{% if c.es_mayorista %}<span class="badge bg-warning text-dark">Mayorista</span>{% endif %}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('clientes_editar', id=c.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarCliente({{ c.id }}, '{{ c.nombre_completo }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td></tr>
{% else %}<tr><td colspan="7" class="text-center text-muted py-4">Sin clientes.</td></tr>{% endfor %}
</tbody></table></div></div>

<div class="modal fade" id="borrarClienteModal" tabindex="-1">
<div class="modal-dialog"><div class="modal-content">
<form id="borrar-cliente-form" method="post">
<div class="modal-header"><h6 class="modal-title">Borrar cliente <span id="borrar-cliente-nombre"></span></h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
<div class="modal-body">
{% if current_user.es_admin %}
<div class="alert alert-warning py-2 small mb-3"><i class="bi bi-exclamation-triangle"></i> Como admin, el cliente se desactiva inmediatamente.</div>
{% else %}
<div class="alert alert-info py-2 small mb-3"><i class="bi bi-info-circle"></i> Se enviara una <strong>solicitud al admin</strong>. El cliente se borra cuando la apruebe.</div>
{% endif %}
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="2"></textarea></div>
</div>
<div class="modal-footer">
<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
<button type="submit" class="btn btn-danger">{% if current_user.es_admin %}Borrar{% else %}Enviar solicitud{% endif %}</button>
</div>
</form></div></div></div>

<script>
function openBorrarCliente(id, nombre) {
  document.getElementById('borrar-cliente-form').action = '/clientes/' + id + '/borrar';
  document.getElementById('borrar-cliente-nombre').textContent = nombre;
  new bootstrap.Modal(document.getElementById('borrarClienteModal')).show();
}
</script>
{% endblock %}
'''


PRODUCTOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Productos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Productos</h4>
<a href="{{ url_for('productos_nuevo') }}" class="btn btn-dark"><i class="bi bi-plus-lg"></i> Nuevo</a>
</div>
<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-10"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control" placeholder="SKU o nombre"></div>
<div class="col-md-2"><button class="btn btn-outline-secondary w-100"><i class="bi bi-search"></i> Buscar</button></div>
</div></form>
<div class="card shadow-sm"><div class="table-responsive">
<table class="table table-hover mb-0 align-middle">
<thead class="table-light"><tr><th>SKU</th><th>Nombre</th><th class="text-end">Costo</th><th class="text-end">Precio</th><th class="text-end">Stock</th><th class="text-end">Minimo</th><th class="text-end">Acciones</th></tr></thead>
<tbody>
{% for p in productos %}
<tr><td class="text-muted small">{{ p.sku or '' }}</td><td>{{ p.nombre }}</td>
<td class="text-end">${{ '%.2f'|format(p.costo) }}</td><td class="text-end">${{ '%.2f'|format(p.precio) }}</td>
<td class="text-end">{% if p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo %}<span class="badge bg-danger">{{ '%g'|format(p.stock_actual) }}</span>{% else %}<span class="badge bg-success">{{ '%g'|format(p.stock_actual) }}</span>{% endif %}</td>
<td class="text-end text-muted">{{ '%g'|format(p.stock_minimo) }}</td>
<td class="text-end text-nowrap">
<a href="{{ url_for('productos_editar', id=p.id) }}" class="btn btn-sm btn-outline-secondary" title="Editar"><i class="bi bi-pencil"></i></a>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrarProducto({{ p.id }}, '{{ p.nombre }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td></tr>
{% else %}<tr><td colspan="7" class="text-center text-muted py-4">Sin productos.</td></tr>{% endfor %}
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
<div class="mb-2"><label class="form-label">Motivo (opcional)</label>
<textarea name="motivo" class="form-control" rows="2"></textarea></div>
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


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app12; app12.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 12: Auto-cancel 24h + Borrado con permiso (F2.2a) ===")
    migrar()
    escribir('app12.py', APP12_PY)
    escribir('templates/base.html', BASE_HTML)
    escribir('templates/solicitudes/lista.html', SOLICITUDES_LISTA)
    escribir('templates/ventas/lista.html', VENTAS_LISTA)
    escribir('templates/clientes/lista.html', CLIENTES_LISTA)
    escribir('templates/productos/lista.html', PRODUCTOS_LISTA)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app12.py)")


if __name__ == '__main__':
    main()