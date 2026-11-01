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
    print(f"[upgrade88] escrito: {relpath}")


APP88_PY = r'''
from flask import render_template
from flask_login import login_required, current_user
from app67 import app
from database import get_db
from datetime import date, timedelta

@app.route('/')
@login_required
def dashboard_v4():
    conn = get_db()
    hoy = date.today()
    inicio_mes = hoy.replace(day=1).isoformat()
    
    if hoy.month == 1:
        ant_ini = date(hoy.year-1, 12, 1).isoformat()
        ant_fin = date(hoy.year-1, 12, 31).isoformat()
    else:
        ant_ini = date(hoy.year, hoy.month-1, 1).isoformat()
        import calendar
        ult_dia = calendar.monthrange(hoy.year, hoy.month-1)[1]
        ant_fin = date(hoy.year, hoy.month-1, ult_dia).isoformat()

    usuario_id = None if current_user.es_admin else current_user.id

    # Reutilizamos las funciones del dashboard original (app7)
    from app7 import _stats_mes, _mes_anterior, _variacion, _ultimos_6_meses, _ventas_por_dia
    from app6 import MESES_ES

    actual = _stats_mes(conn, hoy.year, hoy.month, usuario_id)
    a_ant, m_ant = _mes_anterior(hoy)
    anterior = _stats_mes(conn, a_ant, m_ant, usuario_id)
    variacion = {
        'ventas': _variacion(actual['ventas'], anterior['ventas']),
        'ordenes': _variacion(actual['ordenes'], anterior['ordenes']),
        'mes_anterior_label': MESES_ES[m_ant],
    }

    # Gastos
    if usuario_id:
        gastos_mes = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=? AND usuario_id=?", (inicio_mes, usuario_id)).fetchone()[0]
        gastos_ant = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ? AND usuario_id=?", (ant_ini, ant_fin, usuario_id)).fetchone()[0]
    else:
        gastos_mes = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha)>=?", (inicio_mes,)).fetchone()[0]
        gastos_ant = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE date(fecha) BETWEEN ? AND ?", (ant_ini, ant_fin)).fetchone()[0]
    var_gastos = _variacion(gastos_mes, gastos_ant)

    # Saldo
    ingresos_total = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos").fetchone()[0]
    gastos_total = conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos").fetchone()[0]
    compras_total = conn.execute("SELECT COALESCE(SUM(total),0) FROM compras").fetchone()[0]
    saldo_actual = ingresos_total - gastos_total - compras_total

    # Alertas
    if usuario_id:
        envios_pendientes = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE estado='pagado_sin_enviar' AND usuario_id=?", (usuario_id,)).fetchone()[0]
        ordenes_por_cobrar = conn.execute("SELECT COUNT(*) FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.usuario_id=? AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)", (usuario_id,)).fetchone()[0]
        pendientes = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago' AND usuario_id=?", (usuario_id,)).fetchone()[0]
    else:
        envios_pendientes = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE estado='pagado_sin_enviar'").fetchone()[0]
        ordenes_por_cobrar = conn.execute("SELECT COUNT(*) FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE order_id=o.id),0)").fetchone()[0]
        pendientes = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE estado='pendiente_pago'").fetchone()[0]

    # ===== ARREGLO DE TOP PROVINCIAS Y PRODUCTOS =====
    # Usamos provincia_id y localidad de la tabla correcta
    top_provs = []
    top_prods = []
    
    cond_u = " AND o.usuario_id = ?" if usuario_id else ""
    params_u = [usuario_id] if usuario_id else []

    rows_prov = conn.execute(f"""
        SELECT COALESCE(p.nombre, 'Sin provincia') as provincia, 
               COUNT(o.id) as count, 
               SUM(o.total) as total
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias p ON p.id = c.provincia_id
        WHERE date(o.fecha) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado') {cond_u}
        GROUP BY c.provincia_id, p.nombre
        ORDER BY total DESC LIMIT 5
    """, [inicio_mes, hoy.isoformat()] + params_u).fetchall()
    
    for r in rows_prov:
        top_provs.append({'provincia': r['provincia'], 'count': r['count'], 'total': r['total']})

    rows_prod = conn.execute(f"""
        SELECT pr.nombre, SUM(oi.cantidad) as cantidad, SUM(oi.subtotal) as total
        FROM orden_items oi
        JOIN ordenes_venta o ON o.id = oi.orden_id
        JOIN productos pr ON pr.id = oi.producto_id
        WHERE date(o.fecha) BETWEEN ? AND ?
        AND o.estado IN ('pagado_sin_enviar','pagado_enviado') {cond_u}
        GROUP BY pr.id, pr.nombre
        ORDER BY cantidad DESC LIMIT 5
    """, [inicio_mes, hoy.isoformat()] + params_u).fetchall()
    
    for r in rows_prod:
        top_prods.append({'nombre': r['nombre'], 'cantidad': r['cantidad'], 'total': r['total']})

    # Resto de los datos
    total_clientes = conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0]
    bajo_stock = conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1 AND stock_actual <= stock_minimo AND stock_minimo > 0").fetchone()[0]
    ordenes_pendientes_facturar = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE estado_facturacion='pendiente'").fetchone()[0]
    a_cobrar_total = conn.execute("SELECT COALESCE(SUM(o.total - COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)),0) FROM ordenes_venta o WHERE o.estado != 'cancelado' AND o.total > COALESCE((SELECT SUM(monto) FROM pagos WHERE orden_id=o.id),0)").fetchone()[0]

    ultimos6 = _ultimos_6_meses(conn, usuario_id)
    por_dia = _ventas_por_dia(conn, hoy.year, hoy.month, usuario_id)

    ultimos_clientes = conn.execute("SELECT nombre_completo, provincia, creado FROM clientes WHERE activo=1 ORDER BY id DESC LIMIT 5").fetchall()

    # Objetivos
    from app26 import _get_objetivo, _facturado
    obj_global = _get_objetivo(conn, None, hoy.month, hoy.year)
    fac_global = _facturado(conn, None, hoy.month, hoy.year)
    objetivos_dashboard = {
        'global': {'objetivo': obj_global, 'facturado': fac_global, 'pct': (fac_global/obj_global*100) if obj_global > 0 else 0},
        'vendedores': [],
        'mes_label': MESES_ES[hoy.month],
        'anio': hoy.year
    }
    vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()
    for v in vendedores:
        obj = _get_objetivo(conn, v['id'], hoy.month, hoy.year)
        fac = _facturado(conn, v['id'], hoy.month, hoy.year)
        objetivos_dashboard['vendedores'].append({'nombre': v['nombre'], 'objetivo': obj, 'facturado': fac, 'pct': (fac/obj*100) if obj > 0 else 0})

    conn.close()

    return render_template('dashboard.html',
        actual=actual, anterior=anterior, variacion=variacion,
        gastos_mes=gastos_mes, gastos_ant=gastos_ant, var_gastos=var_gastos,
        saldo_actual=saldo_actual, ingresos_total=ingresos_total, gastos_total=gastos_total, compras_total=compras_total,
        envios_pendientes=envios_pendientes, ordenes_por_cobrar=ordenes_por_cobrar, pendientes=pendientes,
        total_clientes=total_clientes, bajo_stock=bajo_stock, ordenes_pendientes_facturar=ordenes_pendientes_facturar, a_cobrar=a_cobrar_total,
        ultimos6=ultimos6, por_dia=por_dia, top_prods=top_prods, top_provs=top_provs, ultimos_clientes=ultimos_clientes,
        mes_actual_label=MESES_ES[hoy.month], hoy=hoy, objetivos_dashboard=objetivos_dashboard
    )

# Reemplazar la ruta del dashboard en app67
app.view_functions['dashboard'] = dashboard_v4
'''

def main():
    print("=== Upgrade 88: Fix top provincias usando provincia_id ===")
    escribir('app88.py', APP88_PY)
    print("")
    print("Actualizando run.bat...")
    run_bat_content = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(run_bat_content)
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()