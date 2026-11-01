# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade102] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)

    # 1. Agregar campos a mayoristas_cuentas
    cols_m = [r[1] for r in conn.execute("PRAGMA table_info(mayoristas_cuentas)").fetchall()]
    campos_m = ['provincia', 'localidad', 'codigo_postal', 'calle', 'altura', 'piso', 'depto']
    for c in campos_m:
        if c not in cols_m:
            conn.execute(f"ALTER TABLE mayoristas_cuentas ADD COLUMN {c} TEXT")
            print(f"[upgrade102] + mayoristas_cuentas.{c}")

    # 2. Agregar campo requiere_factura a ordenes_venta
    cols_o = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'requiere_factura' not in cols_o:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN requiere_factura INTEGER DEFAULT 0")
        print("[upgrade102] + ordenes_venta.requiere_factura")

    conn.commit(); conn.close()


def patch_registro():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'registro.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    buscar = '''<div class="row g-2 mb-3">
        <div class="col-md-6">
          <label class="form-label">Telefono</label>
          <input name="telefono" class="form-control" value="{{ form.get('telefono', '') }}" placeholder="+54 9...">
        </div>
        <div class="col-md-6">
          <label class="form-label">CUIT / CUIL</label>
          <input name="cuit" class="form-control" value="{{ form.get('cuit', '') }}">
        </div>
      </div>'''

    nuevo = '''<div class="row g-2 mb-3">
        <div class="col-md-6">
          <label class="form-label">Telefono</label>
          <input name="telefono" class="form-control" value="{{ form.get('telefono', '') }}" placeholder="+54 9...">
        </div>
        <div class="col-md-6">
          <label class="form-label">CUIT / CUIL</label>
          <input name="cuit" class="form-control" value="{{ form.get('cuit', '') }}">
        </div>
      </div>

      <div class="row g-2 mb-3">
        <div class="col-md-6">
          <label class="form-label">Provincia *</label>
          <input name="provincia" class="form-control" required value="{{ form.get('provincia', '') }}" placeholder="Ej: Misiones">
        </div>
        <div class="col-md-6">
          <label class="form-label">Localidad *</label>
          <input name="localidad" class="form-control" required value="{{ form.get('localidad', '') }}" placeholder="Ej: Posadas">
        </div>
      </div>

      <div class="row g-2 mb-3">
        <div class="col-md-4">
          <label class="form-label">Calle *</label>
          <input name="calle" class="form-control" required value="{{ form.get('calle', '') }}">
        </div>
        <div class="col-md-2">
          <label class="form-label">Altura *</label>
          <input name="altura" class="form-control" required value="{{ form.get('altura', '') }}">
        </div>
        <div class="col-md-2">
          <label class="form-label">Piso</label>
          <input name="piso" class="form-control" value="{{ form.get('piso', '') }}">
        </div>
        <div class="col-md-2">
          <label class="form-label">Depto</label>
          <input name="depto" class="form-control" value="{{ form.get('depto', '') }}">
        </div>
        <div class="col-md-2">
          <label class="form-label">CP *</label>
          <input name="codigo_postal" class="form-control" required value="{{ form.get('codigo_postal', '') }}">
        </div>
      </div>'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade102] Campos de dirección agregados al registro público")


def patch_app51_registro():
    ruta = os.path.join(BASE, 'app51.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    buscar = '''        conn.execute("""INSERT INTO mayoristas_cuentas
            (nombre_completo, email, telefono, cuit, password_hash, estado)
            VALUES (?, ?, ?, ?, ?, 'pendiente')""",
            (nombre, email, telefono or None, cuit or None,
             generate_password_hash(password)))'''

    nuevo = '''        provincia = request.form.get('provincia', '').strip()
        localidad = request.form.get('localidad', '').strip()
        cp = request.form.get('codigo_postal', '').strip()
        calle = request.form.get('calle', '').strip()
        altura = request.form.get('altura', '').strip()
        piso = request.form.get('piso', '').strip()
        depto = request.form.get('depto', '').strip()

        conn.execute("""INSERT INTO mayoristas_cuentas
            (nombre_completo, email, telefono, cuit, password_hash, estado, provincia, localidad, codigo_postal, calle, altura, piso, depto)
            VALUES (?, ?, ?, ?, ?, 'pendiente', ?, ?, ?, ?, ?, ?, ?)""",
            (nombre, email, telefono or None, cuit or None,
             generate_password_hash(password), provincia, localidad, cp, calle, altura, piso, depto))'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade102] app51.py actualizado para guardar dirección")


def patch_checkout_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'checkout.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Eliminar el selector de transportista
    buscar_transp = '''<div class="mb-3">
              <label style="color:var(--cat-text-muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;">Transportista *</label>
              <select name="transportista_id" class="form-control">
                <option value="">-- Elegir --</option>
                {% for t in transportistas %}
                <option value="{{ t.id }}">{{ t.nombre }}</option>
                {% endfor %}
              </select>
            </div>'''
    contenido = contenido.replace(buscar_transp, '')

    # 2. Cambiar "Confirmar pedido" por dos botones de acción
    buscar_btn = '<button type="submit" class="cat-btn w-100 text-center mt-3">Confirmar pedido</button>'
    nuevo_btn = '''<button type="submit" name="accion" value="pagar" class="cat-btn w-100 text-center mt-3" style="background:#c9a96e; color:#000; border:none;">Pagar Ahora</button>
          <button type="submit" name="accion" value="guardar" class="cat-btn cat-btn-outline w-100 text-center mt-2" style="color:var(--cat-text); border:1px solid var(--cat-border);">Guardar Orden (Pagar después)</button>
          <div class="text-center mt-2 small text-muted">Las órdenes se cancelan a las 24hs si no se paga.</div>'''
    contenido = contenido.replace(buscar_btn, nuevo_btn)

    # 3. Agregar el checkbox de Factura
    buscar_notas = '''<textarea name="notas" class="form-control" rows="3" placeholder="Ej: entregar despues de las 18hs, es para regalo, etc."></textarea>'''
    nuevo_notas = buscar_notas + '''
          <div class="form-check mt-3">
            <input class="form-check-input" type="checkbox" name="requiere_factura" id="requiere_factura" value="1" style="background:var(--cat-surface); border-color:var(--cat-border);">
            <label class="form-check-label" for="requiere_factura" style="color:var(--cat-text-muted);font-size:.85rem;">Requiero Factura A/B</label>
          </div>'''
    contenido = contenido.replace(buscar_notas, nuevo_notas)

    # 4. Arreglar el contraste del botón "Iniciar pedido" en el carrito
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade102] checkout.html actualizado con botones de acción, factura y sin transportista")


def patch_carrito_html():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'carrito.html')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Arreglar el botón "Iniciar pedido"
    buscar_btn = '<a href="{{ url_for(\'catalogo.checkout\') }}" class="cat-btn w-100 text-center">Iniciar pedido</a>'
    nuevo_btn = '<a href="{{ url_for(\'catalogo.checkout\') }}" class="cat-btn w-100 text-center" style="background:#c9a96e; color:#000; text-decoration:none; font-weight:700; padding:1rem;">Ir a pagar / Finalizar pedido</a>'
    contenido = contenido.replace(buscar_btn, nuevo_btn)

    # Arreglar el contraste de la tabla
    buscar_th = '<th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;">Producto</th>'
    nuevo_th = '<th style="color:#a3a3a3;font-size:.75rem;text-transform:uppercase;padding:1rem;border-bottom:2px solid #333;">Producto</th>'
    contenido = contenido.replace(buscar_th, nuevo_th)

    buscar_th2 = '<th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:center;">Cantidad</th>'
    nuevo_th2 = '<th style="color:#a3a3a3;font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:center;border-bottom:2px solid #333;">Cantidad</th>'
    contenido = contenido.replace(buscar_th2, nuevo_th2)

    buscar_th3 = '<th style="color:var(--cat-text-muted);font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:right;">Subtotal</th>'
    nuevo_th3 = '<th style="color:#a3a3a3;font-size:.75rem;text-transform:uppercase;padding:1rem;text-align:right;border-bottom:2px solid #333;">Subtotal</th>'
    contenido = contenido.replace(buscar_th3, nuevo_th3)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade102] carrito.html actualizado (contraste y botón)")


def patch_app53_checkout():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Obtener la acción (pagar o guardar) y requiere_factura
    buscar_post = """        tipo_envio = request.form.get('tipo_envio', '').strip()
        notas = request.form.get('notas', '').strip()"""
    nuevo_post = """        tipo_envio = request.form.get('tipo_envio', '').strip()
        notas = request.form.get('notas', '').strip()
        accion = request.form.get('accion', 'pagar')
        requiere_factura = 1 if request.form.get('requiere_factura') else 0"""
    
    if buscar_post in contenido:
        contenido = contenido.replace(buscar_post, nuevo_post)

    # 2. Actualizar el INSERT de la orden
    buscar_insert = """             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles, origen, costo_envio)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, m['cliente_id'], vendedor_id, canal_id, 'mayorista',
             date.today().isoformat(), 'pendiente_pago', 'no_requiere',
             subtotal, 0, total_con_envio, notas,
             tipo_envio, destino_tipo, sucursal_detalle,
             int(transportista_id) if transportista_id else None, nro_guia,
             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, 'catalogo', info_envio['costo_envio']))"""
             
    nuevo_insert = """             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles, origen, costo_envio, requiere_factura)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, m['cliente_id'], vendedor_id, canal_id, 'mayorista',
             date.today().isoformat(), 'pendiente_pago', 'pendiente' if requiere_factura else 'no_requiere',
             subtotal, 0, total_con_envio, notas,
             tipo_envio, destino_tipo, sucursal_detalle,
             int(transportista_id) if transportista_id else None, nro_guia,
             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, 'catalogo', info_envio.get('costo_envio', 0), requiere_factura))"""

    if buscar_insert in contenido:
        contenido = contenido.replace(buscar_insert, nuevo_insert)
        print("[upgrade102] INSERT de la orden actualizado")

    # 3. Redirección final según la acción elegida
    buscar_redirect = """        flash(f'Pedido {numero} recibido. Te enviamos un email con el resumen y los datos para transferir.', 'success')
        return redirect(url_for('catalogo.mis_pedidos'))"""
        
    nuevo_redirect = """        if accion == 'guardar':
            flash(f'Orden {numero} guardada. Recordá que tenés 24hs para subir el comprobante antes de que se cancele.', 'warning')
            return redirect(url_for('catalogo.mis_pedidos'))
        else:
            flash(f'Pedido {numero} recibido. Por favor subí el comprobante para completar la compra.', 'success')
            return redirect(url_for('catalogo.mi_pedido_detalle', id=orden_id))"""

    if buscar_redirect in contenido:
        contenido = contenido.replace(buscar_redirect, nuevo_redirect)
        print("[upgrade102] Redirección post-checkout actualizada (Pagar vs Guardar)")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    print("=== Upgrade 102: UI Carrito + Registro Completo + Checkout Factura/Guardar ===")
    migrar()
    patch_registro()
    patch_app51_registro()
    patch_checkout_html()
    patch_carrito_html()
    patch_app53_checkout()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()