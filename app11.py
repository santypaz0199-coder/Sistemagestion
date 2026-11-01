
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app10 import app
from app import permiso_required
from database import get_db


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('clientes')
def clientes_editar_v2(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))
    cliente = dict(row)

    if request.method == 'POST':
        d = {
            'nombre_completo': request.form.get('nombre_completo', '').strip(),
            'tipo_doc': request.form.get('tipo_doc', '').strip(),
            'nro_doc': request.form.get('nro_doc', '').strip(),
            'provincia': request.form.get('provincia', '').strip(),
            'localidad': request.form.get('localidad', '').strip(),
            'codigo_postal': request.form.get('codigo_postal', '').strip(),
            'email': request.form.get('email', '').strip(),
            'telefono': request.form.get('telefono', '').strip(),
            'es_minorista': 1 if request.form.get('es_minorista') else 0,
            'es_mayorista': 1 if request.form.get('es_mayorista') else 0,
            'notas': request.form.get('notas', '').strip(),
        }
        if not d['nombre_completo'] or not (d['es_minorista'] or d['es_mayorista']):
            flash('Nombre y al menos un tag son obligatorios.', 'error')
            conn.close()
            return render_template('clientes/form.html', cliente=cliente, valores=d)
        conn.execute("""UPDATE clientes SET
            nombre_completo=?, tipo_doc=?, nro_doc=?, provincia=?, localidad=?, codigo_postal=?,
            email=?, telefono=?, es_minorista=?, es_mayorista=?, notas=? WHERE id=?""",
            (d['nombre_completo'], d['tipo_doc'], d['nro_doc'], d['provincia'],
             d['localidad'], d['codigo_postal'], d['email'], d['telefono'],
             d['es_minorista'], d['es_mayorista'], d['notas'], id))
        conn.commit(); conn.close()
        flash('Cliente actualizado.', 'success')
        return redirect(url_for('clientes_lista'))

    conn.close()
    return render_template('clientes/form.html', cliente=cliente, valores={})


app.view_functions['clientes_editar'] = clientes_editar_v2


@app.route('/productos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def productos_editar_v3(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)

    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
        except ValueError:
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form)
        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=? WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))

    conn.close()
    return render_template('productos/form.html', producto=producto, valores={})


app.view_functions['productos_editar'] = productos_editar_v3


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
