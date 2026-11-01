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
    print(f"[upgrade32] escrito: {relpath}")


APP32_PY = r'''
import re, urllib.parse, calendar
from datetime import date, datetime
from flask import render_template, request
from flask_login import login_required, current_user
from app31 import app
from app import permiso_required
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


def _stats_ventas(conn, usuario_id=None):
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()
    if hoy.month == 1:
        ant_ini = date(hoy.year-1, 12, 1).isoformat()
        ult = 31
        ant_fin = date(hoy.year-1, 12, 31).isoformat()
    else:
        ant_ini = date(hoy.year, hoy.month-1, 1).isoformat()
        ult = calendar.monthrange(hoy.year, hoy.month-1)[1]
        ant_fin = date(hoy.year, hoy.month-1, ult).isoformat()

    if usuario_id:
        cond = " AND usuario_id = ?"
        params_mes = [ini_mes, usuario_id]
        params_ant = [ant_ini, ant_fin, usuario_id]
        params_u = [usuario_id]
    else:
        cond = ""
        params_mes = [ini_mes]
        params_ant = [ant_ini, ant_fin]
        params_u = []

    ordenes_mes = conn.execute(
        f"SELECT COUNT(*) FROM ordenes_venta WHERE date(fecha) >= ?{cond}",
        params_mes).fetchone()[0]
    ordenes_ant = conn.execute(
        f"SELECT COUNT(*) FROM ordenes_venta WHERE date(fecha) BETWEEN ? AND ?{cond}",
        params_ant).fetchone()[0]
    pendientes = conn.execute(
        f"SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago'{cond}",
        params_u).fetchone()[0]
    sin_despachar = conn.execute(
        f"SELECT COUNT(*) FROM ordenes_venta WHERE estado='pagado_sin_enviar'{cond}",
        params_u).fetchone()[0]
    facturado_mes = conn.execute(
        f"""SELECT COALESCE(SUM(total),0) FROM ordenes_venta
        WHERE date(fecha) >= ? AND estado IN ('pagado_sin_enviar','pagado_enviado'){cond}""",
        params_mes).fetchone()[0]
    facturado_ant = conn.execute(
        f"""SELECT COALESCE(SUM(total),0) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ? AND estado IN ('pagado_sin_enviar','pagado_enviado'){cond}""",
        params_ant).fetchone()[0]

    if usuario_id:
        a_cobrar = conn.execute(
            """SELECT COALESCE(SUM(o.total - COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)),0)
            FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.usuario_id = ?
            AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)""",
            (usuario_id,)).fetchone()[0]
    else:
        a_cobrar = conn.execute(
            """SELECT COALESCE(SUM(o.total - COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)),0)
            FROM ordenes_venta o WHERE o.estado != 'cancelado'
            AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)"""
        ).fetchone()[0]

    def _var(a, b):
        if b == 0:
            return None if a == 0 else 100.0
        return ((a - b) / b) * 100

    return {
        'ordenes_mes': ordenes_mes,
        'ordenes_ant': ordenes_ant,
        'variacion_ordenes': _var(ordenes_mes, ordenes_ant),
        'variacion_facturado': _var(facturado_mes, facturado_ant),
        'pendientes': pendientes,
        'sin_despachar': sin_despachar,
        'facturado_mes': facturado_mes,
        'facturado_ant': facturado_ant,
        'a_cobrar': a_cobrar,
    }


@app.route('/ventas')
@login_required
@permiso_required('ventas')
def ventas_lista_v3():
    conn = get_db()
    q = request.args.get('q', '').strip()
    estado = request.args.get('estado', '')
    canal = request.args.get('canal', '')
    tipo = request.args.get('tipo', '')
    vendedor = request.args.get('vendedor', '')
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    con_saldo = request.args.get('con_saldo', '')
    facturado = request.args.get('facturado', '')

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
    if con_saldo == '1':
        sql += """ AND o.estado != 'cancelado'
            AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)"""
    if facturado == '1':
        sql += " AND o.estado_facturacion = 'facturada'"

    sql += " ORDER BY o.id DESC"
    rows = conn.execute(sql, params).fetchall()

    ventas = []
    for r in rows:
        d = dict(r)
        tel = _limpiar_tel(r['cliente_telefono'])
        if tel:
            msg = (f"Hola {r['cliente_nombre']}!\n"
                   f"Te paso el resumen de tu pedido {r['numero_interno']}:\n"
                   f"Total: ${r['total']:.2f}")
            d['wa_url'] = f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"
        else:
            d['wa_url'] = None
        ventas.append(d)

    canales = conn.execute("SELECT * FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT * FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall() if current_user.es_admin else []

    usuario_id = None if current_user.es_admin else current_user.id
    stats = _stats_ventas(conn, usuario_id)

    conn.close()
    return render_template('ventas/lista.html', ventas=ventas, q=q, estado=estado, canal=canal,
                           tipo=tipo, vendedor=vendedor, desde=desde, hasta=hasta,
                           canales=canales, vendedores=vendedores, stats=stats,
                           con_saldo=con_saldo, facturado=facturado)


app.view_functions['ventas_lista'] = ventas_lista_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


def patch_template():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade32] ADVERTENCIA: ventas/lista.html no existe")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Si ya esta el bloque nuevo, no hacer nada
    if 'stats-header-ventas' in contenido:
        print("[upgrade32] header ya existia, nada que hacer")
        return

    # Buscar el inicio del bloque de filtros y agregar antes el header
    buscar = '''<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Nro o cliente"></div>'''

    if buscar not in contenido:
        print("[upgrade32] ADVERTENCIA: no se encontro el patron del form de filtros")
        return

    header_nuevo = '''<!-- Stats Header Ventas (U32) -->
<div class="stats-header-ventas mb-3">
<div class="row g-2">
<div class="col-md-3">
<a href="{{ url_for('ventas_lista') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #3b5bdb;">
<div class="kpi-label">Ordenes de este mes</div>
<div class="kpi-value">{{ stats.ordenes_mes }}</div>
{% if stats.variacion_ordenes is not none %}
<div class="kpi-delta {% if stats.variacion_ordenes >= 0 %}text-success{% else %}text-danger{% endif %}">
<i class="bi bi-arrow-{% if stats.variacion_ordenes >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.variacion_ordenes|abs) }}% vs mes anterior ({{ stats.ordenes_ant }})
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos mes anterior</div>{% endif %}
</div></a></div>

<div class="col-md-3">
<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #f59e0b;{% if estado=='pendiente_pago' %}background:#fffbeb;{% endif %}">
<div class="kpi-label"><i class="bi bi-hourglass-split"></i> Pendientes de pago</div>
<div class="kpi-value">{{ stats.pendientes }}</div>
<div class="kpi-delta text-muted">Click para ver todas</div>
</div></a></div>

<div class="col-md-3">
<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #06b6d4;{% if estado=='pagado_sin_enviar' %}background:#ecfeff;{% endif %}">
<div class="kpi-label"><i class="bi bi-truck"></i> Sin despachar</div>
<div class="kpi-value">{{ stats.sin_despachar }}</div>
<div class="kpi-delta text-muted">Pagadas esperando envio</div>
</div></a></div>

<div class="col-md-3">
<a href="{{ url_for('ventas_lista', con_saldo='1') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #ef4444;{% if con_saldo=='1' %}background:#fef2f2;{% endif %}">
<div class="kpi-label"><i class="bi bi-cash-coin"></i> A cobrar</div>
<div class="kpi-value text-danger">${{ '{:,.0f}'.format(stats.a_cobrar).replace(',','.') }}</div>
<div class="kpi-delta text-muted">Saldo total pendiente</div>
</div></a></div>
</div>

<div class="row g-2 mt-2">
<div class="col-md-6">
<a href="{{ url_for('ventas_lista', facturado='1') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #10b981;{% if facturado=='1' %}background:#ecfdf5;{% endif %}">
<div class="kpi-label"><i class="bi bi-receipt"></i> Facturado este mes (cobrado)</div>
<div class="kpi-value">${{ '{:,.0f}'.format(stats.facturado_mes).replace(',','.') }}</div>
{% if stats.variacion_facturado is not none %}
<div class="kpi-delta {% if stats.variacion_facturado >= 0 %}text-success{% else %}text-danger{% endif %}">
<i class="bi bi-arrow-{% if stats.variacion_facturado >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(stats.variacion_facturado|abs) }}% vs mes anterior (${{ '{:,.0f}'.format(stats.facturado_ant).replace(',','.') }})
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos mes anterior</div>{% endif %}
</div></a></div>

<div class="col-md-6">
{% if con_saldo == '1' or facturado == '1' %}
<a href="{{ url_for('ventas_lista') }}" class="text-decoration-none">
<div class="card-kpi" style="border-left:3px solid #6b7280;">
<div class="kpi-label"><i class="bi bi-x-circle"></i> Filtro activo</div>
<div class="kpi-value" style="font-size:1.1rem;">
{% if con_saldo == '1' %}Mostrando solo ordenes con saldo pendiente{% endif %}
{% if facturado == '1' %}Mostrando solo ordenes facturadas{% endif %}
</div>
<div class="kpi-delta text-primary">Click para quitar filtro</div>
</div></a>
{% else %}
<a href="{{ url_for('ventas_lista', facturado='1') }}" class="text-decoration-none text-reset">
<div class="card-kpi" style="border-left:3px solid #6b7280;">
<div class="kpi-label"><i class="bi bi-file-earmark-check"></i> Ver facturadas</div>
<div class="kpi-value" style="font-size:1.1rem; color:#6b7280;">Todas</div>
<div class="kpi-delta text-muted">Click para filtrar</div>
</div></a>
{% endif %}
</div>
</div>
</div>

<form class="card shadow-sm p-3 mb-3"><div class="row g-2 align-items-end">
<div class="col-md-3"><label class="form-label small text-muted">Buscar</label><input name="q" value="{{ q }}" class="form-control form-control-sm" placeholder="Nro o cliente"></div>'''

    contenido = contenido.replace(buscar, header_nuevo)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade32] header agregado a ventas/lista.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app32; app32.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 32: Header de ventas con metricas (U32) ===")
    escribir('app32.py', APP32_PY)
    patch_template()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app32.py)")


if __name__ == '__main__':
    main()