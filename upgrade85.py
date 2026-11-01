# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app67():
    ruta = os.path.join(BASE, 'app67.py')
    if not os.path.exists(ruta):
        print("[upgrade85] no existe app67.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Borrar los imports que quedaron sueltos al final (si están)
    contenido = contenido.replace("from flask import jsonify\n\n@app.route('/api/detalle-mes", "@app.route('/api/detalle-mes")
    
    # 2. Asegurar que las cabeceras tengan login_required y jsonify
    # Reemplazamos la primera línea que sabemos que existe.
    viejo_import = "from datetime import date\nfrom calendar import monthrange\nfrom app66 import app\nfrom flask import request\nfrom flask_login import current_user\nfrom database import get_db"
    nuevo_import = "from datetime import date, timedelta\nfrom calendar import monthrange\nfrom flask import request, jsonify\nfrom flask_login import current_user, login_required\nfrom app66 import app\nfrom database import get_db"

    if viejo_import in contenido:
        contenido = contenido.replace(viejo_import, nuevo_import, 1)
        print("[upgrade85] Imports corregidos en app67.py (con login_required y jsonify)")
    else:
        # Si el archivo cambió un poco, intentamos inyectar solo el login_required
        if 'login_required' not in contenido.split('def ')[0]: # si no está en las cabeceras
            contenido = "from flask import jsonify\nfrom flask_login import login_required\n" + contenido
            print("[upgrade85] Imports inyectados forzadamente")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 85: Fix import login_required en app67 ===")
    patch_app67()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()