
import os, re, time
from datetime import date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app39 import app, _enviar_con_remitente, _remitentes_disponibles, _remitente_por_email
from app import admin_required
from werkzeug.datastructures import ImmutableMultiDict
from database import get_db


def _construir_filtros():
    """Toma los filtros del form y devuelve (sql_where, params, descripcion)."""
    where = ["c.activo = 1", "c.email IS NOT NULL", "c.email != ''", "c.email LIKE '%@%'"]
    params = []
    descripcion = []

    if request.form.get('filtro_tags') == 'minorista':
        where.append("c.es_minorista = 1")
        descripcion.append("Minoristas")
    elif request.form.get('filtro_tags') == 'mayorista':
        where.append("c.es_mayorista = 1")
        descripcion.append("Mayoristas")

    provincia_ids = request.form.getlist('filtro_provincia')
    if provincia_ids:
        placeholders = ','.join(['?'] * len(provincia_ids))
        where.append(f"c.provincia_id IN ({placeholders})")
        params += [int(p) for p in provincia_ids]
        descripcion.append(f"{len(provincia_ids)} provincia(s)")

    clase = request.form.get('filtro_clase', '').strip()
    if clase == 'con_compras':
        where.append("""c.id IN (
            SELECT cliente_id FROM ordenes_venta
            WHERE estado IN ('pagado_sin_enviar','pagado_enviado')
            GROUP BY cliente_id
        )""")
        descripcion.append("Con compras")
    elif clase == 'sin_compras':
        where.append("""c.id NOT IN (
            SELECT cliente_id FROM ordenes_venta
            WHERE estado IN ('pagado_sin_enviar','pagado_enviado')
        )""")
        descripcion.append("Sin compras")

    color = request.form.get('filtro_color', '').strip()
    if color:
        # Calcular dias en Python es complejo en SQL puro, hacemos un post-filtro
        descripcion.append(f"Color {color}")

    vendedor_id = request.form.get('filtro_vendedor', '').strip()
    if vendedor_id:
        where.append("c.vendedor_id = ?")
        params.append(int(vendedor_id))
        descripcion.append(f"Vendedor #{vendedor_id}")

    return ' AND '.join(where), params, descripcion, color


def _clientes_filtrados(conn, where_sql, params, color_filter=''):
    from datetime import datetime, date as _date
    rows = conn.execute(f"SELECT c.*, p.nombre as provincia_nombre, u.nombre as vendedor_nombre FROM clientes c LEFT JOIN provincias p ON p.id = c.provincia_id LEFT JOIN usuarios u ON u.id = c.vendedor_id WHERE {where_sql}", params).fetchall()

    if not color_filter:
        return rows

    # Filtrar por color RFM en Python
    resultado = []
    hoy = _date.today()
    for r in rows:
        ult = conn.execute("""SELECT MAX(COALESCE(fecha_envio, fecha)) FROM ordenes_venta
            WHERE cliente_id = ? AND estado IN ('pagado_sin_enviar','pagado_enviado')""",
            (r['id'],)).fetchone()[0]
        dias = None
        if ult:
            try:
                f = datetime.strptime(ult[:10], '%Y-%m-%d').date()
                dias = (hoy - f).days
            except Exception:
                pass
        if dias is None:
            color = 'gris'
        elif dias <= 45:
            color = 'verde-brillante'
        elif dias <= 66:
            color = 'verde'
        elif dias <= 87:
            color = 'amarillo'
        elif dias <= 108:
            color = 'naranja'
        else:
            color = 'rojo'
        if color == color_filter:
            resultado.append(r)
    return resultado


def _render_variables(texto, cliente):
    return (texto
            .replace('{{nombre}}', cliente['nombre_completo'] or '')
            .replace('{{nombre_completo}}', cliente['nombre_completo'] or '')
            .replace('{{provincia}}', cliente['provincia_nombre'] or '')
            .replace('{{localidad}}', cliente['localidad'] or '')
            .replace('{{vendedor}}', cliente['vendedor_nombre'] or 'Equipo Familia Zaragoza'))


@app.route('/campanas')
@login_required
@admin_required
def campanas_lista():
    conn = get_db()
    campanas = conn.execute("""
        SELECT c.*, u.nombre as creado_por_nombre
        FROM campanas c LEFT JOIN usuarios u ON u.id = c.usuario_id
        ORDER BY c.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template('campanas/lista.html', campanas=campanas)


@app.route('/campanas/nueva', methods=['GET', 'POST'])
@login_required
@admin_required
def campanas_nueva():
    conn = get_db()
    if request.method == 'POST':
        accion = request.form.get('accion', 'preview')

        where_sql, params, descripcion, color_filter = _construir_filtros()
        clientes = _clientes_filtrados(conn, where_sql, params, color_filter)

        if accion == 'preview':
            remitentes = _remitentes_disponibles(conn)
            provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
            vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()
            conn.close()
            return render_template('campanas/form.html',
                                   remitentes=remitentes, provincias=provincias,
                                   vendedores=vendedores,
                                   form_data=request.form,
                                   preview_count=len(clientes),
                                   descripcion_filtros=descripcion)

        if accion == 'guardar' or accion == 'enviar':
            nombre = request.form.get('nombre', '').strip()
            asunto = request.form.get('asunto', '').strip()
            cuerpo = request.form.get('cuerpo', '').strip()
            remitente_email = request.form.get('remitente_email', '').strip()

            if not nombre or not asunto or not cuerpo:
                conn.close(); flash('Completa nombre, asunto y cuerpo.', 'error')
                return redirect(url_for('campanas_nueva'))

            if not clientes:
                conn.close(); flash('No hay destinatarios con esos filtros.', 'error')
                return redirect(url_for('campanas_nueva'))

            # Guardar campaña
            import json as _json
            filtros_json = _json.dumps({
                'tags': request.form.get('filtro_tags'),
                'provincias': request.form.getlist('filtro_provincia'),
                'clase': request.form.get('filtro_clase'),
                'color': request.form.get('filtro_color'),
                'vendedor': request.form.get('filtro_vendedor'),
                'descripcion': descripcion,
            })
            cur = conn.execute("""INSERT INTO campanas (nombre, filtros_json, cuerpo_html, asunto, remitente, estado, usuario_id)
                VALUES (?,?,?,?,?,?,?)""",
                (nombre, filtros_json, cuerpo, asunto,
                 remitente_email or None,
                 'borrador' if accion == 'guardar' else 'enviando',
                 current_user.id))
            campana_id = cur.lastrowid
            conn.commit()

            if accion == 'guardar':
                conn.close()
                flash(f'Campaña guardada como borrador ({len(clientes)} destinatarios).', 'success')
                return redirect(url_for('campanas_lista'))

            # Enviar
            remitente_override = _remitente_por_email(conn, remitente_email) if remitente_email else None
            # Validar remitente (evita admin@local invalido)
            try:
                from app39 import _validar_remitente
                remitente_override = _validar_remitente(remitente_override)
            except Exception:
                pass
            enviados = 0
            errores = 0
            errores_detalle = []
            for i, cliente in enumerate(clientes):
                try:
                    asunto_final = _render_variables(asunto, cliente)
                    cuerpo_final = _render_variables(cuerpo, cliente)
                    ok, msg = _enviar_con_remitente(cliente['email'], asunto_final, cuerpo_final,
                                                     remitente_override=remitente_override)
                    conn.execute("""INSERT INTO campanas_envios (campana_id, cliente_id, destinatario, estado, error)
                        VALUES (?,?,?,?,?)""",
                        (campana_id, cliente['id'], cliente['email'], 'ok' if ok else 'error', None if ok else msg))
                    if ok:
                        enviados += 1
                    else:
                        errores += 1
                        errores_detalle.append(f"{cliente['email']}: {msg}")
                    # Rate limit
                    if i < len(clientes) - 1:
                        time.sleep(0.5)
                except Exception as e:
                    errores += 1
                    errores_detalle.append(f"{cliente['email']}: {e}")
                    conn.execute("""INSERT INTO campanas_envios (campana_id, cliente_id, destinatario, estado, error)
                        VALUES (?,?,?,?,?)""",
                        (campana_id, cliente['id'], cliente['email'], 'error', str(e)))

            conn.execute("""UPDATE campanas SET estado='enviada', total_enviados=?, total_errores=?,
                enviada_en=datetime('now') WHERE id=?""",
                (enviados, errores, campana_id))
            conn.commit(); conn.close()

            if errores == 0:
                flash(f'Campaña enviada: {enviados} emails OK.', 'success')
            else:
                flash(f'Campaña enviada: {enviados} OK, {errores} errores. Revisa el detalle.', 'warning')
            return redirect(url_for('campanas_detalle', id=campana_id))

    remitentes = _remitentes_disponibles(conn)
    provincias = conn.execute("SELECT id, nombre FROM provincias ORDER BY nombre").fetchall()
    vendedores = conn.execute("SELECT id, nombre FROM usuarios WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('campanas/form.html',
                           remitentes=remitentes, provincias=provincias,
                           vendedores=vendedores, form_data=ImmutableMultiDict(),
                           preview_count=None, descripcion_filtros=[])


@app.route('/campanas/<int:id>')
@login_required
@admin_required
def campanas_detalle(id):
    conn = get_db()
    campana = conn.execute("SELECT * FROM campanas WHERE id=?", (id,)).fetchone()
    if not campana:
        conn.close(); flash('Campaña no encontrada.', 'error')
        return redirect(url_for('campanas_lista'))
    envios = conn.execute("""SELECT e.*, c.nombre_completo FROM campanas_envios e
        LEFT JOIN clientes c ON c.id = e.cliente_id
        WHERE e.campana_id=? ORDER BY e.id DESC""", (id,)).fetchall()
    conn.close()
    return render_template('campanas/detalle.html', campana=campana, envios=envios)


@app.route('/campanas/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def campanas_eliminar(id):
    conn = get_db()
    conn.execute("DELETE FROM campanas WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Campaña eliminada.', 'success')
    return redirect(url_for('campanas_lista'))


if __name__ == '__main__':
    from database import init_db
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)
