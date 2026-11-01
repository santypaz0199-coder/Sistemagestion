# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade34] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade34] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'tiene_costo_variable' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN tiene_costo_variable INTEGER DEFAULT 0")
        print("[upgrade34] + productos.tiene_costo_variable")
    if 'costo_variable_unitario' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN costo_variable_unitario REAL DEFAULT 0")
        print("[upgrade34] + productos.costo_variable_unitario")

    # Actualizar trigger para incluir costo variable
    conn.execute("DROP TRIGGER IF EXISTS trg_orden_items_costo")
    conn.execute("""
        CREATE TRIGGER trg_orden_items_costo
        AFTER INSERT ON orden_items
        WHEN NEW.costo_unitario IS NULL OR NEW.costo_unitario = 0
        BEGIN
            UPDATE orden_items
            SET costo_unitario = COALESCE((
                SELECT costo + COALESCE(
                    CASE WHEN tiene_costo_variable = 1 THEN costo_variable_unitario ELSE 0 END, 0
                )
                FROM productos WHERE id = NEW.producto_id
            ), 0)
            WHERE id = NEW.id;
        END
    """)
    print("[upgrade34] trigger actualizado (costo + costo variable)")

    conn.commit(); conn.close()


APP34_PY = r'''
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app32 import app
from app import permiso_required
from database import get_db
from app16 import _guardar_foto, _categorias_arbol


def _peso_data(form):
    try:
        pv = float(form.get('peso_valor') or 0)
    except ValueError:
        pv = 0
    return pv, form.get('peso_unidad', 'kg')


def _costo_variable(form):
    tiene = 1 if form.get('tiene_costo_variable') else 0
    try:
        cv = float(form.get('costo_variable_unitario') or 0)
    except ValueError:
        cv = 0
    if not tiene:
        cv = 0
    return tiene, cv


def productos_nuevo_v5():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_actual = float(request.form.get('stock_actual') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor, peso_unidad = _peso_data(request.form)
            tiene_cv, cv_unit = _costo_variable(request.form)
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            flash('SKU ya existe.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form,
                                   padres=padres, hijos=hijos)

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo,
             peso_valor, peso_unidad, categoria_id, foto, actualizado,
             tiene_costo_variable, costo_variable_unitario)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo,
             peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit))
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=None, valores={},
                           padres=padres, hijos=hijos)


def productos_editar_v5(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))
    producto = dict(row)
    padres, hijos = _categorias_arbol(conn)

    if request.method == 'POST':
        try:
            sku = request.form.get('sku', '').strip() or None
            nombre = request.form['nombre'].strip()
            costo = float(request.form.get('costo') or 0)
            precio = float(request.form.get('precio') or 0)
            stock_minimo = float(request.form.get('stock_minimo') or 0)
            peso_valor, peso_unidad = _peso_data(request.form)
            tiene_cv, cv_unit = _costo_variable(request.form)
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if sku and conn.execute("SELECT id FROM productos WHERE sku=? AND id!=?", (sku, id)).fetchone():
            flash('SKU ya existe en otro producto.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)

        foto_nombre = producto.get('foto')
        if request.form.get('eliminar_foto') == '1':
            if foto_nombre:
                try: os.remove(os.path.join(BASE_UPLOADS, foto_nombre))
                except Exception: pass
            foto_nombre = None
        nueva_foto, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form,
                                   padres=padres, hijos=hijos)
        if nueva_foto:
            if foto_nombre:
                try: os.remove(os.path.join(BASE_UPLOADS, foto_nombre))
                except Exception: pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad,
             categoria_id, foto_nombre, tiene_cv, cv_unit, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={},
                           padres=padres, hijos=hijos)


import os
BASE_UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos')

app.view_functions['productos_nuevo'] = productos_nuevo_v5
app.view_functions['productos_editar'] = productos_editar_v5


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
'''


PRODUCTOS_FORM = r'''{% extends "base.html" %}
{% block title %}Producto{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">{{ 'Editar' if producto else 'Nuevo' }} producto</h4>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
{% set v = valores if valores else (producto if producto else {}) %}
<div class="card shadow-sm"><div class="card-body">
<form method="post" enctype="multipart/form-data">
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
<label class="form-label">Costo del producto</label>
<input type="number" step="0.01" name="costo" id="costo-input" class="form-control" value="{{ v.get('costo', 0) or 0 }}" onchange="updateMargen()">
<div class="form-text">Lo que pagas al proveedor</div>
</div>
<div class="col-md-4">
<label class="form-label">Precio de venta</label>
<input type="number" step="0.01" name="precio" id="precio-input" class="form-control" value="{{ v.get('precio', 0) or 0 }}" onchange="updateMargen()">
</div>
<div class="col-md-4">
<label class="form-label">Stock minimo</label>
<input type="number" step="0.01" name="stock_minimo" class="form-control" value="{{ v.get('stock_minimo', 0) or 0 }}">
</div>

{% if not producto %}
<div class="col-md-4">
<label class="form-label">Stock inicial</label>
<input type="number" step="0.01" name="stock_actual" class="form-control" value="0">
<div class="form-text">Solo al crear.</div>
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
</div>

<div class="col-md-8">
<label class="form-label">Categoria</label>
<select name="categoria_id" class="form-select">
<option value="">— Sin categoria —</option>
{% for p in padres %}
<option value="{{ p.id }}" {% if v.get('categoria_id') == p.id %}selected{% endif %}>{{ p.nombre }}</option>
{% for h in hijos.get(p.id, []) %}
<option value="{{ h.id }}" {% if v.get('categoria_id') == h.id %}selected{% endif %}>&nbsp;&nbsp;— {{ h.nombre }}</option>
{% endfor %}
{% endfor %}
</select>
</div>

<!-- COSTO VARIABLE -->
<div class="col-12">
<div class="border rounded p-3" style="background:#f8f9fc;">
<div class="form-check mb-2">
<input class="form-check-input" type="checkbox" name="tiene_costo_variable" id="tiene_cv" {% if v.get('tiene_costo_variable') %}checked{% endif %} onchange="toggleCV()">
<label class="form-check-label fw-semibold" for="tiene_cv">
<i class="bi bi-box"></i> Este producto tiene costo variable adicional
</label>
</div>
<div class="form-text mb-2">Ej: packaging, bolsa, flete logistico que pagas solo cuando vendes.</div>
<div id="bloque-cv" class="row g-2 mt-1" {% if not v.get('tiene_costo_variable') %}style="display:none;"{% endif %}>
<div class="col-md-4">
<label class="form-label">Costo variable por unidad</label>
<input type="number" step="0.01" min="0" name="costo_variable_unitario" id="cv-input" class="form-control" value="{{ v.get('costo_variable_unitario', 0) or 0 }}" onchange="updateMargen()">
<div class="form-text">Se suma al costo al calcular el margen.</div>
</div>
<div class="col-md-8">
<div class="border rounded p-2" style="background:#fff;">
<div class="small text-muted mb-1">Costo total unitario</div>
<div class="fs-5 fw-semibold" id="costo-total-view">$0.00</div>
<div class="small" id="margen-view"></div>
</div>
</div>
</div>
</div>
</div>

<div class="col-12">
<label class="form-label">Foto del producto</label>
<div class="d-flex align-items-start gap-3">
{% if producto and producto.get('foto') %}
<div>
<img src="{{ url_for('productos_ver_foto', nombre=producto.foto) }}" style="width:120px;height:120px;object-fit:cover;border-radius:12px;border:1px solid #e5e7eb;">
<div class="form-check mt-2">
<input class="form-check-input" type="checkbox" name="eliminar_foto" value="1" id="eliminar_foto">
<label class="form-check-label small text-danger" for="eliminar_foto">Eliminar foto actual</label>
</div>
</div>
{% endif %}
<div class="flex-grow-1">
<input type="file" name="foto" class="form-control" accept="image/png,image/jpeg,image/webp,image/gif">
<div class="form-text">JPG, PNG, WEBP o GIF. Max 5 MB.</div>
</div>
</div>
</div>

</div>
<div class="mt-4"><button class="btn btn-dark">Guardar</button></div>
</form></div></div>

<script>
function toggleCV() {
  const check = document.getElementById('tiene_cv');
  document.getElementById('bloque-cv').style.display = check.checked ? 'flex' : 'none';
  if (!check.checked) {
    document.getElementById('cv-input').value = 0;
  }
  updateMargen();
}

function updateMargen() {
  const costo = parseFloat(document.getElementById('costo-input').value) || 0;
  const cv = document.getElementById('tiene_cv').checked ? (parseFloat(document.getElementById('cv-input').value) || 0) : 0;
  const precio = parseFloat(document.getElementById('precio-input').value) || 0;
  const total = costo + cv;
  document.getElementById('costo-total-view').textContent = '$' + total.toFixed(2);
  const margen_view = document.getElementById('margen-view');
  if (precio > 0) {
    const margen = precio - total;
    const pct = (margen / precio * 100);
    const color = margen >= 0 ? 'text-success' : 'text-danger';
    margen_view.className = 'small ' + color;
    margen_view.innerHTML = 'Margen unitario: <strong>$' + margen.toFixed(2) + '</strong> (' + pct.toFixed(1) + '%)';
  } else {
    margen_view.textContent = '';
  }
}

document.addEventListener('DOMContentLoaded', () => { updateMargen(); });
</script>
{% endblock %}
'''


def patch_lista_productos():
    """Agrega un icono en la lista de productos si tiene costo variable."""
    ruta = os.path.join(BASE, 'templates', 'productos', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade34] no existe productos/lista.html")
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'costo-variable-badge' in contenido:
        print("[upgrade34] badge de costo variable ya estaba")
        return

    # Insertar badge despues del nombre del producto
    buscar = '<td class="fw-semibold">{{ p.nombre }}</td>'
    if buscar not in contenido:
        print("[upgrade34] no se encontro el nombre del producto en la lista")
        return

    nuevo = ('<td class="fw-semibold">{{ p.nombre }}'
             '{% if p.tiene_costo_variable %} '
             '<span class="badge bg-light text-dark border costo-variable-badge" style="font-size:.65rem;" title="Costo variable: ${{ \'%.2f\'|format(p.costo_variable_unitario or 0) }}">'
             '<i class="bi bi-box"></i> +${{ \'%g\'|format(p.costo_variable_unitario or 0) }}</span>'
             '{% endif %}</td>')
    contenido = contenido.replace(buscar, nuevo, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade34] badge agregado a productos/lista.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app34; app34.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 34: Costos variables por producto (U33a) ===")
    migrar()
    escribir('app34.py', APP34_PY)
    escribir('templates/productos/form.html', PRODUCTOS_FORM)
    patch_lista_productos()
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat (ahora corre app34.py)")


if __name__ == '__main__':
    main()