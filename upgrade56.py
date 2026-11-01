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
    print(f"[upgrade56] escrito: {relpath}")


def migrar_remitentes():
    """Corrige remitentes invalidos (admin@local, etc.) por uno valido."""
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade56] sin DB."); return
    conn = sqlite3.connect(db)

    REMITENTE_VALIDO = 'hola@familiazaragoza.com'
    NOMBRE_VALIDO = 'Familia Zaragoza'

    # 1. Corregir smtp_remitente_email si es invalido
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='smtp_remitente_email'").fetchone()
    if not row or not row[0] or '@local' in (row[0] or '') or '.' not in (row[0] or ''):
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_email', ?) "
                     "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (REMITENTE_VALIDO,))
        print(f"[upgrade56] smtp_remitente_email corregido a {REMITENTE_VALIDO}")

    # 2. Corregir smtp_remitente_nombre
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='smtp_remitente_nombre'").fetchone()
    if not row or not row[0]:
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('smtp_remitente_nombre', ?) "
                     "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (NOMBRE_VALIDO,))
        print(f"[upgrade56] smtp_remitente_nombre corregido a {NOMBRE_VALIDO}")

    # 3. Corregir empresa_email si es invalido
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='empresa_email'").fetchone()
    if not row or not row[0] or '@local' in (row[0] or '') or '.' not in (row[0] or ''):
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('empresa_email', ?) "
                     "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (REMITENTE_VALIDO,))
        print(f"[upgrade56] empresa_email corregido a {REMITENTE_VALIDO}")

    # 4. Corregir remitente_notificaciones_email si es invalido
    row = conn.execute("SELECT valor FROM configuracion WHERE clave='remitente_notificaciones_email'").fetchone()
    if not row or not row[0] or '@local' in (row[0] or '') or '.' not in (row[0] or ''):
        conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('remitente_notificaciones_email', ?) "
                     "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (REMITENTE_VALIDO,))
        print(f"[upgrade56] remitente_notificaciones_email corregido a {REMITENTE_VALIDO}")

    # 5. Corregir email_remitente de usuarios que sean invalidos (admin@local, etc)
    usuarios_malos = conn.execute("""
        SELECT id, email, email_remitente FROM usuarios
        WHERE email_remitente IS NOT NULL
        AND (email_remitente LIKE '%@local' OR email_remitente NOT LIKE '%.%' OR email_remitente='')
    """).fetchall()
    for uid, email, email_r in usuarios_malos:
        # Si el email de login tambien es invalido, dejar email_remitente en NULL para usar default
        if not email or '@local' in (email or ''):
            conn.execute("UPDATE usuarios SET email_remitente=NULL, nombre_remitente=NULL WHERE id=?", (uid,))
            print(f"[upgrade56] usuario #{uid} ({email}) - remitente limpiado (usara default)")
        else:
            # Si el email de login es valido, usarlo
            conn.execute("UPDATE usuarios SET email_remitente=? WHERE id=?", (email, uid))
            print(f"[upgrade56] usuario #{uid} - remitente corregido a {email}")

    # 6. Verificar que existe el remitente hola@ en la tabla remitentes
    if not conn.execute("SELECT id FROM remitentes WHERE lower(email)='hola@familiazaragoza.com'").fetchone():
        conn.execute("INSERT INTO remitentes (email, nombre, activo) VALUES (?, ?, 1)",
                     (REMITENTE_VALIDO, 'Familia Zaragoza'))
        print("[upgrade56] remitente hola@familiazaragoza.com agregado a la lista")

    conn.commit(); conn.close()


def patch_base_css():
    """Achica el sidebar de 250px a 210px."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade56] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'width:210px' in contenido:
        print("[upgrade56] sidebar ya esta en 210px")
        return

    # Reemplazar 250px por 210px en las 2 reglas (sidebar y content margin-left)
    contenido = contenido.replace('width:250px;', 'width:210px;')
    contenido = contenido.replace('margin-left:250px;', 'margin-left:210px;')

    # Achicar paddings del sidebar para que el texto no se corte
    contenido = contenido.replace(
        '.sidebar a{\n  color:#94a3b8;\n  text-decoration:none;\n  padding:.65rem 1.5rem;',
        '.sidebar a{\n  color:#94a3b8;\n  text-decoration:none;\n  padding:.6rem 1.1rem;'
    )
    contenido = contenido.replace(
        'padding:1.5rem 1.5rem 1.25rem;',
        'padding:1.5rem 1.1rem 1.25rem;'
    )
    contenido = contenido.replace(
        'padding:0 1.5rem 1.5rem;',
        'padding:0 1.1rem 1.5rem;'
    )
    contenido = contenido.replace(
        '.sidebar .user-info{\n  flex-shrink:0;\n  padding:1rem 1.25rem;',
        '.sidebar .user-info{\n  flex-shrink:0;\n  padding:1rem 1.1rem;'
    )
    contenido = contenido.replace(
        'padding:.9rem 1.25rem;\n  background:linear-gradient',
        'padding:.9rem 1.1rem;\n  background:linear-gradient'
    )

    # Reducir font-size de los links para que entren mejor
    contenido = contenido.replace(
        'gap:.75rem;\n  font-size:.9rem;\n  font-weight:500;',
        'gap:.6rem;\n  font-size:.85rem;\n  font-weight:500;'
    )
    # Reducir el tamano de los iconos
    contenido = contenido.replace(
        '.sidebar a i{\n  font-size:1.1rem;\n  width:20px;\n  text-align:center;\n}',
        '.sidebar a i{\n  font-size:1rem;\n  width:18px;\n  text-align:center;\n}'
    )
    # Reducir el brand
    contenido = contenido.replace(
        'font-size:1.1rem;\n  letter-spacing:-.02em;\n  display:flex;',
        'font-size:1rem;\n  letter-spacing:-.02em;\n  display:flex;'
    )

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade56] sidebar achicado a 210px con paddings reducidos")


def patch_envio_remitente_fallback():
    """Asegura que si el remitente es invalido (admin@local) use el default valido."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        print("[upgrade56] no existe app39.py"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar la funcion _enviar_con_remitente y agregar fallback
    if '_validar_remitente' in contenido:
        print("[upgrade56] app39 ya tiene validacion de remitente")
        return

    # Insertar una funcion helper al inicio del archivo (despues de imports)
    buscar_import = 'def _enviar_con_remitente('
    if buscar_import not in contenido:
        print("[upgrade56] ADVERTENCIA: no se encontro _enviar_con_remitente")
        return

    helper = '''def _validar_remitente(remitente):
    """Si el remitente es invalido (ej: admin@local), usar el default configurado."""
    if not remitente:
        return None
    email = remitente.get('email', '') if isinstance(remitente, dict) else str(remitente)
    if not email or '@local' in email or '.' not in email.split('@')[-1]:
        # Remitente invalido, usar el default
        from app4 import get_config
        default_email = get_config('smtp_remitente_email') or 'hola@familiazaragoza.com'
        default_nombre = get_config('smtp_remitente_nombre') or 'Familia Zaragoza'
        return {'email': default_email, 'nombre': default_nombre}
    return remitente


def _enviar_con_remitente('''

    contenido = contenido.replace('def _enviar_con_remitente(', helper, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade56] app39: helper _validar_remitente agregado")


def patch_ventas_email_enviar():
    """Parchea la funcion de envio de emails para usar _validar_remitente."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if '_validar_remitente(remitente_override)' in contenido:
        print("[upgrade56] validacion ya aplicada en ventas_email_enviar")
        return

    # Buscar donde se llama _enviar_con_remitente en ventas_email_enviar_v2
    viejo = '''    # Si no hay override (vendedor), usar SU propio remitente
    if remitente_override is None and not current_user.es_admin:
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitente_override = {'email': row['email_remitente'],
                                   'nombre': row['nombre_remitente'] or row['nombre']}'''

    nuevo = '''    # Si no hay override (vendedor), usar SU propio remitente
    if remitente_override is None and not current_user.es_admin:
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitente_override = {'email': row['email_remitente'],
                                   'nombre': row['nombre_remitente'] or row['nombre']}

    # Validar que el remitente sea un email valido (evita admin@local)
    remitente_override = _validar_remitente(remitente_override)'''

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade56] ventas_email_enviar usa _validar_remitente")
    else:
        print("[upgrade56] ADVERTENCIA: no se encontro el bloque de override")


def patch_emails_nuevo():
    """Parchea la funcion de envio manual para usar _validar_remitente."""
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    viejo = '''        remitente_override = None
        if current_user.es_admin and remitente_email:
            remitente_override = _remitente_por_email(conn, remitente_email)
        elif not current_user.es_admin:
            row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
            if row and row['email_remitente']:
                remitente_override = {'email': row['email_remitente'],
                                       'nombre': row['nombre_remitente'] or row['nombre']}'''

    nuevo = '''        remitente_override = None
        if current_user.es_admin and remitente_email:
            remitente_override = _remitente_por_email(conn, remitente_email)
        elif not current_user.es_admin:
            row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
            if row and row['email_remitente']:
                remitente_override = {'email': row['email_remitente'],
                                       'nombre': row['nombre_remitente'] or row['nombre']}

        # Validar remitente
        remitente_override = _validar_remitente(remitente_override)'''

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade56] emails_nuevo usa _validar_remitente")
    else:
        print("[upgrade56] ADVERTENCIA: no se encontro el bloque de emails_nuevo")


def patch_campanas():
    """Parchea campanas para usar _validar_remitente."""
    ruta = os.path.join(BASE, 'app40.py')
    if not os.path.exists(ruta):
        return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if '_validar_remitente' in contenido:
        print("[upgrade56] campanas ya validan remitente")
        return

    viejo = """            # Enviar
            remitente_override = _remitente_por_email(conn, remitente_email) if remitente_email else None"""
    nuevo = """            # Enviar
            remitente_override = _remitente_por_email(conn, remitente_email) if remitente_email else None
            # Validar remitente (evita admin@local invalido)
            try:
                from app39 import _validar_remitente
                remitente_override = _validar_remitente(remitente_override)
            except Exception:
                pass"""

    if viejo in contenido:
        contenido = contenido.replace(viejo, nuevo, 1)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade56] campanas usan _validar_remitente")
    else:
        print("[upgrade56] ADVERTENCIA: no se encontro el bloque de campanas")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 56: Fix SMTP (remitente valido) + sidebar fino ===")
    migrar_remitentes()
    patch_base_css()
    patch_envio_remitente_fallback()
    patch_ventas_email_enviar()
    patch_emails_nuevo()
    patch_campanas()
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")
    print("")
    print("IMPORTANTE: cerra sesion y volve a entrar para tomar los cambios")


if __name__ == '__main__':
    main()