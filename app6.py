
from datetime import date, timedelta
from flask import render_template
from flask_login import login_required, current_user
from app5 import app
from database import get_db


MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def _mes_anterior(ref):
    if ref.month == 1:
        return ref.year - 1, 12
    return ref.year, ref.month - 1


def _rango_mes(anio, mes):
    ini = date(anio, mes, 1)
    if mes == 12:
        fin = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(anio, mes + 1, 1) - timedelta(days=1)
    return ini, fin


def _stats_mes(conn, anio, mes, usuario_id=None):
    ini, fin = _rango_mes(anio, mes)
    ini_s, fin_s = ini.isoformat(), fin.isoformat()
    extra = ""
    params = [ini_s, fin_s]
    if usuario_id:
        extra = " AND usuario_id=?"
        params.append(usuario_id)
    row = conn.execute(
        f"""SELECT COALESCE(SUM(total),0), COUNT(*) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ?
        AND estado IN ('pagado_sin_enviar','pagado_enviado'){extra}""", params).fetchone()
    total_ordenes = conn.execute(
        f"""SELECT COUNT(*) FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ?{extra}""", params).fetchone()[0]
    return {'ventas': row[0], 'count_cobradas': row[1], 'ordenes': total_ordenes,
            'anio': anio, 'mes': mes}


def _ventas_por_dia(conn, anio, mes, usuario_id=None):
    ini, fin = _rango_mes(anio, mes)
    extra = ""
    params = [ini.isoformat(), fin.isoformat()]
    if usuario_id:
        extra = " AND usuario_id=?"
        params.append(usuario_id)
    rows = conn.execute(
        f"""SELECT date(fecha) as d, COALESCE(SUM(total),0) as t FROM ordenes_venta
        WHERE date(fecha) BETWEEN ? AND ? AND estado IN ('pagado_sin_enviar','pagado_enviado'){extra}
        GROUP BY date(fecha)""", params).fetchall()
    dias = {r['d']: r['t'] for r in rows}
    resultado = []
    d = ini
    while d <= fin:
        resultado.append({'dia': d.isoformat(), 'label': d.day, 'total': dias.get(d.isoformat(), 0)})
        d += timedelta(days=1)
    return resultado


def _ultimos_6_meses(conn, usuario_id=None):
    hoy = date.today()
    meses = []
    for i in range(5, -1, -1):
        m = hoy.month - i
        a = hoy.year
        while m <= 0:
            m += 12
            a -= 1
        meses.append((a, m))
    out = []
    for a, m in meses:
        s = _stats_mes(conn, a, m, usuario_id)
        out.append({'label': MESES_ES[m][:3] + ' ' + str(a)[2:], 'total': s['ventas']})
    return out


def _top_productos(conn, anio, mes, usuario_id=None, limit=5):
    ini, fin = _rango_mes(anio, mes)
    extra = ""
    params = [ini.isoformat(), fin.isoformat()]
    if usuario_id:
        extra = " AND o.usuario_id=?"
        params.append(usuario_id)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT p.nombre, SUM(oi.cantidad) as cant, SUM(oi.subtotal) as total
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id=oi.orden_id
        JOIN productos p ON p.id=oi.producto_id
        WHERE date(o.fecha) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado'){extra}
        GROUP BY p.id, p.nombre ORDER BY cant DESC LIMIT ?""", params).fetchall()
    return [{'nombre': r['nombre'], 'cantidad': r['cant'], 'total': r['total']} for r in rows]


def _top_provincias(conn, anio, mes, usuario_id=None, limit=5):
    ini, fin = _rango_mes(anio, mes)
    extra = ""
    params = [ini.isoformat(), fin.isoformat()]
    if usuario_id:
        extra = " AND o.usuario_id=?"
        params.append(usuario_id)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT c.provincia, COUNT(*) as cnt, COALESCE(SUM(o.total),0) as total
        FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id
        WHERE date(o.fecha) BETWEEN ? AND ?
        AND c.provincia IS NOT NULL AND c.provincia != ''
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado'){extra}
        GROUP BY c.provincia ORDER BY total DESC LIMIT ?""", params).fetchall()
    return [{'provincia': r['provincia'], 'count': r['cnt'], 'total': r['total']} for r in rows]


def _variacion(curr, prev):
    if prev == 0:
        return None if curr == 0 else 100.0
    return ((curr - prev) / prev) * 100


@app.route('/')
@login_required
def dashboard_v2():
    conn = get_db()
    hoy = date.today()
    usuario_id = None if current_user.es_admin else current_user.id

    actual = _stats_mes(conn, hoy.year, hoy.month, usuario_id)
    a_ant, m_ant = _mes_anterior(hoy)
    anterior = _stats_mes(conn, a_ant, m_ant, usuario_id)

    variacion = {
        'ventas': _variacion(actual['ventas'], anterior['ventas']),
        'ordenes': _variacion(actual['ordenes'], anterior['ordenes']),
        'mes_anterior_label': MESES_ES[m_ant],
    }

    total_clientes = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
    total_productos = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0]
    bajo_stock = conn.execute(
        "SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_actual <= stock_minimo AND stock_minimo > 0"
    ).fetchone()[0]
    pendientes = conn.execute(
        "SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago'"
    ).fetchone()[0]
    a_cobrar = conn.execute(
        """SELECT COALESCE(SUM(o.total - COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)),0)
        FROM ordenes_venta o WHERE o.estado != 'cancelado'
        AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)"""
    ).fetchone()[0]
    ordenes_pendientes_facturar = conn.execute(
        "SELECT COUNT(*) FROM ordenes_venta WHERE estado_facturacion='pendiente'"
    ).fetchone()[0]

    ultimos6 = _ultimos_6_meses(conn, usuario_id)
    por_dia = _ventas_por_dia(conn, hoy.year, hoy.month, usuario_id)
    top_prods = _top_productos(conn, hoy.year, hoy.month, usuario_id)
    top_provs = _top_provincias(conn, hoy.year, hoy.month, usuario_id)

    # Últimos 5 clientes (admin)
    ultimos_clientes = conn.execute(
        "SELECT nombre_completo, provincia, creado FROM clientes WHERE activo=1 ORDER BY id DESC LIMIT 5"
    ).fetchall()

    conn.close()
    return render_template('dashboard.html',
        actual=actual, anterior=anterior, variacion=variacion,
        total_clientes=total_clientes, total_productos=total_productos,
        bajo_stock=bajo_stock, pendientes=pendientes, a_cobrar=a_cobrar,
        ordenes_pendientes_facturar=ordenes_pendientes_facturar,
        ultimos6=ultimos6, por_dia=por_dia,
        top_prods=top_prods, top_provs=top_provs,
        ultimos_clientes=ultimos_clientes,
        mes_actual_label=MESES_ES[hoy.month],
        hoy=hoy,
    )


app.view_functions['dashboard'] = dashboard_v2


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
