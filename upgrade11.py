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
    print(f"[upgrade11] escrito: {relpath}")


APP11_PY = r'''
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
'''


PRODUCTOS_FORM = r'''{% extends "base.html" %}
{% block title %}Producto{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if producto and not valores else ('Editar' if producto else 'Nuevo') }} producto</h4>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (producto if producto else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-4">
<label class="form-label">SKU</label>
<input name="sku" class="form-control" value="{{ v.get('sku') or '' }}">
</div>
<div class="col-md-8">
<label class="form-label">Nombre *</label>
<input name="nombre" class="form-control" required value="{{ v.get('nombre') or '' }}">
</div>
<div class="col-md-4">
<label class="form-label">Costo</label>
<input type="number" step="0.01" name="costo" class="form-control" value="{{ v.get('costo', 0) or 0 }}">
</div>
<div class="col-md-4">
<label class="form-label">Precio</label>
<input type="number" step="0.01" name="precio" class="form-control" value="{{ v.get('precio', 0) or 0 }}">
</div>
<div class="col-md-4">
<label class="form-label">Stock minimo</label>
<input type="number" step="0.01" name="stock_minimo" class="form-control" value="{{ v.get('stock_minimo', 0) or 0 }}">
</div>
{% if not producto %}
<div class="col-md-4">
<label class="form-label">Stock inicial</label>
<input type="number" step="0.01" name="stock_actual" class="form-control" value="0">
<div class="form-text">Solo al crear el producto.</div>
</div>
{% endif %}
<div class="col-md-4">
<label class="form-label">Peso del producto</label>
<div class="input-group">
<input type="number" step="0.01" min="0" name="peso_valor" class="form-control" value="{{ v.get('peso_valor', 0) or 0 }}">
<select name="peso_unidad" class="form-select" style="max-width:80px;">
<option value="kg" {% if (v.get('peso_unidad') or 'kg') == 'kg' %}selected{% endif %}>kg</option>
<option value="g" {% if v.get('peso_unidad') == 'g' %}selected{% endif %}>g</option>
</select>
</div>
<div class="form-text">Se usa para calcular kilos por pedido.</div>
</div>
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
'''


CLIENTES_FORM = r'''{% extends "base.html" %}
{% block title %}Cliente{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if cliente else 'Nuevo' }} cliente</h4>
<a href="{{ url_for('clientes_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (cliente if cliente else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Nombre completo *</label>
<input name="nombre_completo" class="form-control" required value="{{ v.get('nombre_completo') or '' }}">
</div>
<div class="col-md-3">
<label class="form-label">Tipo doc</label>
<select name="tipo_doc" class="form-select">
<option value="">--</option>
{% for t in ['CUIT','CUIL','DNI'] %}
<option value="{{ t }}" {% if v.get('tipo_doc') == t %}selected{% endif %}>{{ t }}</option>
{% endfor %}
</select>
</div>
<div class="col-md-3">
<label class="form-label">Numero</label>
<input name="nro_doc" class="form-control" value="{{ v.get('nro_doc') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Email</label>
<input type="email" name="email" class="form-control" value="{{ v.get('email') or '' }}">
</div>
<div class="col-md-6">
<label class="form-label">Telefono</label>
<input name="telefono" class="form-control" value="{{ v.get('telefono') or '' }}">
</div>
<div class="col-md-4">
<label class="form-label">Provincia</label>
<input name="provincia" class="form-control" value="{{ v.get('provincia') or '' }}">
</div>
<div class="col-md-4">
<label class="form-label">Localidad</label>
<input name="localidad" class="form-control" value="{{ v.get('localidad') or '' }}">
</div>
<div class="col-md-4">
<label class="form-label">Codigo postal</label>
<input name="codigo_postal" class="form-control" value="{{ v.get('codigo_postal') or '' }}">
</div>
<div class="col-md-12">
<label class="form-label d-block">Tags *</label>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_minorista" id="es_minorista" {% if v.get('es_minorista') %}checked{% endif %}>
<label class="form-check-label" for="es_minorista">Minorista</label>
</div>
<div class="form-check form-check-inline">
<input class="form-check-input" type="checkbox" name="es_mayorista" id="es_mayorista" {% if v.get('es_mayorista') %}checked{% endif %}>
<label class="form-check-label" for="es_mayorista">Mayorista</label>
</div>
<div class="form-text">Un cliente puede ser ambos a la vez.</div>
</div>
<div class="col-12">
<label class="form-label">Notas</label>
<textarea name="notas" class="form-control" rows="2">{{ v.get('notas') or '' }}</textarea>
</div>
</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app11; app11.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 11: Fix formularios de edicion (cliente/producto) ===")
    escribir('app11.py', APP11_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    escribir('templates/clientes/form.html', CLIENTES_FORM)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app11.py)")


if __name__ == '__main__':
    main()