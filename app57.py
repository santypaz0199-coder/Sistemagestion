
import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, send_file, abort
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app49 import catalogo_bp
from app51 import get_current_mayorista, mayorista_requerido
from app48 import app as main_app
from app import admin_required
from database import get_db

BASE = os.path.dirname(os.path.abspath(__file__))
COMPROBANTES_DIR = os.path.join(BASE, 'uploads', 'comprobantes')
os.makedirs(COMPROBANTES_DIR, exist_ok=True)

EXT_VALIDAS = {'pdf', 'jpg', 'jpeg', 'png', 'webp'}
MAX_SIZE = 10 * 1024 * 1024


# ===== Helpers =====
def _guardar_comprobante(file):
    if not file or not file.filename:
        return None, None, 'Selecciona un archivo.'
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in EXT_VALIDAS:
        return None, None, f'Formato no permitido. Usa: {", ".join(EXT_VALIDAS)}.'
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return None, None, 'El archivo supera 10 MB.'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f"{timestamp}_{secure_filename(file.filename)}"
    file.save(os.path.join(COMPROBANTES_DIR, nombre))
    return nombre, file.filename, None


def _datos_pago(conn):
    claves = ['pago_alias', 'pago_cbu', 'pago_titular', 'pago_cuit', 'pago_banco', 'pago_instrucciones']
    resultado = {}
    for k in claves:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (k,)).fetchone()
        resultado[k] = row['valor'] if row and row['valor'] else ''
    return resultado


def _notificar(mayorista_email, asunto, cuerpo):
    try:
        from app39 import _enviar_con_remitente
        _enviar_con_remitente(mayorista_email, asunto, cuerpo, None)
    except Exception as e:
        print(f"[notificar] {e}")


# ===== Catalogo: mayorista sube comprobante =====
@catalogo_bp.route('/mis-pedidos/<int:id>/subir-comprobante', methods=['POST'])
@mayorista_requerido
def subir_comprobante(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        flash('Cuenta no vinculada.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    if orden['estado'] != 'pendiente_pago':
        conn.close(); flash('Este pedido ya no esta pendiente de pago.', 'warning')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    archivo = request.files.get('comprobante')
    nombre_arch, nombre_orig, err = _guardar_comprobante(archivo)
    if err:
        conn.close(); flash(err, 'error')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    # Borrar comprobante anterior si existia
    if orden['comprobante_archivo']:
        try: os.remove(os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo']))
        except: pass

    conn.execute("""UPDATE ordenes_venta SET
        comprobante_archivo=?, comprobante_nombre=?,
        comprobante_estado='subido', comprobante_subido_en=datetime('now'),
        comprobante_motivo_rechazo=NULL
        WHERE id=?""",
        (nombre_arch, nombre_orig, id))
    conn.commit()
    conn.close()

    # Notificar al admin
    try:
        from app4 import get_config
        admin_email = get_config('empresa_email') or get_config('smtp_remitente_email')
        if admin_email:
            cuerpo = f"""Nuevo comprobante subido:

Pedido: {orden['numero_interno']}
Cliente: {m['nombre_completo']} <{m['email']}>
Total: ${orden['total']:.2f}

Revisalo en: /pagos-pendientes

{get_config('firma_email')}"""
            _notificar(admin_email, f'Comprobante subido - {orden["numero_interno"]}', cuerpo)
    except Exception as e:
        print(f"[notificar admin] {e}")

    flash('Comprobante subido. Estamos verificando el pago.', 'success')
    return redirect(url_for('catalogo.mi_pedido_detalle', id=id))


@catalogo_bp.route('/mis-pedidos/<int:id>/cancelar', methods=['POST'])
@mayorista_requerido
def cancelar_pedido_mayorista(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        return redirect(url_for('catalogo.mis_pedidos'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('catalogo.mis_pedidos'))

    if orden['estado'] != 'pendiente_pago' or orden['comprobante_estado'] == 'subido':
        conn.close()
        flash('No podes cancelar este pedido. Ya fue pagado o el comprobante esta en revision.', 'error')
        return redirect(url_for('catalogo.mi_pedido_detalle', id=id))

    conn.execute("UPDATE ordenes_venta SET estado='cancelado' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Pedido cancelado.', 'success')
    return redirect(url_for('catalogo.mis_pedidos'))


@catalogo_bp.route('/comprobante/<int:id>')
@mayorista_requerido
def ver_mi_comprobante(id):
    m = get_current_mayorista()
    if not m['cliente_id']:
        abort(404)
    conn = get_db()
    orden = conn.execute("SELECT comprobante_archivo, comprobante_nombre FROM ordenes_venta WHERE id=? AND cliente_id=?",
                         (id, m['cliente_id'])).fetchone()
    conn.close()
    if not orden or not orden['comprobante_archivo']:
        abort(404)
    ruta = os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo'])
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta, as_attachment=False, download_name=orden['comprobante_nombre'])


# ===== Admin: Pagos pendientes =====
@main_app.route('/pagos-pendientes')
@login_required
@admin_required
def pagos_pendientes_lista():
    filtro = request.args.get('filtro', 'subido')
    conn = get_db()

    if filtro == 'subido':
        # Solo comprobantes esperando aprobacion
        rows = conn.execute("""
            SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
            FROM ordenes_venta o
            JOIN clientes c ON c.id = o.cliente_id
            WHERE o.comprobante_estado = 'subido'
            AND o.estado = 'pendiente_pago'
            ORDER BY o.comprobante_subido_en ASC
        """).fetchall()
    elif filtro == 'todos':
        rows = conn.execute("""
            SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email
            FROM ordenes_venta o
            JOIN clientes c ON c.id = o.cliente_id
            WHERE o.comprobante_estado IN ('subido','aprobado','rechazado')
            ORDER BY o.id DESC LIMIT 100
        """).fetchall()
    else:
        rows = []

    counts = {
        'subido': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='subido' AND estado='pendiente_pago'").fetchone()[0],
        'aprobado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='aprobado'").fetchone()[0],
        'rechazado': conn.execute("SELECT COUNT(*) FROM ordenes_venta WHERE comprobante_estado='rechazado'").fetchone()[0],
    }
    conn.close()
    return render_template('pagos_pendientes/lista.html', rows=rows, filtro=filtro, counts=counts)


@main_app.route('/pagos-pendientes/<int:id>/aprobar', methods=['POST'])
@login_required
@admin_required
def pagos_pendientes_aprobar(id):
    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

    # Marcar como pagado (esto descuenta stock via trigger o via funcion)
    if not orden['stock_descontado']:
        # Aplicar descuento de stock
        try:
            from app import aplicar_descuento_stock
            aplicar_descuento_stock(conn, id, current_user.id)
        except Exception as e:
            print(f"[aprobar] error stock: {e}")

    conn.execute("""UPDATE ordenes_venta SET
        estado='pagado_sin_enviar',
        comprobante_estado='aprobado',
        comprobante_aprobado_por=?,
        comprobante_aprobado_en=datetime('now')
        WHERE id=?""",
        (current_user.id, id))
    conn.commit()

    # Datos para notificar
    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    # Notificar al mayorista
    if cliente and cliente['email']:
        try:
            from app4 import get_config
            cuerpo = f"""Hola {cliente['nombre_completo']},

Tu pago fue aprobado. Tu pedido {orden['numero_interno']} ya esta en preparacion.

En cuanto lo despachemos te enviamos el numero de seguimiento.

{get_config('firma_email')}"""
            _notificar(cliente['email'], f'Pago aprobado - Pedido {orden["numero_interno"]}', cuerpo)
        except Exception as e:
            print(f"[notificar aprobado] {e}")

    flash(f'Pedido {orden["numero_interno"]} marcado como pagado. Stock descontado.', 'success')
    return redirect(url_for('pagos_pendientes_lista'))


@main_app.route('/pagos-pendientes/<int:id>/rechazar', methods=['POST'])
@login_required
@admin_required
def pagos_pendientes_rechazar(id):
    motivo = request.form.get('motivo', '').strip()
    if not motivo:
        flash('Indica el motivo del rechazo.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

    conn = get_db()
    orden = conn.execute("SELECT * FROM ordenes_venta WHERE id=?", (id,)).fetchone()
    if not orden:
        conn.close(); flash('Pedido no encontrado.', 'error')
        return redirect(url_for('pagos_pendientes_lista'))

    conn.execute("""UPDATE ordenes_venta SET
        comprobante_estado='rechazado',
        comprobante_motivo_rechazo=?
        WHERE id=?""", (motivo, id))
    conn.commit()

    cliente = conn.execute("SELECT * FROM clientes WHERE id=?", (orden['cliente_id'],)).fetchone()
    conn.close()

    if cliente and cliente['email']:
        try:
            from app4 import get_config
            cuerpo = f"""Hola {cliente['nombre_completo']},

Revisamos el comprobante de tu pedido {orden['numero_interno']} y no pudimos aprobarlo.

Motivo: {motivo}

Podes subir un nuevo comprobante desde "Mis pedidos" en el catalogo.

{get_config('firma_email')}"""
            _notificar(cliente['email'], f'Comprobante rechazado - Pedido {orden["numero_interno"]}', cuerpo)
        except Exception as e:
            print(f"[notificar rechazo] {e}")

    flash(f'Comprobante rechazado. Se notifico al cliente.', 'warning')
    return redirect(url_for('pagos_pendientes_lista'))


@main_app.route('/pagos-pendientes/<int:id>/comprobante')
@login_required
@admin_required
def pagos_pendientes_ver_comprobante(id):
    conn = get_db()
    orden = conn.execute("SELECT comprobante_archivo, comprobante_nombre FROM ordenes_venta WHERE id=?",
                         (id,)).fetchone()
    conn.close()
    if not orden or not orden['comprobante_archivo']:
        abort(404)
    ruta = os.path.join(COMPROBANTES_DIR, orden['comprobante_archivo'])
    if not os.path.exists(ruta):
        abort(404)
    return send_file(ruta, as_attachment=False, download_name=orden['comprobante_nombre'])


# ===== Configuracion: Datos de pago =====
@main_app.route('/configuracion/datos-pago', methods=['GET', 'POST'])
@login_required
@admin_required
def configuracion_datos_pago():
    conn = get_db()
    if request.method == 'POST':
        for k in ['pago_alias', 'pago_cbu', 'pago_titular', 'pago_cuit', 'pago_banco', 'pago_instrucciones']:
            v = request.form.get(k, '').strip()
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, v))
        conn.commit(); conn.close()
        flash('Datos de pago guardados.', 'success')
        return redirect(url_for('configuracion_datos_pago'))

    datos = _datos_pago(conn)
    conn.close()
    return render_template('configuracion/datos_pago.html', datos=datos)
