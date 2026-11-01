import os
import sqlite3

def actualizar_base_de_datos():
    print("1. Actualizando base de datos (agregando columnas para archivos)...")
    ruta_db = 'sistema.db'
    if not os.path.exists(ruta_db):
        print("No se encontró sistema.db")
        return

    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    # Tabla ordenes_venta (por si tiene tilde o no)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%rdenes_venta%'")
    tabla = cursor.fetchone()[0]
    
    cursor.execute(f"PRAGMA table_info('{tabla}')")
    cols = [c[1] for c in cursor.fetchall()]
    
    if 'requiere_factura' not in cols:
        cursor.execute(f"ALTER TABLE '{tabla}' ADD COLUMN requiere_factura TEXT DEFAULT 'no'")
        print(" -> Columna 'requiere_factura' agregada.")
    if 'archivo_factura' not in cols:
        cursor.execute(f"ALTER TABLE '{tabla}' ADD COLUMN archivo_factura TEXT")
        print(" -> Columna 'archivo_factura' agregada.")

    # Tabla pagos
    cursor.execute("PRAGMA table_info(pagos)")
    cols_pagos = [c[1] for c in cursor.fetchall()]
    if 'archivo_comprobante' not in cols_pagos:
        cursor.execute("ALTER TABLE pagos ADD COLUMN archivo_comprobante TEXT")
        print(" -> Columna 'archivo_comprobante' agregada a pagos.")

    conn.commit()
    conn.close()
    print("Base de datos lista.\n")

def crear_app181():
    print("2. Creando el cerebro para procesar pagos y facturas (app181.py)...")
    codigo = """
from flask import render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from app48 import app
from app import permiso_required
from database import get_db
from datetime import date
import os
import uuid

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/ventas/<int:id>', methods=['GET', 'POST'])
@login_required
@permiso_required('ventas')
def ventas_detalle_v2(id):
    conn = get_db()
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'actualizar_admin':
            notas = request.form.get('notas', '').strip()
            requiere_factura = request.form.get('requiere_factura', 'no')
            estado_facturacion = request.form.get('estado_facturacion', 'no_requiere')
            
            archivo_factura = None
            if 'archivo_factura' in request.files:
                file = request.files['archivo_factura']
                if file and file.filename != '':
                    filename = str(uuid.uuid4()) + "_" + file.filename
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    archivo_factura = filename
            
            if archivo_factura:
                conn.execute("UPDATE ordenes_venta SET notas=?, requiere_factura=?, estado_facturacion=?, archivo_factura=? WHERE id=?",
                             (notas, requiere_factura, estado_facturacion, archivo_factura, id))
            else:
                conn.execute("UPDATE ordenes_venta SET notas=?, requiere_factura=?, estado_facturacion=? WHERE id=?",
                             (notas, requiere_factura, estado_facturacion, id))
            conn.commit()
            flash('Datos actualizados correctamente.', 'success')
            
        elif accion == 'registrar_pago':
            monto = float(request.form.get('monto_pago') or 0)
            
            archivo_comprobante = None
            if 'archivo_comprobante' in request.files:
                file = request.files['archivo_comprobante']
                if file and file.filename != '':
                    filename = str(uuid.uuid4()) + "_" + file.filename
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    archivo_comprobante = filename
            
            # Intentamos guardar el pago
            conn.execute("INSERT INTO pagos (orden_id, monto, fecha, archivo_comprobante) VALUES (?, ?, ?, ?)",
                         (id, monto, date.today().isoformat(), archivo_comprobante))
            conn.commit()
            flash('Pago registrado correctamente.', 'success')
            
        conn.close()
        return redirect(url_for('ventas_detalle', id=id))

    # GET logic (igual al original)
    orden = conn.execute(\"\"\"SELECT o.*, c.nombre_completo as cliente_nombre, c.email as cliente_email,
        c.telefono as cliente_telefono, c.provincia as cliente_provincia, c.localidad as cliente_localidad,
        c.nro_doc as cliente_doc, c.tipo_doc as cliente_tipo_doc,
        u.nombre as vendedor_nombre, cv.nombre as canal_nombre, t.nombre as transportista_nombre
        FROM ordenes_venta o JOIN clientes c ON c.id=o.cliente_id JOIN usuarios u ON u.id=o.usuario_id
        LEFT JOIN canales_venta cv ON cv.id=o.canal_id LEFT JOIN transportistas t ON t.id=o.transportista_id
        WHERE o.id=?\"\"\", (id,)).fetchone()
        
    if not orden:
        conn.close(); return redirect(url_for('ventas_lista'))
    if not current_user.es_admin and orden['usuario_id'] != current_user.id:
        conn.close(); flash('Sin permiso.', 'error'); return redirect(url_for('ventas_lista'))
        
    items = conn.execute("SELECT oi.*, p.nombre as producto_nombre, p.sku FROM orden_items oi JOIN productos p ON p.id=oi.producto_id WHERE oi.orden_id=?", (id,)).fetchall()
    pagos = conn.execute("SELECT pg.*, mp.nombre as medio_nombre FROM pagos pg LEFT JOIN medios_pago mp ON mp.id=pg.medio_pago_id WHERE pg.orden_id=? ORDER BY pg.id", (id,)).fetchall()
    total_pagado = sum(p['monto'] for p in pagos)
    medios = conn.execute("SELECT * FROM medios_pago WHERE activo=1 ORDER BY nombre").fetchall()
    transportistas = conn.execute("SELECT * FROM transportistas WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template('ventas/detalle.html', orden=orden, items=items, pagos=pagos,
                           total_pagado=total_pagado, medios=medios, transportistas=transportistas)

app.view_functions['ventas_detalle'] = ventas_detalle_v2
"""
    with open('app181.py', 'w', encoding='utf-8') as f:
        f.write(codigo)
    print("Archivo app181.py creado con éxito.")

def modificar_app_py():
    print("3. Conectando app181.py con tu sistema...")
    ruta_app = 'app.py'
    if os.path.exists(ruta_app):
        with open(ruta_app, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        if 'import app181' not in contenido:
            with open(ruta_app, 'a', encoding='utf-8') as f:
                f.write('\nimport app181\n')
            print(" -> ¡Conectado con éxito! Se agregó 'import app181' al final de app.py.")
        else:
            print(" -> Ya estaba conectado.")
    else:
        print(" -> OJO: No se encontró app.py. Tendrás que agregar 'import app181' al final del archivo que arranca tu sistema manualmente.")

def actualizar_html():
    print("4. Actualizando detalle.html para mostrar los archivos...")
    ruta = os.path.join('templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return

    with open(ruta, 'r', encoding='utf-8') as f:
        html = f.read()

    # Mostrar link de factura si existe
    buscar_factura = "{% if orden.archivo_factura %}\n                    <div class=\"small text-success mt-1\"><i class=\"bi bi-check-circle-fill\"></i> Factura cargada</div>\n                    {% endif %}"
    reemplazar_factura = "{% if orden.archivo_factura %}\n                    <div class=\"small text-success mt-1\"><i class=\"bi bi-check-circle-fill\"></i> Factura cargada: <a href=\"/uploads/{{ orden.archivo_factura }}\" target=\"_blank\">Ver Archivo</a></div>\n                    {% endif %}"
    
    if buscar_factura in html:
        html = html.replace(buscar_factura, reemplazar_factura)
    
    # Mostrar link de comprobante en la lista de pagos
    buscar_pagos = "<td>{{ p.fecha }}</td><td>{{ p.medio_nombre or '—' }}</td><td class=\"num\">${{ '%.2f'|format(p.monto) }}</td>"
    reemplazar_pagos = "<td>{{ p.fecha }}</td><td>{{ p.medio_nombre or '—' }} {% if p.archivo_comprobante %}<a href=\"/uploads/{{ p.archivo_comprobante }}\" target=\"_blank\" class=\"ms-2 badge bg-info text-dark\"><i class=\"bi bi-paperclip\"></i> Comprobante</a>{% endif %}</td><td class=\"num\">${{ '%.2f'|format(p.monto) }}</td>"
    
    if buscar_pagos in html:
        html = html.replace(buscar_pagos, reemplazar_pagos)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(html)
    print(" -> detalle.html actualizado.")

if __name__ == '__main__':
    actualizar_base_de_datos()
    crear_app181()
    modificar_app_py()
    actualizar_html()
    print("\n¡TODO LISTO! Reinicia el servidor (run.bat) y presiona Ctrl+F5 en el navegador.")