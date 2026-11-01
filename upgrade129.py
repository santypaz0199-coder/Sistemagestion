# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade129] escrito: {relpath}")

def migrar_db():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db): return
    conn = sqlite3.connect(db)
    
    # 1. Nuevos campos en usuarios
    cols = [r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
    campos = ['nro_doc', 'provincia', 'localidad', 'codigo_postal', 'telefono']
    for c in campos:
        if c not in cols:
            conn.execute(f"ALTER TABLE usuarios ADD COLUMN {c} TEXT")
            print(f"[upgrade129] + usuarios.{c}")
            
    # 2. Limpiar toda la base de datos transaccional
    tablas_a_borrar = [
        'orden_items', 'pagos', 'ordenes_venta', 'movimientos_stock', 
        'compra_items', 'compras', 'gastos', 'objetivos', 'objetivos_canal',
        'mayoristas_cuentas', 'emails_enviados', 'archivos', 'solicitudes_borrado',
        'campanas_envios', 'campanas', 'escalas_envio_b2b', 'clientes', 'productos',
        'proveedores', 'categorias_productos', 'medios_pago', 'transportistas',
        'canales_venta', 'categorias_gastos', 'usuarios'
    ]
    
    for t in tablas_a_borrar:
        try:
            conn.execute(f"DELETE FROM {t}")
            print(f"[upgrade129] Tabla '{t}' vaciada")
        except Exception as e:
            pass
            
    conn.commit(); conn.close()
    print("[upgrade129] Base de datos reseteada con exito.")

APP129_PY = r'''
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from app122 import app
from database import get_db

# Parcheamos la ruta de login para aceptar DNI o Email y validar contrasena
@app.route('/login', methods=['GET', 'POST'])
def login_v3():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        identificador = request.form.get('email', '').strip().lower() # El campo en el HTML se sigue llamando email
        pw = request.form.get('password', '')
        
        conn = get_db()
        # Buscamos si lo que ingresó coincide con el email O con el DNI
        row = conn.execute("SELECT * FROM usuarios WHERE (lower(email)=? OR nro_doc=?) AND activo=1", (identificador, identificador)).fetchone()
        conn.close()
        
        if row and check_password_hash(row['password_hash'], pw):
            login_user(User(row['id'], row['nombre'], row['email'], row['rol']))
            return redirect(url_for('dashboard'))
        flash('Credenciales incorrectas.', 'error')
    return render_template('login.html')

# Parcheamos la creacion de usuarios para validar la contrasena
def validar_password(pw):
    if len(pw) < 8: return False, 'La contrasena debe tener al menos 8 caracteres.'
    if not any(char.isdigit() for char in pw): return False, 'La contrasena debe contener al menos un numero.'
    return True, ''

import app122
app122.app.view_functions['login'] = login_v3
'''

SETUP_ADMIN_PY = r'''
# -*- coding: utf-8 -*-
import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(BASE, 'sistema.db')

def main():
    print("=== CREACION DEL NUEVO ADMINISTRADOR ===")
    print("Vamos a crear tu cuenta principal para empezar de cero.\n")
    
    nombre = input("Nombre completo: ").strip()
    nro_doc = input("DNI / CUIT: ").strip()
    email = input("Email (Gmail): ").strip().lower()
    provincia = input("Provincia: ").strip()
    localidad = input("Localidad: ").strip()
    cp = input("Codigo Postal: ").strip()
    telefono = input("Telefono: ").strip()
    
    while True:
        pw = input("\nContrasena (minimo 8 caracteres y al menos 1 numero): ")
        if len(pw) >= 8 and any(char.isdigit() for char in pw):
            break
        print("Error: La contrasena no cumple los requisitos.")

    conn = sqlite3.connect(db)
    
    # Borrar cualquier usuario que haya quedado
    conn.execute("DELETE FROM usuarios")
    
    conn.execute("""INSERT INTO usuarios 
        (nombre, email, password_hash, rol, nro_doc, provincia, localidad, codigo_postal, telefono) 
        VALUES (?, ?, ?, 'admin', ?, ?, ?, ?, ?)""", 
        (nombre, email, generate_password_hash(pw), nro_doc, provincia, localidad, cp, telefono))
    
    conn.commit()
    conn.close()
    print("\n✅ Administrador creado exitosamente.")
    print(f"Usuario para ingresar: Tu DNI ({nro_doc}) o tu Email ({email})")
    print("Ya podes arrancar el sistema con run.bat")

if __name__ == '__main__':
    main()
'''

# 1. Inyectar la validacion de password en las rutas de usuarios
def patch_app43():
    ruta = os.path.join(BASE, 'app43.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'def validar_password' not in contenido:
        helper = '''
def validar_password(pw):
    if len(pw) < 8: return False, 'La contrasena debe tener al menos 8 caracteres.'
    if not any(char.isdigit() for char in pw): return False, 'La contrasena debe contener al menos un numero.'
    return True, ''
'''
        contenido = contenido.replace('app = ', helper + '\napp = ', 1)
        
        # En usuarios_nuevo_v2
        buscar_nuevo = """        if not nombre or not email or not password:
            conn.close(); flash('Completa todos los campos.', 'error')"""
        nuevo_nuevo = """        if not nombre or not email or not password:
            conn.close(); flash('Completa todos los campos.', 'error')
            return render_template('usuarios/form.html', usuario=None, valores=request.form, roles=_get_roles(conn))
            
        ok_pw, msg_pw = validar_password(password)
        if not ok_pw:
            conn.close(); flash(msg_pw, 'error')"""
            
        if buscar_nuevo in contenido:
            contenido = contenido.replace(buscar_nuevo, nuevo_nuevo)

        # En usuarios_editar_v3
        buscar_edit = """        if password:
            conn.execute("""
        nuevo_edit = """        if password:
            ok_pw, msg_pw = validar_password(password)
            if not ok_pw:
                conn.close(); flash(msg_pw, 'error')
                return redirect(url_for('usuarios_editar', id=id))
            conn.execute("""
        
        if buscar_edit in contenido:
            contenido = contenido.replace(buscar_edit, nuevo_edit)

        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade129] Validacion de contrasena inyectada en app43.py")


# 2. Actualizar el Login HTML para que diga DNI/Email
def patch_login_html():
    ruta = os.path.join(BASE, 'templates', 'login.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
    buscar = '<label class="form-label">Email</label>'
    nuevo = '<label class="form-label">DNI o Email</label>'
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        
    buscar_input = '<input type="email" name="email" class="form-control" required autofocus placeholder="tu@email.com"'
    nuevo_input = '<input type="text" name="email" class="form-control" required autofocus placeholder="Tu DNI o Email"'
    if buscar_input in contenido:
        contenido = contenido.replace(buscar_input, nuevo_input)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade129] Login HTML actualizado a DNI/Email")


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 129: Reset del sistema y Login por DNI ===")
    migrar_db()
    escribir('app129.py', APP129_PY)
    escribir('setup_admin.py', SETUP_ADMIN_PY)
    patch_app43()
    patch_login_html()
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("1. Ejecuta: python setup_admin.py")
    print("2. Luego arranca con: run.bat")
    print("3. Anda a Configuracion para reconectar el SMTP y el Logo.")

if __name__ == '__main__':
    main()