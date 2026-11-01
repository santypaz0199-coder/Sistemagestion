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
    print(f"[upgrade29] escrito: {relpath}")


APP29_PY = r'''
from datetime import date, timedelta
from flask import render_template, request
from flask_login import login_required
from app28 import app
from database import get_db
from app27 import (
    _periodo, _periodo_ant, _periodo_ap,
    _financiero, _kilos, _top_vendedores, _top_canales,
    _top_productos, _top_provincias, _var,
)


def _clientes_stats(conn, ini, fin):
    """Clientes nuevos vs recurrentes en el periodo."""
    ini_s, fin_s = ini.isoformat(), fin.isoformat()
    # Nuevos: creados en el periodo Y con al menos 1 compra cobrada
    nuevos = conn.execute("""
        SELECT COUNT(DISTINCT c.id) FROM clientes c
        JOIN ordenes_venta o ON o.cliente_id = c.id
        WHERE date(c.creado) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) BETWEEN ? AND ?
    """, (ini_s, fin_s, ini_s, fin_s)).fetchone()[0]

    # Recurrentes: existian antes del periodo Y compraron en el periodo
    recurrentes = conn.execute("""
        SELECT COUNT(DISTINCT c.id) FROM clientes c
        JOIN ordenes_venta o ON o.cliente_id = c.id
        WHERE date(c.creado) < ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) BETWEEN ? AND ?
    """, (ini_s, ini_s, fin_s)).fetchone()[0]

    # Facturado por tipo de cliente
    nuevo_fact = conn.execute("""
        SELECT COALESCE(SUM(o.total),0) FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE date(c.creado) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) BETWEEN ? AND ?
    """, (ini_s, fin_s, ini_s, fin_s)).fetchone()[0]

    recur_fact = conn.execute("""
        SELECT COALESCE(SUM(o.total),0) FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        WHERE date(c.creado) < ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) BETWEEN ? AND ?
    """, (ini_s, ini_s, fin_s)).fetchone()[0]

    return {
        'nuevos': nuevos, 'recurrentes': recurrentes,
        'nuevo_fact': nuevo_fact, 'recur_fact': recur_fact,
    }


def _minorista_mayorista(conn, ini, fin):
    """Facturado segun tag del cliente en la orden."""
    ini_s, fin_s = ini.isoformat(), fin.isoformat()

    # Segun el TIPO de la orden (minorista/mayorista)
    mi = conn.execute("""
        SELECT COALESCE(SUM(total),0), COUNT(*) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ?
        AND estado IN ('pagado_sin_enviar','pagado_enviado')
        AND tipo = 'minorista'
    """, (ini_s, fin_s)).fetchone()
    ma = conn.execute("""
        SELECT COALESCE(SUM(total),0), COUNT(*) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ?
        AND estado IN ('pagado_sin_enviar','pagado_enviado')
        AND tipo = 'mayorista'
    """, (ini_s, fin_s)).fetchone()

    return {
        'minorista_total': mi[0], 'minorista_count': mi[1],
        'mayorista_total': ma[0], 'mayorista_count': ma[1],
    }


def _kilos_desglosado(conn):
    """Kilos por dia, semana, mes, año."""
    hoy = date.today()
    ini_dia = hoy.isoformat()
    ini_semana = (hoy - timedelta(days=hoy.weekday())).isoformat()
    ini_mes = hoy.replace(day=1).isoformat()
    ini_anio = hoy.replace(month=1, day=1).isoformat()
    fin = hoy.isoformat()

    def kilos_between(ini, fin):
        return conn.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN p.peso_unidad = 'g' THEN (oi.cantidad * p.peso_valor) / 1000.0
                     ELSE oi.cantidad * COALESCE(p.peso_valor, 0) END
            ), 0) FROM orden_items oi
            JOIN ordenes_venta o ON o.id = oi.orden_id
            JOIN productos p ON p.id = oi.producto_id
            WHERE date(o.fecha) BETWEEN ? AND ?
            AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        """, (ini, fin)).fetchone()[0]

    return {
        'dia': kilos_between(ini_dia, fin),
        'semana': kilos_between(ini_semana, fin),
        'mes': kilos_between(ini_mes, fin),
        'anio': kilos_between(ini_anio, fin),
    }


def _top_clientes(conn, ini, fin, limit=10):
    return conn.execute("""
        SELECT c.id, c.nombre_completo, COALESCE(SUM(o.total),0) as total, COUNT(DISTINCT o.id) as cnt
        FROM clientes c
        JOIN ordenes_venta o ON o.cliente_id = c.id
        WHERE date(o.fecha) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
        GROUP BY c.id ORDER BY total DESC LIMIT ?
    """, (ini.isoformat(), fin.isoformat(), limit)).fetchall()


def reportes_v3():
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
    kilos_des = _kilos_desglosado(conn)

    clientes_stats = _clientes_stats(conn, ini, fin)
    mi_ma = _minorista_mayorista(conn, ini, fin)

    top_v = _top_vendedores(conn, ini, fin)
    top_c = _top_canales(conn, ini, fin)
    top_p = _top_productos(conn, ini, fin)
    top_pr = _top_provincias(conn, ini, fin)
    top_cli = _top_clientes(conn, ini, fin)

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

    labels = {'mes': 'Este mes', 'trimestre': 'Ultimos 90 dias', 'anio': 'Este año'}
    conn.close()
    return render_template('reportes/index.html',
        tipo=tipo, ini=ini, fin=fin,
        actual=actual, anterior=anterior, anio_pas=anio_pas,
        kilos_act=kilos_act, kilos_ant=kilos_ant, kilos_ap=kilos_ap,
        kilos_des=kilos_des,
        clientes_stats=clientes_stats, mi_ma=mi_ma,
        top_v=top_v, top_c=top_c, top_p=top_p, top_pr=top_pr, top_cli=top_cli,
        var=var, label_periodo=labels[tipo])


app.view_functions['reportes'] = reportes_v3


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
<option value="trimestre" {% if tipo=='trimestre' %}selected{% endif %}>Ultimos 90 dias</option>
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
<div class="kpi-label">Gastos fijos</div>
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
<div class="text-muted small">Cuanto necesitas facturar para cubrir gastos fijos con el margen de contribucion actual</div>
</div>
<span class="badge-soft-primary">Margen contribucion {{ '%.1f'|format(actual.margen_contrib_pct) }}%</span>
</div>
<div class="row g-3">
<div class="col-md-4"><div class="text-muted small mb-1">Facturado</div><div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }}</div></div>
<div class="col-md-4"><div class="text-muted small mb-1">Punto de equilibrio</div><div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(actual.punto_eq).replace(',','.') }}</div></div>
<div class="col-md-4"><div class="text-muted small mb-1">Estado</div>
{% if actual.facturado >= actual.punto_eq and actual.punto_eq > 0 %}
<div class="badge-soft-success"><i class="bi bi-check-circle-fill"></i> Por encima del punto</div>
{% elif actual.punto_eq > 0 %}
<div class="badge-soft-danger"><i class="bi bi-x-circle-fill"></i> Faltan ${{ '{:,.0f}'.format(actual.faltante_eq).replace(',','.') }}</div>
{% else %}
<div class="badge-soft-warning">Sin datos</div>
{% endif %}
</div>
</div>
</div>
</div>

<!-- Clientes nuevos vs recurrentes + Minorista vs Mayorista -->
<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-people"></i> Clientes nuevos vs recurrentes</h6>
<div class="row g-2 mb-3">
<div class="col-6">
<div class="border rounded p-2">
<div class="text-muted small">Nuevos</div>
<div class="fs-4 fw-semibold text-success">{{ clientes_stats.nuevos }}</div>
<div class="small text-muted">${{ '{:,.0f}'.format(clientes_stats.nuevo_fact).replace(',','.') }} facturado</div>
</div>
</div>
<div class="col-6">
<div class="border rounded p-2">
<div class="text-muted small">Recurrentes</div>
<div class="fs-4 fw-semibold text-primary">{{ clientes_stats.recurrentes }}</div>
<div class="small text-muted">${{ '{:,.0f}'.format(clientes_stats.recur_fact).replace(',','.') }} facturado</div>
</div>
</div>
</div>
{% set total_cli = clientes_stats.nuevos + clientes_stats.recurrentes %}
{% if total_cli > 0 %}
<div class="progress-fz" style="height:12px;">
<div class="progress-bar" style="width:{{ (clientes_stats.recurrentes / total_cli * 100)|round }}%; background:#3b5bdb;"></div>
</div>
<div class="d-flex justify-content-between small mt-1">
<span><span class="badge bg-success" style="font-size:.7rem;">&nbsp;</span> Nuevos {{ '%.0f'|format(clientes_stats.nuevos/total_cli*100) }}%</span>
<span><span class="badge bg-primary" style="font-size:.7rem;">&nbsp;</span> Recurrentes {{ '%.0f'|format(clientes_stats.recurrentes/total_cli*100) }}%</span>
</div>
{% else %}
<p class="text-muted small mb-0">Sin clientes con compras en el periodo.</p>
{% endif %}
</div></div>
</div>
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-tags"></i> Minorista vs Mayorista</h6>
{% set total_mm = mi_ma.minorista_total + mi_ma.mayorista_total %}
<div class="row g-2 mb-3">
<div class="col-6">
<div class="border rounded p-2" style="border-left:3px solid #06b6d4 !important;">
<div class="text-muted small">Minorista</div>
<div class="fs-4 fw-semibold">${{ '{:,.0f}'.format(mi_ma.minorista_total).replace(',','.') }}</div>
<div class="small text-muted">{{ mi_ma.minorista_count }} ordenes</div>
</div>
</div>
<div class="col-6">
<div class="border rounded p-2" style="border-left:3px solid #f59e0b !important;">
<div class="text-muted small">Mayorista</div>
<div class="fs-4 fw-semibold">${{ '{:,.0f}'.format(mi_ma.mayorista_total).replace(',','.') }}</div>
<div class="small text-muted">{{ mi_ma.mayorista_count }} ordenes</div>
</div>
</div>
</div>
{% if total_mm > 0 %}
<div class="progress-fz" style="height:12px;">
<div class="progress-bar" style="width:{{ (mi_ma.minorista_total / total_mm * 100)|round }}%; background:#06b6d4;"></div>
</div>
<div class="d-flex justify-content-between small mt-1">
<span><span class="badge" style="font-size:.7rem; background:#06b6d4;">&nbsp;</span> Minorista {{ '%.0f'|format(mi_ma.minorista_total/total_mm*100) }}%</span>
<span><span class="badge" style="font-size:.7rem; background:#f59e0b;">&nbsp;</span> Mayorista {{ '%.0f'|format(mi_ma.mayorista_total/total_mm*100) }}%</span>
</div>
{% else %}
<p class="text-muted small mb-0">Sin ventas en el periodo.</p>
{% endif %}
</div></div>
</div>
</div>

<!-- Kilos vendidos -->
<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-box-seam"></i> Kilos vendidos</h6>
<span class="badge-soft-primary">Total {{ label_periodo|lower }}: {{ '%.2f'|format(kilos_act) }} kg</span>
</div>
<div class="row row-cols-2 row-cols-md-4 g-2">
<div class="col">
<div class="border rounded p-2 text-center">
<div class="text-muted small">Hoy</div>
<div class="fs-5 fw-semibold">{{ '%.2f'|format(kilos_des.dia) }} kg</div>
</div>
</div>
<div class="col">
<div class="border rounded p-2 text-center">
<div class="text-muted small">Esta semana</div>
<div class="fs-5 fw-semibold">{{ '%.2f'|format(kilos_des.semana) }} kg</div>
</div>
</div>
<div class="col">
<div class="border rounded p-2 text-center">
<div class="text-muted small">Este mes</div>
<div class="fs-5 fw-semibold">{{ '%.2f'|format(kilos_des.mes) }} kg</div>
</div>
</div>
<div class="col">
<div class="border rounded p-2 text-center">
<div class="text-muted small">Este año</div>
<div class="fs-5 fw-semibold">{{ '%.2f'|format(kilos_des.anio) }} kg</div>
</div>
</div>
</div>
</div></div>

<!-- Comparativas -->
<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-arrow-left-right"></i> vs Mes anterior</h6>
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
<tr><td class="small">Kilos</td><td class="text-end">{{ '%.2f'|format(kilos_ant) }} kg</td>
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
<tr><td class="small">Kilos</td><td class="text-end">{{ '%.2f'|format(kilos_ap) }} kg</td>
<td class="text-end small {% if var.kilos_ap and var.kilos_ap >= 0 %}text-success{% else %}text-danger{% endif %}">
{% if var.kilos_ap is not none %}{{ '%+.1f'|format(var.kilos_ap) }}%{% else %}—{% endif %}
</td></tr>
</table>
</div></div>
</div>
</div>

<!-- Top vendedores + canales -->
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
{% else %}<p class="text-muted small mb-0">Sin ventas.</p>{% endif %}
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
{% else %}<p class="text-muted small mb-0">Sin ventas.</p>{% endif %}
</div></div>
</div>
</div>

<!-- Top productos + provincias -->
<div class="row g-3 mb-3">
<div class="col-md-6">
<div class="card shadow-sm h-100"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-trophy"></i> Top productos</h6>
{% if top_p %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Producto</th><th class="text-end">Unid.</th><th class="text-end">Total</th></tr></thead>
<tbody>
{% for p in top_p %}
<tr><td>{{ loop.index }}</td><td>{{ p.nombre }}{% if p.sku %} <small class="text-muted">({{ p.sku }})</small>{% endif %}</td>
<td class="text-end">{{ '%g'|format(p.cant) }}</td>
<td class="text-end">${{ '{:,.0f}'.format(p.total).replace(',','.') }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas.</p>{% endif %}
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
{% else %}<p class="text-muted small mb-0">Sin ventas.</p>{% endif %}
</div></div>
</div>
</div>

<!-- Top clientes -->
<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-people"></i> Top clientes por facturacion</h6>
<a href="{{ url_for('clientes_top', tab='facturacion', periodo='mes') }}" class="btn btn-sm btn-outline-secondary">Ver completo</a>
</div>
{% if top_cli %}
<table class="table table-sm mb-0">
<thead><tr><th>#</th><th>Cliente</th><th class="text-end">Facturado</th><th class="text-end">Ordenes</th></tr></thead>
<tbody>
{% for c in top_cli %}
<tr><td>{{ loop.index }}</td>
<td><a href="{{ url_for('clientes_editar', id=c.id) }}" class="text-decoration-none">{{ c.nombre_completo }}</a></td>
<td class="text-end">${{ '{:,.0f}'.format(c.total).replace(',','.') }}</td>
<td class="text-end text-muted">{{ c.cnt }}</td></tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">Sin ventas.</p>{% endif %}
</div></div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app29; app29.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 29: Reportes extendidos (F5.2c) ===")
    escribir('app29.py', APP29_PY)
    escribir('templates/reportes/index.html', REPORTES_INDEX)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app29.py)")


if __name__ == '__main__':
    main()