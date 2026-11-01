
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app18 import app
from app import permiso_required
from database import get_db


def _provincias(conn):
    return conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()


def _localidades_por_provincia(conn):
    rows = conn.execute("SELECT id, provincia_id, nombre FROM localidades WHERE activo=1 ORDER BY nombre").fetchall()
    resultado = {}
    for r in rows:
        resultado.setdefault(r['provincia_id'], []).append({'id': r['id'], 'nombre': r['nombre']})
    return resultado


@app.route('/api/localidades/por-provincia/<int:pid>')
@login_required
def api_localidades_por_provincia(pid):
    conn = get_db()
    rows = conn.execute("SELECT id, nombre FROM localidades WHERE provincia_id=? AND activo=1 ORDER BY nombre",
                        (pid,)).fetchall()
    conn.close()
    return jsonify([{'id': r['id'], 'nombre': r['nombre']} for r in rows])


@app.route('/api/localidades/agregar', methods=['POST'])
@login_required
def api_localidad_agregar():
    nombre = (request.json or {}).get('nombre', '').strip()
    provincia_id = (request.json or {}).get('provincia_id')
    if not nombre or not provincia_id:
        return jsonify({'ok': False, 'error': 'Nombre y provincia son obligatorios'}), 400
    try:
        provincia_id = int(provincia_id)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Provincia invalida'}), 400
    conn = get_db()
    # Verificar que la provincia exista
    if not conn.execute("SELECT id FROM provincias WHERE id=?", (provincia_id,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'error': 'Provincia no encontrada'}), 404
    # Verificar si ya existe
    existente = conn.execute("SELECT id FROM localidades WHERE provincia_id=? AND lower(nombre)=lower(?)",
                             (provincia_id, nombre)).fetchone()
    if existente:
        conn.close()
        return jsonify({'ok': True, 'id': existente[0], 'nombre': nombre, 'existia': True})
    cur = conn.execute("INSERT INTO localidades (provincia_id, nombre) VALUES (?, ?)", (provincia_id, nombre))
    new_id = cur.lastrowid
    conn.commit(); conn.close()
    return jsonify({'ok': True, 'id': new_id, 'nombre': nombre, 'existia': False})


def _datos_cliente_form():
    try:
        provincia_id = int(request.form.get('provincia_id') or 0) or None
    except ValueError:
        provincia_id = None
    try:
        localidad_id = int(request.form.get('localidad_id') or 0) or None
    except ValueError:
        localidad_id = None
    return {
        'nombre_completo': request.form.get('nombre_completo', '').strip(),
        'tipo_doc': request.form.get('tipo_doc', '').strip(),
        'nro_doc': request.form.get('nro_doc', '').strip(),
        'provincia_id': provincia_id,
        'localidad_id': localidad_id,
        'codigo_postal': request.form.get('codigo_postal', '').strip(),
        'email': request.form.get('email', '').strip(),
        'telefono': request.form.get('telefono', '').strip(),
        'es_minorista': 1 if request.form.get('es_minorista') else 0,
        'es_mayorista': 1 if request.form.get('es_mayorista') else 0,
        'notas': request.form.get('notas', '').strip(),
    }


def _render_form(conn, cliente, valores):
    provincias = _provincias(conn)
    locs = _localidades_por_provincia(conn)
    return render_template('clientes/form.html', cliente=cliente, valores=valores,
                           provincias=provincias, localidades_por_provincia=locs)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_nuevo_v2():
    conn = get_db()
    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form(get_db(), None, d) if False else _render_form(_reopen(), None, d)
        # Guardar
        conn2 = get_db()
        conn2.execute("""INSERT INTO clientes
            (nombre_completo, tipo_doc, nro_doc, provincia_id, localidad_id, codigo_postal,
             email, telefono, es_minorista, es_mayorista, notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'], d['notas']))
        conn2.commit(); conn2.close()
        conn.close()
        flash('Cliente creado.', 'success')
        return redirect(url_for('clientes_lista'))
    conn.close()
    return _render_form(get_db(), None, {})


def _reopen():
    return get_db()


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_editar_v3(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))
    cliente = dict(row)

    if request.method == 'POST':
        d = _datos_cliente_form()
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return _render_form(get_db(), cliente, d)
        conn.execute("""UPDATE clientes SET
            nombre_completo=?, tipo_doc=?, nro_doc=?, provincia_id=?, localidad_id=?, codigo_postal=?,
            email=?, telefono=?, es_minorista=?, es_mayorista=?, notas=? WHERE id=?""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia_id'], d['localidad_id'],
             d['codigo_postal'], d['email'], d['telefono'], d['es_minorista'], d['es_mayorista'],
             d['notas'], id))
        conn.commit(); conn.close()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('clientes_lista'))

    conn.close()
    return _render_form(get_db(), cliente, {})


app.view_functions['clientes_nuevo'] = clientes_nuevo_v2
app.view_functions['clientes_editar'] = clientes_editar_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
