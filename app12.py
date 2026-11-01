
import time
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app11 import app
from app import permiso_required, admin_required, revertir_stock
from database import get_db


_ultimo_chequeo_auto_cancel = 0
_INTERVALO_AUTO_CANCEL = 300  # 5 min


def _auto_cancelar():
    """Cancela ordenes pendiente_pago con mas de 24 hs y avisa por email."""
    global _ultimo_chequeo_auto_cancel
    ahora = time.time()
    if ahora - _ultimo_chequeo_auto_cancel < _INTERVALO_AUTO_CANCEL:
        return
    _ultimo_chequeo_auto_cancel = ahora

    conn = get_db()
    try:
        # ordenes pendiente_pago con mas de 24 hs
        candidatas = conn.execute("""
            SELECT * FROM ordenes_venta
            WHERE estado='pendiente_pago'
            AND auto_cancelada=0
            AND datetime(creado) < datetime('now', '-24 hours')
        """).fetchall()

        if not candidatas:
            return

        # Importar solo cuando hace falta
        try:
            from app4 import enviar_email, get_config, render_plantilla
        except Exception:
            enviar_email = None

        for orden in candidatas:
            # Revertir stock si estaba descontado (por seguridad)
            if orden['stock_descontado']:
                try:
                    revertir_stock(conn, orden['id'], 1)  # usuario=1 (sistema)
                except Exception:
                    pass

            conn.execute(
                "UPDATE ordenes_venta SET estado='cancelado', auto_cancelada=1 WHERE id=?",
                (orden['id'],)
            )

            # Enviar email al cliente
            if enviar_email:
                try:
                    c = conn.execute(
                        "SELECT email, nombre_completo FROM clientes WHERE id=?",
                        (orden['cliente_id'],)
                    ).fetchone()
                    if c and c['email']:
                        ctx = {
                            'cliente_nombre': c['nombre_completo'],
                            'numero_orden': orden['numero_interno'],
                            'fecha': orden['fecha'],
                            'total': f"{orden['total']:.2f}",
                            'firma': get_config('firma_email'),
                        }
                        asunto = render_plantilla(get_config('plantilla_cancelacion_asunto'), ctx)
                        cuerpo = render_plantilla(get_config('plantilla_cancelacion_cuerpo'), ctx)
                        ok, _msg = enviar_email(c['email'], asunto, cuerpo)
                        conn.execute("""INSERT INTO emails_enviados
                            (destinatario, asunto, tipo, orden_id, estado) VALUES (?,?,?,?,?)""",
                            (c['email'], asunto, 'cancelacion', orden['id'], 'ok' if ok else 'error'))
                except Exception as e:
                    print(f"[auto-cancel email] {e}")

        conn.commit()
        print(f"[auto-cancel] {len(candidatas)} orden(es) canceladas automaticamente")
    except Exception as e:
        print(f"[auto-cancel] error: {e}")
    finally:
        conn.close()


@app.before_request
def _hook_auto_cancelar():
    if request.endpoint in (None, 'static'):
        return
    if not current_user.is_authenticated:
        return
    try:
        _auto_cancelar()
    except Exception as e:
        print(f"[hook auto-cancel] {e}")


# ===== Solicitudes de borrado =====
def _crear_solicitud(conn, tipo, entidad_id, descripcion, motivo):
    ya = conn.execute("""SELECT id FROM solicitudes_borrado
        WHERE tipo=? AND entidad_id=? AND usuario_id=? AND estado='pendiente'""",
        (tipo, entidad_id, current_user.id)).fetchone()
    if ya:
        return False
    conn.execute("""INSERT INTO solicitudes_borrado
        (tipo, entidad_id, descripcion, motivo, usuario_id) VALUES (?,?,?,?,?)""",
        (tipo, entidad_id, descripcion, motivo, current_user.id))
    return True


def _borrar_entidad(conn, tipo, entidad_id):
    if tipo == 'orden':
        conn.execute("DELETE FROM ordenes_venta WHERE id=?", (entidad_id,))
    elif tipo == 'cliente':
        conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (entidad_id,))
    elif tipo == 'producto':
        conn.execute("UPDATE productos SET activo=0 WHERE id=?", (entidad_id,))


@app.route('/solicitudes')
@login_required
def solicitudes_lista():
    conn = get_db()
    if current_user.es_admin:
        solicitudes = conn.execute("""
            SELECT s.*, u.nombre as usuario_nombre, r.nombre as resuelto_por_nombre
            FROM solicitudes_borrado s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            LEFT JOIN usuarios r ON r.id = s.resuelto_por
            ORDER BY s.estado='pendiente' DESC, s.id DESC
        """).fetchall()
    else:
        solicitudes = conn.execute("""
            SELECT s.*, u.nombre as usuario_nombre, r.nombre as resuelto_por_nombre
            FROM solicitudes_borrado s
            LEFT JOIN usuarios u ON u.id = s.usuario_id
            LEFT JOIN usuarios r ON r.id = s.resuelto_por
            WHERE s.usuario_id=?
            ORDER BY s.id DESC
        """, (current_user.id,)).fetchall()
    pendientes = sum(1 for s in solicitudes if s['estado'] == 'pendiente' and current_user.es_admin)
    conn.close()
    return render_template('solicitudes/lista.html', solicitudes=solicitudes, pendientes=pendientes)


@app.route('/solicitudes/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def solicitudes_aprobar(id):
    conn = get_db()
    s = conn.execute("SELECT * FROM solicitudes_borrado WHERE id=? AND estado='pendiente'", (id,)).fetchone()
    if not s:
        conn.close(); flash('Solicitud no encontrada o ya resuelta.', 'error')
        return redirect(url_for('solicitudes_lista'))
    _borrar_entidad(conn, s['tipo'], s['entidad_id'])
    conn.execute("""UPDATE solicitudes_borrado SET estado='aprobada',
        resuelto_por=?, resuelto_en=datetime('now') WHERE id=?""",
        (current_user.id, id))
    conn.commit(); conn.close()
    flash(f'Solicitud aprobada. {s["tipo"].capitalize()} borrado.', 'success')
    return redirect(url_for('solicitudes_lista'))


@app.route('/solicitudes/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def solicitudes_rechazar(id):
    conn = get_db()
    conn.execute("""UPDATE solicitudes_borrado SET estado='rechazada',
        resuelto_por=?, resuelto_en=datetime('now') WHERE id=? AND estado='pendiente'""",
        (current_user.id, id))
    conn.commit(); conn.close()
    flash('Solicitud rechazada.', 'success')
    return redirect(url_for('solicitudes_lista'))


# ===== Borrar orden =====
@app.route('/ventas/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_borrar(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Orden no encontrada.', 'error')
        return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso sobre esta orden.', 'error')
        return redirect(url_for('ventas_lista'))

    # Si tiene stock descontado y no está cancelada, primero cancelar
    if orden['stock_descontado'] and orden['estado'] != 'cancelado':
        conn.close()
        flash('Antes de borrar tenes que cancelar la orden (para devolver el stock).', 'error')
        return redirect(url_for('ventas_detalle', id=id))

    if current_user.es_admin:
        conn.execute("DELETE FROM ordenes_venta WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Orden {orden["numero_interno"]} borrada.', 'success')
        return redirect(url_for('ventas_lista'))

    # Vendedor: crear solicitud
    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'orden', id,
                          f'Orden {orden["numero_interno"]} (${orden["total"]:.2f})', motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin para borrar esta orden. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para esta orden.', 'error')
    return redirect(url_for('ventas_lista'))


# ===== Borrar cliente =====
@app.route('/clientes/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('clientes')
def clientes_borrar_v2(id):
    conn = get_db()
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    if not cliente:
        conn.close(); flash('Cliente no encontrado.', 'error')
        return redirect(url_for('clientes_lista'))

    if current_user.es_admin:
        conn.execute("UPDATE clientes SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Cliente {cliente["nombre_completo"]} desactivado.', 'success')
        return redirect(url_for('clientes_lista'))

    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'cliente', id, cliente['nombre_completo'], motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para este cliente.', 'error')
    return redirect(url_for('clientes_lista'))


# ===== Borrar producto =====
@app.route('/productos/<int:id>/borrar', methods=['POST'])
@login_required
@permiso_required('productos')
def productos_borrar_v2(id):
    conn = get_db()
    producto = conn.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
    if not producto:
        conn.close(); flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos_lista'))

    if current_user.es_admin:
        conn.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))
        conn.commit(); conn.close()
        flash(f'Producto {producto["nombre"]} desactivado.', 'success')
        return redirect(url_for('productos_lista'))

    motivo = request.form.get('motivo', '').strip()
    ok = _crear_solicitud(conn, 'producto', id, producto['nombre'], motivo)
    conn.commit(); conn.close()
    if ok:
        flash('Se envio una solicitud al admin. Te avisamos cuando la resuelva.', 'success')
    else:
        flash('Ya tenes una solicitud pendiente para este producto.', 'error')
    return redirect(url_for('productos_lista'))


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
