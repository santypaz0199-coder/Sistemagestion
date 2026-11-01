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
    print(f"[upgrade61] escrito: {relpath}")


APP61_PY = r'''
from datetime import date
from flask import render_template, request
from flask_login import login_required
from app57 import app
from app import admin_required
from database import get_db


@app.route('/reportes/pdf')
@login_required
@admin_required
def reportes_pdf():
    from app27 import (_financiero, _kilos, _top_vendedores, _top_canales,
                       _top_productos, _top_provincias, _periodo, _periodo_ant, _periodo_ap, _var)
    from app29 import (_clientes_stats, _minorista_mayorista,
                       _kilos_desglosado, _top_clientes)

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
    kilos_des = _kilos_desglosado(conn)

    clientes_stats = _clientes_stats(conn, ini, fin)
    mi_ma = _minorista_mayorista(conn, ini, fin)

    top_v = _top_vendedores(conn, ini, fin)
    top_c = _top_canales(conn, ini, fin)
    top_p = _top_productos(conn, ini, fin)
    top_pr = _top_provincias(conn, ini, fin)
    top_cli = _top_clientes(conn, ini, fin)

    # Cumplimiento por canal
    ini_s, fin_s = ini.isoformat(), fin.isoformat()
    canales = conn.execute("SELECT id, nombre FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    cumplimiento_canales = []
    for c in canales:
        obj_row = conn.execute("SELECT monto FROM objetivos_canal WHERE canal_id=? AND mes=? AND anio=?",
                               (c['id'], ini.month, ini.year)).fetchone()
        objetivo = obj_row['monto'] if obj_row else 0
        fact = conn.execute("""SELECT COALESCE(SUM(total),0) FROM ordenes_venta
            WHERE date(fecha) BETWEEN ? AND ? AND canal_id=?
            AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (ini_s, fin_s, c['id'])).fetchone()[0]
        cumplimiento_canales.append({
            'nombre': c['nombre'], 'objetivo': objetivo, 'facturado': fact,
            'pct': (fact/objetivo*100) if objetivo > 0 else 0,
            'gap': max(0, objetivo - fact),
        })

    # Gastos fijos del periodo
    gastos_fijos_periodo = conn.execute(
        "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE es_fijo = 1 AND date(fecha) BETWEEN ? AND ?",
        (ini_s, fin_s)).fetchone()[0]
    gastos_fijos_detalle = conn.execute("""
        SELECT g.monto, g.descripcion, g.fecha, cg.nombre as categoria
        FROM gastos g LEFT JOIN categorias_gastos cg ON cg.id = g.categoria_id
        WHERE g.es_fijo = 1 AND date(g.fecha) BETWEEN ? AND ?
        ORDER BY g.fecha
    """, (ini_s, fin_s)).fetchall()

    # Punto de eq sobre fijos
    margen_contrib = actual['margen_contrib_pct']
    punto_eq_fijos = (gastos_fijos_periodo / (margen_contrib / 100)) if margen_contrib > 0 else 0

    # Config empresa
    empresa = {}
    for k in ['empresa_nombre', 'empresa_telefono', 'empresa_email', 'empresa_web', 'empresa_logo']:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        empresa[k] = row['valor'] if row and row['valor'] else ''
    if not empresa['empresa_nombre']:
        empresa['empresa_nombre'] = 'Familia Zaragoza ®'

    # Objetivo global del mes
    obj_global_row = conn.execute("SELECT monto FROM objetivos WHERE usuario_id IS NULL AND mes=? AND anio=?",
                                   (ini.month, ini.year)).fetchone()
    objetivo_global = obj_global_row['monto'] if obj_global_row else 0

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
    }

    labels = {'mes': 'Mensual', 'trimestre': 'Trimestral (90 dias)', 'anio': 'Anual'}
    conn.close()

    return render_template('reportes/pdf.html',
        tipo=tipo, ini=ini, fin=fin, label_tipo=labels[tipo],
        actual=actual, anterior=anterior, anio_pas=anio_pas,
        kilos_act=kilos_act, kilos_ant=kilos_ant, kilos_des=kilos_des,
        clientes_stats=clientes_stats, mi_ma=mi_ma,
        top_v=top_v, top_c=top_c, top_p=top_p, top_pr=top_pr, top_cli=top_cli,
        cumplimiento_canales=cumplimiento_canales,
        gastos_fijos_periodo=gastos_fijos_periodo,
        gastos_fijos_detalle=gastos_fijos_detalle,
        punto_eq_fijos=punto_eq_fijos,
        objetivo_global=objetivo_global,
        empresa=empresa, var=var,
        generado=date.today(),
    )


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


PDF_HTML = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Reporte {{ label_tipo }} - {{ ini.strftime('%m/%Y') }} - {{ empresa.empresa_nombre }}</title>
<style>
@page { size: A4; margin: 15mm; }
* { box-sizing: border-box; }
body {
  font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
  color: #1f2937;
  margin: 0;
  padding: 30px;
  font-size: 12px;
  line-height: 1.5;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}

/* Botones flotantes */
.acciones {
  position: fixed; top: 20px; right: 20px;
  display: flex; gap: 8px; z-index: 100;
}
.btn-accion {
  padding: 10px 18px; border-radius: 8px; border: none;
  font-size: 13px; font-weight: 600; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
.btn-imprimir { background: #3b5bdb; color: #fff; }
.btn-cerrar { background: #e5e7eb; color: #1f2937; }
.btn-accion:hover { opacity: .9; }

/* Encabezado */
.header {
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 3px solid #1f2937;
  padding-bottom: 15px; margin-bottom: 25px;
}
.header .empresa img { max-height: 50px; margin-bottom: 8px; }
.header .empresa h1 { margin: 0 0 4px 0; font-size: 22px; letter-spacing: -.02em; }
.header .empresa .info { font-size: 10px; color: #6b7280; line-height: 1.6; }
.header .reporte-info { text-align: right; }
.header .reporte-info h2 { margin: 0 0 4px 0; font-size: 18px; font-weight: 700; }
.header .reporte-info .periodo { font-size: 13px; color: #4b5563; font-weight: 500; }
.header .reporte-info .generado { font-size: 10px; color: #9ca3af; margin-top: 4px; }

/* Secciones */
.section { margin-bottom: 22px; page-break-inside: avoid; }
.section h3 {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 6px;
  margin-bottom: 12px;
  font-weight: 700;
}

/* KPIs grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.kpi-grid.kpi-grid-3 { grid-template-columns: repeat(3, 1fr); }
.kpi-grid.kpi-grid-2 { grid-template-columns: repeat(2, 1fr); }

.kpi-box {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fafbfd;
}
.kpi-box .label { font-size: 9px; text-transform: uppercase; letter-spacing: .04em; color: #6b7280; font-weight: 600; margin-bottom: 3px; }
.kpi-box .value { font-size: 17px; font-weight: 700; letter-spacing: -.02em; }
.kpi-box .sub { font-size: 9px; color: #9ca3af; margin-top: 3px; }
.kpi-box.green .value { color: #059669; }
.kpi-box.red .value { color: #dc2626; }
.kpi-box.blue .value { color: #2563eb; }
.kpi-box.amber .value { color: #d97706; }
.kpi-box.violet .value { color: #7c3aed; }

/* Tablas */
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
  font-size: 11px;
}
table thead th {
  background: #f3f4f6;
  text-align: left;
  padding: 7px 10px;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 700;
}
table tbody td {
  padding: 7px 10px;
  border-bottom: 1px solid #f3f4f6;
}
table tbody tr:last-child td { border-bottom: none; }
table .num { text-align: right; }
table .center { text-align: center; }
table tfoot td {
  padding: 8px 10px;
  font-weight: 700;
  border-top: 2px solid #e5e7eb;
  font-size: 11px;
}

/* Barra comparativa */
.compare-bar {
  height: 6px;
  background: #e5e7eb;
  border-radius: 20px;
  overflow: hidden;
  margin: 4px 0;
}
.compare-bar .fill { height: 100%; border-radius: 20px; }
.fill-green { background: #10b981; }
.fill-blue { background: #3b5bdb; }
.fill-amber { background: #f59e0b; }

/* Badge */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
}
.badge-green { background: #d1fae5; color: #065f46; }
.badge-red { background: #fee2e2; color: #991b1b; }
.badge-amber { background: #fef3c7; color: #92400e; }
.badge-blue { background: #dbeafe; color: #1e40af; }
.badge-gray { background: #f3f4f6; color: #4b5563; }

/* Footer */
.footer {
  margin-top: 30px;
  padding-top: 15px;
  border-top: 1px solid #e5e7eb;
  text-align: center;
  font-size: 9px;
  color: #9ca3af;
}

/* Ocultar en impresión */
@media print {
  body { padding: 0; font-size: 10.5px; }
  .acciones { display: none; }
  .section { page-break-inside: avoid; }
  .kpi-grid { page-break-inside: avoid; }
}
</style>
</head>
<body>

<div class="acciones">
<button class="btn-accion btn-imprimir" onclick="window.print()">🖨️ Imprimir / Guardar PDF</button>
<button class="btn-accion btn-cerrar" onclick="window.close()">✕ Cerrar</button>
</div>

<!-- HEADER -->
<div class="header">
<div class="empresa">
{% if empresa.empresa_logo %}
<img src="{{ url_for('ver_logo_empresa') }}" alt="{{ empresa.empresa_nombre }}">
{% endif %}
<h1>{{ empresa.empresa_nombre }}</h1>
<div class="info">
{% if empresa.empresa_telefono %}{{ empresa.empresa_telefono }}<br>{% endif %}
{% if empresa.empresa_email %}{{ empresa.empresa_email }}<br>{% endif %}
{% if empresa.empresa_web %}{{ empresa.empresa_web }}{% endif %}
</div>
</div>
<div class="reporte-info">
<h2>Reporte {{ label_tipo }}</h2>
<div class="periodo">{{ ini.strftime('%d/%m/%Y') }} — {{ fin.strftime('%d/%m/%Y') }}</div>
<div class="generado">Generado el {{ generado.strftime('%d/%m/%Y a las %H:%M') }}</div>
</div>
</div>

<!-- RESUMEN FINANCIERO -->
<div class="section">
<h3>Resumen financiero</h3>
<div class="kpi-grid">
<div class="kpi-box blue">
<div class="label">Facturado</div>
<div class="value">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }}</div>
<div class="sub">{{ actual.num_ordenes }} ordenes · ticket prom. ${{ '{:,.0f}'.format(actual.ticket_prom).replace(',','.') }}</div>
</div>
<div class="kpi-box amber">
<div class="label">CMV (costo mercaderia)</div>
<div class="value">${{ '{:,.0f}'.format(actual.cmv).replace(',','.') }}</div>
<div class="sub">{{ '%.1f'|format((actual.cmv/actual.facturado*100) if actual.facturado > 0 else 0) }}% del facturado</div>
</div>
<div class="kpi-box {% if actual.ganancia_bruta >= 0 %}green{% else %}red{% endif %}">
<div class="label">Ganancia bruta</div>
<div class="value">${{ '{:,.0f}'.format(actual.ganancia_bruta).replace(',','.') }}</div>
<div class="sub">Margen: {{ '%.1f'|format(actual.margen_bruto_pct) }}%</div>
</div>
<div class="kpi-box {% if actual.ganancia_neta >= 0 %}green{% else %}red{% endif %}">
<div class="label">Ganancia neta</div>
<div class="value">${{ '{:,.0f}'.format(actual.ganancia_neta).replace(',','.') }}</div>
<div class="sub">Margen neto: {{ '%.1f'|format(actual.margen_neto_pct) }}%</div>
</div>
</div>
</div>

<!-- EGRESOS Y PUNTO DE EQUILIBRIO -->
<div class="section">
<h3>Egresos y punto de equilibrio</h3>
<div class="kpi-grid">
<div class="kpi-box red">
<div class="label">Gastos fijos</div>
<div class="value">${{ '{:,.0f}'.format(actual.gastos).replace(',','.') }}</div>
<div class="sub">{{ gastos_fijos_detalle|length }} gastos registrados</div>
</div>
<div class="kpi-box red">
<div class="label">Insumos (variables)</div>
<div class="value">${{ '{:,.0f}'.format(actual.insumos).replace(',','.') }}</div>
</div>
<div class="kpi-box violet">
<div class="label">Punto de equilibrio</div>
<div class="value">${{ '{:,.0f}'.format(punto_eq_fijos).replace(',','.') }}</div>
<div class="sub">Con margen contrib. {{ '%.1f'|format(actual.margen_contrib_pct) }}%</div>
</div>
<div class="kpi-box {% if actual.facturado >= punto_eq_fijos and punto_eq_fijos > 0 %}green{% else %}red{% endif %}">
<div class="label">Estado</div>
<div class="value" style="font-size:13px;">
{% if actual.facturado >= punto_eq_fijos and punto_eq_fijos > 0 %}
<span class="badge badge-green">Por encima</span>
{% elif punto_eq_fijos > 0 %}
<span class="badge badge-red">Faltan ${{ '{:,.0f}'.format(punto_eq_fijos - actual.facturado).replace(',','.') }}</span>
{% else %}
<span class="badge badge-gray">Sin datos</span>
{% endif %}
</div>
</div>
</div>
</div>

<!-- OBJETIVO GLOBAL -->
{% if objetivo_global > 0 %}
<div class="section">
<h3>Objetivo mensual</h3>
<div class="kpi-grid kpi-grid-2">
<div class="kpi-box">
<div class="label">Objetivo del mes</div>
<div class="value">${{ '{:,.0f}'.format(objetivo_global).replace(',','.') }}</div>
</div>
<div class="kpi-box {% if actual.facturado >= objetivo_global %}green{% else %}amber{% endif %}">
<div class="label">Cumplimiento</div>
<div class="value">{{ '%.1f'|format((actual.facturado/objetivo_global*100) if objetivo_global > 0 else 0) }}%</div>
<div class="compare-bar">
<div class="fill fill-blue" style="width:{{ [actual.facturado/objetivo_global*100, 100]|min }}%"></div>
</div>
<div class="sub">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }} facturado</div>
</div>
</div>
</div>
{% endif %}

<!-- KILOS VENDIDOS -->
<div class="section">
<h3>Kilos vendidos</h3>
<div class="kpi-grid">
<div class="kpi-box">
<div class="label">Hoy</div>
<div class="value">{{ '%.2f'|format(kilos_des.dia) }} kg</div>
</div>
<div class="kpi-box">
<div class="label">Esta semana</div>
<div class="value">{{ '%.2f'|format(kilos_des.semana) }} kg</div>
</div>
<div class="kpi-box">
<div class="label">Este mes</div>
<div class="value">{{ '%.2f'|format(kilos_des.mes) }} kg</div>
</div>
<div class="kpi-box blue">
<div class="label">Total periodo</div>
<div class="value">{{ '%.2f'|format(kilos_act) }} kg</div>
</div>
</div>
</div>

<!-- CLIENTES -->
<div class="section">
<h3>Clientes</h3>
<div class="kpi-grid kpi-grid-4">
<div class="kpi-box">
<div class="label">Nuevos</div>
<div class="value">{{ clientes_stats.nuevos }}</div>
<div class="sub">${{ '{:,.0f}'.format(clientes_stats.nuevo_fact).replace(',','.') }} facturado</div>
</div>
<div class="kpi-box blue">
<div class="label">Recurrentes</div>
<div class="value">{{ clientes_stats.recurrentes }}</div>
<div class="sub">${{ '{:,.0f}'.format(clientes_stats.recur_fact).replace(',','.') }} facturado</div>
</div>
<div class="kpi-box">
<div class="label">Minorista</div>
<div class="value">${{ '{:,.0f}'.format(mi_ma.minorista_total).replace(',','.') }}</div>
<div class="sub">{{ mi_ma.minorista_count }} ordenes</div>
</div>
<div class="kpi-box amber">
<div class="label">Mayorista</div>
<div class="value">${{ '{:,.0f}'.format(mi_ma.mayorista_total).replace(',','.') }}</div>
<div class="sub">{{ mi_ma.mayorista_count }} ordenes</div>
</div>
</div>
</div>

<!-- COMPARATIVAS -->
<div class="section">
<h3>Comparativas</h3>
<table>
<thead>
<tr>
<th>Metrica</th>
<th class="num">Actual</th>
<th class="num">Mes anterior</th>
<th class="num">Variacion</th>
<th class="num">Año pasado</th>
<th class="num">Variacion</th>
</tr>
</thead>
<tbody>
<tr>
<td>Facturado</td>
<td class="num">${{ '{:,.0f}'.format(actual.facturado).replace(',','.') }}</td>
<td class="num">${{ '{:,.0f}'.format(anterior.facturado).replace(',','.') }}</td>
<td class="num">{% if var.facturado_ant is not none %}<span class="badge {% if var.facturado_ant >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.facturado_ant) }}%</span>{% else %}—{% endif %}</td>
<td class="num">${{ '{:,.0f}'.format(anio_pas.facturado).replace(',','.') }}</td>
<td class="num">{% if var.facturado_ap is not none %}<span class="badge {% if var.facturado_ap >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.facturado_ap) }}%</span>{% else %}—{% endif %}</td>
</tr>
<tr>
<td>Ganancia bruta</td>
<td class="num">${{ '{:,.0f}'.format(actual.ganancia_bruta).replace(',','.') }}</td>
<td class="num">${{ '{:,.0f}'.format(anterior.ganancia_bruta).replace(',','.') }}</td>
<td class="num">{% if var.ganancia_bruta_ant is not none %}<span class="badge {% if var.ganancia_bruta_ant >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.ganancia_bruta_ant) }}%</span>{% else %}—{% endif %}</td>
<td class="num">${{ '{:,.0f}'.format(anio_pas.ganancia_bruta).replace(',','.') }}</td>
<td class="num">{% if var.ganancia_bruta_ap is not none %}<span class="badge {% if var.ganancia_bruta_ap >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.ganancia_bruta_ap) }}%</span>{% else %}—{% endif %}</td>
</tr>
<tr>
<td>Ganancia neta</td>
<td class="num">${{ '{:,.0f}'.format(actual.ganancia_neta).replace(',','.') }}</td>
<td class="num">${{ '{:,.0f}'.format(anterior.ganancia_neta).replace(',','.') }}</td>
<td class="num">{% if var.ganancia_neta_ant is not none %}<span class="badge {% if var.ganancia_neta_ant >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.ganancia_neta_ant) }}%</span>{% else %}—{% endif %}</td>
<td class="num">${{ '{:,.0f}'.format(anio_pas.ganancia_neta).replace(',','.') }}</td>
<td class="num">{% if var.ganancia_neta_ap is not none %}<span class="badge {% if var.ganancia_neta_ap >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.ganancia_neta_ap) }}%</span>{% else %}—{% endif %}</td>
</tr>
<tr>
<td>Ordenes</td>
<td class="num">{{ actual.num_ordenes }}</td>
<td class="num">{{ anterior.num_ordenes }}</td>
<td class="num">{% if var.num_ordenes_ant is not none %}<span class="badge {% if var.num_ordenes_ant >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.num_ordenes_ant) }}%</span>{% else %}—{% endif %}</td>
<td class="num">{{ anio_pas.num_ordenes }}</td>
<td class="num">{% if var.num_ordenes_ap is not none %}<span class="badge {% if var.num_ordenes_ap >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.num_ordenes_ap) }}%</span>{% else %}—{% endif %}</td>
</tr>
<tr>
<td>Kilos vendidos</td>
<td class="num">{{ '%.2f'|format(kilos_act) }} kg</td>
<td class="num">{{ '%.2f'|format(kilos_ant) }} kg</td>
<td class="num">{% if var.kilos_ant is not none %}<span class="badge {% if var.kilos_ant >= 0 %}badge-green{% else %}badge-red{% endif %}">{{ '%+.1f'|format(var.kilos_ant) }}%</span>{% else %}—{% endif %}</td>
<td class="num">—</td>
<td class="num">—</td>
</tr>
</tbody>
</table>
</div>

<!-- CUMPLIMIENTO POR CANAL -->
{% if cumplimiento_canales %}
<div class="section">
<h3>Cumplimiento por canal</h3>
<table>
<thead>
<tr>
<th>Canal</th>
<th class="num">Objetivo</th>
<th class="num">Facturado</th>
<th class="num">Cumplimiento</th>
<th class="num">Falta</th>
</tr>
</thead>
<tbody>
{% for c in cumplimiento_canales %}
<tr>
<td>{{ c.nombre }}</td>
<td class="num">{% if c.objetivo > 0 %}${{ '{:,.0f}'.format(c.objetivo).replace(',','.') }}{% else %}—{% endif %}</td>
<td class="num">${{ '{:,.0f}'.format(c.facturado).replace(',','.') }}</td>
<td class="num">{% if c.objetivo > 0 %}<span class="badge {% if c.pct >= 100 %}badge-green{% elif c.pct >= 75 %}badge-amber{% else %}badge-red{% endif %}">{{ '%.0f'|format(c.pct) }}%</span>{% else %}—{% endif %}</td>
<td class="num">{% if c.gap > 0 %}${{ '{:,.0f}'.format(c.gap).replace(',','.') }}{% else %}—{% endif %}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
{% endif %}

<!-- TOP VENDEDORES Y CANALES -->
<div class="section">
<h3>Top vendedores y canales</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
<div>
<table>
<thead><tr><th>#</th><th>Vendedor</th><th class="num">Ventas</th><th class="num">Ordenes</th></tr></thead>
<tbody>
{% for v in top_v[:5] %}
<tr><td>{{ loop.index }}</td><td>{{ v.nombre }}</td><td class="num">${{ '{:,.0f}'.format(v.total).replace(',','.') }}</td><td class="num">{{ v.cnt }}</td></tr>
{% endfor %}
{% if not top_v %}
<tr><td colspan="4" style="text-align:center;color:#9ca3af;padding:15px;">Sin datos</td></tr>
{% endif %}
</tbody>
</table>
</div>
<div>
<table>
<thead><tr><th>#</th><th>Canal</th><th class="num">Ventas</th><th class="num">Ordenes</th></tr></thead>
<tbody>
{% for c in top_c[:5] %}
<tr><td>{{ loop.index }}</td><td>{{ c.canal }}</td><td class="num">${{ '{:,.0f}'.format(c.total).replace(',','.') }}</td><td class="num">{{ c.cnt }}</td></tr>
{% endfor %}
{% if not top_c %}
<tr><td colspan="4" style="text-align:center;color:#9ca3af;padding:15px;">Sin datos</td></tr>
{% endif %}
</tbody>
</table>
</div>
</div>
</div>

<!-- TOP PRODUCTOS Y PROVINCIAS -->
<div class="section">
<h3>Top productos y provincias</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
<div>
<table>
<thead><tr><th>#</th><th>Producto</th><th class="num">Unidades</th><th class="num">Total</th></tr></thead>
<tbody>
{% for p in top_p[:5] %}
<tr><td>{{ loop.index }}</td><td>{{ p.nombre }}</td><td class="num">{{ '%g'|format(p.cant) }}</td><td class="num">${{ '{:,.0f}'.format(p.total).replace(',','.') }}</td></tr>
{% endfor %}
{% if not top_p %}
<tr><td colspan="4" style="text-align:center;color:#9ca3af;padding:15px;">Sin datos</td></tr>
{% endif %}
</tbody>
</table>
</div>
<div>
<table>
<thead><tr><th>#</th><th>Provincia</th><th class="num">Facturado</th><th class="num">Clientes</th></tr></thead>
<tbody>
{% for p in top_pr[:5] %}
<tr><td>{{ loop.index }}</td><td>{{ p.provincia }}</td><td class="num">${{ '{:,.0f}'.format(p.total).replace(',','.') }}</td><td class="num">{{ p.clientes }}</td></tr>
{% endfor %}
{% if not top_pr %}
<tr><td colspan="4" style="text-align:center;color:#9ca3af;padding:15px;">Sin datos</td></tr>
{% endif %}
</tbody>
</table>
</div>
</div>
</div>

<!-- TOP CLIENTES -->
{% if top_cli %}
<div class="section">
<h3>Top clientes</h3>
<table>
<thead><tr><th>#</th><th>Cliente</th><th class="num">Facturado</th><th class="num">Ordenes</th></tr></thead>
<tbody>
{% for c in top_cli[:10] %}
<tr><td>{{ loop.index }}</td><td>{{ c.nombre_completo }}</td><td class="num">${{ '{:,.0f}'.format(c.total).replace(',','.') }}</td><td class="num">{{ c.cnt }}</td></tr>
{% endfor %}
</tbody>
</table>
</div>
{% endif %}

<!-- DETALLE GASTOS FIJOS -->
{% if gastos_fijos_detalle %}
<div class="section">
<h3>Detalle de gastos fijos</h3>
<table>
<thead><tr><th>Fecha</th><th>Descripcion</th><th>Categoria</th><th class="num">Monto</th></tr></thead>
<tbody>
{% for g in gastos_fijos_detalle %}
<tr>
<td style="font-size:10px;color:#6b7280;">{{ g.fecha }}</td>
<td>{{ g.descripcion }}</td>
<td style="font-size:10px;color:#6b7280;">{{ g.categoria or '—' }}</td>
<td class="num">${{ '{:,.0f}'.format(g.monto).replace(',','.') }}</td>
</tr>
{% endfor %}
</tbody>
<tfoot>
<tr>
<td colspan="3" style="text-align:right;">Total gastos fijos</td>
<td class="num">${{ '{:,.0f}'.format(gastos_fijos_periodo).replace(',','.') }}</td>
</tr>
</tfoot>
</table>
</div>
{% endif %}

<!-- FOOTER -->
<div class="footer">
{{ empresa.empresa_nombre }} · Reporte {{ label_tipo }} · {{ ini.strftime('%d/%m/%Y') }} — {{ fin.strftime('%d/%m/%Y') }}<br>
Documento generado automaticamente por el Sistema de Gestion Interno
</div>

</body>
</html>
'''


def patch_reportes_boton():
    """Agrega el boton 'Descargar PDF' en la pagina de reportes."""
    ruta = os.path.join(BASE, 'templates', 'reportes', 'index.html')
    if not os.path.exists(ruta):
        print("[upgrade61] no existe reportes/index.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'reportes_pdf' in contenido:
        print("[upgrade61] reportes ya tiene boton PDF")
        return

    # Buscar donde estan los botones existentes (Cierres)
    buscar = '<a href="{{ url_for(\'reportes_cierres\') }}" class="btn btn-outline-secondary btn-sm"><i class="bi bi-archive"></i> Cierres</a>'

    if buscar not in contenido:
        print("[upgrade61] ADVERTENCIA: no se encontro el boton Cierres"); return

    nuevo = ('<a href="{{ url_for(\'reportes_pdf\', tipo=tipo) }}" target="_blank" class="btn btn-dark btn-sm" title="Descargar reporte en PDF">'
             '<i class="bi bi-file-earmark-pdf"></i> Descargar PDF</a>\n' + buscar)

    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade61] boton Descargar PDF agregado a reportes")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 61: Reportes PDF (U61) ===")
    escribir('app61.py', APP61_PY)
    escribir('templates/reportes/pdf.html', PDF_HTML)
    patch_reportes_boton()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()