# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        print("[upgrade54] no existe app53.py"); return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    viejo = """        return jsonify({'ok': False, 'error': 'Tu cuenta aun no esta aprobada.')}), 403"""
    nuevo = """        return jsonify({'ok': False, 'error': 'Tu cuenta aun no esta aprobada.'}), 403"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade54] FIX aplicado: parentesis corregido en linea 63")
    elif nuevo in contenido:
        print("[upgrade54] ya estaba corregido")
    else:
        print("[upgrade54] ADVERTENCIA: no se encontro la linea exacta")

    # Buscar otras posibles variantes del mismo error
    if 'return jsonify({' in contenido and '}), 403' in contenido:
        # Ya lo corregimos arriba
        pass


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 54: Fix sintaxis en app53.py ===")
    patch_app53()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()