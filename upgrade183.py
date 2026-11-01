import os

def arreglar_app_py():
    print("1. Limpiando app.py...")
    ruta = 'app.py'
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            lineas = f.readlines()
        
        nuevas_lineas = []
        for linea in lineas:
            if 'import app181' in linea:
                print(" -> Se eliminó 'import app181' de app.py.")
                continue
            nuevas_lineas.append(linea)
        
        with open(ruta, 'w', encoding='utf-8') as f:
            f.writelines(nuevas_lineas)

def arreglar_run_bat():
    print("2. Arreglando run.bat...")
    ruta = 'run.bat'
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Borramos cualquier intento anterior fallido
        contenido = contenido.replace('; import app181', '')
        contenido = contenido.replace('import app181; ', '')
        
        # Lo agregamos justo al final, antes de que arranque el servidor
        if 'app48.app.run' in contenido:
            contenido = contenido.replace('app48.app.run', 'import app181; app48.app.run')
            print(" -> Se agregó 'import app181' al final de run.bat. ¡Perfecto!")
        
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)

def crear_app181_definitivo():
    print("3. Generando el cerebro de pagos y facturas (a prueba de errores)...")
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
            
            conn.execute("INSERT INTO pagos (orden_id, monto, fecha, archivo_comprobante) VALUES (?, ?, ?, ?)",
                         (id, monto, date.today().isoformat(), archivo_comprobante))
            conn.commit()
            flash('Pago registrado correctamente.', 'success')
            
        conn.close()
        return redirect(url_for('ventas_detalle', id=id))

    # GET logic
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

# LA MAGIA PARA QUE NO CHOQUEN LAS RUTAS:
# Registramos la ruta con un nombre interno único (ventas_detalle_v2_endpoint)
# y le decimos a Flask que el nombre "ventas_detalle" use esta nueva función.
if 'ventas_detalle_v2_endpoint' not in app.view_functions:
    app.add_url_rule('/ventas/<int:id>', 'ventas_detalle_v2_endpoint', ventas_detalle_v2, methods=['GET', 'POST'])
    app.view_functions['ventas_detalle'] = ventas_detalle_v2
"""
    with open('app181.py', 'w', encoding='utf-8') as f:
        f.write(codigo)
    print(" -> app181.py generado correctamente sin choques de rutas.")

if __name__ == '__main__':
    arreglar_app_py()
    arreglar_run_bat()
    crear_app181_definitivo()
    print("\n¡TODO ARREGLADO! Ejecutá run.bat y probá subir un archivo. Vas a ver que ahora sí funciona.")