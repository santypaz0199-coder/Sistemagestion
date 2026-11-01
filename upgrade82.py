# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade82] no existe base.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Quitar los scripts del fondo (por si están ahí)
    contenido = contenido.replace('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>', '')
    contenido = contenido.replace('<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>', '')

    # 2. Insertarlos arriba en el <head>
    scripts = '''
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
'''
    if 'chart.umd.min.js' not in contenido:
        contenido = contenido.replace('</head>', scripts + '</head>')
        print("[upgrade82] Chart.js movido al <head> de base.html")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_dashboard():
    ruta = os.path.join(BASE, 'templates', 'dashboard.html')
    if not os.path.exists(ruta):
        print("[upgrade82] no existe dashboard.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 3. Envolver el código JS en un evento DOMContentLoaded
    # para asegurarnos de que el HTML y las librerías estén listos.
    
    # Buscar donde inicia el script
    pos_inicio = contenido.find('<script>')
    pos_fin = contenido.rfind('</script>')
    
    if pos_inicio != -1 and pos_fin != -1:
        js_actual = contenido[pos_inicio+8:pos_fin] # 8 es len('<script>')
        
        # Sacar la comprobación de typeof Chart que estaba ocultando el error
        js_actual = js_actual.replace("if (typeof Chart === 'undefined') return;", "")
        
        nuevo_js = f'''
<script>
document.addEventListener("DOMContentLoaded", function() {{
    try {{
{js_actual}
    }} catch(e) {{
        console.error("Error dibujando gráficos:", e);
    }}
}});
</script>
'''
        contenido = contenido[:pos_inicio] + nuevo_js + contenido[pos_fin+9:]
        print("[upgrade82] Código JS envuelto en DOMContentLoaded")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def main():
    print("=== Upgrade 82: Fix de carga de Chart.js (esperando que cargue) ===")
    patch_base()
    patch_dashboard()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()