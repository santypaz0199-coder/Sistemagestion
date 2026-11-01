
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
