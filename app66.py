
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app65 import app
from app import admin_required
from database import get_db


def canales_gestionar_v2():
    conn = get_db()
    canales = conn.execute("""
        SELECT c.*,
        (SELECT COUNT(*) FROM ordenes_venta WHERE canal_id = c.id) as total_ordenes
        FROM canales_venta c ORDER BY c.es_sistema DESC, c.activo DESC, c.nombre
    """).fetchall()
    conn.close()
    return render_template('catalogos/canales.html', canales=canales)


def canales_toggle_v2(id):
    conn = get_db()
    canal = conn.execute("SELECT * FROM canales_venta WHERE id=?", (id,)).fetchone()
    if not canal:
        conn.close(); flash('Canal no encontrado.', 'error')
        return redirect(url_for('canales_gestionar'))
    if canal['es_sistema']:
        conn.close()
        flash('El canal "Tienda online" es del sistema y no se puede desactivar (recibe los pedidos del catalogo B2B).', 'error')
        return redirect(url_for('canales_gestionar'))
    conn.execute("UPDATE canales_venta SET activo = 1 - COALESCE(activo, 0) WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Canal actualizado.', 'success')
    return redirect(url_for('canales_gestionar'))


def canales_eliminar_v2(id):
    conn = get_db()
    canal = conn.execute("SELECT * FROM canales_venta WHERE id=?", (id,)).fetchone()
    if not canal:
        conn.close(); flash('Canal no encontrado.', 'error')
        return redirect(url_for('canales_gestionar'))
    if canal['es_sistema']:
        conn.close()
        flash('El canal "Tienda online" es del sistema y no se puede eliminar (recibe los pedidos del catalogo B2B).', 'error')
        return redirect(url_for('canales_gestionar'))

    total = conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE canal_id=?", (id,)).fetchone()[0]
    if total > 0:
        conn.execute("UPDATE canales_venta SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Canal desactivado (tiene {total} ordenes asociadas).', 'success')
    else:
        conn.execute("DELETE FROM canales_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash('Canal eliminado definitivamente.', 'success')
    return redirect(url_for('canales_gestionar'))


app.view_functions['canales_gestionar'] = canales_gestionar_v2
app.view_functions['canales_toggle'] = canales_toggle_v2
app.view_functions['canales_eliminar'] = canales_eliminar_v2
