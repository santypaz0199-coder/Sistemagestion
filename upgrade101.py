# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app95():
    ruta = os.path.join(BASE, 'app95.py')
    if not os.path.exists(ruta):
        print("[upgrade101] no existe app95.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Actualizar la consulta principal en calcular_envio_carrito
    viejo_sql1 = """        SELECT * FROM escalas_envio_b2b 
        WHERE peso_desde <= ? AND peso_hasta >= ? AND tipo_destino = ? AND activo=1
        LIMIT 1"""
    
    nuevo_sql1 = """        SELECT * FROM escalas_envio_b2b 
        WHERE peso_desde <= ? AND peso_hasta >= ? AND (tipo_destino = ? OR tipo_destino = 'ambos') AND activo=1
        LIMIT 1"""

    if viejo_sql1 in contenido:
        contenido = contenido.replace(viejo_sql1, nuevo_sql1)
        print("[upgrade101] Consulta principal actualizada (incluye 'ambos')")

    # 2. Actualizar la consulta de fallback (por si se pasa del peso máximo)
    viejo_sql2 = """        escala = conn.execute("SELECT * FROM escalas_envio_b2b WHERE tipo_destino = ? AND activo=1 ORDER BY peso_hasta DESC LIMIT 1", (destino_tipo,)).fetchone()"""
    
    nuevo_sql2 = """        escala = conn.execute("SELECT * FROM escalas_envio_b2b WHERE (tipo_destino = ? OR tipo_destino = 'ambos') AND activo=1 ORDER BY peso_hasta DESC LIMIT 1", (destino_tipo,)).fetchone()"""

    if viejo_sql2 in contenido:
        contenido = contenido.replace(viejo_sql2, nuevo_sql2)
        print("[upgrade101] Consulta de fallback actualizada (incluye 'ambos')")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_envios_html():
    ruta = os.path.join(BASE, 'templates', 'b2b', 'envios.html')
    if not os.path.exists(ruta):
        print("[upgrade101] no existe templates/b2b/envios.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Agregar la opción "Ambos" al dropdown del formulario
    viejo_select = '''<select name="tipo_destino" class="form-select" required>
<option value="sucursal">Sucursal (Retiro en agencia)</option>
<option value="domicilio">Domicilio (Envío a casa)</option>
</select>'''

    nuevo_select = '''<select name="tipo_destino" class="form-select" required>
<option value="sucursal">Sucursal (Retiro en agencia)</option>
<option value="domicilio">Domicilio (Envío a casa)</option>
<option value="ambos">Ambos (Mismo precio)</option>
</select>'''

    if viejo_select in contenido:
        contenido = contenido.replace(viejo_select, nuevo_select)
        print("[upgrade101] Opción 'Ambos' agregada al formulario")

    # 2. Actualizar la tabla para mostrar el badge de "Ambos"
    viejo_badge = '''{% if e.tipo_destino == 'domicilio' %}
<span class="badge bg-primary">Domicilio</span>
{% else %}
<span class="badge bg-secondary">Sucursal</span>
{% endif %}'''

    nuevo_badge = '''{% if e.tipo_destino == 'ambos' %}
<span class="badge bg-info text-dark">Ambos</span>
{% elif e.tipo_destino == 'domicilio' %}
<span class="badge bg-primary">Domicilio</span>
{% else %}
<span class="badge bg-secondary">Sucursal</span>
{% endif %}'''

    if viejo_badge in contenido:
        contenido = contenido.replace(viejo_badge, nuevo_badge)
        print("[upgrade101] Badge 'Ambos' agregado a la tabla")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 101: Opción 'Ambos' para envíos al mismo precio ===")
    patch_app95()
    patch_envios_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")

if __name__ == '__main__':
    main()