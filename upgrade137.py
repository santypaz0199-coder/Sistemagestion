# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app4():
    ruta = os.path.join(BASE, 'app4.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Inyectar la función de plantilla HTML
    if 'def _plantilla_html_correo' not in contenido:
        helper = '''
def _plantilla_html_correo(cuerpo_texto, firma):
    import html
    # Convertimos saltos de linea a <br> y escapamos HTML por seguridad
    cuerpo_html = html.escape(cuerpo_texto).replace('\\n', '<br>')
    firma_html = html.escape(firma or '').replace('\\n', '<br>')
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background-color:#f4f6fb; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
<table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#f4f6fb; padding: 40px 20px;">
<tr><td align="center">
<table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
<!-- Encabezado -->
<tr><td align="center" style="background-color:#0f172a; padding:30px;">
<h1 style="margin:0; color:#ffffff; font-size:24px; font-weight:700; letter-spacing:1px;">FAMILIA ZARAGOZA ®</h1>
</td></tr>
<!-- Cuerpo -->
<tr><td style="padding: 40px 30px; color:#334155; font-size:15px; line-height:1.6;">
{cuerpo_html}
</td></tr>
<!-- Firma -->
<tr><td style="padding: 0 30px 40px 30px; color:#64748b; font-size:13px; line-height:1.5; border-top:1px solid #f1f5f9;">
<br>
{firma_html}
</td></tr>
</table>
</div>
</td></tr>
</table>
</body>
</html>"""

'''
        contenido = contenido.replace('def enviar_email(', helper + '\ndef enviar_email(', 1)
        print("[upgrade137] Función _plantilla_html_correo agregada a app4.py")

    # 2. Modificar enviar_email para que envíe en HTML
    buscar_envio = "msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))"
    nuevo_envio = """from flask import has_app_context
    from app4 import get_config as _get_conf
    firma = _get_conf('firma_email') if has_app_context() else 'Familia Zaragoza'
    cuerpo_html = _plantilla_html_correo(cuerpo, firma)
    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))"""
    
    if buscar_envio in contenido:
        contenido = contenido.replace(buscar_envio, nuevo_envio)
        print("[upgrade137] enviar_email (app4) ahora envia HTML")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_app39():
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Importar el helper desde app4
    if 'from app4 import _plantilla_html_correo' not in contenido:
        contenido = contenido.replace('from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden, UPLOADS', 
                                      'from app4 import enviar_email, get_config, render_plantilla, construir_contexto, _cargar_orden, UPLOADS, _plantilla_html_correo')

    # Modificar _enviar_con_remitente
    buscar_envio = "msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))"
    nuevo_envio = """firma = get_config('firma_email')
    cuerpo_html = _plantilla_html_correo(cuerpo, firma)
    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))"""

    if buscar_envio in contenido:
        contenido = contenido.replace(buscar_envio, nuevo_envio)
        print("[upgrade137] _enviar_con_remitente (app39) ahora envia HTML")
    else:
        # Si por alguna razon el string es distinto, usamos un reemplazo directo de MIMEText
        contenido = re.sub(r"msg\.attach\(MIMEText\(cuerpo, 'plain', 'utf-8'\)\)", nuevo_envio, contenido)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)


def patch_app53():
    ruta = os.path.join(BASE, 'app53.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Verificar si hay algun envio directo en app53 que no use la función wrapper
    if "msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))" in contenido:
        nuevo_envio = """from app4 import _plantilla_html_correo
    firma = get_config('firma_email')
    cuerpo_html = _plantilla_html_correo(cuerpo, firma)
    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))"""
        contenido = contenido.replace("msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))", nuevo_envio)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade137] Correos de app53 actualizados a HTML")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app137; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade137] escrito: {relpath}")

def main():
    print("=== Upgrade 137: Correos con diseno HTML (Wepa!) ===")
    patch_app4()
    patch_app39()
    patch_app53()
    
    # Escribimos un archivo dummy para que run.bat lo importe y no falle
    escribir('app137.py', '# Modulo vacio\npass')
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y proba mandar un correo desde una orden.")

if __name__ == '__main__':
    main()