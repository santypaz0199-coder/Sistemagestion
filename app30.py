
import re, urllib.parse
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app29 import app
from database import get_db


def _limpiar_tel(t):
    if not t:
        return ''
    n = re.sub(r'\D', '', t)
    if n and not n.startswith('54'):
        n = '54' + n
    return n


def _rfm_color(dias):
    if dias is None:
        return 'gris'
    if dias <= 45:
        return 'verde-brillante'
    if dias <= 66:
        return 'verde'
    if dias <= 87:
        return 'amarillo'
    if dias <= 108:
        return 'naranja'
    return 'rojo'


def _clasificar(num_compras, total_compras, top_threshold):
    if num_compras == 0:
        return 'sin-compras'
    if total_compras >= top_threshold and top_threshold > 0:
        return 'top'
    if num_compras >= 3:
        return 'recurrente'
    return 'ocasional'


@app.route('/clientes')
@login_required
def clientes_lista_v4():
    q = request.args.get('q', '').strip()
    filtro_tipo = request.args.get('tipo', '')
    provincia_id = request.args.get('provincia_id', '').strip()
    localidad_id = request.args.get('localidad_id', '').strip()
    vendedor_filtro = request.args.get('vendedor', '').strip()
    filtro_color = request.args.get('color', '').strip()
    filtro_clase = request.args.get('clase', '').strip()

    conn = get_db()

    # Query base con metricas de RFM
    sql = """SELECT c.*,
             p.nombre as provincia_nombre,
             l.nombre as localidad_nombre,
             v.nombre as vendedor_nombre,
             COALESCE((
                 SELECT SUM(o.total) FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
             ), 0) as total_compras,
             COALESCE((
                 SELECT COUNT(DISTINCT o.id) FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                 AND date(o.fecha) >= date('now','-12 months')
             ), 0) as compras_12m,
             (
                 SELECT MAX(COALESCE(o.fecha_envio, o.fecha))
                 FROM ordenes_venta o
                 WHERE o.cliente_id = c.id AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
             ) as ultimo_despacho
             FROM clientes c
             LEFT JOIN provincias p ON p.id = c.provincia_id
             LEFT JOIN localidades l ON l.id = c.localidad_id
             LEFT JOIN usuarios v ON v.id = c.vendedor_id
             WHERE c.activo=1"""
    params = []

    if not current_user.es_admin:
        sql += " AND c.vendedor_id = ?"; params.append(current_user.id)
    elif vendedor_filtro:
        sql += " AND c.vendedor_id = ?"; params.append(int(vendedor_filtro))

    if q:
        sql += " AND (c.nombre_completo LIKE ? OR c.nro_doc LIKE ? OR c.email LIKE ? OR c.telefono LIKE ?)"
        params += [f'%{q}%'] * 4
    if filtro_tipo == 'minorista':
        sql += " AND c.es_minorista=1"
    elif filtro_tipo == 'mayorista':
        sql += " AND c.es_mayorista=1"
    if provincia_id:
        sql += " AND c.provincia_id=?"; params.append(int(provincia_id))
    if localidad_id:
        sql += " AND c.localidad_id=?"; params.append(int(localidad_id))
    sql += " ORDER BY c.nombre_completo"

    rows = conn.execute(sql, params).fetchall()

    # Calcular threshold top 20%
    totales = sorted([r['total_compras'] for r in rows if r['total_compras'] > 0], reverse=True)
    top_threshold = 0
    if totales:
        corte = max(1, int(len(totales) * 0.2))
        top_threshold = totales[corte - 1]

    hoy = date.today()
    clientes = []
    for r in rows:
        d = dict(r)
        # Color
        if r['ultimo_despacho']:
            try:
                fecha_ult = datetime.strptime(r['ultimo_despacho'][:10], '%Y-%m-%d').date()
                dias = (hoy - fecha_ult).days
            except Exception:
                dias = None
        else:
            dias = None
        d['dias_desde_ultimo'] = dias
        d['rfm_color'] = _rfm_color(dias)
        d['clasificacion'] = _clasificar(r['compras_12m'], r['total_compras'], top_threshold)
        # URLs
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

    # Filtros por color/clase (post-procesamiento)
    if filtro_color:
        clientes = [c for c in clientes if c['rfm_color'] == filtro_color]
    if filtro_clase:
        clientes = [c for c in clientes if c['clasificacion'] == filtro_clase]

    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    locs_rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    localidades_por_provincia = {}
    for r in locs_rows:
        localidades_por_provincia.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})

    vendedores = []
    if current_user.es_admin:
        vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()

    # Stats por color (del total sin filtros de color/clase aplicados)
    todos_rows = conn.execute(sql, params).fetchall()
    stats_color = {'verde-brillante': 0, 'verde': 0, 'amarillo': 0, 'naranja': 0, 'rojo': 0, 'gris': 0}
    stats_clase = {'top': 0, 'recurrente': 0, 'ocasional': 0, 'sin-compras': 0}
    for r in todos_rows:
        if r['ultimo_despacho']:
            try:
                fecha_ult = datetime.strptime(r['ultimo_despacho'][:10], '%Y-%m-%d').date()
                dias = (hoy - fecha_ult).days
            except Exception:
                dias = None
        else:
            dias = None
        stats_color[_rfm_color(dias)] += 1
        stats_clase[_clasificar(r['compras_12m'], r['total_compras'], top_threshold)] += 1

    stats = {
        'total': len(todos_rows),
        'minoristas': sum(1 for c in todos_rows if c['es_minorista']),
        'mayoristas': sum(1 for c in todos_rows if c['es_mayorista']),
        'por_color': stats_color,
        'por_clase': stats_clase,
    }
    conn.close()
    return render_template('clientes/lista.html', clientes=clientes, q=q,
                           filtro_tipo=filtro_tipo, provincia_id=provincia_id,
                           localidad_id=localidad_id, provincias=provincias,
                           localidades_por_provincia=localidades_por_provincia,
                           stats=stats, vendedores=vendedores, vendedor_filtro=vendedor_filtro,
                           filtro_color=filtro_color, filtro_clase=filtro_clase)


app.view_functions['clientes_lista'] = clientes_lista_v4


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
