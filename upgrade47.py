# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base_css():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade47] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Actualizar el CSS del sidebar para que tenga scroll interno y user-info fijo abajo
    viejo_css = """.sidebar{
  width:250px;
  min-height:100vh;
  position:fixed;
  top:0; left:0;
  background:linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color:#cbd5e1;
  padding:1.5rem 0 1rem;
  display:flex;
  flex-direction:column;
  border-right:1px solid rgba(255,255,255,.04);
}"""

    nuevo_css = """.sidebar{
  width:250px;
  height:100vh;
  position:fixed;
  top:0; left:0;
  background:linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color:#cbd5e1;
  display:flex;
  flex-direction:column;
  border-right:1px solid rgba(255,255,255,.04);
  overflow:hidden;
}
.sidebar-nav{
  flex:1;
  overflow-y:auto;
  padding:.5rem 0;
  min-height:0;
}
.sidebar-nav::-webkit-scrollbar{ width:6px; }
.sidebar-nav::-webkit-scrollbar-track{ background:transparent; }
.sidebar-nav::-webkit-scrollbar-thumb{ background:rgba(255,255,255,.15); border-radius:3px; }
.sidebar-nav::-webkit-scrollbar-thumb:hover{ background:rgba(255,255,255,.25); }"""

    if viejo_css in contenido:
        contenido = contenido.replace(viejo_css, nuevo_css, 1)
        print("[upgrade47] CSS del sidebar actualizado (scroll interno)")
    else:
        print("[upgrade47] ADVERTENCIA: no se encontro el CSS del sidebar")
        # Intentar buscar de otra manera
        idx = contenido.find('.sidebar{')
        if idx > 0:
            # Encontrar el cierre del bloque
            cierre = contenido.find('}', idx)
            if cierre > 0:
                bloque_viejo = contenido[idx:cierre+1]
                contenido = contenido.replace(bloque_viejo, nuevo_css, 1)
                print("[upgrade47] CSS del sidebar reemplazado por patron")

    # 2. Envolver los links del menu en un div scrollable
    # Buscar el inicio del bloque de links (justo despues del brand)
    buscar_inicio = '''<div class="brand">Familia Zaragoza ®</div>
<a href="{{ url_for('dashboard') }}"'''

    nuevo_inicio = '''<div class="brand">Familia Zaragoza ®</div>
<div class="sidebar-nav">
<a href="{{ url_for('dashboard') }}"'''

    if buscar_inicio in contenido:
        contenido = contenido.replace(buscar_inicio, nuevo_inicio, 1)
        print("[upgrade47] abertura de sidebar-nav agregada")
    else:
        print("[upgrade47] ADVERTENCIA: no se encontro el brand + dashboard")

    # Cerrar el div antes del bloque objetivo_sidebar
    buscar_cierre = '''{% if objetivo_sidebar is defined and objetivo_sidebar and objetivo_sidebar.monto > 0 %}
<div class="sidebar-objetivo">'''

    nuevo_cierre = '''</div><!-- /sidebar-nav -->

{% if objetivo_sidebar is defined and objetivo_sidebar and objetivo_sidebar.monto > 0 %}
<div class="sidebar-objetivo">'''

    if buscar_cierre in contenido:
        contenido = contenido.replace(buscar_cierre, nuevo_cierre, 1)
        print("[upgrade47] cierre de sidebar-nav agregado")
    else:
        print("[upgrade47] ADVERTENCIA: no se encontro el bloque objetivo_sidebar para cerrar el nav")

    # 3. Asegurar que el user-info no se achique
    viejo_ui = """.sidebar .user-info{
  margin-top:auto;
  padding:1.25rem 1.25rem;
  border-top:1px solid rgba(255,255,255,.06);
  font-size:.82rem;
}"""

    nuevo_ui = """.sidebar .user-info{
  flex-shrink:0;
  padding:1rem 1.25rem;
  border-top:1px solid rgba(255,255,255,.06);
  font-size:.82rem;
}"""

    if viejo_ui in contenido:
        contenido = contenido.replace(viejo_ui, nuevo_ui, 1)
        print("[upgrade47] user-info con flex-shrink:0")

    # 4. Tambien asegurar que el brand no scrollee
    viejo_brand = """.sidebar .brand{
  padding:0 1.5rem 1.5rem;
  font-weight:800;
  color:#fff;
  border-bottom:1px solid rgba(255,255,255,.06);
  margin-bottom:.75rem;
  font-size:1.1rem;
  letter-spacing:-.02em;
  display:flex;
  align-items:center;
  gap:.5rem;
}"""

    nuevo_brand = """.sidebar .brand{
  flex-shrink:0;
  padding:1.5rem 1.5rem 1.25rem;
  font-weight:800;
  color:#fff;
  border-bottom:1px solid rgba(255,255,255,.06);
  font-size:1.1rem;
  letter-spacing:-.02em;
  display:flex;
  align-items:center;
  gap:.5rem;
}"""

    if viejo_brand in contenido:
        contenido = contenido.replace(viejo_brand, nuevo_brand, 1)
        print("[upgrade47] brand con flex-shrink:0 y padding corregido")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app45; app45.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 47: Fix sidebar con scroll (Salir y Mi Cuenta siempre visibles) ===")
    patch_base_css()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("")
    print("Recarga el navegador con Ctrl+F5 para ver los cambios")


if __name__ == '__main__':
    main()