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
    print(f"[upgrade15] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade15] sin DB."); return
    conn = sqlite3.connect(db)

    # Nueva clave: email de atencion al cliente
    if not conn.execute("SELECT clave FROM configuracion WHERE clave='empresa_email'").fetchone():
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
                     ('empresa_email', 'hola@familiazaragoza.com'))
        print("[upgrade15] + empresa_email = hola@familiazaragoza.com")

    # Agregar ® al nombre de empresa
    conn.execute("UPDATE configuracion SET valor = 'Familia Zaragoza ®' WHERE clave = 'empresa_nombre'")
    conn.execute("UPDATE configuracion SET valor = 'Familia Zaragoza ®' WHERE clave = 'smtp_remitente_nombre'")
    print("[upgrade15] empresa_nombre y smtp_remitente_nombre con ®")

    # Firma: si todavia dice notificacion@, cambiar a hola@
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='firma_email'").fetchone()
    if row and row[0] and 'notificacion@familiazaragoza.com' in row[0]:
        nuevo = row[0].replace('notificacion@familiazaragoza.com', 'hola@familiazaragoza.com')
        conn.execute("UPDATE configuracion SET valor=? WHERE clave='firma_email'", (nuevo,))
        print("[upgrade15] firma_email: notificacion@ -> hola@")

    conn.commit(); conn.close()


APP15_PY = r'''
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app12 import app
from app4 import _cargar_orden
from app import permiso_required
from database import get_db


def _config(clave, default=''):
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return (row['valor'] if row and row['valor'] else default)


@app.context_processor
def _ctx_empresa():
    return {
        'empresa_nombre_cfg': _config('empresa_nombre', 'Familia Zaragoza ®'),
        'empresa_email_cfg': _config('empresa_email', 'hola@familiazaragoza.com'),
    }


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
        'nombre': _config('empresa_nombre', 'Familia Zaragoza ®'),
        'telefono': _config('empresa_telefono', '+54 9 3755 531691'),
        'web': _config('empresa_web', 'familiazaragoza.com'),
        'email': _config('empresa_email', 'hola@familiazaragoza.com'),
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
<div class="brand">{{ empresa_nombre_cfg }}</div>
<a href="{{ url_for('dashboard') }}" class="{% if request.endpoint=='dashboard' %}active{% endif %}"><i class="bi bi-speedometer2"></i> Dashboard</a>
{% if current_user.puede('clientes') %}<a href="{{ url_for('clientes_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('clientes') %}active{% endif %}"><i class="bi bi-people"></i> Clientes</a>{% endif %}
{% if current_user.puede('ventas') %}<a href="{{ url_for('ventas_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('ventas') %}active{% endif %}"><i class="bi bi-cart"></i> Ventas</a>{% endif %}
{% if current_user.es_admin %}
<a href="{{ url_for('compras_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('compras') %}active{% endif %}"><i class="bi bi-bag"></i> Compras</a>
<a href="{{ url_for('gastos_lista') }}" class="{% if request.endpoint and request.endpoint.startswith('gastos') %}active{% endif %}"><i class="bi bi-cash-coin"></i> Gastos</a>
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
</body></html>
'''


LOGIN_HTML = r'''{% extends "base.html" %}
{% block title %}Login - Sistema FZ{% endblock %}
{% block content %}
<div class="row justify-content-center">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body p-4">
<h3 class="mb-1">{{ empresa_nombre_cfg }}</h3>
<p class="text-muted mb-4">Sistema de gestion interno</p>
<form method="post">
<div class="mb-3"><label class="form-label">Email</label><input type="email" name="email" class="form-control" required autofocus></div>
<div class="mb-3"><label class="form-label">Contrasena</label><input type="password" name="password" class="form-control" required></div>
<button class="btn btn-dark w-100">Entrar</button>
</form></div></div>
<p class="text-center text-muted mt-3 small">Acceso restringido</p>
</div></div>
{% endblock %}
'''


IMPRIMIR_HTML = r'''<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<title>{{ orden.numero_interno }} - {{ empresa.nombre }}</title>
<style>
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 40px; font-size: 13px; max-width: 800px; margin-left: auto; margin-right: auto; }
.header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1f2937; padding-bottom: 16px; margin-bottom: 24px; }
.header .empresa h1 { margin: 0 0 6px 0; font-size: 22px; letter-spacing: -.02em; }
.header .empresa .info { font-size: 11px; color: #4b5563; line-height: 1.7; }
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


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app15; app15.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 15: Email atencion cliente + marca (R) ===")
    migrar()
    escribir('app15.py', APP15_PY)
    escribir('templates/base.html', BASE_HTML)
    escribir('templates/login.html', LOGIN_HTML)
    escribir('templates/ventas/imprimir.html', IMPRIMIR_HTML)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app15.py)")


if __name__ == '__main__':
    main()