
from datetime import date, timedelta
from flask import render_template
from flask_login import login_required, current_user
from app6 import app, MESES_ES, _stats_mes, _mes_anterior, _variacion, \
    _ultimos_6_meses, _ventas_por_dia, _top_productos, _top_provincias
from database import get_db


@app.route('/')
@login_required
def dashboard_v3():
    conn = get_db()
    hoy = date.today()
    inicio_mes = hoy.replace(day=1).isoformat()
    a_ant, m_ant = _mes_anterior(hoy)
    ini_ant = date(a_ant, m_ant, 1).isoformat()
    if m_ant == 12:
        fin_ant = date(a_ant + 1, 1, 1) - timedelta(days=1)
    else:
        fin_ant = date(a_ant, m_ant + 1, 1) - timedelta(days=1)
    fin_ant_s = fin_ant.isoformat()

    usuario_id = None if current_user.es_admin else current_user.id

    actual = _stats_mes(conn, hoy.year, hoy.month, usuario_id)
    anterior = _stats_mes(conn, a_ant, m_ant, usuario_id)
    variacion = {
        'ventas': _variacion(actual['ventas'], anterior['ventas']),
        'ordenes': _variacion(actual['ordenes'], anterior['ordenes']),
        'mes_anterior_label': MESES_ES[m_ant],
    }

    # Gastos del mes + mes anterior
    if usuario_id:
        gastos_mes = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=? AND usuario_id=?",
            (inicio_mes, usuario_id)).fetchone()[0]
        gastos_ant = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ? AND usuario_id=?",
            (ini_ant, fin_ant_s, usuario_id)).fetchone()[0]
    else:
        gastos_mes = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=?",
            (inicio_mes,)).fetchone()[0]
        gastos_ant = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ?",
            (ini_ant, fin_ant_s)).fetchone()[0]
    var_gastos = _variacion(gastos_mes, gastos_ant)

    # Saldo actual (histórico, caja)
    ingresos_total = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos").fetchone()[0]
    gastos_total = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos").fetchone()[0]
    compras_total = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras").fetchone()[0]
    saldo_actual = ingresos_total - gastos_total - compras_total

    # Envíos pendientes y órdenes por cobrar
    if usuario_id:
        envios_pendientes = conn.execute(
            "SELECT COUNT(*) FROM ordenes_venta WHERE estado='pagado_sin_enviar' AND usuario_id=?",
            (usuario_id,)).fetchone()[0]
        ordenes_por_cobrar = conn.execute(
            """SELECT COUNT(*) FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.usuario_id=?
            AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)""",
            (usuario_id,)).fetchone()[0]
        pendientes_pago = conn.execute(
            "SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago' AND usuario_id=?",
            (usuario_id,)).fetchone()[0]
    else:
        envios_pendientes = conn.execute(
            "SELECT COUNT(*) FROM ordenes_venta WHERE estado='pagado_sin_enviar'").fetchone()[0]
        ordenes_por_cobrar = conn.execute(
            """SELECT COUNT(*) FROM ordenes_venta o WHERE o.estado != 'cancelado'
            AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)"""
        ).fetchone()[0]
        pendientes_pago = conn.execute(
            "SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago'").fetchone()[0]

    # Resto igual que antes
    total_clientes = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
    total_productos = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0]
    bajo_stock = conn.execute(
        "SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_actual <= stock_minimo AND stock_minimo > 0"
    ).fetchone()[0]
    a_cobrar_total = conn.execute(
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

    ultimos_clientes = conn.execute(
        "SELECT nombre_completo, provincia, creado FROM clientes WHERE activo=1 ORDER BY id DESC LIMIT 5"
    ).fetchall()

    conn.close()
    return render_template('dashboard.html',
        actual=actual, anterior=anterior, variacion=variacion,
        gastos_mes=gastos_mes, gastos_ant=gastos_ant, var_gastos=var_gastos,
        saldo_actual=saldo_actual, ingresos_total=ingresos_total,
        gastos_total=gastos_total, compras_total=compras_total,
        envios_pendientes=envios_pendientes, ordenes_por_cobrar=ordenes_por_cobrar,
        pendientes_pago=pendientes_pago,
        total_clientes=total_clientes, total_productos=total_productos,
        bajo_stock=bajo_stock, pendientes=pendientes_pago, a_cobrar=a_cobrar_total,
        ordenes_pendientes_facturar=ordenes_pendientes_facturar,
        ultimos6=ultimos6, por_dia=por_dia,
        top_prods=top_prods, top_provs=top_provs,
        ultimos_clientes=ultimos_clientes,
        mes_actual_label=MESES_ES[hoy.month],
        hoy=hoy,
    )


app.view_functions['dashboard'] = dashboard_v3
