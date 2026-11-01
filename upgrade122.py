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
    print(f"[upgrade122] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    # Crear configuraciones por defecto si no existen
    configs = [
        ('portada_imagen', ''),
        ('portada_titulo', 'Yerba Mate Premium'),
        ('portada_subtitulo', 'Elaborada con paciencia, siguiendo el tradicional método Barbacuá.')
    ]
    for k, v in configs:
        if not conn.execute("SELECT clave FROM configuracion WHERE clave=?", (k,)).fetchone():
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))
            print(f"[upgrade122] + config {k}")
            
    conn.commit(); conn.close()


APP122_PY = r'''
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required
from app48 import app
from app import admin_required
from database import get_db
from werkzeug.utils import secure_filename
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PORTADAS_DIR = os.path.join(BASE, 'uploads', 'portadas')
os.makedirs(PORTADAS_DIR, exist_ok=True)

EXT_IMG = {'png', 'jpg', 'jpeg', 'webp'}
MAX_SIZE = 5 * 1024 * 1024 # 5MB

def _get_config(clave, default=''):
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row['valor'] if row and row['valor'] is not None else default

def _set_config(clave, valor):
    conn = get_db()
    conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, valor))
    conn.commit(); conn.close()

@app.route('/api/portada/<path:nombre>')
def ver_portada(nombre):
    ruta = os.path.join(PORTADAS_DIR, secure_filename(nombre))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)

@app.route('/b2b/portada', methods=['GET', 'POST'])
@login_required
@admin_required
def b2b_portada():
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        subtitulo = request.form.get('subtitulo', '').strip()
        
        _set_config('portada_titulo', titulo)
        _set_config('portada_subtitulo', subtitulo)

        # Manejo de imagen
        actual_imagen = _get_config('portada_imagen')
        if request.form.get('eliminar_imagen') == '1':
            if actual_imagen:
                try: os.remove(os.path.join(PORTADAS_DIR, actual_imagen))
                except: pass
            _set_config('portada_imagen', '')
            flash('Imagen de portada eliminada.', 'success')
        else:
            file = request.files.get('imagen')
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in EXT_IMG:
                    flash('Formato no permitido. Usa JPG, PNG o WEBP.', 'error')
                    return redirect(url_for('b2b_portada'))
                
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_SIZE:
                    flash('La imagen supera 5 MB.', 'error')
                    return redirect(url_for('b2b_portada'))

                from datetime import datetime
                nombre = f"portada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                file.save(os.path.join(PORTADAS_DIR, nombre))
                
                if actual_imagen:
                    try: os.remove(os.path.join(PORTADAS_DIR, actual_imagen))
                    except: pass
                _set_config('portada_imagen', nombre)
                flash('Imagen de portada actualizada.', 'success')

        flash('Textos de portada guardados.', 'success')
        return redirect(url_for('b2b_portada'))

    cfg = {
        'titulo': _get_config('portada_titulo'),
        'subtitulo': _get_config('portada_subtitulo'),
        'imagen': _get_config('portada_imagen')
    }
    return render_template('b2b/portada.html', cfg=cfg)
'''

B2B_PORTADA_HTML = r'''{% extends "base.html" %}
{% block title %}Portada del Catálogo{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<div>
<h4 class="mb-1">Portada del Catálogo</h4>
<div class="text-muted small">Personalizá la imagen de fondo, el título y el subtítulo de la página principal del catálogo B2B.</div>
</div>
<a href="{{ url_for('b2b_index', tab='cuentas') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver a B2B</a>
</div>

<div class="card shadow-sm"><div class="card-body">
<form method="post" enctype="multipart/form-data">
<div class="row g-3">
<div class="col-md-6">
<label class="form-label">Título principal</label>
<input name="titulo" class="form-control" value="{{ cfg.titulo }}" placeholder="Ej: Yerba Mate Premium">
</div>
<div class="col-md-6">
<label class="form-label">Subtítulo</label>
<input name="subtitulo" class="form-control" value="{{ cfg.subtitulo }}" placeholder="Ej: Elaborada con paciencia...">
</div>

<div class="col-12 mt-4">
<label class="form-label fw-semibold">Imagen de Fondo (Banner)</label>
<div class="form-text mb-2">Recomendado: Imagen horizontal, alta calidad (JPG o PNG). Tamaño ideal: 1920x800px. Máx 5MB.</div>
<div class="d-flex align-items-start gap-3">
{% if cfg.imagen %}
<div class="text-center">
<img src="{{ url_for('ver_portada', nombre=cfg.imagen) }}" style="max-width:300px; max-height:150px; object-fit:cover; border-radius:8px; border:1px solid #e5e7eb;">
<div class="form-check mt-2">
<input class="form-check-input" type="checkbox" name="eliminar_imagen" value="1" id="eliminar_imagen">
<label class="form-check-label small text-danger" for="eliminar_imagen">Eliminar imagen actual</label>
</div>
</div>
{% endif %}
<div class="flex-grow-1">
<input type="file" name="imagen" class="form-control" accept="image/png, image/jpeg, image/webp">
</div>
</div>
</div>
</div>
<div class="mt-4">
<button type="submit" class="btn btn-dark"><i class="bi bi-save"></i> Guardar Portada</button>
</div>
</form>
</div></div>
{% endblock %}
'''

def patch_b2b_menu():
    ruta = os.path.join(BASE, 'templates', 'mayoristas', 'lista.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    if 'b2b_portada' in contenido:
        return

    buscar = '<a href="{{ url_for(\'b2b_envios\') }}" class="btn btn-outline-dark btn-sm"><i class="bi bi-truck"></i> Escala de Envíos</a>'
    nuevo = buscar + '\n<a href="{{ url_for(\'b2b_portada\') }}" class="btn btn-outline-dark btn-sm"><i class="bi bi-image"></i> Portada del Catálogo</a>'
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade122] Boton 'Portada del Catálogo' agregado a B2B")

def patch_app49():
    ruta = os.path.join(BASE, 'app49.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    # 1. Inyectar la obtención de la config en la ruta index
    buscar_index = "    productos = conn.execute(query, params).fetchall()\n\n    conn.close()"
    nuevo_index = """    productos = conn.execute(query, params).fetchall()

    # Obtener config de portada
    portada_imagen = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_imagen'").fetchone()
    portada_imagen = portada_imagen['valor'] if portada_imagen and portada_imagen['valor'] else None
    portada_titulo = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_titulo'").fetchone()
    portada_titulo = portada_titulo['valor'] if portada_titulo and portada_titulo['valor'] else 'Yerba Mate Premium'
    portada_subtitulo = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_subtitulo'").fetchone()
    portada_subtitulo = portada_subtitulo['valor'] if portada_subtitulo and portada_subtitulo['valor'] else ''

    conn.close()"""
    
    if buscar_index in contenido:
        contenido = contenido.replace(buscar_index, nuevo_index)

    # 2. Pasar las variables al render_template
    buscar_render = "busqueda=busqueda)"
    nuevo_render = "busqueda=busqueda, portada_imagen=portada_imagen, portada_titulo=portada_titulo, portada_subtitulo=portada_subtitulo)"
    
    if buscar_render in contenido:
        contenido = contenido.replace(buscar_render, nuevo_render)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade122] app49.py actualizado con las variables de portada")

def patch_catalogo_index():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'index.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'hero-portada-dinamica' in contenido:
        return

    # Reemplazar el hero-title viejo por el nuevo con imagen opcional
    buscar_hero = '''  <!-- TÍTULO PRINCIPAL -->
  <div class="hero-title">
    <h1>Yerba Mate Premium</h1>
    <p>Elaborada con paciencia, siguiendo el tradicional método Barbacuá.</p>
  </div>'''

    nuevo_hero = '''  <!-- PORTADA DINÁMICA -->
  {% if portada_imagen %}
  <div class="hero-portada-dinamica" style="background-image: linear-gradient(rgba(10,10,10,0.4), rgba(10,10,10,0.7)), url('{{ url_for('ver_portada', nombre=portada_imagen) }}'); background-size: cover; background-position: center; padding: 6rem 1rem; border-radius: 16px; text-align: center; margin-top: 1rem; margin-bottom: 2rem; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
    <h1 style="font-size: 3rem; font-weight: 300; color: #fff; margin-bottom: 0.5rem; text-shadow: 0 2px 8px rgba(0,0,0,0.6);">{{ portada_titulo }}</h1>
    {% if portada_subtitulo %}
    <p style="font-size: 1.1rem; color: #e5e5e5; max-width: 600px; margin: 0 auto; text-shadow: 0 2px 4px rgba(0,0,0,0.6);">{{ portada_subtitulo }}</p>
    {% endif %}
  </div>
  {% else %}
  <div class="hero-title">
    <h1>{{ portada_titulo }}</h1>
    {% if portada_subtitulo %}
    <p>{{ portada_subtitulo }}</p>
    {% endif %}
  </div>
  {% endif %}'''

    if buscar_hero in contenido:
        contenido = contenido.replace(buscar_hero, nuevo_hero)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade122] Home del catálogo actualizada para mostrar la portada dinámica")
    else:
        print("[upgrade122] ADVERTENCIA: no se encontró el bloque hero-title en la home")

RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 122: Portada Dinámica para el Catálogo ===")
    migrar()
    escribir('app122.py', APP122_PY)
    escribir('templates/b2b/portada.html', B2B_PORTADA_HTML)
    patch_b2b_menu()
    patch_app49()
    patch_catalogo_index()
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()