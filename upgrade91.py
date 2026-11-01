# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app67():
    ruta = os.path.join(BASE, 'app67.py')
    if not os.path.exists(ruta):
        print("[upgrade91] no existe app67.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Reemplazar la consulta del endpoint de ciudades
    viejo = """        SELECT COALESCE(p.nombre, 'Sin provincia') as provincia,
               COALESCE(c.localidad, 'Sin localidad') as localidad,
               COUNT(o.id) as cantidad,
               SUM(o.total) as total
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias p ON p.id = c.provincia_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) >= ?
        GROUP BY c.provincia_id, c.localidad
        ORDER BY total DESC
        LIMIT 15"""

    nuevo = """        SELECT COALESCE(p.nombre, 'Sin provincia') as provincia,
               COALESCE(l.nombre, c.localidad, 'Sin localidad') as localidad,
               COUNT(o.id) as cantidad,
               SUM(o.total) as total
        FROM ordenes_venta o
        JOIN clientes c ON c.id = o.cliente_id
        LEFT JOIN provincias p ON p.id = c.provincia_id
        LEFT JOIN localidades l ON l.id = c.localidad_id
        WHERE o.estado IN ('pagado_sin_enviar','pagado_enviado')
        AND date(o.fecha) >= ?
        GROUP BY c.provincia_id, c.localidad_id, c.localidad, p.nombre, l.nombre
        ORDER BY total DESC
        LIMIT 15"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade91] Consulta de ciudades corregida (ahora usa localidad_id)")
    else:
        print("[upgrade91] ADVERTENCIA: no se encontró la consulta exacta. Intentando otra variante...")
        
        # Si el texto exacto falló (por espacios), intentamos con regex
        patron = re.compile(r"COALESCE\(c\.localidad, 'Sin localidad'\) as localidad.*?GROUP BY c\.provincia_id, c\.localidad", re.DOTALL)
        
        def reemplazar(match):
            texto = match.group(0)
            texto = texto.replace("COALESCE(c.localidad, 'Sin localidad')", "COALESCE(l.nombre, c.localidad, 'Sin localidad')")
            texto = texto.replace("LEFT JOIN provincias p ON p.id = c.provincia_id", "LEFT JOIN provincias p ON p.id = c.provincia_id\n        LEFT JOIN localidades l ON l.id = c.localidad_id")
            texto = texto.replace("GROUP BY c.provincia_id, c.localidad", "GROUP BY c.provincia_id, c.localidad_id, c.localidad, p.nombre, l.nombre")
            return texto

        contenido, n = patron.subn(reemplazar, contenido)
        if n > 0:
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("[upgrade91] Consulta corregida usando regex")
        else:
            print("[upgrade91] ERROR: no se pudo aplicar el parche automático. Revisá app67.py manualmente.")

def main():
    print("=== Upgrade 91: Fix localidad_id en detalle de ciudades ===")
    patch_app67()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()