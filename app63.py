
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app48 import app
from app import admin_required
from database import get_db


# ===== MEDIOS DE PAGO: editar =====
@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def medios_pago_editar(id):
    nombre = request.form.get('nombre', '').strip()
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_gestionar'))

    conn = get_db()
    # Verificar que no exista otro con ese nombre
    existe = conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_gestionar'))

    conn.execute("UPDATE medios_pago SET nombre=?, comision_pct=? WHERE id=?",
                 (nombre, comision, id))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))


# ===== TRANSPORTISTAS: editar con URL inteligente =====
@app.route('/catalogos/transportistas/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def transportistas_editar_v2(id):
    nombre = request.form.get('nombre', '').strip()
    url_seg = request.form.get('url_seguimiento', '').strip()
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('transportistas_gestionar'))

    conn = get_db()
    # Verificar que no exista otro con ese nombre
    existe = conn.execute("SELECT id FROM transportistas WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro transportista con ese nombre.', 'error')
        return redirect(url_for('transportistas_gestionar'))

    conn.execute("UPDATE transportistas SET nombre=?, url_seguimiento=? WHERE id=?",
                 (nombre, url_seg or None, id))
    conn.commit(); conn.close()
    flash('Transportista actualizado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


@app.route('/catalogos/transportistas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def transportistas_eliminar_v2(id):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE transportista_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE transportistas SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Transportista desactivado (tiene {total} envios).', 'success')
    else:
        conn.execute("DELETE FROM transportistas WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Transportista eliminado.', 'success')
    return redirect(url_for('transportistas_gestionar'))


app.view_functions['transportistas_editar'] = transportistas_editar_v2
app.view_functions['transportistas_eliminar'] = transportistas_eliminar_v2


# ===== Helper para construir URL de seguimiento =====
def construir_url_seguimiento(url_base, nro_guia):
    """
    Dada una URL base y un numero de guia, devuelve la URL final.
    - Si tiene {guia}, lo reemplaza.
    - Si NO tiene, agrega el numero al final (con / si hace falta).
    """
    if not url_base or not nro_guia:
        return None
    guia = str(nro_guia).strip()
    if not guia:
        return None

    if '{guia}' in url_base:
        return url_base.replace('{guia}', guia)

    # Agregar al final
    url = url_base.rstrip('/')
    return f'{url}/{guia}'


@app.context_processor
def _helper_seguimiento():
    return {'construir_url_seguimiento': construir_url_seguimiento}
