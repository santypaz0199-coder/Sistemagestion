# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade59] no existe base.html"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Reescribir TODO el bloque del sidebar con reglas mas robustas
    patron_sidebar = re.compile(
        r'\.sidebar\{.*?\}',
        re.DOTALL
    )
    match = patron_sidebar.search(contenido)

    nuevo_sidebar_css = """.sidebar{
  width:210px;
  height:100vh;
  max-height:100vh;
  position:fixed !important;
  top:0; left:0;
  bottom:0;
  background:linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color:#cbd5e1;
  display:flex;
  flex-direction:column;
  border-right:1px solid rgba(255,255,255,.04);
  overflow:hidden;
  z-index:1000;
  box-sizing:border-box;
}"""

    if match:
        contenido = contenido[:match.start()] + nuevo_sidebar_css + contenido[match.end():]
        print("[upgrade59] CSS del sidebar reescrito")
    else:
        print("[upgrade59] ADVERTENCIA: no se encontro .sidebar{...}")

    # 2. Asegurar que el content tenga min-height y no empuje el layout
    patron_content = re.compile(
        r'\.content\{.*?\}',
        re.DOTALL
    )
    match_c = patron_content.search(contenido)

    nuevo_content_css = """.content{
  margin-left:210px;
  padding:2rem 2.5rem;
  min-height:100vh;
  box-sizing:border-box;
}"""

    if match_c:
        contenido = contenido[:match_c.start()] + nuevo_content_css + contenido[match_c.end():]
        print("[upgrade59] CSS del content reescrito")

    # 3. Asegurar que el body NO tenga overflow:hidden en el root
    # y que tenga min-height
    patron_body = re.compile(r'body\{[^}]*\}', re.DOTALL)
    match_b = patron_body.search(contenido)
    if match_b:
        bloque_actual = match_b.group(0)
        # Agregar min-height y box-sizing
        if 'min-height' not in bloque_actual:
            bloque_actual_nuevo = bloque_actual.replace('}', '  min-height:100vh;\n}')
            contenido = contenido[:match_b.start()] + bloque_actual_nuevo + contenido[match_b.end():]
            print("[upgrade59] body con min-height:100vh")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade59] base.html actualizado")


def main():
    print("=== Upgrade 59: Fix sidebar fijo (no se mueve al scrollear) ===")
    patch_base_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y recarga con Ctrl+F5")


if __name__ == '__main__':
    main()