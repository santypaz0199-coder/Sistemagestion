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
    print(f"[upgrade27] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade27] sin DB."); return
    conn = sqlite3.connect(db)

    # Agregar costo_unitario a orden_items
    cols = [r[1] for r in conn.execute("PRAGMA table_info(orden_items)").fetchall()]
    if 'costo_unitario' not in cols:
        conn.execute("ALTER TABLE orden_items ADD COLUMN costo_unitario REAL DEFAULT 0")
        print("[upgrade27] + orden_items.costo_unitario")

        # Backfill: usar costo actual del producto
        conn.execute("""
            UPDATE orden_items
            SET costo_unitario = COALESCE((SELECT costo FROM productos WHERE id = orden_items.producto_id), 0)
            WHERE costo_unitario = 0 OR costo_unitario IS NULL
        """)
        print("[upgrade27] backfill costo en ventas existentes")

    # Trigger para capturar costo al crear nuevas ventas
    conn.execute("DROP TRIGGER IF EXISTS trg_orden_items_costo")
    conn.execute("""
        CREATE TRIGGER trg_orden_items_costo
        AFTER INSERT ON orden_items
        WHEN NEW.costo_unitario IS NULL OR NEW.costo_unitario = 0
        BEGIN
            UPDATE orden_items
            SET costo_unitario = COALESCE((SELECT costo FROM productos WHERE id = NEW.producto_id), 0)
            WHERE id = NEW.id;
        END
    """)
    print("[upgrade27] trigger trg_orden_items_costo OK")

    conn.commit(); conn.close()


APP27_PY = r'''
from datetime import date, timedelta
from flask import render_template, request
from flask_login import login_required, current_user
from app26 import app, MESES, _get_objetivo, _facturado
from app import admin_required
from database import get_db


def _periodo(tipo):
    hoy = date.today()
    if tipo == 'trimestre':
        return hoy - timedelta(days=90), hoy
    if tipo == 'anio':
        return date(hoy.year, 1, 1), date(hoy.year, 12, 31)
    # mes (default)
    ini = hoy.replace(day=1)
    if ini.month == 12:
        fin = date(ini.year+1, 1, 1) - timedelta(days=1)
    else:
        fin = date(ini.year, ini.month+1, 1) - timedelta(days=1)
    return ini, fin


def _periodo_ant(tipo, ini, fin):
    if tipo == 'trimestre':
        return ini - timedelta(days=91), fin - timedelta(days=91)
    if tipo == 'anio':
        return date(ini.year-1, 1, 1), date(ini.year-1, 12, 31)
    # mes
    ant_fin = ini - timedelta(days=1)
    ant_ini = ant_fin.replace(day=1)
    return ant_ini, ant_fin


def _periodo_ap(tipo, ini, fin):
    if tipo == 'trimestre':
        return ini.replace(year=ini.year-1), fin.replace(year=fin.year-1)
    if tipo == 'anio':
        return date(ini.year-1, 1, 1), date(ini.year-1, 12, 31)
    return date(ini.year-1, ini.month, 1), fin.replace(year=fin.year-1)


def _financiero(conn, ini, fin):
    ini_s, fin_s = ini.isoformat(), fin.isoformat()
    facturado = conn.execute(
        """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ? AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
        (ini_s, fin_s)).fetchone()[0]
    num_ordenes = conn.execute(
        """SELECT COUNT(*) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ? AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
        (ini_s, fin_s)).fetchone()[0]
    cmv = conn.execute(
        """SELECT COALESCE(SUM(oi.cantidad * oi.costo_unitario),0) FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')""",
        (ini_s, fin_s)).fetchone()[0]
    gastos = conn.execute(
        "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ?",
        (ini_s, fin_s)).fetchone()[0]
    insumos = conn.execute(
        """SELECT COALESCE(SUM(total),0) FROM compras
        WHERE date(fecha) BETWEEN ? AND ? AND tipo='insumo'""",
        (ini_s, fin_s)).fetchone()[0]

    ganancia_bruta = facturado - cmv
    total_gastos = gastos + insumos
    ganancia_neta = ganancia_bruta - total_gastos
    margen_bruto_pct = (ganancia_bruta/facturado*100) if facturado > 0 else 0
    margen_neto_pct = (ganancia_neta/facturado*100) if facturado > 0 else 0
    margen_contrib_pct = ((facturado - cmv - insumos)/facturado*100) if facturado > 0 else 0
    punto_eq = (gastos / (margen_contrib_pct/100)) if margen_contrib_pct > 0 else 0
    ticket_prom = (facturado/num_ordenes) if num_ordenes > 0 else 0
    faltante_eq = max(0, punto_eq - facturado)

    return {
        'facturado': facturado, 'cmv': cmv, 'ganancia_bruta': ganancia_bruta,
        'gastos': gastos, 'insumos': insumos, 'total_gastos': total_gastos,
        'ganancia_neta': ganancia_neta, 'margen_bruto_pct': margen_bruto_pct,
        'margen_neto_pct': margen_neto_pct, 'margen_contrib_pct': margen_contrib_pct,
        'punto_eq': punto_eq, 'num_ordenes': num_ordenes, 'ticket_prom': ticket_prom,
        'faltante_eq': faltante_eq,
    }


def _kilos(conn, ini, fin):
    return conn.execute(
        """SELECT COALESCE(SUM(
            CASE WHEN p.peso_unidad = 'g' THEN (oi.cantidad * p.peso_valor) / 1000.0
                 ELSE oi.cantidad * COALESCE(p.peso_valor, 0)
            END
        ), 0) FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')""",
        (ini.isoformat(), fin.isoformat())).fetchone()[0]


def _top_vendedores(conn, ini, fin, limit=10):
    return conn.execute(
        """SELECT u.nombre, COALESCE(SUM(o.total),0) as total, COUNT(o.id) as cnt
        FROM usuarios u
        JOIN ordenes_venta o ON o.usuario_id = u.id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        GROUP BY u.id ORDER BY total DESC LIMIT ?""",
        (ini.isoformat(), fin.isoformat(), limit)).fetchall()


def _top_canales(conn, ini, fin, limit=10):
    return conn.execute(
        """SELECT COALESCE(cv.nombre,'Sin canal') as canal, COALESCE(SUM(o.total),0) as total, COUNT(o.id) as cnt
        FROM ordenes_venta o LEFT JOIN canales_venta cv ON cv.id = o.canal_id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        GROUP BY o.canal_id ORDER BY total DESC LIMIT ?""",
        (ini.isoformat(), fin.isoformat(), limit)).fetchall()


def _top_productos(conn, ini, fin, limit=10):
    return conn.execute(
        """SELECT p.nombre, p.sku, SUM(oi.cantidad) as cant, SUM(oi.subtotal) as total
        FROM orden_items oi JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos p ON p.id = oi.producto_id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        GROUP BY p.id ORDER BY total DESC LIMIT ?""",
        (ini.isoformat(), fin.isoformat(), limit)).fetchall()


def _top_provincias(conn, ini, fin, limit=10):
    return conn.execute(
        """SELECT COALESCE(pr.nombre,'Sin provincia') as provincia, COALESCE(SUM(o.total),0) as total, COUNT(DISTINCT o.cliente_id) as clientes
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias pr ON pr.id = c.provincia_id
        WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        GROUP BY c.provincia_id ORDER BY total DESC LIMIT ?""",
        (ini.isoformat(), fin.isoformat(), limit)).fetchall()


def _var(a, b):
    if b == 0:
        return None if a == 0 else 100.0
    return ((a - b) / b) * 100


def reportes_v2():
    tipo = request.args.get('tipo', 'mes')
    if tipo not in ('mes', 'trimestre', 'anio'):
        tipo = 'mes'
    ini, fin = _periodo(tipo)
    ini_ant, fin_ant = _periodo_ant(tipo, ini, fin)
    ini_ap, fin_ap = _periodo_ap(tipo, ini, fin)

    conn = get_db()
    actual = _financiero(conn, ini, fin)
    anterior = _financiero(conn, ini_ant, fin_ant)
    anio_pas = _financiero(conn, ini_ap, fin_ap)

    kilos_act = _kilos(conn, ini, fin)
    kilos_ant = _kilos(conn, ini_ant, fin_ant)
    kilos_ap = _kilos(conn, ini_ap, fin_ap)

    top_v = _top_vendedores(conn, ini, fin)
    top_c = _top_canales(conn, ini, fin)
    top_p = _top_productos(conn, ini, fin)
    top_pr = _top_provincias(conn, ini, fin)

    var = {
        'facturado_ant': _var(actual['facturado'], anterior['facturado']),
        'facturado_ap': _var(actual['facturado'], anio_pas['facturado']),
        'ganancia_bruta_ant': _var(actual['ganancia_bruta'], anterior['ganancia_bruta']),
        'ganancia_bruta_ap': _var(actual['ganancia_bruta'], anio_pas['ganancia_bruta']),
        'ganancia_neta_ant': _var(actual['ganancia_neta'], anterior['ganancia_neta']),
        'ganancia_neta_ap': _var(actual['ganancia_neta'], anio_pas['ganancia_neta']),
        'num_ordenes_ant': _var(actual['num_ordenes'], anterior['num_ordenes']),
        'num_ordenes_ap': _var(actual['num_ordenes'], anio_pas['num_ordenes']),
        'kilos_ant': _var(kilos_act, kilos_ant),
        'kilos_ap': _var(kilos_act, kilos_ap),
    }

    labels = {'mes': 'Este mes', 'trimestre': 'Últimos 90 días', 'anio': 'Este año'}
    conn.close()
    return render_template('reportes/index.html',
        tipo=tipo, ini=ini, fin=fin,
        actual=actual, anterior=anterior, anio_pas=anio_pas,
        kilos_act=kilos_act, kilos_ant=kilos_ant, kilos_ap=kilos_ap,
        top_v=top_v, top_c=top_c, top_p=top_p, top_pr=top_pr,
        var=var, label_periodo=labels[tipo])


app.view_functions['reportes'] = reportes_v2


@app.context_processor
def _ctx_objetivos_dashboard():
    if not current_user.is_authenticated or not current_user.es_admin:
        return {}
    if request.endpoint != 'dashboard':
        return {}
    conn = get_db()
    try:
        hoy = date.today()
        obj_global = _get_objetivo(conn, None, hoy.month, hoy.year)
        fac_global = _facturado(conn, None, hoy.month, hoy.year)
        vendedores = conn.execute(
            "SELECT id, nombre FROM usuarios WHERE activo=1 AND rol='vendedor' ORDER BY nombre"
        ).fetchall()
        objetivos_v = []
        for v in vendedores:
            obj = _get_objetivo(conn, v['id'], hoy.month, hoy.year)
            fac = _facturado(conn, v['id'], hoy.month, hoy.year)
            pct = (fac/obj*100) if obj > 0 else 0
            objetivos_v.append({'nombre': v['nombre'], 'objetivo': obj, 'facturado': fac, 'pct': pct})
        return {'objetivos_dashboard': {
            'global': {'objetivo': obj_global, 'facturado': fac_global,
                       'pct': (fac_global/obj_global*100) if obj_global > 0 else 0},
            'vendedores': objetivos_v,
            'mes_label': MESES[hoy.month],
            'anio': hoy.year,
        }}
    finally:
        conn.close()


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


REPORTES_INDEX = r'''{% extends "base.html" %}
{% block title %}Reportes{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
<div>
<h4 class="mb-1">Reportes financieros</h4>
<div class="text-muted small">{{ ini.strftime('%d/%m/%Y') }} al {{ fin.strftime('%d/%m/%Y') }}</div>
</div>
<div class="d-flex gap-2">
<form class="d-flex gap-2">
<select name="tipo" class="form-select form-select-sm" onchange="this.form.submit()">
<option value="mes" {% if tipo=='mes' %}selected{% endif %}>Este mes</option>
<option value="trimestre" {% if tipo=='trimestre' %}selected{% endif %}>Últimos 90 días</option>
<option value="anio" {% if tipo=='anio' %}selected{% endif %}>Este año</option>
</select>
</form>
<a href="{{ url_for('reportes_cierres') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-archive"></i> Cierres</a>
</div>
</div>

<!-- KPIs financieros -->
<div class="row row-cols-2 row-cols-md-4 g-2 mb-3">
<div class="col">
<div class="card-kpi" style="border-left:3px solid #3b5bdb;">
<div class="kpi-label">Facturado</div>
<div class="kpi-value">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }}</div>
<div class="kpi-delta text-muted small">{{ actual.num_ordenes }} ordenes · ticket ${{ '{:,.0f}'.format(actual.ticket_prom).replace(',','.') }}</div>
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #f59e0b;">
<div class="kpi-label">CMV (costo mercaderia)</div>
<div class="kpi-value">${{ '{:,.0f}'.format(actual.cmv).replace(',','.') }}</div>
<div class="kpi-delta text-muted small">{{ '%.1f'|format((actual.cmv/actual.facturado*100) if actual.facturado > 0 else 0) }}% del facturado</div>
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid #10b981;">
<div class="kpi-label">Ganancia bruta</div>
<div class="kpi-value text-{% if actual.ganancia_bruta >= 0 %}success{% else %}danger{% endif %}">${{ '{:,.0f}'.format(actual.ganancia_bruta).replace(',','.') }}</div>
<div class="kpi-delta small">Margen bruto: <strong>{{ '%.1f'|format(actual.margen_bruto_pct) }}%</strong></div>
</div>
</div>
<div class="col">
<div class="card-kpi" style="border-left:3px solid {% if actual.ganancia_neta >= 0 %}#10b981{% else %}#ef4444{% endif %};">
<div class="kpi-label">Ganancia neta</div>
<div class="kpi-value text-{% if actual.ganancia_neta >= 0 %}success{% else %}danger{% endif %}">${{ '{:,.0f}'.format(actual.ganancia_neta).replace(',','.') }}</div>
<div class="kpi-delta small">Margen neto: <strong>{{ '%.1f'|format(actual.margen_neto_pct) }}%</strong></div>
</div>
</div>
</div>

<!-- Egresos -->
<div class="row g-2 mb-3">
<div class="col-md-6"><div class="card-kpi" style="border-left:3px solid #ef4444;">
<div class="kpi-label">Gastos fijos del periodo</div>
<div class="kpi-value">${{ '{:,.0f}'.format(actual.gastos).replace(',','.') }}</div>
</div></div>
<div class="col-md-6"><div class="card-kpi" style="border-left:3px solid #06b6d4;">
<div class="kpi-label">Insumos (variables)</div>
<div class="kpi-value">${{ '{:,.0f}'.format(actual.insumos).replace(',','.') }}</div>
</div></div>
</div>

<!-- Punto de equilibrio -->
<div class="card shadow-sm mb-3" style="border-left:4px solid #8b5cf6;">
<div class="card-body">
<div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
<div>
<h6 class="mb-1"><i class="bi bi-bullseye"></i> Punto de equilibrio</h6>
<div class="text-muted small">Cuanto necesitas facturar para cubrir los gastos fijos con el margen de contribucion actual</div>
</div>
<span class="badge-soft-primary">Margen contribucion {{ '%.1f'|format(actual.margen_contrib_pct) }}%</span>
</div>
<div class="row g-3">
<div class="col-md-4">
<div class="text-muted small mb-1">Facturado</div>
<div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }}</div>
</div>
<div class="col-md-4">
<div class="text-muted small mb-1">Punto de equilibrio</div>
<div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(actual.punto_eq).replace(',','.') }}</div>
</div>
<div class="col-md-4">
<div class="text-muted small mb-1">Estado</div>
{% if actual.facturado >= actual.punto_eq and actual.punto_eq > 0 %}
<div class="badge-soft-success"><i class="bi bi-check-circle-fill"></i> Por encima del punto</div>
{% elif actual.punto_eq > 0 %}
<div class="badge-soft-danger"><i class="bi bi-x-circle-fill"></i> Faltan ${{ '{:,.0f}'.format(actual.faltante_eq).replace(',','.') }}</div>
{% else %}
<div class="badge-soft-warning">Sin datos suficientes</div>
{% endif %}
</div>
</div>
{% if actual.punto_eq > 0 %}
<div class="progress-fz {% if actual.facturado >= actual.punto_eq %}p-ok{% elif actual.facturado >= actual.punto_eq*0.75 %}p-warn{% else %}p-low{% endif %} mt-3" style="height:10px;">
<div class="progress-bar" style="width:{{ [actual.facturado/actual.punto_eq*100, 100]|min }}%"></div>
</div>
{% endif %}
</div>
</div>

<!-- Comparativas -->
<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-arrow-left-right"></i> vs Mes anterior ({{ anterior.facturado|round|int if false else '' }})</h6>
<table class="table table-sm mb-0">
<tr><td class="small">Facturado</td><td class="text-end">${{ '{:,.0f}'.format(anterior.facturado).replace(',','.') }}</td>
<td class="text-end small {% if var.facturado_ant and var.facturado_ant >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.facturado_ant is not none %}{{ '%+.1f'|format(var.facturado_ant) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ganancia bruta</td><td class="text-end">${{ '{:,.0f}'.format(anterior.ganancia_bruta).replace(',','.') }}</td>
<td class="text-end small {% if var.ganancia_bruta_ant and var.ganancia_bruta_ant >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.ganancia_bruta_ant is not none %}{{ '%+.1f'|format(var.ganancia_bruta_ant) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ganancia neta</td><td class="text-end">${{ '{:,.0f}'.format(anterior.ganancia_neta).replace(',','.') }}</td>
<td class="text-end small {% if var.ganancia_neta_ant and var.ganancia_neta_ant >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.ganancia_neta_ant is not none %}{{ '%+.1f'|format(var.ganancia_neta_ant) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ordenes</td><td class="text-end">{{ anterior.num_ordenes }}</td>
<td class="text-end small {% if var.num_ordenes_ant and var.num_ordenes_ant >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.num_ordenes_ant is not none %}{{ '%+.1f'|format(var.num_ordenes_ant) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Kilos vendidos</td><td class="text-end">{{ '%.2f'|format(kilos_ant) }} kg</td>
<td class="text-end small {% if var.kilos_ant and var.kilos_ant >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.kilos_ant is not none %}{{ '%+.1f'|format(var.kilos_ant) }}%{% else %}—{% endif %}
</td></tr>
</table>
</div></div>
</div>
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-calendar-event"></i> vs Mismo periodo año pasado</h6>
<table class="table table-sm mb-0">
<tr><td class="small">Facturado</td><td class="text-end">${{ '{:,.0f}'.format(anio_pas.facturado).replace(',','.') }}</td>
<td class="text-end small {% if var.facturado_ap and var.facturado_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.facturado_ap is not none %}{{ '%+.1f'|format(var.facturado_ap) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ganancia bruta</td><td class="text-end">${{ '{:,.0f}'.format(anio_pas.ganancia_bruta).replace(',','.') }}</td>
<td class="text-end small {% if var.ganancia_bruta_ap and var.ganancia_bruta_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.ganancia_bruta_ap is not none %}{{ '%+.1f'|format(var.ganancia_bruta_ap) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ganancia neta</td><td class="text-end">${{ '{:,.0f}'.format(anio_pas.ganancia_neta).replace(',','.') }}</td>
<td class="text-end small {% if var.ganancia_neta_ap and var.ganancia_neta_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.ganancia_neta_ap is not none %}{{ '%+.1f'|format(var.ganancia_neta_ap) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Ordenes</td><td class="text-end">{{ anio_pas.num_ordenes }}</td>
<td class="text-end small {% if var.num_ordenes_ap and var.num_ordenes_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.num_ordenes_ap is not none %}{{ '%+.1f'|format(var.num_ordenes_ap) }}%{% else %}—{% endif %}
</td></tr>
<tr><td class="small">Kilos vendidos</td><td class="text-end">{{ '%.2f'|format(kilos_ap) }} kg</td>
<td class="text-end small {% if var.kilos_ap and var.kilos_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.kilos_ap is not none %}{{ '%+.1f'|format(var.kilos_ap) }}%{% else %}—{% endif %}
</td></tr>
</table>
</div></div>
</div>
</div>

<!-- Kilos -->
<div class="card shadow-sm mb-3"><div class="card-body">
<h6 class="mb-2"><i class="bi bi-box-seam"></i> Kilos vendidos en {{ label_periodo|lower }}</h6>
<div class="fs-3 fw-semibold">{{ '%.2f'|format(kilos_act) }} kg</div>
<div class="text-muted small">Se calcula con el peso configurado en cada producto.</div>
</div></div>

<!-- Top rankings -->
<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-person-badge"></i> Top vendedores</h6>
{% if top_v %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Vendedor</th><th class="text-end">Ventas</th><th class="text-end">Ordenes</th></tr></thead>
<tbody>
{% for v in top_v %}
<tr><td>{{ loop.index }}</td><td>{{ v.nombre }}</td>
<td class="text-end">${{ '{:,.0f}'.format(v.total).replace(',','.') }}</td>
<td class="text-end text-muted">{{ v.cnt }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas en el periodo.</p>{% endif %}
</div></div>
</div>
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-broadcast"></i> Top canales</h6>
{% if top_c %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Canal</th><th class="text-end">Ventas</th><th class="text-end">Ordenes</th></tr></thead>
<tbody>
{% for c in top_c %}
<tr><td>{{ loop.index }}</td><td>{{ c.canal }}</td>
<td class="text-end">${{ '{:,.0f}'.format(c.total).replace(',','.') }}</td>
<td class="text-end text-muted">{{ c.cnt }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas en el periodo.</p>{% endif %}
</div></div>
</div>
</div>

<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-trophy"></i> Top productos</h6>
{% if top_p %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Producto</th><th class="text-end">Unidades</th><th class="text-end">Total $</th></tr></thead>
<tbody>
{% for p in top_p %}
<tr><td>{{ loop.index }}</td><td>{{ p.nombre }}{% if p.sku %} <small class="text-muted">({{ p.sku }})</small>{% endif %}</td>
<td class="text-end">{{ '%g'|format(p.cant) }}</td>
<td class="text-end">${{ '{:,.0f}'.format(p.total).replace(',','.') }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas en el periodo.</p>{% endif %}
</div></div>
</div>
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-geo-alt"></i> Top provincias</h6>
{% if top_pr %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Provincia</th><th class="text-end">Facturado</th><th class="text-end">Clientes</th></tr></thead>
<tbody>
{% for p in top_pr %}
<tr><td>{{ loop.index }}</td><td>{{ p.provincia }}</td>
<td class="text-end">${{ '{:,.0f}'.format(p.total).replace(',','.') }}</td>
<td class="text-end text-muted">{{ p.clientes }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas en el periodo.</p>{% endif %}
</div></div>
</div>
</div>
{% endblock %}
'''


DASHBOARD_HTML = r'''{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
<div>
<h3 class="mb-1" style="font-weight:700; letter-spacing:-.02em;">Hola, {{ current_user.nombre }} 👋</h3>
<div class="text-muted">{{ hoy.strftime('%d/%m/%Y') }} · {{ 'Administrador' if current_user.es_admin else 'Vendedor' }}</div>
</div>
</div>

<!-- Alertas clickeables -->
<div class="row g-2 mb-4">
{% if envios_pendientes > 0 %}
<div class="col-md-6">
<a href="{{ url_for('ventas_lista', estado='pagado_sin_enviar') }}" class="text-decoration-none">
<div class="alert alert-warning d-flex align-items-center mb-0" style="border-left:4px solid #f59e0b; border-radius:10px;">
<i class="bi bi-truck fs-4 me-3"></i>
<div>
<div class="fw-semibold text-dark">{{ envios_pendientes }} envio{{ 's' if envios_pendientes != 1 else '' }} pendiente{{ 's' if envios_pendientes != 1 else '' }}</div>
<div class="small text-muted">Ordenes cobradas esperando despacho</div>
</div>
<i class="bi bi-chevron-right ms-auto text-muted"></i>
</div>
</a>
</div>
{% endif %}
{% if ordenes_por_cobrar > 0 %}
<div class="col-md-6">
<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="text-decoration-none">
<div class="alert alert-info d-flex align-items-center mb-0" style="border-left:4px solid #06b6d4; border-radius:10px;">
<i class="bi bi-cash-coin fs-4 me-3"></i>
<div>
<div class="fw-semibold text-dark">{{ ordenes_por_cobrar }} orden{{ 'es' if ordenes_por_cobrar != 1 else '' }} por cobrar</div>
<div class="small text-muted">Saldo pendiente de acreditacion</div>
</div>
<i class="bi bi-chevron-right ms-auto text-muted"></i>
</div>
</a>
</div>
{% endif %}
</div>

<!-- KPIs grandes -->
<div class="row g-3 mb-4">
<div class="col-md-4">
<div class="card-kpi" style="background:linear-gradient(135deg,#eef2ff 0%,#ffffff 100%);">
<div class="kpi-icon kpi-icon-primary"><i class="bi bi-currency-dollar"></i></div>
<div class="kpi-label">Ventas de {{ mes_actual_label }}</div>
<div class="kpi-value">${{ '{:,.0f}'.format(actual.ventas).replace(',', '.') }}</div>
{% if variacion.ventas is not none %}
<div class="kpi-delta {% if variacion.ventas >= 0 %}text-success{% else %}text-danger{% endif %}">
<i class="bi bi-arrow-{% if variacion.ventas >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(variacion.ventas|abs) }}% vs {{ variacion.mes_anterior_label }}
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col-md-4">
<div class="card-kpi" style="background:linear-gradient(135deg,#fef2f2 0%,#ffffff 100%);">
<div class="kpi-icon kpi-icon-danger"><i class="bi bi-wallet2"></i></div>
<div class="kpi-label">Gastos de {{ mes_actual_label }}</div>
<div class="kpi-value">${{ '{:,.0f}'.format(gastos_mes).replace(',', '.') }}</div>
{% if var_gastos is not none %}
<div class="kpi-delta {% if var_gastos <= 0 %}text-success{% else %}text-danger{% endif %}">
<i class="bi bi-arrow-{% if var_gastos >= 0 %}up-right{% else %}down-right{% endif %}"></i>
{{ '%.1f'|format(var_gastos|abs) }}% vs {{ variacion.mes_anterior_label }}
</div>
{% else %}<div class="kpi-delta text-muted">Sin datos del mes anterior</div>{% endif %}
</div>
</div>
<div class="col-md-4">
<div class="card-kpi" style="background:linear-gradient(135deg,#ecfdf5 0%,#ffffff 100%);">
<div class="kpi-icon kpi-icon-success"><i class="bi bi-piggy-bank"></i></div>
<div class="kpi-label">Saldo actual (caja)</div>
<div class="kpi-value {% if saldo_actual >= 0 %}text-success{% else %}text-danger{% endif %}">
${{ '{:,.0f}'.format(saldo_actual).replace(',', '.') }}
</div>
<div class="kpi-delta text-muted"><i class="bi bi-info-circle"></i> Ingresos − gastos − compras</div>
</div>
</div>
</div>

{% if objetivos_dashboard is defined and objetivos_dashboard %}
<!-- Objetivos -->
<div class="card shadow-sm mb-4">
<div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-bullseye"></i> Objetivos de {{ objetivos_dashboard.mes_label }} {{ objetivos_dashboard.anio }}</h6>
<a href="{{ url_for('objetivos_lista') }}" class="btn btn-sm btn-outline-secondary">Gestionar</a>
</div>

{% if objetivos_dashboard.global.objetivo > 0 %}
<div class="mb-3">
<div class="d-flex justify-content-between mb-1">
<span class="small fw-semibold"><i class="bi bi-globe"></i> Objetivo global</span>
<span class="small">
${{ '{:,.0f}'.format(objetivos_dashboard.global.facturado).replace(',','.') }} / ${{ '{:,.0f}'.format(objetivos_dashboard.global.objetivo).replace(',','.') }}
· <strong>{{ '%.1f'|format(objetivos_dashboard.global.pct) }}%</strong>
</span>
</div>
<div class="progress-fz {% if objetivos_dashboard.global.pct >= 75 %}p-ok{% elif objetivos_dashboard.global.pct >= 50 %}p-warn{% else %}p-low{% endif %}" style="height:10px;">
<div class="progress-bar" style="width:{{ [objetivos_dashboard.global.pct, 100]|min }}%"></div>
</div>
</div>
{% endif %}

{% if objetivos_dashboard.vendedores %}
<div class="row g-2">
{% for v in objetivos_dashboard.vendedores %}
<div class="col-md-6">
<div class="border rounded p-2">
<div class="d-flex justify-content-between mb-1">
<span class="small fw-semibold">{{ v.nombre }}</span>
<span class="small">
{% if v.objetivo > 0 %}{{ '%.0f'|format(v.pct) }}%{% else %}<span class="text-muted">Sin objetivo</span>{% endif %}
</span>
</div>
{% if v.objetivo > 0 %}
<div class="progress-fz {% if v.pct >= 75 %}p-ok{% elif v.pct >= 50 %}p-warn{% else %}p-low{% endif %}" style="height:6px;">
<div class="progress-bar" style="width:{{ [v.pct, 100]|min }}%"></div>
</div>
<div class="small text-muted mt-1">${{ '{:,.0f}'.format(v.facturado).replace(',','.') }} / ${{ '{:,.0f}'.format(v.objetivo).replace(',','.') }}</div>
{% else %}
<div class="text-muted small">Sin objetivo asignado</div>
{% endif %}
</div>
</div>
{% endfor %}
</div>
{% endif %}
</div>
</div>
{% endif %}

<!-- Accesos directos -->
<div class="row g-3 mb-4">
<div class="col-md-4">
<a href="{{ url_for('ventas_nueva') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-primary mx-auto"><i class="bi bi-cart-plus"></i></div>
<div class="fw-semibold text-dark">Crear orden</div>
<div class="small text-muted">Nueva venta</div>
</div>
</a>
</div>
<div class="col-md-4">
<a href="{{ url_for('clientes_nuevo') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-success mx-auto"><i class="bi bi-person-plus"></i></div>
<div class="fw-semibold text-dark">Añadir cliente</div>
<div class="small text-muted">Nuevo registro</div>
</div>
</a>
</div>
{% if current_user.es_admin %}
<div class="col-md-4">
<a href="{{ url_for('productos_nuevo') }}" class="text-decoration-none">
<div class="card card-kpi text-center h-100" style="transition:transform .15s, box-shadow .15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 24px rgba(59,91,219,.12)'" onmouseout="this.style.transform=''; this.style.boxShadow=''">
<div class="kpi-icon kpi-icon-warning mx-auto"><i class="bi bi-box-seam"></i></div>
<div class="fw-semibold text-dark">Nuevo producto</div>
<div class="small text-muted">Agregar al catalogo</div>
</div>
</a>
</div>
{% endif %}
</div>

<!-- Gráficos -->
<div class="row g-3 mb-4">
<div class="col-md-7">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0">Ventas de los ultimos 6 meses</h6>
<span class="badge-soft-primary">$ total por mes</span>
</div>
<canvas id="chart-6meses" height="110"></canvas>
</div></div>
</div>
<div class="col-md-5">
<div class="card"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0">Ventas dia por dia · {{ mes_actual_label }}</h6>
</div>
<canvas id="chart-diario" height="150"></canvas>
</div></div>
</div>
</div>

<div class="row g-3 mb-4">
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Top 5 productos del mes</h6>
{% if top_prods %}
<canvas id="chart-productos" height="180"></canvas>
{% else %}
<p class="text-muted small mb-0">Sin ventas cobradas este mes aun.</p>
{% endif %}
</div></div>
</div>
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Top 5 provincias por facturacion</h6>
{% if top_provs %}
<canvas id="chart-provincias" height="180"></canvas>
{% else %}
<p class="text-muted small mb-0">Sin datos de provincias aun.</p>
{% endif %}
</div></div>
</div>
</div>

{% if current_user.es_admin %}
<div class="row g-3">
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Alertas</h6>
<a href="{{ url_for('ventas_lista', estado='pendiente_pago') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-exclamation-circle text-warning"></i> Ordenes pendientes de pago</span>
<strong>{{ pendientes }}</strong>
</a>
<a href="{{ url_for('ventas_lista') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-file-earmark-x text-secondary"></i> Pendientes de facturar</span>
<strong>{{ ordenes_pendientes_facturar }}</strong>
</a>
<a href="{{ url_for('productos_lista') }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none text-dark">
<span class="small"><i class="bi bi-exclamation-triangle text-danger"></i> Productos con bajo stock</span>
<strong>{{ bajo_stock }}</strong>
</a>
<a href="{{ url_for('clientes_lista') }}" class="d-flex justify-content-between align-items-center py-2 text-decoration-none text-dark">
<span class="small"><i class="bi bi-people text-primary"></i> Clientes activos</span>
<strong>{{ total_clientes }}</strong>
</a>
</div></div>
</div>
<div class="col-md-6">
<div class="card"><div class="card-body">
<h6 class="mb-3">Ultimos clientes agregados</h6>
{% for c in ultimos_clientes %}
<div class="d-flex justify-content-between align-items-center py-2 border-bottom">
<div>
<div class="small fw-semibold">{{ c.nombre_completo }}</div>
<div class="text-muted" style="font-size:.75rem;">{{ c.provincia or '—' }}</div>
</div>
<span class="text-muted" style="font-size:.75rem;">{{ c.creado[:10] if c.creado else '' }}</span>
</div>
{% else %}
<p class="text-muted small mb-0">Sin clientes cargados.</p>
{% endfor %}
</div></div>
</div>
</div>
{% endif %}

<script>
const primaryColor = '#3b5bdb';
const palette = ['#3b5bdb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

const data6meses = {
  labels: [{% for m in ultimos6 %}'{{ m.label }}'{% if not loop.last %},{% endif %}{% endfor %}],
  values: [{% for m in ultimos6 %}{{ m.total }}{% if not loop.last %},{% endif %}{% endfor %}]
};
new Chart(document.getElementById('chart-6meses'), {
  type: 'bar',
  data: { labels: data6meses.labels, datasets: [{ data: data6meses.values, backgroundColor: primaryColor, borderRadius: 8, borderSkipped: false, maxBarThickness: 40 }] },
  options: { responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => '$' + Number(c.raw).toLocaleString('es-AR') } } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k', color: '#9ca3af' } }, x: { grid: { display: false }, ticks: { color: '#6b7280' } } } }
});

const diarioLabels = [{% for d in por_dia %}{{ d.label }}{% if not loop.last %},{% endif %}{% endfor %}];
const diarioValues = [{% for d in por_dia %}{{ d.total }}{% if not loop.last %},{% endif %}{% endfor %}];
new Chart(document.getElementById('chart-diario'), {
  type: 'line',
  data: { labels: diarioLabels, datasets: [{ data: diarioValues, borderColor: primaryColor, backgroundColor: 'rgba(59,91,219,0.08)', borderWidth: 2, fill: true, tension: .35, pointRadius: 0, pointHoverRadius: 5 }] },
  options: { responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => 'Dia ' + c[0].label, label: (c) => '$' + Number(c.raw).toLocaleString('es-AR') } } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k', color: '#9ca3af' } }, x: { grid: { display: false }, ticks: { color: '#9ca3af', maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } } } }
});

{% if top_prods %}
new Chart(document.getElementById('chart-productos'), {
  type: 'bar',
  data: { labels: [{% for p in top_prods %}{{ p.nombre|tojson }}{% if not loop.last %},{% endif %}{% endfor %}], datasets: [{ data: [{% for p in top_prods %}{{ p.cantidad }}{% if not loop.last %},{% endif %}{% endfor %}], backgroundColor: palette.slice(0, {{ top_prods|length }}), borderRadius: 8, borderSkipped: false }] },
  options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => c.raw + ' unidades' } } }, scales: { x: { beginAtZero: true, grid: { color: '#f1f3f8' }, ticks: { color: '#9ca3af' } }, y: { grid: { display: false }, ticks: { color: '#4b5563' } } } }
});
{% endif %}

{% if top_provs %}
new Chart(document.getElementById('chart-provincias'), {
  type: 'doughnut',
  data: { labels: [{% for p in top_provs %}{{ p.provincia|tojson }}{% if not loop.last %},{% endif %}{% endfor %}], datasets: [{ data: [{% for p in top_provs %}{{ p.total }}{% if not loop.last %},{% endif %}{% endfor %}], backgroundColor: palette.slice(0, {{ top_provs|length }}), borderWidth: 0, spacing: 2 }] },
  options: { responsive: true, cutout: '62%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, padding: 12, font: { size: 12 }, color: '#4b5563' } }, tooltip: { callbacks: { label: (c) => c.label + ': $' + Number(c.raw).toLocaleString('es-AR') } } } }
});
{% endif %}
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app27; app27.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 27: Reportes financieros + Punto de equilibrio + Objetivos dashboard (F5.2b) ===")
    migrar()
    escribir('app27.py', APP27_PY)
    escribir('templates/reportes/index.html', REPORTES_INDEX)
    escribir('templates/dashboard.html', DASHBOARD_HTML)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app27.py)")


if __name__ == '__main__':
    main()