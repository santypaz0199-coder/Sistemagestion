
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
