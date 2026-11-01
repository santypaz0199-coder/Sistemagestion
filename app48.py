
import os
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app45 import app
from app import admin_required
from database import get_db
from app4 import enviar_email, get_config


def _remitentes_activos(conn):
    return conn.execute("SELECT * FROM remitentes WHERE activo=1 ORDER BY email").fetchall()


@app.route('/configuracion/remitentes', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_remitentes():
    conn = get_db()
    if request.method == 'POST':
        accion = request.form.get('accion', 'config')

        if accion == 'agregar':
            email = request.form.get('email', '').strip().lower()
            nombre = request.form.get('nombre', '').strip()
            if not email or '@' not in email or not nombre:
                conn.close(); flash('Email y nombre son obligatorios.', 'error')
                return redirect(url_for('configuracion_remitentes'))
            ya = conn.execute("SELECT id FROM remitentes WHERE lower(email)=?", (email,)).fetchone()
            if ya:
                conn.close(); flash('Ese email ya esta en la lista.', 'error')
                return redirect(url_for('configuracion_remitentes'))
            conn.execute("INSERT INTO remitentes (email, nombre, activo) VALUES (?, ?, 1)", (email, nombre))
            conn.commit(); conn.close()
            flash('Remitente agregado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'toggle':
            rid = int(request.form.get('remitente_id', 0))
            conn.execute("UPDATE remitentes SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (rid,))
            conn.commit(); conn.close()
            flash('Estado actualizado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'eliminar':
            rid = int(request.form.get('remitente_id', 0))
            conn.execute("DELETE FROM remitentes WHERE id=?", (rid,))
            conn.commit(); conn.close()
            flash('Remitente eliminado.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'config':
            # Guardar default para cada proposito + smtp
            claves = ['remitente_atencion_email', 'remitente_notificaciones_email', 'remitente_campanas_email']
            for k in claves:
                v = request.form.get(k, '').strip()
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))

            # Actualizar nombres de remitentes del sistema
            for key in ['remitente_atencion_nombre', 'remitente_notificaciones_nombre', 'remitente_campanas_nombre']:
                v = request.form.get(key, '').strip()
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (key, v))

            # SMTP
            for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password', 'smtp_seguridad']:
                v = request.form.get(k, '').strip()
                if k == 'smtp_password' and not v:
                    continue
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))

            # Actualizar el default smtp_remitente_email para que coincida con notificaciones
            notif = request.form.get('remitente_notificaciones_email', '').strip()
            notif_nombre = request.form.get('remitente_notificaciones_nombre', '').strip()
            if notif:
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_email', ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (notif,))
                if notif_nombre:
                    conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_nombre', ?) "
                                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (notif_nombre,))

            # Actualizar empresa_email (atencion al cliente)
            aten = request.form.get('remitente_atencion_email', '').strip()
            aten_nombre = request.form.get('remitente_atencion_nombre', '').strip()
            if aten:
                conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_email', ?) "
                             "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (aten,))
                if aten_nombre:
                    conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_nombre', ?) "
                                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (aten_nombre,))

            conn.commit(); conn.close()
            flash('Configuracion de remitentes guardada.', 'success')
            return redirect(url_for('configuracion_remitentes'))

        elif accion == 'probar':
            destino = request.form.get('probar_destino', '').strip()
            from_email = request.form.get('probar_desde', '').strip()
            from_nombre = request.form.get('probar_nombre', '').strip() or 'Familia Zaragoza'
            if not destino:
                conn.close(); flash('Ingresa el email de destino.', 'error')
                return redirect(url_for('configuracion_remitentes'))

            # Override temporal del remitente para la prueba
            remitente_override = {'email': from_email, 'nombre': from_nombre} if from_email else None
            ok, msg = _enviar_con_remitente(destino, 'Prueba de envio - Sistema FZ',
                                             'Este es un email de prueba del sistema.\n\nSi lo recibis, todo funciona OK.',
                                             remitente_override=remitente_override)
            conn.close()
            flash(('OK: ' + msg) if ok else msg, 'success' if ok else 'error')
            return redirect(url_for('configuracion_remitentes'))

    # GET: cargar todo para mostrar
    remitentes = _remitentes_activos(conn)
    remitentes_inactivos = conn.execute("SELECT * FROM remitentes WHERE activo=0 ORDER BY email").fetchall()

    cfg = {}
    for k in ['smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_seguridad',
              'remitente_atencion_email', 'remitente_notificaciones_email',
              'remitente_campanas_email', 'remitente_atencion_nombre',
              'remitente_notificaciones_nombre', 'remitente_campanas_nombre']:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        cfg[k] = row['valor'] if row and row['valor'] else ''

    smtp_pass = conn.execute("SELECT valor FROM configuracion WHERE clave='smtp_password'").fetchone()
    cfg['smtp_password_set'] = bool(smtp_pass and smtp_pass['valor'])

    conn.close()
    return render_template('configuracion/remitentes.html',
                           remitentes=remitentes,
                           remitentes_inactivos=remitentes_inactivos,
                           cfg=cfg)


def _enviar_con_remitente(destinatario, asunto, cuerpo, remitente_override=None, adjuntos=None):
    from app39 import _enviar_con_remitente as env
    return env(destinatario, asunto, cuerpo, remitente_override, adjuntos)


# ===== Actualizar rutas de envio para respetar las nuevas configuraciones =====
def _get_remitente_por_proposito(conn, proposito):
    """proposito: 'atencion', 'notificaciones', 'campanas'"""
    clave_email = f'remitente_{proposito}_email'
    clave_nombre = f'remitente_{proposito}_nombre'
    email = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave_email,)).fetchone()
    nombre = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave_nombre,)).fetchone()
    return {
        'email': email['valor'] if email else None,
        'nombre': nombre['valor'] if nombre else 'Familia Zaragoza',
    }


app.view_functions['configuracion_remitentes'] = configuracion_remitentes


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
