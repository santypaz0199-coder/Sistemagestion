# -*- coding: utf-8 -*-
import os, sqlite3, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade93] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade93] sin DB."); return
    conn = sqlite3.connect(db)
    
    cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
    if 'mostrar_en_catalogo' not in cols:
        conn.execute("ALTER TABLE productos ADD COLUMN mostrar_en_catalogo INTEGER DEFAULT 1")
        print("[upgrade93] + productos.mostrar_en_catalogo")
        
    conn.commit(); conn.close()


def patch_app49():
    """Filtra los productos en el catalogo publico para que solo muestre los tildados."""
    ruta = os.path.join(BASE, 'app49.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
    if 'mostrar_en_catalogo=1' in contenido:
        print("[upgrade93] app49 ya tiene el filtro")
        return
        
    # Reemplazar todas las consultas al catalogo
    contenido = contenido.replace("WHERE p.activo=1", "WHERE p.activo=1 AND p.mostrar_en_catalogo=1")
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade93] Filtro mostrar_en_catalogo aplicado a app49.py")


APP93_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required
from database import get_db
from app34 import _guardar_foto, _categorias_arbol
from datetime import date
import os

# Reemplazamos las funciones de crear y editar producto para incluir el check de catalogo
def productos_nuevo_v6():
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
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
            tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
            cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
            mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
        
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)
            
        if sku and conn.execute("SELECT id FROM productos WHERE sku=?", (sku,)).fetchone():
            flash('SKU ya existe.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        foto_nombre, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=None, valores=request.form, padres=padres, hijos=hijos)

        cur = conn.execute("""INSERT INTO productos
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto, actualizado, tiene_costo_variable, costo_variable_unitario, mostrar_en_catalogo)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'), ?, ?, ?)""",
            (sku, nombre, costo, precio, stock_actual, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat))
        
        if stock_actual > 0:
            conn.execute("INSERT INTO movimientos_stock (producto_id,tipo,cantidad,referencia,usuario_id) VALUES (?,?,?,?,?)",
                         (cur.lastrowid, 'ajuste_inicial', stock_actual, 'Carga inicial', current_user.id))
        
        conn.commit(); conn.close()
        flash('Producto creado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=None, valores={}, padres=padres, hijos=hijos)


def productos_editar_v6(id):
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
            peso_valor = float(request.form.get('peso_valor') or 0)
            peso_unidad = request.form.get('peso_unidad', 'kg')
            categoria_id = int(request.form['categoria_id']) if request.form.get('categoria_id') else None
            tiene_cv = 1 if request.form.get('tiene_costo_variable') else 0
            cv_unit = float(request.form.get('costo_variable_unitario') or 0) if tiene_cv else 0
            mostrar_cat = 1 if request.form.get('mostrar_en_catalogo') else 0
        except (ValueError, KeyError):
            flash('Revisa los numeros.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
        
        if not nombre:
            flash('Nombre obligatorio.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
            
        if sku and conn.execute("SELECT id FROM productos WHERE sku=? AND id!=?", (sku, id)).fetchone():
            flash('SKU ya existe en otro producto.', 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)

        foto_nombre = producto.get('foto')
        if request.form.get('eliminar_foto') == '1':
            if foto_nombre:
                try: os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos', foto_nombre))
                except Exception: pass
            foto_nombre = None
            
        nueva_foto, err = _guardar_foto(request.files.get('foto'))
        if err:
            flash(err, 'error')
            conn.close()
            return render_template('productos/form.html', producto=producto, valores=request.form, padres=padres, hijos=hijos)
            
        if nueva_foto:
            if foto_nombre:
                try: os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'productos', foto_nombre))
                except Exception: pass
            foto_nombre = nueva_foto

        conn.execute("""UPDATE productos SET sku=?, nombre=?, costo=?, precio=?,
            stock_minimo=?, peso_valor=?, peso_unidad=?, categoria_id=?, foto=?,
            actualizado=datetime('now'), tiene_costo_variable=?, costo_variable_unitario=?, mostrar_en_catalogo=?
            WHERE id=?""",
            (sku, nombre, costo, precio, stock_minimo, peso_valor, peso_unidad, categoria_id, foto_nombre, tiene_cv, cv_unit, mostrar_cat, id))
        conn.commit(); conn.close()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('productos_lista'))
    conn.close()
    return render_template('productos/form.html', producto=producto, valores={}, padres=padres, hijos=hijos)


app.view_functions['productos_nuevo'] = productos_nuevo_v6
app.view_functions['productos_editar'] = productos_editar_v6

# ===== CATALOGO PDF =====
@app.route('/productos/catalogo-pdf', methods=['GET', 'POST'])
@login_required
@permiso_required('productos')
def catalogo_pdf_seleccionar():
    conn = get_db()
    if request.method == 'POST':
        ids = request.form.getlist('productos')
        if not ids:
            flash('Seleccioná al menos un producto.', 'error')
            return redirect(url_for('catalogo_pdf_seleccionar'))
        
        placeholders = ','.join(['?'] * len(ids))
        productos = conn.execute(f"SELECT * FROM productos WHERE id IN ({placeholders})", ids).fetchall()
        
        # Datos de la empresa
        empresa = {}
        for k in ['empresa_nombre', 'empresa_telefono', 'empresa_email', 'empresa_web', 'empresa_logo']:
            row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
            empresa[k] = row['valor'] if row and row['valor'] else ''
        if not empresa['empresa_nombre']: empresa['empresa_nombre'] = 'Familia Zaragoza ®'
        
        conn.close()
        return render_template('productos/catalogo_pdf_print.html', productos=productos, empresa=empresa, generado=date.today())

    # GET
    productos = conn.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('productos/catalogo_pdf_form.html', productos=productos)

if __name__ == '__main__':
    pass
'''


CATALOGO_PDF_FORM = r'''{% extends "base.html" %}
{% block title %}Crear Catálogo PDF{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Crear Catálogo PDF</h4>
<div class="text-muted small">Seleccioná los productos que querés incluir en el catálogo para imprimir o enviar.</div>
</div>
<a href="{{ url_for('productos_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>

<form method="post" target="_blank">
<div class="card shadow-sm mb-3">
<div class="card-body">
<div class="form-check mb-3">
<input class="form-check-input" type="checkbox" id="select-all">
<label class="form-check-label fw-semibold" for="select-all">Seleccionar todos</label>
</div>
<div class="row g-3">
{% for p in productos %}
<div class="col-md-3">
<div class="card h-100" style="border:1px solid #e5e7eb; border-radius:8px; padding:10px;">
<div class="d-flex align-items-start gap-2">
<input class="form-check-input mt-1 prod-check" type="checkbox" name="productos" value="{{ p.id }}" id="prod-{{ p.id }}">
<label class="form-check-label w-100" for="prod-{{ p.id }}" style="cursor:pointer;">
{% if p.foto %}
<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" style="width:100%; height:80px; object-fit:cover; border-radius:6px; margin-bottom:8px;">
{% else %}
<div style="width:100%; height:80px; background:#f3f4f6; border-radius:6px; margin-bottom:8px; display:flex; align-items:center; justify-content:center; color:#9ca3af;"><i class="bi bi-image fs-3"></i></div>
{% endif %}
<div class="fw-semibold text-dark" style="font-size:0.85rem; line-height:1.2;">{{ p.nombre }}</div>
<div class="text-success fw-bold mt-1">${{ '%.2f'|format(p.precio) }}</div>
</label>
</div>
</div>
</div>
{% endfor %}
</div>
</div>
</div>
<button type="submit" class="btn btn-dark btn-lg"><i class="bi bi-file-earmark-pdf"></i> Generar Catálogo PDF</button>
</form>

<script>
document.getElementById('select-all').addEventListener('change', function() {
    document.querySelectorAll('.prod-check').forEach(c => c.checked = this.checked);
});
</script>
{% endblock %}
'''


CATALOGO_PDF_PRINT = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Catálogo - {{ empresa.empresa_nombre }}</title>
<style>
@page { size: A4; margin: 10mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; color: #1f2937; margin: 0; padding: 30px; font-size: 12px; }
.header { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 3px solid #1f2937; padding-bottom: 15px; margin-bottom: 25px; }
.header .empresa img { max-height: 50px; margin-bottom: 8px; }
.header .empresa h1 { margin: 0 0 4px 0; font-size: 24px; letter-spacing: -.02em; }
.header .empresa .info { font-size: 11px; color: #6b7280; line-height: 1.5; }
.header .titulo { text-align: right; }
.header .titulo h2 { margin: 0 0 4px 0; font-size: 20px; color: #3b5bdb; text-transform: uppercase; letter-spacing: .1em; }
.header .titulo .fecha { font-size: 10px; color: #9ca3af; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
.card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; page-break-inside: avoid; display: flex; flex-direction: column; }
.card-img { width: 100%; height: 140px; background: #f9fafb; border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.card-img img { width: 100%; height: 100%; object-fit: contain; }
.card-title { font-weight: 600; font-size: 13px; line-height: 1.2; margin-bottom: 5px; flex-grow: 1; }
.card-price { font-size: 15px; font-weight: 700; color: #059669; }
.acciones { position: fixed; top: 20px; right: 20px; display: flex; gap: 8px; z-index: 100; }
.btn-accion { padding: 10px 18px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.15); }
.btn-imprimir { background: #3b5bdb; color: #fff; }
.btn-cerrar { background: #e5e7eb; color: #1f2937; }
@media print {
  body { padding: 0; }
  .acciones { display: none; }
  .card { border: 1px solid #d1d5db; }
}
</style>
</head>
<body>

<div class="acciones">
<button class="btn-accion btn-imprimir" onclick="window.print()">🖨️ Imprimir / Guardar PDF</button>
<button class="btn-accion btn-cerrar" onclick="window.close()">✕ Cerrar</button>
</div>

<div class="header">
<div class="empresa">
{% if empresa.empresa_logo %}
<img src="{{ url_for('ver_logo_empresa') }}" alt="{{ empresa.empresa_nombre }}">
{% endif %}
<h1>{{ empresa.empresa_nombre }}</h1>
<div class="info">
{% if empresa.empresa_telefono %}{{ empresa.empresa_telefono }}<br>{% endif %}
{% if empresa.empresa_email %}{{ empresa.empresa_email }}<br>{% endif %}
{% if empresa.empresa_web %}{{ empresa.empresa_web }}{% endif %}
</div>
</div>
<div class="titulo">
<h2>Catálogo</h2>
<div class="fecha">Generado el {{ generado.strftime('%d/%m/%Y') }}</div>
</div>
</div>

<div class="grid">
{% for p in productos %}
<div class="card">
<div class="card-img">
{% if p.foto %}
<img src="{{ url_for('productos_ver_foto', nombre=p.foto) }}" alt="{{ p.nombre }}">
{% else %}
<i class="bi bi-image" style="font-size:2rem; color:#d1d5db;"></i>
{% endif %}
</div>
<div class="card-title">{{ p.nombre }}</div>
<div class="card-price">${{ '%.2f'|format(p.precio) }}</div>
</div>
{% endfor %}
</div>

</body>
</html>
'''


def patch_lista_productos():
    ruta = os.path.join(BASE, 'templates', 'productos', 'lista.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'catalogo_pdf_seleccionar' in contenido:
        print("[upgrade93] Boton PDF ya estaba en la lista")
        return

    buscar = '<a href="{{ url_for(\'productos_ranking\') }}" class="btn btn-outline-primary btn-sm"><i class="bi bi-trophy"></i> Ranking</a>'
    if buscar in contenido:
        nuevo = buscar + '\n<a href="{{ url_for(\'catalogo_pdf_seleccionar\') }}" class="btn btn-outline-danger btn-sm"><i class="bi bi-file-earmark-pdf"></i> Crear Catálogo PDF</a>'
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade93] Boton 'Crear Catálogo PDF' agregado a la lista")
    else:
        print("[upgrade93] ADVERTENCIA: no se encontro el boton Ranking")

def patch_form_producto():
    ruta = os.path.join(BASE, 'templates', 'productos', 'form.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'mostrar_en_catalogo' in contenido:
        print("[upgrade93] Checkbox catálogo ya estaba en el form")
        return

    buscar = '<div class="col-md-12">\n<label class="form-label d-block">Tags *</label>'
    nuevo = '''<div class="col-md-12 mt-3">
<div class="form-check form-switch">
<input class="form-check-input" type="checkbox" name="mostrar_en_catalogo" id="mostrar_en_catalogo" value="1" {% if v.get('mostrar_en_catalogo') != 0 %}checked{% endif %}>
<label class="form-check-label fw-semibold" for="mostrar_en_catalogo">Mostrar en el catálogo público (B2B)</label>
</div>
</div>

''' + buscar

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade93] Switch 'Mostrar en catálogo' agregado al form de producto")
    else:
        print("[upgrade93] ADVERTENCIA: no se encontró el bloque de tags en form.html")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 93: Visibilidad en catálogo + PDF Catálogo ===")
    migrar()
    escribir('app93.py', APP93_PY)
    escribir('templates/productos/catalogo_pdf_form.html', CATALOGO_PDF_FORM)
    escribir('templates/productos/catalogo_pdf_print.html', CATALOGO_PDF_PRINT)
    patch_app49()
    patch_lista_productos()
    patch_form_producto()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()