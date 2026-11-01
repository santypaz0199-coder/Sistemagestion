
from datetime import date, timedelta
from calendar import monthrange
from flask import request, jsonify
from flask_login import current_user, login_required
from app66 import app
from database import get_db

MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def _semanas_del_mes(anio, mes):
    """Divide un mes en semanas (lunes a domingo)."""
    from datetime import timedelta
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, monthrange(anio, mes)[1])
    semanas = []
    inicio = primer_dia
    while inicio <= ultimo_dia:
        dias_hasta_domingo = 6 - inicio.weekday()
        fin = inicio + timedelta(days=dias_hasta_domingo)
        if fin > ultimo_dia:
            fin = ultimo_dia
        semanas.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return semanas


def _datos_semanales(conn, anio, mes):
    """Devuelve ventas, gastos y saldo por semana del mes dado."""
    semanas = _semanas_del_mes(anio, mes)
    resultado = []
    for i, (ini, fin) in enumerate(semanas, start=1):
        ini_s, fin_s = ini.isoformat(), fin.isoformat()

        ventas = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM ordenes_venta "
            "WHERE date(fecha) BETWEEN ? AND ? "
            "AND estado IN ('pagado_sin_enviar','pagado_enviado')",
            (ini_s, fin_s)).fetchone()[0] or 0

        gastos = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM gastos "
            "WHERE date(fecha) BETWEEN ? AND ?",
            (ini_s, fin_s)).fetchone()[0] or 0

        compras = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM compras "
            "WHERE date(fecha) BETWEEN ? AND ?",
            (ini_s, fin_s)).fetchone()[0] or 0

        egresos = float(gastos) + float(compras)
        ventas_f = float(ventas)
        resultado.append({
            'semana': i,
            'rango': f"{ini.strftime('%d')} a {fin.strftime('%d/%m')}",
            'ventas': ventas_f,
            'gastos': egresos,
            'saldo': ventas_f - egresos,
        })
    return resultado


def _pad_semanas(semanas, total):
    """Rellena con semanas vacias hasta llegar a 'total'."""
    while len(semanas) < total:
        semanas.append({
            'semana': len(semanas) + 1,
            'rango': '',
            'ventas': 0,
            'gastos': 0,
            'saldo': 0,
        })
    return semanas


@app.context_processor
def _ctx_semanas_dashboard():
    if request.endpoint != 'dashboard':
        return {}
    if not current_user.is_authenticated or not current_user.es_admin:
        return {}

    conn = get_db()
    try:
        hoy = date.today()
        if hoy.month == 1:
            ant_anio, ant_mes = hoy.year - 1, 12
        else:
            ant_anio, ant_mes = hoy.year, hoy.month - 1

        sem_act = _datos_semanales(conn, hoy.year, hoy.month)
        sem_ant = _datos_semanales(conn, ant_anio, ant_mes)

        # Padding para que ambas listas tengan la misma longitud
        max_len = max(len(sem_act), len(sem_ant))
        sem_act = _pad_semanas(sem_act, max_len)
        sem_ant = _pad_semanas(sem_ant, max_len)

        return {
            'semanas_actual': sem_act,
            'semanas_ant': sem_ant,
            'sem_mes_actual': MESES_ES[hoy.month],
            'sem_mes_ant': MESES_ES[ant_mes],
        }
    finally:
        conn.close()


@app.route('/api/detalle-mes/<tipo>')
@login_required
def detalle_mes(tipo):
    from datetime import date
    from flask_login import current_user
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()
    
    if hoy.month == 1:
        ant_ini = date(hoy.year-1, 12, 1).isoformat()
        ant_fin = date(hoy.year-1, 12, 31).isoformat()
    else:
        ant_ini = date(hoy.year, hoy.month-1, 1).isoformat()
        # ultimo dia del mes anterior
        import calendar
        ult_dia = calendar.monthrange(hoy.year, hoy.month-1)[1]
        ant_fin = date(hoy.year, hoy.month-1, ult_dia).isoformat()

    resultado = {'actual': [], 'anterior': []}

    if tipo == 'ventas':
        q_act = """SELECT o.fecha, o.numero_interno, c.nombre_completo as cliente, o.total, o.estado 
                   FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id
                   WHERE date(o.fecha) >= ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                   ORDER BY o.fecha DESC"""
        q_ant = """SELECT o.fecha, o.numero_interno, c.nombre_completo as cliente, o.total, o.estado 
                   FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id
                   WHERE date(o.fecha) BETWEEN ? AND ? AND o.estado IN ('pagado_sin_enviar','pagado_enviado')
                   ORDER BY o.fecha DESC"""
    elif tipo == 'gastos':
        q_act = """SELECT fecha, descripcion as numero_interno, 'Gasto' as cliente, monto as total, 'Pagado' as estado 
                   FROM gastos WHERE date(fecha) >= ? ORDER BY fecha DESC"""
        q_ant = """SELECT fecha, descripcion as numero_interno, 'Gasto' as cliente, monto as total, 'Pagado' as estado 
                   FROM gastos WHERE date(fecha) BETWEEN ? AND ? ORDER BY fecha DESC"""
    else:
        conn.close()
        return jsonify(resultado)

    rows_act = conn.execute(q_act, (ini_mes,)).fetchall()
    rows_ant = conn.execute(q_ant, (ant_ini, ant_fin)).fetchall()

    resultado['actual'] = [dict(r) for r in rows_act]
    resultado['anterior'] = [dict(r) for r in rows_ant]

    conn.close()
    return jsonify(resultado)


@app.route('/api/detalle-ciudades')
@login_required
def detalle_ciudades():
    from datetime import date
    conn = get_db()
    hoy = date.today()
    ini_mes = hoy.replace(day=1).isoformat()

    rows = conn.execute("""
        SELECT COALESCE(p.nombre, 'Sin provincia') as provincia,
               COALESCE(l.nombre, c.localidad, 'Sin localidad') as localidad,
               COUNT(o.id) as cantidad,
               SUM(o.total) as total
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias p ON p.id = c.provincia_id
        LEFT JOIN localidades l ON l.id = c.localidad_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) >= ?
        GROUP BY c.provincia_id, c.localidad_id, c.localidad, p.nombre, l.nombre
        ORDER BY total DESC
        LIMIT 15
    """, (ini_mes,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
