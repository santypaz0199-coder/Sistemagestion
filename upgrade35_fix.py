# -*- coding: utf-8 -*-
"""
Fix del upgrade35. Hace las mismas cosas pero con la sintaxis corregida.
Reemplaza la funcion patch_reportes_route rota.
"""
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade35_fix] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade35_fix] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(gastos)").fetchall()]
    if 'es_fijo' not in cols:
        conn.execute("ALTER TABLE gastos ADD COLUMN es_fijo INTEGER DEFAULT 0")
        print("[upgrade35_fix] + gastos.es_fijo")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS objetivos_canal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canal_id INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            monto REAL NOT NULL,
            creado TEXT DEFAULT CURRENT_TIMESTAMP,
            actualizado TEXT,
            UNIQUE(canal_id, mes, anio),
            FOREIGN KEY (canal_id) REFERENCES canales_venta(id) ON DELETE CASCADE
        )
    """)
    print("[upgrade35_fix] tabla objetivos_canal OK")

    conn.commit(); conn.close()


APP35_PY = r'''
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
'''


OBJETIVOS_LISTA = r'''{% extends "base.html" %}
{% block title %}Objetivos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
<div>
<h4 class="mb-1">Objetivos</h4>
<div class="text-muted small">Metas mensuales global, por vendedor y por canal</div>
</div>
<form class="d-flex gap-2">
<input type="hidden" name="tab" value="{{ tab }}">
<select name="mes" class="form-select form-select-sm" onchange="this.form.submit()">
{% for i in range(1, 13) %}<option value="{{ i }}" {% if mes == i %}selected{% endif %}>{{ MESES[i] }}</option>{% endfor %}
</select>
<select name="anio" class="form-select form-select-sm" onchange="this.form.submit()">
{% for a in range(2024, 2031) %}<option value="{{ a }}" {% if anio == a %}selected{% endif %}>{{ a }}</option>{% endfor %}
</select>
</form>
</div>

<ul class="nav nav-pills mb-3">
<li class="nav-item"><a class="nav-link {% if tab=='global' %}active{% endif %}" href="{{ url_for('objetivos_lista', mes=mes, anio=anio, tab='global') }}"><i class="bi bi-globe"></i> Global</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='vendedores' %}active{% endif %}" href="{{ url_for('objetivos_lista', mes=mes, anio=anio, tab='vendedores') }}"><i class="bi bi-people"></i> Vendedores</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='canales' %}active{% endif %}" href="{{ url_for('objetivos_lista', mes=mes, anio=anio, tab='canales') }}"><i class="bi bi-broadcast"></i> Canales</a></li>
<li class="nav-item"><a class="nav-link {% if tab=='fijos' %}active{% endif %}" href="{{ url_for('objetivos_gastos_fijos', mes=mes, anio=anio) }}"><i class="bi bi-wallet2"></i> Gastos fijos</a></li>
</ul>

{% if tab == 'global' %}
<div class="card shadow-sm mb-3" style="border-left:4px solid #3b5bdb;">
<div class="card-body">
<h6 class="mb-1"><i class="bi bi-globe"></i> Objetivo global de {{ mes_label }} {{ anio }}</h6>
<div class="text-muted small mb-3">Meta de facturacion total</div>
<div class="row g-3 align-items-center">
<div class="col-md-5">
<form method="post" action="{{ url_for('objetivos_global') }}" class="input-group">
<input type="hidden" name="mes" value="{{ mes }}">
<input type="hidden" name="anio" value="{{ anio }}">
<span class="input-group-text">$</span>
<input type="number" step="0.01" min="0" name="monto" class="form-control" value="{{ objetivo_global or '' }}" placeholder="0">
<button class="btn btn-dark">Guardar</button>
</form>
</div>
<div class="col-md-7">
{% if objetivo_global > 0 %}
<div class="d-flex justify-content-between mb-1">
<span class="small">Facturado: <strong>${{ '{:,.0f}'.format(facturado_global).replace(',', '.') }}</strong></span>
<span class="small fw-semibold">{{ '%.1f'|format(pct_global) }}%</span>
</div>
<div class="progress-fz {% if pct_global >= 75 %}p-ok{% elif pct_global >= 50 %}p-warn{% else %}p-low{% endif %}">
<div class="progress-bar" style="width:{{ [pct_global, 100]|min }}%"></div>
</div>
<div class="mt-1 small text-muted">
{% if pct_global >= 100 %}Objetivo cumplido
{% else %}Faltan <strong>${{ '{:,.0f}'.format(objetivo_global - facturado_global).replace(',', '.') }}</strong>{% endif %}
</div>
{% else %}<p class="text-muted small mb-0">Sin objetivo cargado.</p>{% endif %}
</div>
</div>
</div>
</div>

{% elif tab == 'vendedores' %}
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-people"></i> Objetivos por vendedor</h6>
{% if filas_v %}
<table class="table align-middle mb-0">
<thead class="table-light"><tr><th>Vendedor</th><th style="width:220px;">Objetivo</th><th>Progreso</th><th class="text-end">Cumplimiento</th></tr></thead>
<tbody>
{% for f in filas_v %}
<tr>
<td><div class="fw-semibold">{{ f.usuario.nombre }}</div><div class="small text-muted">{{ f.usuario.email }}</div></td>
<td>
<form method="post" action="{{ url_for('objetivos_vendedor', uid=f.usuario.id) }}" class="input-group input-group-sm">
<input type="hidden" name="mes" value="{{ mes }}"><input type="hidden" name="anio" value="{{ anio }}">
<span class="input-group-text">$</span>
<input type="number" step="0.01" min="0" name="monto" class="form-control" value="{{ f.objetivo or '' }}" placeholder="0">
<button class="btn btn-outline-dark">OK</button>
</form>
</td>
<td>
{% if f.objetivo > 0 %}
<div class="small mb-1">${{ '{:,.0f}'.format(f.facturado).replace(',', '.') }} / ${{ '{:,.0f}'.format(f.objetivo).replace(',', '.') }}</div>
<div class="progress-fz {% if f.pct >= 75 %}p-ok{% elif f.pct >= 50 %}p-warn{% else %}p-low{% endif %}">
<div class="progress-bar" style="width:{{ [f.pct, 100]|min }}%"></div>
</div>
{% if f.gap > 0 %}<div class="small text-muted mt-1">Faltan ${{ '{:,.0f}'.format(f.gap).replace(',', '.') }}</div>{% endif %}
{% else %}<span class="text-muted small">Sin objetivo</span>{% endif %}
</td>
<td class="text-end fw-semibold">{% if f.objetivo > 0 %}{{ '%.1f'|format(f.pct) }}%{% else %}—{% endif %}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}<p class="text-muted small mb-0">No hay vendedores activos.</p>{% endif %}
</div></div>

{% elif tab == 'canales' %}
<div class="card shadow-sm"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h6 class="mb-1"><i class="bi bi-broadcast"></i> Objetivos por canal</h6>
<div class="small text-muted">Total: <strong>${{ '{:,.0f}'.format(total_obj_canal).replace(',', '.') }}</strong> objetivo · <strong>${{ '{:,.0f}'.format(total_fac_canal).replace(',', '.') }}</strong> facturado</div>
</div>
</div>
<form method="post" action="{{ url_for('objetivos_canal_guardar') }}">
<input type="hidden" name="mes" value="{{ mes }}">
<input type="hidden" name="anio" value="{{ anio }}">
<table class="table align-middle mb-3">
<thead class="table-light"><tr><th>Canal</th><th style="width:200px;">Objetivo</th><th>Progreso</th><th class="text-end">Cumplimiento</th></tr></thead>
<tbody>
{% for f in filas_c %}
<tr>
<td class="fw-semibold">{{ f.canal.nombre }}</td>
<td>
<div class="input-group input-group-sm">
<span class="input-group-text">$</span>
<input type="number" step="0.01" min="0" name="monto_canal_{{ f.canal.id }}" class="form-control" value="{{ f.objetivo or '' }}" placeholder="0">
</div>
</td>
<td>
{% if f.objetivo > 0 %}
<div class="small mb-1">${{ '{:,.0f}'.format(f.facturado).replace(',', '.') }} / ${{ '{:,.0f}'.format(f.objetivo).replace(',', '.') }}</div>
<div class="progress-fz {% if f.pct >= 75 %}p-ok{% elif f.pct >= 50 %}p-warn{% else %}p-low{% endif %}">
<div class="progress-bar" style="width:{{ [f.pct, 100]|min }}%"></div>
</div>
{% if f.gap > 0 %}<div class="small text-muted mt-1">Faltan ${{ '{:,.0f}'.format(f.gap).replace(',', '.') }}</div>{% endif %}
{% else %}<span class="text-muted small">Sin objetivo</span>{% endif %}
</td>
<td class="text-end fw-semibold">{% if f.objetivo > 0 %}{{ '%.1f'|format(f.pct) }}%{% else %}—{% endif %}</td>
</tr>
{% endfor %}
</tbody></table>
<button class="btn btn-dark">Guardar todos</button>
</form>
</div></div>
{% endif %}
{% endblock %}
'''


GASTOS_FIJOS_HTML = r'''{% extends "base.html" %}
{% block title %}Gastos fijos{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
<div>
<h4 class="mb-1">Gastos fijos de {{ mes_label }} {{ anio }}</h4>
<div class="text-muted small">Total: <strong>${{ '{:,.0f}'.format(gastos_fijos_total).replace(',', '.') }}</strong> · Se usan para el punto de equilibrio</div>
</div>
<a href="{{ url_for('objetivos_lista', mes=mes, anio=anio) }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<div class="row g-3">
<div class="col-md-4">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-plus-circle"></i> Nuevo gasto fijo</h6>
<form method="post">
<input type="hidden" name="mes" value="{{ mes }}">
<input type="hidden" name="anio" value="{{ anio }}">
<div class="mb-2">
<label class="form-label small">Descripcion *</label>
<input name="descripcion" class="form-control" required placeholder="Ej: Sueldo contador">
</div>
<div class="mb-2">
<label class="form-label small">Monto *</label>
<input type="number" step="0.01" min="0" name="monto" class="form-control" required placeholder="0">
</div>
<div class="mb-2">
<label class="form-label small">Categoria</label>
<select name="categoria_id" class="form-select">
<option value="">— Sin categoria —</option>
{% for c in categorias %}<option value="{{ c.id }}">{{ c.nombre }}</option>{% endfor %}
</select>
</div>
<div class="mb-3">
<label class="form-label small">Fecha</label>
<input type="date" name="fecha" class="form-control" value="{{ '%04d-%02d-01'|format(anio, mes) }}">
</div>
<button class="btn btn-dark w-100">Guardar gasto fijo</button>
</form>
</div></div>
</div>

<div class="col-md-8">
<div class="card shadow-sm"><div class="card-body">
<h6 class="mb-3"><i class="bi bi-list-check"></i> Gastos fijos del mes</h6>
{% if gastos_fijos %}
<table class="table table-sm mb-0">
<thead class="table-light"><tr><th>Fecha</th><th>Descripcion</th><th>Categoria</th><th class="text-end">Monto</th><th></th></tr></thead>
<tbody>
{% for g in gastos_fijos %}
<tr>
<td class="small">{{ g.fecha }}</td>
<td>{{ g.descripcion }}</td>
<td class="small text-muted">{{ g.categoria_nombre or '—' }}</td>
<td class="text-end fw-semibold">${{ '{:,.0f}'.format(g.monto).replace(',', '.') }}</td>
<td class="text-end">
<form method="post" action="{{ url_for('objetivos_gasto_fijo_toggle', id=g.id) }}" class="d-inline">
<button class="btn btn-sm btn-outline-danger" title="Quitar de fijos"><i class="bi bi-x"></i></button>
</form>
</td>
</tr>
{% endfor %}
</tbody>
<tfoot class="table-light">
<tr><td colspan="3" class="text-end fw-semibold">Total:</td><td class="text-end fw-semibold">${{ '{:,.0f}'.format(gastos_fijos_total).replace(',', '.') }}</td><td></td></tr>
</tfoot>
</table>
{% else %}
<div class="text-center py-4">
<i class="bi bi-wallet2 fs-1 text-muted"></i>
<p class="text-muted mt-2 mb-0">No hay gastos fijos cargados para este mes.</p>
<p class="small text-muted">Cargalos a la izquierda o marca gastos existentes como fijos desde <a href="{{ url_for('gastos_lista') }}">Gastos</a>.</p>
</div>
{% endif %}
</div></div>
</div>
</div>
{% endblock %}
'''


def patch_gastos_form():
    ruta = os.path.join(BASE, 'templates', 'gastos', 'form.html')
    if not os.path.exists(ruta):
        print("[upgrade35_fix] no existe gastos/form.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'es_fijo' in contenido:
        print("[upgrade35_fix] gastos/form ya tiene es_fijo"); return

    buscar_btn = '<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>'
    if buscar_btn not in contenido:
        print("[upgrade35_fix] no se encontro boton guardar"); return

    nuevo = ('<div class="col-12">\n'
             '<div class="form-check">\n'
             '<input class="form-check-input" type="checkbox" name="es_fijo" id="es_fijo" value="1" '
             '{% if gasto and gasto.es_fijo %}checked{% endif %}>\n'
             '<label class="form-check-label" for="es_fijo"><strong>Es gasto fijo</strong> '
             '(se usa para el punto de equilibrio)</label>\n'
             '</div>\n</div>\n') + buscar_btn

    contenido = contenido.replace(buscar_btn, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade35_fix] checkbox es_fijo agregado a gastos/form.html")


def patch_reportes():
    ruta = os.path.join(BASE, 'templates', 'reportes', 'index.html')
    if not os.path.exists(ruta):
        print("[upgrade35_fix] no existe reportes/index.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'bloque-canales-objetivo' in contenido:
        print("[upgrade35_fix] reportes ya tiene bloque canales"); return

    idx = contenido.rfind('{% endblock %}')
    if idx == -1:
        print("[upgrade35_fix] no se encontro endblock"); return

    bloque = '''
<div class="card shadow-sm mb-3 bloque-canales-objetivo"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-broadcast"></i> Cumplimiento por canal</h6>
<a href="{{ url_for('objetivos_lista', tab='canales') }}" class="btn btn-sm btn-outline-secondary">Configurar objetivos</a>
</div>
{% if cumplimiento_canales %}
<table class="table table-sm mb-0">
<thead class="table-light"><tr><th>Canal</th><th class="text-end">Objetivo</th><th class="text-end">Facturado</th><th class="text-end">Cumplimiento</th><th class="text-end">Estado</th></tr></thead>
<tbody>
{% for c in cumplimiento_canales %}
<tr>
<td class="fw-semibold">{{ c.nombre }}</td>
<td class="text-end">{% if c.objetivo > 0 %}${{ '{:,.0f}'.format(c.objetivo).replace(',','.') }}{% else %}—{% endif %}</td>
<td class="text-end">${{ '{:,.0f}'.format(c.facturado).replace(',','.') }}</td>
<td class="text-end">{% if c.objetivo > 0 %}<span class="fw-semibold">{{ '%.1f'|format(c.pct) }}%</span>{% else %}—{% endif %}</td>
<td class="text-end">
{% if c.objetivo > 0 and c.pct >= 100 %}<span class="badge-soft-success">Cumplido</span>
{% elif c.objetivo > 0 and c.pct >= 75 %}<span class="badge-soft-warning">{{ '%.0f'|format(c.pct) }}%</span>
{% elif c.objetivo > 0 %}<span class="badge-soft-danger">Faltan ${{ '{:,.0f}'.format(c.gap).replace(',','.') }}</span>
{% else %}<span class="text-muted small">Sin objetivo</span>{% endif %}
</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}
<p class="text-muted small mb-0">Sin canales activos o sin objetivos cargados.</p>
{% endif %}
</div></div>

<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-3">
<h6 class="mb-0"><i class="bi bi-wallet2"></i> Gastos fijos y punto de equilibrio</h6>
<a href="{{ url_for('objetivos_gastos_fijos') }}" class="btn btn-sm btn-outline-secondary">Gestionar fijos</a>
</div>
<div class="row g-3">
<div class="col-md-6">
<div class="text-muted small mb-1">Gastos fijos del periodo</div>
<div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(gastos_fijos_periodo).replace(',','.') }}</div>
{% if gastos_fijos_periodo == 0 %}
<div class="small text-muted mt-1"><i class="bi bi-info-circle"></i> Marca gastos como "fijos" para calcular el punto de equilibrio real.</div>
{% endif %}
</div>
<div class="col-md-6">
<div class="text-muted small mb-1">Punto de equilibrio (con fijos)</div>
<div class="fs-5 fw-semibold">${{ '{:,.0f}'.format(punto_eq_fijos).replace(',','.') }}</div>
<div class="small text-muted mt-1">
{% if actual.facturado >= punto_eq_fijos and punto_eq_fijos > 0 %}
<span class="text-success"><i class="bi bi-check-circle-fill"></i> Por encima del punto</span>
{% elif punto_eq_fijos > 0 %}
<span class="text-danger">Faltan ${{ '{:,.0f}'.format(punto_eq_fijos - actual.facturado).replace(',','.') }}</span>
{% else %}
Sin datos para calcular
{% endif %}
</div>
</div>
</div>
</div></div>

'''

    contenido = contenido[:idx] + bloque + contenido[idx:]
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade35_fix] bloques nuevos agregados a reportes/index.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app35; app35.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 35 FIX: version corregida (U33b) ===")
    migrar()
    escribir('app35.py', APP35_PY)
    escribir('templates/objetivos/lista.html', OBJETIVOS_LISTA)
    escribir('templates/objetivos/gastos_fijos.html', GASTOS_FIJOS_HTML)
    patch_gastos_form()
    patch_reportes()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app35.py)")


if __name__ == '__main__':
    main()