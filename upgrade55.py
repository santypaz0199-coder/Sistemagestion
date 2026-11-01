# -*- coding: utf-8 -*-
import os, sqlite3, re

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade55] escrito: {relpath}")


def migrar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade55] sin DB."); return
    conn = sqlite3.connect(db)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(ordenes_venta)").fetchall()]
    if 'origen' not in cols:
        conn.execute("ALTER TABLE ordenes_venta ADD COLUMN origen TEXT DEFAULT 'interno'")
        print("[upgrade55] + ordenes_venta.origen")

    # Marcar las ordenes existentes con canal 'Tienda online' como origen catalogo
    conn.execute("""
        UPDATE ordenes_venta SET origen='catalogo'
        WHERE canal_id IN (SELECT id FROM canales_venta WHERE lower(nombre)='tienda online')
        AND (origen IS NULL OR origen='interno')
    """)
    print("[upgrade55] ordenes existentes de Tienda online marcadas como catalogo")

    conn.commit(); conn.close()


def patch_app39():
    """Corrige el import roto de PLANTILLAS_DEFAULT."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        print("[upgrade55] no existe app39.py"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    viejo = """def ventas_email_enviar_v2(id, tipo):
    from app4 import PLANTILLAS_DEFAULT
    if tipo not in PLANTILLAS_DEFAULT:
        from flask import abort
        abort(404)"""

    nuevo = """def ventas_email_enviar_v2(id, tipo):
    TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}
    if tipo not in TIPOS_VALIDOS:
        from flask import abort
        abort(404)"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade55] fix import PLANTILLAS_DEFAULT en app39.py")
    elif 'TIPOS_VALIDOS' in contenido:
        print("[upgrade55] app39 ya tiene el fix")
    else:
        # Buscar variantes
        contenido = contenido.replace(
            "from app4 import PLANTILLAS_DEFAULT",
            "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}"
        )
        contenido = contenido.replace(
            "if tipo not in PLANTILLAS_DEFAULT:",
            "if tipo not in TIPOS_VALIDOS:"
        )
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade55] fix aplicado por reemplazo directo")


def patch_app53_marcar_origen():
    """Marca las ordenes creadas desde el catalogo con origen='catalogo'."""
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        print("[upgrade55] no existe app53.py"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if "origen" in contenido and "origen='catalogo'" in contenido:
        print("[upgrade55] app53 ya marca origen")
        return

    viejo = """        cur = conn.execute(\"\"\"INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)\"\"\","""

    nuevo = """        cur = conn.execute(\"\"\"INSERT INTO ordenes_venta
            (numero_interno, cliente_id, usuario_id, canal_id, tipo, fecha, estado,
             estado_facturacion, subtotal, descuento, total, notas,
             tipo_envio, destino_tipo, sucursal_detalle, transportista_id, nro_guia,
             destinatario_nombre, destinatario_provincia, destinatario_localidad,
             destinatario_cp, destinatario_calle, destinatario_detalles, origen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)\"\"\","""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        # Ahora buscar la tupla de valores para agregar 'catalogo' al final
        viejo_val = """             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles))"""
        nuevo_val = """             dest_nombre, dest_prov, dest_loc, dest_cp, dest_calle, dest_detalles, 'catalogo'))"""
        if viejo_val in contenido:
            contenido = contenido.replace(viejo_val, nuevo_val, 1)
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade55] app53 marca origen='catalogo' al crear orden")
        else:
            print("[upgrade55] ADVERTENCIA: no se encontro la tupla de valores")
    else:
        print("[upgrade55] ADVERTENCIA: no se encontro el INSERT de app53")


def patch_ventas_lista():
    """Reemplaza los botones de acciones por un dropdown y agrega badge catalogo."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade55] no existe ventas/lista.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'dropdown-acciones' in contenido:
        print("[upgrade55] ventas/lista ya tiene dropdown")
        return

    # 1. Agregar columna origen a la tabla (despues del ID)
    buscar_th = '<th>Fecha</th><th>ID</th><th>Estado</th>'
    nuevo_th = '<th>Fecha</th><th>ID</th><th>Origen</th><th>Estado</th>'
    if buscar_th in contenido:
        contenido = contenido.replace(buscar_th, nuevo_th, 1)
        print("[upgrade55] header Origen agregado")

    # 2. Agregar celda origen en cada fila (despues del ID)
    buscar_td = '''<td class="fw-semibold text-nowrap">{{ v.numero_interno }}</td>
<td>
<button type="button" class="btn btn-sm p-0 border-0" onclick="openEstado'''
    nuevo_td = '''<td class="fw-semibold text-nowrap">{{ v.numero_interno }}</td>
<td>
{% if v.origen == 'catalogo' %}<span class="badge" style="background:#8b5cf6;color:#fff;" title="Pedido desde el catalogo publico"><i class="bi bi-globe"></i> Catalogo</span>
{% else %}<span class="badge bg-light text-dark border" style="font-size:.7rem;">Interno</span>{% endif %}
</td>
<td>
<button type="button" class="btn btn-sm p-0 border-0" onclick="openEstado'''
    if buscar_td in contenido:
        contenido = contenido.replace(buscar_td, nuevo_td, 1)
        print("[upgrade55] celda Origen agregada")

    # 3. Reemplazar los botones de acciones por un dropdown
    buscar_acc = '''<td class="text-end text-nowrap">
<a href="{{ url_for('ventas_detalle', id=v.id) }}" class="btn btn-sm btn-outline-secondary" title="Ver / Editar"><i class="bi bi-eye"></i></a>
<a href="{{ url_for('ventas_imprimir', id=v.id) }}" target="_blank" class="btn btn-sm btn-outline-dark" title="Imprimir / PDF"><i class="bi bi-printer"></i></a>
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openCompartir({{ v.id }})" title="Compartir"><i class="bi bi-share"></i></button>
{% if v.wa_url %}<a href="{{ v.wa_url }}" target="_blank" class="btn btn-sm btn-outline-success" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
{% else %}<button class="btn btn-sm btn-outline-secondary" disabled title="Sin telefono"><i class="bi bi-whatsapp"></i></button>{% endif %}
<button type="button" class="btn btn-sm btn-outline-primary" onclick="openEmail({{ v.id }})" title="Email"><i class="bi bi-envelope"></i></button>
<button type="button" class="btn btn-sm btn-outline-danger" onclick="openBorrar({{ v.id }}, '{{ v.numero_interno }}')" title="Borrar"><i class="bi bi-trash"></i></button>
</td>'''

    nuevo_acc = '''<td class="text-end text-nowrap dropdown-acciones">
<div class="dropdown">
<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="dropdown" aria-expanded="false" title="Acciones">
<i class="bi bi-three-dots-vertical"></i>
</button>
<ul class="dropdown-menu dropdown-menu-end">
<li><a class="dropdown-item" href="{{ url_for('ventas_detalle', id=v.id) }}"><i class="bi bi-eye text-secondary"></i> Ver / Editar</a></li>
<li><a class="dropdown-item" href="{{ url_for('ventas_imprimir', id=v.id) }}" target="_blank"><i class="bi bi-printer text-secondary"></i> Imprimir / PDF</a></li>
<li><a class="dropdown-item" href="#" onclick="openCompartir({{ v.id }}); return false;"><i class="bi bi-share text-secondary"></i> Compartir</a></li>
<li><hr class="dropdown-divider"></li>
{% if v.wa_url %}
<li><a class="dropdown-item" href="{{ v.wa_url }}" target="_blank"><i class="bi bi-whatsapp text-success"></i> WhatsApp</a></li>
{% else %}
<li><span class="dropdown-item text-muted disabled"><i class="bi bi-whatsapp"></i> WhatsApp (sin telefono)</span></li>
{% endif %}
<li><a class="dropdown-item" href="#" onclick="openEmail({{ v.id }}); return false;"><i class="bi bi-envelope text-primary"></i> Enviar email</a></li>
<li><hr class="dropdown-divider"></li>
<li><a class="dropdown-item text-danger" href="#" onclick="openBorrar({{ v.id }}, '{{ v.numero_interno }}'); return false;"><i class="bi bi-trash"></i> Borrar</a></li>
</ul>
</div>
</td>'''

    if buscar_acc in contenido:
        contenido = contenido.replace(buscar_acc, nuevo_acc, 1)
        print("[upgrade55] acciones reemplazadas por dropdown")
    else:
        # Buscar una variante mas flexible
        patron = re.compile(
            r'<td class="text-end text-nowrap">\s*'
            r'<a href="\{\{ url_for\(\'ventas_detalle\'.*?</td>',
            re.DOTALL
        )
        match = patron.search(contenido)
        if match:
            contenido = contenido[:match.start()] + nuevo_acc + contenido[match.end():]
            print("[upgrade55] acciones reemplazadas por dropdown (patron regex)")
        else:
            print("[upgrade55] ADVERTENCIA: no se encontro el bloque de acciones")

    # 4. Actualizar el colspan de "sin ventas"
    contenido = contenido.replace(
        '<td colspan="10" class="text-center text-muted py-4">No hay ventas cargadas.</td>',
        '<td colspan="11" class="text-center text-muted py-4">No hay ventas cargadas.</td>'
    )

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade55] ventas/lista.html actualizado")


def patch_dashboard_badge():
    """Agrega un badge de 'Origen' en el detalle de la orden si es del catalogo."""
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta):
        print("[upgrade55] no existe ventas/detalle.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'badge-origen-catalogo' in contenido:
        print("[upgrade55] detalle ya tiene badge origen")
        return

    # Buscar la linea del numero de orden y agregar el badge
    buscar = '''<h4 class="mb-0">{{ orden.numero_interno }}
{% if orden.estado=='pendiente_pago' %}'''

    nuevo = '''<h4 class="mb-0">{{ orden.numero_interno }}
{% if orden.origen == 'catalogo' %}<span class="badge ms-2 badge-origen-catalogo" style="background:#8b5cf6;color:#fff;font-size:.7rem;"><i class="bi bi-globe"></i> Catalogo</span>{% endif %}
{% if orden.estado=='pendiente_pago' %}'''

    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade55] badge origen catalogo en detalle")
    else:
        print("[upgrade55] ADVERTENCIA: no se encontro el titulo del detalle")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


APP55_PY = r'''
# Modulo vacio: solo se usa para forzar carga de app55 en run.bat
# Los cambios reales estan en los patches de arriba
pass
'''


def main():
    print("=== Upgrade 55: Fix email + origen catalogo + dropdown acciones ===")
    migrar()
    patch_app39()
    patch_app53_marcar_origen()
    patch_ventas_lista()
    patch_dashboard_badge()
    escribir('app55.py', APP55_PY)
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()