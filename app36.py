
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app35 import app
from app import admin_required
from database import get_db


# ===== Canales =====
@app.route('/catalogos/canales')
@login_required
@admin_required
def canales_gestionar():
    conn = get_db()
    canales = conn.execute("""
        SELECT c.*, 
        (SELECT COUNT(*) FROM ordenes_venta WHERE canal_id = c.id) as total_ordenes
        FROM canales_venta c ORDER BY c.activo DESC, c.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/canales.html', canales=canales)


@app.route('/catalogos/canales/nuevo', methods=['POST'])
@login_required
@admin_required
def canales_nuevo():
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('canales_gestionar'))
    conn = get_db()
    if conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un canal con ese nombre.', 'error')
        return redirect(url_for('canales_gestionar'))
    conn.execute("INSERT INTO canales_venta (nombre, activo) VALUES (?, 1)", (nombre,))
    conn.commit(); conn.close()
    flash('Canal creado.', 'success')
    return redirect(url_for('canales_gestionar'))


@app.route('/catalogos/canales/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def canales_toggle(id):
    conn = get_db()
    conn.execute("UPDATE canales_venta SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Canal actualizado.', 'success')
    return redirect(url_for('canales_gestionar'))


@app.route('/catalogos/canales/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def canales_eliminar(id):
    conn = get_db()
    # Si tiene ordenes, solo desactivar. Si no, borrar de verdad.
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE canal_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE canales_venta SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Canal desactivado (tiene {total} ordenes asociadas, no se puede borrar).', 'success')
    else:
        conn.execute("DELETE FROM canales_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Canal eliminado definitivamente.', 'success')
    return redirect(url_for('canales_gestionar'))


# ===== Medios de pago =====
@app.route('/catalogos/medios-pago')
@login_required
@admin_required
def medios_pago_gestionar():
    conn = get_db()
    medios = conn.execute("""
        SELECT m.*, 
        (SELECT COUNT(*) FROM pagos WHERE medio_pago_id = m.id) as total_pagos
        FROM medios_pago m ORDER BY m.activo DESC, m.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/medios_pago.html', medios=medios)


@app.route('/catalogos/medios-pago/nuevo', methods=['POST'])
@login_required
@admin_required
def medios_pago_nuevo():
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    conn = get_db()
    if conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    conn.execute("INSERT INTO medios_pago (nombre, comision_pct, activo) VALUES (?, ?, 1)",
                 (nombre, comision))
    conn.commit(); conn.close()
    flash('Medio de pago creado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


@app.route('/catalogos/medios-pago/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def medios_pago_toggle(id):
    conn = get_db()
    conn.execute("UPDATE medios_pago SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


@app.route('/catalogos/medios-pago/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def medios_pago_eliminar(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM pagos WHERE medio_pago_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE medios_pago SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Medio desactivado (tiene {total} pagos asociados).', 'success')
    else:
        conn.execute("DELETE FROM medios_pago WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Medio eliminado definitivamente.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


# ===== Transportistas =====
@app.route('/catalogos/transportistas')
@login_required
@admin_required
def transportistas_gestionar():
    conn = get_db()
    transportistas = conn.execute("""
        SELECT t.*, 
        (SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id = t.id) as total_envios
        FROM transportistas t ORDER BY t.activo DESC, t.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/transportistas.html', transportistas=transportistas)


@app.route('/catalogos/transportistas/nuevo', methods=['POST'])
@login_required
@admin_required
def transportistas_nuevo():
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('transportistas_gestionar'))
    conn = get_db()
    if conn.execute("SELECT id FROM transportistas WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
        conn.close(); flash('Ya existe un transportista con ese nombre.', 'error')
        return redirect(url_for('transportistas_gestionar'))
    conn.execute("INSERT INTO transportistas (nombre, url_seguimiento, activo) VALUES (?, ?, 1)",
                 (nombre, url_seg or None))
    conn.commit(); conn.close()
    flash('Transportista creado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def transportistas_editar(id):
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    conn = get_db()
    conn.execute("UPDATE transportistas SET nombre=?, url_seguimiento=? WHERE id=?",
                 (nombre, url_seg or None, id))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def transportistas_toggle(id):
    conn = get_db()
    conn.execute("UPDATE transportistas SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def transportistas_eliminar(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE transportistas SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Transportista desactivado (tiene {total} envios asociados).', 'success')
    else:
        conn.execute("DELETE FROM transportistas WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Transportista eliminado definitivamente.', 'success')
    return redirect(url_for('transportistas_gestionar'))


# ===== Pantalla de catalogos principal =====
@app.route('/catalogos')
@login_required
@admin_required
def catalogos_index():
    return render_template('catalogos/index.html')


# ===== Redirects de compatibilidad =====
# Nada que agregar


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
