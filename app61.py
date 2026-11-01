
from datetime import date
from flask import render_template, request
from flask_login import login_required
from app48 import app
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
