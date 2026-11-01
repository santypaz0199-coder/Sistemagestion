
import re, urllib.parse
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app21 import app
from app import permiso_required
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


@app.route('/clientes')
@login_required
@permiso_required('clientes')
def clientes_lista_v2():
    q = request.args.get('q', '').strip()
    filtro_tipo = request.args.get('tipo', '')
    provincia_id = request.args.get('provincia_id', '').strip()
    localidad_id = request.args.get('localidad_id', '').strip()

    conn = get_db()
    sql = """SELECT c.*,
             p.nombre as provincia_nombre,
             l.nombre as localidad_nombre,
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
             WHERE c.activo=1"""
    params = []
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
                           stats=stats)


@app.route('/clientes/top')
@login_required
@permiso_required('clientes')
def clientes_top():
    tab = request.args.get('tab', 'facturacion')
    periodo = request.args.get('periodo', 'todo')
    conn = get_db()

    # Rango de fechas segun periodo
    hoy = date.today()
    if periodo == 'mes':
        ini = hoy.replace(day=1).isoformat()
    elif periodo == 'trimestre':
        ini = (hoy - timedelta(days=90)).isoformat()
    elif periodo == 'anio':
        ini = hoy.replace(month=1, day=1).isoformat()
    else:
        ini = '2000-01-01'
    fin = hoy.isoformat()

    if tab == 'facturacion':
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COALESCE(SUM(o.total),0) as metrica,
                   COUNT(DISTINCT o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Facturado'

    elif tab == 'ordenes':
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COUNT(o.id) as metrica,
                   COUNT(o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Ordenes'

    else:  # kilos
        ranking = conn.execute("""
            SELECT c.id, c.nombre_completo, c.telefono, c.email,
                   p.nombre as provincia_nombre,
                   COALESCE(SUM(
                       CASE WHEN prod.peso_unidad = 'g'
                            THEN (oi.cantidad * prod.peso_valor) / 1000.0
                            ELSE oi.cantidad * COALESCE(prod.peso_valor, 0)
                       END
                   ), 0) as metrica,
                   COUNT(DISTINCT o.id) as num_ordenes
            FROM clientes c
            LEFT JOIN provincias p ON p.id = c.provincia_id
            LEFT JOIN ordenes_venta o ON o.cliente_id = c.id
                AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                AND date(o.fecha) BETWEEN ? AND ?
            LEFT JOIN orden_items oi ON oi.orden_id = o.id
            LEFT JOIN productos prod ON prod.id = oi.producto_id
            WHERE c.activo = 1
            GROUP BY c.id
            HAVING metrica > 0
            ORDER BY metrica DESC
            LIMIT 20
        """, (ini, fin)).fetchall()
        metrica_label = 'Kilos'

    conn.close()
    return render_template('clientes/top.html', ranking=ranking, tab=tab,
                           periodo=periodo, metrica_label=metrica_label,
                           ini=ini, fin=fin)


app.view_functions['clientes_lista'] = clientes_lista_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
