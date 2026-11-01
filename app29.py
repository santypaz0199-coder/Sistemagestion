
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
