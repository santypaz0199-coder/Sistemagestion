
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app23 import app
from app import admin_required
from database import get_db


MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


def _get_objetivo(conn, usuario_id, mes, anio):
    if usuario_id is None:
        row = conn.execute("SELECT monto FROM objetivos WHERE usuario_id IS NULL AND mes=? AND anio=?",
                           (mes, anio)).fetchone()
    else:
        row = conn.execute("SELECT monto FROM objetivos WHERE usuario_id=? AND mes=? AND anio=?",
                           (usuario_id, mes, anio)).fetchone()
    return row['monto'] if row else 0


def _facturado(conn, usuario_id, mes, anio):
    if mes == 12:
        ini = date(anio, 12, 1).isoformat()
        fin = date(anio+1, 1, 1).isoformat()
    else:
        ini = date(anio, mes, 1).isoformat()
        fin = date(anio, mes+1, 1).isoformat()
    if usuario_id is None:
        total = conn.execute(
            """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
            WHERE date(fecha) >= ? AND date(fecha) < ?
            AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (ini, fin)).fetchone()[0]
    else:
        total = conn.execute(
            """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
            WHERE date(fecha) >= ? AND date(fecha) < ?
            AND usuario_id = ?
            AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (ini, fin, usuario_id)).fetchone()[0]
    return total


@app.context_processor
def _ctx_objetivo_sidebar():
    if not current_user.is_authenticated:
        return {}
    conn = get_db()
    try:
        hoy = date.today()
        if current_user.es_admin:
            objetivo = _get_objetivo(conn, None, hoy.month, hoy.year)
            facturado = _facturado(conn, None, hoy.month, hoy.year)
            return {'objetivo_sidebar': {
                'monto': objetivo,
                'facturado': facturado,
                'pct': (facturado / objetivo * 100) if objetivo > 0 else 0,
                'mes_label': MESES[hoy.month],
            }}
        else:
            objetivo = _get_objetivo(conn, current_user.id, hoy.month, hoy.year)
            if objetivo <= 0:
                return {}
            facturado = _facturado(conn, current_user.id, hoy.month, hoy.year)
            return {'objetivo_sidebar': {
                'monto': objetivo,
                'facturado': facturado,
                'pct': (facturado / objetivo * 100) if objetivo > 0 else 0,
                'mes_label': MESES[hoy.month],
            }}
    finally:
        conn.close()


@app.route('/objetivos')
@login_required
@admin_required
def objetivos_lista():
    conn = get_db()
    hoy = date.today()
    mes = request.args.get('mes', hoy.month, type=int)
    anio = request.args.get('anio', hoy.year, type=int)

    # Objetivo global
    objetivo_global = _get_objetivo(conn, None, mes, anio)
    facturado_global = _facturado(conn, None, mes, anio)

    # Objetivos por vendedor
    vendedores = conn.execute("SELECT id, nombre, email, rol FROM usuarios WHERE activo=1 AND rol='vendedor' ORDER BY nombre").fetchall()
    filas = []
    for v in vendedores:
        obj = _get_objetivo(conn, v['id'], mes, anio)
        fac = _facturado(conn, v['id'], mes, anio)
        filas.append({
            'usuario': v, 'objetivo': obj, 'facturado': fac,
            'pct': (fac / obj * 100) if obj > 0 else 0,
        })

    conn.close()
    return render_template('objetivos/lista.html',
                           mes=mes, anio=anio, mes_label=MESES[mes],
                           objetivo_global=objetivo_global, facturado_global=facturado_global,
                           pct_global=(facturado_global / objetivo_global * 100) if objetivo_global > 0 else 0,
                           filas=filas, MESES=MESES)


@app.route('/objetivos/global', methods=['POST'])
@login_required
@admin_required
def objetivos_global():
    mes = int(request.form['mes'])
    anio = int(request.form['anio'])
    try:
        monto = float(request.form['monto'] or 0)
    except ValueError:
        flash('Monto invalido.', 'error'); return redirect(url_for('objetivos_lista', mes=mes, anio=anio))
    conn = get_db()
    if monto > 0:
        conn.execute("""INSERT INTO objetivos (usuario_id, mes, anio, monto)
            VALUES (NULL, ?, ?, ?)
            ON CONFLICT(usuario_id, mes, anio) DO UPDATE SET monto=excluded.monto, actualizado=CURRENT_TIMESTAMP""",
            (mes, anio, monto))
        flash(f'Objetivo global de {MESES[mes]} {anio}: ${monto:,.0f}'.replace(',','.'), 'success')
    else:
        conn.execute("DELETE FROM objetivos WHERE usuario_id IS NULL AND mes=? AND anio=?", (mes, anio))
        flash('Objetivo global eliminado.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio))


@app.route('/objetivos/vendedor/<int:uid>', methods=['POST'])
@login_required
@admin_required
def objetivos_vendedor(uid):
    mes = int(request.form['mes'])
    anio = int(request.form['anio'])
    try:
        monto = float(request.form['monto'] or 0)
    except ValueError:
        flash('Monto invalido.', 'error'); return redirect(url_for('objetivos_lista', mes=mes, anio=anio))
    conn = get_db()
    if monto > 0:
        conn.execute("""INSERT INTO objetivos (usuario_id, mes, anio, monto)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(usuario_id, mes, anio) DO UPDATE SET monto=excluded.monto, actualizado=CURRENT_TIMESTAMP""",
            (uid, mes, anio, monto))
        flash('Objetivo del vendedor guardado.', 'success')
    else:
        conn.execute("DELETE FROM objetivos WHERE usuario_id=? AND mes=? AND anio=?", (uid, mes, anio))
        flash('Objetivo del vendedor eliminado.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio))


# ====== Dashboard con objetivos ======
@app.route('/')
@login_required
def dashboard_objetivos():
    # Reusar el dashboard original
    from app22 import ventas_lista_v2  # dummy import para asegurar carga
    from app17 import productos_lista_v3  # dummy
    # Ejecutar el dashboard real
    from app import app as app_base
    # Pero el dashboard real está en app7/app8 (dashboard_v3)
    # Lo llamamos manualmente
    from app7 import dashboard_v3
    result = dashboard_v3()
    # No podemos añadir al template desde aca sin modificar más
    # Por eso el objetivo se muestra en el sidebar (ya lo pusimos en _ctx_objetivo_sidebar)
    return result


# Reemplazar el dashboard original
from app7 import dashboard_v3
app.view_functions['dashboard'] = dashboard_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
