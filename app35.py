
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app34 import app
from app import admin_required
from database import get_db


MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


def _facturado_canal(conn, canal_id, mes, anio):
    if mes == 12:
        ini = date(anio, 12, 1).isoformat()
        fin = date(anio+1, 1, 1).isoformat()
    else:
        ini = date(anio, mes, 1).isoformat()
        fin = date(anio, mes+1, 1).isoformat()
    return conn.execute(
        """SELECT COALESCE(SUM(total),0) FROM ordenes_venta
        WHERE date(fecha) >= ? AND date(fecha) < ?
        AND canal_id = ?
        AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
        (ini, fin, canal_id)).fetchone()[0]


def _objetivo_canal(conn, canal_id, mes, anio):
    row = conn.execute("SELECT monto FROM objetivos_canal WHERE canal_id=? AND mes=? AND anio=?",
                       (canal_id, mes, anio)).fetchone()
    return row['monto'] if row else 0


def _gastos_fijos_mes(conn, mes, anio):
    if mes == 12:
        ini = date(anio, 12, 1).isoformat()
        fin = date(anio+1, 1, 1).isoformat()
    else:
        ini = date(anio, mes, 1).isoformat()
        fin = date(anio, mes+1, 1).isoformat()
    rows = conn.execute("""
        SELECT g.*, cg.nombre as categoria_nombre
        FROM gastos g LEFT JOIN categorias_gastos cg ON cg.id = g.categoria_id
        WHERE g.es_fijo = 1
        AND date(g.fecha) >= ? AND date(g.fecha) < ?
        ORDER BY g.fecha DESC
    """, (ini, fin)).fetchall()
    total = sum(r['monto'] for r in rows)
    return rows, total


def objetivos_lista_v2():
    conn = get_db()
    hoy = date.today()
    mes = request.args.get('mes', hoy.month, type=int)
    anio = request.args.get('anio', hoy.year, type=int)
    tab = request.args.get('tab', 'global')

    from app26 import _get_objetivo, _facturado
    objetivo_global = _get_objetivo(conn, None, mes, anio)
    facturado_global = _facturado(conn, None, mes, anio)

    vendedores = conn.execute(
        "SELECT id, nombre, email, rol FROM usuarios WHERE activo=1 AND rol='vendedor' ORDER BY nombre"
    ).fetchall()
    filas_v = []
    for v in vendedores:
        obj = _get_objetivo(conn, v['id'], mes, anio)
        fac = _facturado(conn, v['id'], mes, anio)
        filas_v.append({'usuario': v, 'objetivo': obj, 'facturado': fac,
                        'pct': (fac/obj*100) if obj > 0 else 0,
                        'gap': max(0, obj - fac)})

    canales = conn.execute("SELECT id, nombre FROM canales_venta WHERE activo=1 ORDER BY nombre").fetchall()
    filas_c = []
    total_obj_canal = 0
    total_fac_canal = 0
    for c in canales:
        obj = _objetivo_canal(conn, c['id'], mes, anio)
        fac = _facturado_canal(conn, c['id'], mes, anio)
        total_obj_canal += obj
        total_fac_canal += fac
        filas_c.append({'canal': c, 'objetivo': obj, 'facturado': fac,
                        'pct': (fac/obj*100) if obj > 0 else 0,
                        'gap': max(0, obj - fac)})

    gf_rows, gf_total = _gastos_fijos_mes(conn, mes, anio)

    conn.close()
    return render_template('objetivos/lista.html',
                           mes=mes, anio=anio, mes_label=MESES[mes], tab=tab,
                           objetivo_global=objetivo_global, facturado_global=facturado_global,
                           pct_global=(facturado_global/objetivo_global*100) if objetivo_global > 0 else 0,
                           filas_v=filas_v, filas_c=filas_c,
                           total_obj_canal=total_obj_canal, total_fac_canal=total_fac_canal,
                           gastos_fijos=gf_rows, gastos_fijos_total=gf_total,
                           MESES=MESES, hoy=hoy)


app.view_functions['objetivos_lista'] = objetivos_lista_v2


def objetivos_global_v2():
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
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio, tab='global'))


def objetivos_vendedor_v2(uid):
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
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio, tab='vendedores'))


app.view_functions['objetivos_global'] = objetivos_global_v2
app.view_functions['objetivos_vendedor'] = objetivos_vendedor_v2


@app.route('/objetivos/canal', methods=['POST'])
@login_required
@admin_required
def objetivos_canal_guardar():
    mes = int(request.form['mes'])
    anio = int(request.form['anio'])
    conn = get_db()
    canales = conn.execute("SELECT id FROM canales_venta WHERE activo=1").fetchall()
    for c in canales:
        campo = f'monto_canal_{c["id"]}'
        if campo in request.form:
            try:
                monto = float(request.form[campo] or 0)
            except ValueError:
                monto = 0
            if monto > 0:
                conn.execute("""INSERT INTO objetivos_canal (canal_id, mes, anio, monto)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(canal_id, mes, anio) DO UPDATE SET monto=excluded.monto, actualizado=CURRENT_TIMESTAMP""",
                    (c['id'], mes, anio, monto))
            else:
                conn.execute("DELETE FROM objetivos_canal WHERE canal_id=? AND mes=? AND anio=?",
                             (c['id'], mes, anio))
    conn.commit(); conn.close()
    flash('Objetivos por canal guardados.', 'success')
    return redirect(url_for('objetivos_lista', mes=mes, anio=anio, tab='canales'))


@app.route('/objetivos/gastos-fijos', methods=['GET', 'POST'])
@login_required
@admin_required
def objetivos_gastos_fijos():
    conn = get_db()
    hoy = date.today()
    mes = request.values.get('mes', hoy.month, type=int)
    anio = request.values.get('anio', hoy.year, type=int)

    if request.method == 'POST':
        try:
            monto = float(request.form['monto'] or 0)
        except ValueError:
            conn.close(); flash('Monto invalido.', 'error')
            return redirect(url_for('objetivos_gastos_fijos', mes=mes, anio=anio))
        desc = request.form.get('descripcion', '').strip()
        cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        fecha = request.form.get('fecha') or date(anio, mes, 1).isoformat()
        if monto <= 0 or not desc:
            conn.close(); flash('Descripcion y monto obligatorios.', 'error')
            return redirect(url_for('objetivos_gastos_fijos', mes=mes, anio=anio))
        conn.execute("""INSERT INTO gastos (fecha, categoria_id, descripcion, monto, usuario_id, es_fijo)
            VALUES (?,?,?,?,?,1)""",
            (fecha, cat_id, desc, monto, current_user.id))
        conn.commit(); conn.close()
        flash('Gasto fijo registrado.', 'success')
        return redirect(url_for('objetivos_gastos_fijos', mes=mes, anio=anio))

    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    gf_rows, gf_total = _gastos_fijos_mes(conn, mes, anio)
    conn.close()
    return render_template('objetivos/gastos_fijos.html',
                           mes=mes, anio=anio, mes_label=MESES[mes],
                           categorias=categorias, gastos_fijos=gf_rows,
                           gastos_fijos_total=gf_total, MESES=MESES, hoy=hoy)


@app.route('/objetivos/gastos-fijos/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def objetivos_gasto_fijo_toggle(id):
    conn = get_db()
    conn.execute("UPDATE gastos SET es_fijo = 1 - COALESCE(es_fijo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for('objetivos_gastos_fijos'))


# ===== Gastos v3 (con es_fijo) =====
def _datos_gasto():
    try:
        monto = float(request.form['monto'])
    except (ValueError, KeyError):
        return None, 'Monto invalido.'
    cat_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
    fecha = request.form.get('fecha') or date.today().isoformat()
    es_fijo = 1 if request.form.get('es_fijo') else 0
    return {
        'fecha': fecha, 'categoria_id': cat_id,
        'descripcion': request.form.get('descripcion', '').strip(),
        'monto': monto, 'es_fijo': es_fijo,
    }, None


def gastos_nuevo_v3():
    conn = get_db()
    if request.method == 'POST':
        d, err = _datos_gasto()
        if err:
            conn.close(); flash(err, 'error'); return redirect(url_for('gastos_nuevo'))
        conn.execute("INSERT INTO gastos (fecha,categoria_id,descripcion,monto,usuario_id,es_fijo) VALUES (?,?,?,?,?,?)",
                     (d['fecha'], d['categoria_id'], d['descripcion'], d['monto'], current_user.id, d['es_fijo']))
        conn.commit(); conn.close()
        flash('Gasto registrado.', 'success')
        return redirect(url_for('gastos_lista'))
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('gastos/form.html', gasto=None, categorias=categorias, hoy=date.today().isoformat())


def gastos_editar_v3(id):
    conn = get_db()
    gasto = conn.execute("SELECT * FROM gastos WHERE id=?", (id,)).fetchone()
    if not gasto:
        conn.close(); return redirect(url_for('gastos_lista'))
    if request.method == 'POST':
        d, err = _datos_gasto()
        if err:
            conn.close(); flash(err, 'error'); return redirect(url_for('gastos_editar', id=id))
        conn.execute("UPDATE gastos SET fecha=?,categoria_id=?,descripcion=?,monto=?,es_fijo=? WHERE id=?",
                     (d['fecha'], d['categoria_id'], d['descripcion'], d['monto'], d['es_fijo'], id))
        conn.commit(); conn.close()
        flash('Gasto actualizado.', 'success')
        return redirect(url_for('gastos_lista'))
    categorias = conn.execute("SELECT * FROM categorias_gastos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('gastos/form.html', gasto=gasto, categorias=categorias, hoy=gasto['fecha'])


app.view_functions['gastos_nuevo'] = gastos_nuevo_v3
app.view_functions['gastos_editar'] = gastos_editar_v3


# ===== Reportes v4 =====
def reportes_v4():
    from app27 import _financiero, _kilos, _top_vendedores, _top_canales, _top_productos, _top_provincias, _periodo, _periodo_ant, _periodo_ap, _var
    from app29 import _clientes_stats, _minorista_mayorista, _kilos_desglosado, _top_clientes
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

    gastos_fijos_periodo = conn.execute(
        "SELECT COALESCE(SUM(monto),0) FROM gastos WHERE es_fijo = 1 AND date(fecha) BETWEEN ? AND ?",
        (ini_s, fin_s)).fetchone()[0]
    margen_contrib = actual['margen_contrib_pct']
    punto_eq_fijos = (gastos_fijos_periodo / (margen_contrib / 100)) if margen_contrib > 0 else 0

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
        cumplimiento_canales=cumplimiento_canales,
        gastos_fijos_periodo=gastos_fijos_periodo,
        punto_eq_fijos=punto_eq_fijos,
        var=var, label_periodo=labels[tipo])


app.view_functions['reportes'] = reportes_v4


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
