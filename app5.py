
from flask import render_template
from flask_login import login_required, current_user
from app4 import app
from database import get_db
from app4 import _cargar_orden


@app.route('/ventas/<int:id>')
@login_required
def ventas_detalle_v2(id):
    conn = get_db()
    orden = _cargar_orden(conn, id)
    if not orden:
        conn.close(); return render_template('ventas/lista.html', ventas=[])
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); return render_template('ventas/lista.html', ventas=[])

    items = conn.execute("""SELECT oi.*, p.nombre as producto_nombre, p.sku
        FROM orden_items oi JOIN productos p ON p.id=oi.producto_id
        WHERE oi.orden_id=?""", (id,)).fetchall()
    pagos = conn.execute("""SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg
        LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id
        WHERE pg.orden_id=? ORDER BY pg.id""", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1 ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    archivos = conn.execute("SELECT * FROM archivos WHERE orden_id=? ORDER BY id DESC", (id,)).fetchall()
    emails = conn.execute("SELECT * FROM emails_enviados WHERE orden_id=? ORDER BY id DESC LIMIT 20", (id,)).fetchall()

    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas,
                           archivos=archivos, emails=emails)


app.view_functions['ventas_detalle'] = ventas_detalle_v2
