
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app63 import app
from app import admin_required
from database import get_db


# ===== MEDIOS DE PAGO: pagina de edicion separada =====
@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['GET'])
@login_required
@admin_required
def medios_pago_editar_form(id):
    conn = get_db()
    medio = conn.execute("SELECT * FROM medios_pago WHERE id=?", (id,)).fetchone()
    conn.close()
    if not medio:
        flash('Medio de pago no encontrado.', 'error')
        return redirect(url_for('medios_pago_gestionar'))
    return render_template('catalogos/medios_pago_form.html', medio=dict(medio))


@app.route('/catalogos/medios-pago/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def medios_pago_editar_guardar(id):
    nombre = request.form.get('nombre', '').strip()
    try:
        comision = float(request.form.get('comision_pct') or 0)
    except ValueError:
        comision = 0
    if not nombre:
        flash('Nombre obligatorio.', 'error')
        return redirect(url_for('medios_pago_editar_form', id=id))

    conn = get_db()
    existe = conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?) AND id!=?",
                           (nombre, id)).fetchone()
    if existe:
        conn.close()
        flash('Ya existe otro medio con ese nombre.', 'error')
        return redirect(url_for('medios_pago_editar_form', id=id))

    conn.execute("UPDATE medios_pago SET nombre=?, comision_pct=? WHERE id=?",
                 (nombre, comision, id))
    conn.commit(); conn.close()
    flash('Medio de pago actualizado.', 'success')
    return redirect(url_for('medios_pago_gestionar'))
