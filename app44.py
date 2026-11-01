
import os
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from app43 import app
from app import admin_required
from database import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
PERFILES_DIR = os.path.join(BASE, 'uploads', 'perfiles')
os.makedirs(PERFILES_DIR, exist_ok=True)
LOGOS_DIR = os.path.join(BASE, 'uploads', 'logos')
os.makedirs(LOGOS_DIR, exist_ok=True)

EXT_IMG = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'}
MAX_SIZE = 3 * 1024 * 1024  # 3 MB


def _guardar_imagen(file, carpeta):
    if not file or not file.filename:
        return None, None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in EXT_IMG:
        return None, f'Formato no permitido. Usa: {", ".join(EXT_IMG)}'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return None, 'La imagen supera 3 MB.'
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f"{timestamp}_{secure_filename(file.filename)}"
    file.save(os.path.join(carpeta, nombre))
    return nombre, None


@app.route('/api/avatar/<path:nombre>')
@login_required
def ver_avatar(nombre):
    ruta = os.path.join(PERFILES_DIR, secure_filename(nombre))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)


@app.route('/api/logo-empresa')
@login_required
def ver_logo_empresa():
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
    conn.close()
    if not row or not row['valor']:
        abort(404)
    ruta = os.path.join(LOGOS_DIR, secure_filename(row['valor']))
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta)


# ===== Mi Cuenta =====
@app.route('/mi-cuenta', methods=['GET', 'POST'])
@login_required
def mi_cuenta_v3():
    conn = get_db()
    usuario = conn.execute("SELECT * FROM usuarios WHERE id=?", (current_user.id,)).fetchone()

    if request.method == 'POST':
        accion = request.form.get('accion', 'perfil')

        if accion == 'perfil':
            nombre = request.form.get('nombre', '').strip()
            telefono = request.form.get('telefono', '').strip()
            email = request.form.get('email', '').strip().lower()

            if not nombre:
                conn.close(); flash('El nombre es obligatorio.', 'error')
                return redirect(url_for('mi_cuenta'))
            if not email or '@' not in email:
                conn.close(); flash('Email invalido.', 'error')
                return redirect(url_for('mi_cuenta'))
            # Verificar que el nuevo email no este en uso por otro
            existe = conn.execute("SELECT id FROM usuarios WHERE lower(email)=? AND id!=?", (email, current_user.id)).fetchone()
            if existe:
                conn.close(); flash('Ese email ya esta en uso por otro usuario.', 'error')
                return redirect(url_for('mi_cuenta'))

            foto_nombre = usuario['foto_perfil']
            # Eliminar foto si lo piden
            if request.form.get('eliminar_foto') == '1':
                if foto_nombre:
                    try: os.remove(os.path.join(PERFILES_DIR, foto_nombre))
                    except Exception: pass
                foto_nombre = None
            # Nueva foto
            nueva_foto, err = _guardar_imagen(request.files.get('foto'), PERFILES_DIR)
            if err:
                conn.close(); flash(err, 'error')
                return redirect(url_for('mi_cuenta'))
            if nueva_foto:
                if foto_nombre:
                    try: os.remove(os.path.join(PERFILES_DIR, foto_nombre))
                    except Exception: pass
                foto_nombre = nueva_foto

            conn.execute("""UPDATE usuarios SET nombre=?, telefono=?, email=?, foto_perfil=? WHERE id=?""",
                         (nombre, telefono or None, email, foto_nombre, current_user.id))
            conn.commit(); conn.close()
            flash('Perfil actualizado. Cerra y volve a entrar si cambiaste el email.', 'success')
            return redirect(url_for('mi_cuenta'))

        elif accion == 'password':
            actual = request.form.get('actual', '')
            nueva = request.form.get('nueva', '')
            confirmar = request.form.get('confirmar', '')
            if not check_password_hash(usuario['password_hash'], actual):
                conn.close(); flash('La contrasena actual no es correcta.', 'error')
                return redirect(url_for('mi_cuenta'))
            if len(nueva) < 6:
                conn.close(); flash('La nueva contrasena debe tener al menos 6 caracteres.', 'error')
                return redirect(url_for('mi_cuenta'))
            if nueva != confirmar:
                conn.close(); flash('Las contrasenas no coinciden.', 'error')
                return redirect(url_for('mi_cuenta'))
            conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?",
                         (generate_password_hash(nueva), current_user.id))
            conn.commit(); conn.close()
            flash('Contrasena actualizada.', 'success')
            return redirect(url_for('mi_cuenta'))

    conn.close()
    return render_template('mi_cuenta.html', usuario=dict(usuario))


app.view_functions['mi_cuenta'] = mi_cuenta_v3


# ===== Config: Logo empresa =====
def configuracion_firma_v2():
    conn = get_db()
    if request.method == 'POST':
        for k in ['firma_email', 'empresa_nombre', 'empresa_telefono', 'empresa_web', 'empresa_email']:
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
                         (k, request.form.get(k, '')))
        # Logo
        logo_actual_row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
        logo_actual = logo_actual_row['valor'] if logo_actual_row else None

        if request.form.get('eliminar_logo') == '1':
            if logo_actual:
                try: os.remove(os.path.join(LOGOS_DIR, logo_actual))
                except Exception: pass
            conn.execute("UPDATE configuracion SET valor='' WHERE clave='empresa_logo'")
            flash('Logo eliminado.', 'success')
        else:
            nuevo_logo, err = _guardar_imagen(request.files.get('logo'), LOGOS_DIR)
            if err:
                conn.close(); flash(err, 'error')
                return redirect(url_for('configuracion_firma'))
            if nuevo_logo:
                if logo_actual:
                    try: os.remove(os.path.join(LOGOS_DIR, logo_actual))
                    except Exception: pass
                conn.execute("UPDATE configuracion SET valor=? WHERE clave='empresa_logo'", (nuevo_logo,))
                flash('Logo actualizado.', 'success')

        conn.commit(); conn.close()
        flash('Configuracion guardada.', 'success')
        return redirect(url_for('configuracion_firma'))

    cfg = {}
    for k in ['firma_email', 'empresa_nombre', 'empresa_telefono', 'empresa_web', 'empresa_email', 'empresa_logo']:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        cfg[k] = row['valor'] if row else ''
    conn.close()
    return render_template('configuracion/firma.html', cfg=cfg, tiene_logo=bool(cfg.get('empresa_logo')))


app.view_functions['configuracion_firma'] = configuracion_firma_v2


# ===== Vista de impresion: incluir logo =====
@app.context_processor
def _ctx_logo():
    conn = get_db()
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_logo'").fetchone()
    conn.close()
    return {'empresa_logo_nombre': row['valor'] if row and row['valor'] else None}


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
