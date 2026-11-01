# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade131] escrito: {relpath}")


# 1. CREAR EL MÓDULO CON LAS RUTAS DE SETUP
APP131_PY = r'''
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user
from app129 import app, User
from database import get_db
from app4 import enviar_email, get_config
import random

@app.route('/login', methods=['GET', 'POST'])
def login_v4():
    conn = get_db()
    hay_usuarios = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0
    conn.close()

    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        identificador = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE (lower(email)=? OR nro_doc=?) AND activo=1", (identificador, identificador)).fetchone()
        conn.close()
        
        if row and check_password_hash(row['password_hash'], pw):
            login_user(User(row['id'], row['nombre'], row['email'], row['rol']))
            return redirect(url_for('dashboard'))
        flash('Credenciales incorrectas.', 'error')
        
    return render_template('login.html', hay_usuarios=hay_usuarios)

app.view_functions['login'] = login_v4

@app.route('/setup', methods=['GET', 'POST'])
def setup_admin():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0:
        conn.close()
        flash('El sistema ya tiene un administrador configurado.', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        nro_doc = request.form.get('nro_doc', '').strip()
        email = request.form.get('email', '').strip().lower()
        provincia = request.form.get('provincia', '').strip()
        localidad = request.form.get('localidad', '').strip()
        cp = request.form.get('codigo_postal', '').strip()
        telefono = request.form.get('telefono', '').strip()
        pw = request.form.get('password', '')
        
        if not nombre or not nro_doc or not email or not pw:
            flash('Completa todos los campos obligatorios.', 'error')
            return render_template('setup.html', valores=request.form)
            
        if len(pw) < 8 or not any(char.isdigit() for char in pw):
            flash('La contrasena debe tener al menos 8 caracteres y 1 numero.', 'error')
            return render_template('setup.html', valores=request.form)

        codigo = str(random.randint(100000, 999999))
        
        session['setup_data'] = {
            'nombre': nombre, 'nro_doc': nro_doc, 'email': email, 'provincia': provincia,
            'localidad': localidad, 'codigo_postal': cp, 'telefono': telefono, 'pw': pw
        }
        session['setup_code'] = codigo
        
        ok, msg = False, ''
        try:
            asunto = "Tu codigo de verificacion - Familia Zaragoza"
            cuerpo = f"Hola {nombre},\n\nTu codigo para crear la cuenta de administrador es: {codigo}"
            ok, msg = enviar_email(email, asunto, cuerpo)
        except Exception:
            pass
            
        if not ok:
            flash(f'Aviso: Mailrelay no esta configurado. Tu codigo de verificacion es: {codigo}', 'warning')
        else:
            flash(f'Te enviamos un correo a {email} con el codigo de 6 digitos.', 'success')
            
        return redirect(url_for('setup_verificar'))
        
    conn.close()
    return render_template('setup.html', valores={})

@app.route('/setup/verificar', methods=['GET', 'POST'])
def setup_verificar():
    if 'setup_data' not in session:
        return redirect(url_for('setup_admin'))
        
    if request.method == 'POST':
        codigo_ingresado = request.form.get('codigo', '').strip()
        if codigo_ingresado == session.get('setup_code'):
            d = session['setup_data']
            conn = get_db()
            conn.execute("""INSERT INTO usuarios 
                (nombre, email, password_hash, rol, nro_doc, provincia, localidad, codigo_postal, telefono) 
                VALUES (?, ?, ?, 'admin', ?, ?, ?, ?, ?)""", 
                (d['nombre'], d['email'], generate_password_hash(d['pw']), d['nro_doc'], d['provincia'], d['localidad'], d['codigo_postal'], d['telefono']))
            conn.commit(); conn.close()
            
            session.pop('setup_data', None)
            session.pop('setup_code', None)
            
            flash('Cuenta creada con exito. Ya podes iniciar sesion.', 'success')
            return redirect(url_for('login'))
        else:
            flash('El codigo es incorrecto.', 'error')
            
    return render_template('setup_verificar.html')
'''

LOGIN_HTML = r'''{% extends "base.html" %}
{% block title %}Login - Sistema FZ{% endblock %}
{% block content %}
<div class="row justify-content-center" style="margin-top:8vh;">
<div class="col-md-5 col-lg-4">
<div class="card shadow-sm" style="border-radius:20px;">
<div class="card-body p-5">
<div class="text-center mb-4">
<div style="width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg, #4f46e5, #8b5cf6);display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:1.6rem;font-weight:800;box-shadow:0 8px 24px rgba(79,70,229,.3);margin-bottom:1rem;">
<i class="bi bi-shop"></i>
</div>
<h3 class="mb-1" style="font-weight:800;letter-spacing:-.03em;">Familia Zaragoza ®</h3>
<p class="text-muted mb-0" style="font-size:.9rem;">Sistema de gestion interno</p>
</div>

{% if not hay_usuarios %}
<div class="alert alert-warning text-center mb-4">
<p class="mb-2 small">El sistema no tiene usuarios.</p>
<a href="{{ url_for('setup_admin') }}" class="btn btn-dark w-100">Crear cuenta de Administrador</a>
</div>
{% else %}

<form method="post">
<div class="mb-3">
<label class="form-label">DNI o Email</label>
<input type="text" name="email" class="form-control" required autofocus placeholder="Tu DNI o Email" style="padding:.7rem .9rem;">
</div>
<div class="mb-4">
<label class="form-label">Contrasena</label>
<input type="password" name="password" class="form-control" required placeholder="••••••••" style="padding:.7rem .9rem;">
</div>
<button class="btn btn-dark w-100" style="padding:.7rem;">Ingresar <i class="bi bi-arrow-right"></i></button>
</form>

{% endif %}
</div>
</div>
<p class="text-center text-muted mt-4" style="font-size:.82rem;">Acceso restringido</p>
</div>
</div>
{% endblock %}
'''

SETUP_HTML = r'''{% extends "base.html" %}
{% block title %}Crear Administrador - Sistema FZ{% endblock %}
{% block content %}
<div class="row justify-content-center" style="margin-top:5vh; margin-bottom:5vh;">
<div class="col-md-8 col-lg-6">
<div class="card shadow-sm" style="border-radius:20px;">
<div class="card-body p-5">
<div class="text-center mb-4">
<h3 class="mb-1" style="font-weight:800;letter-spacing:-.03em;">Configuracion Inicial</h3>
<p class="text-muted">Crea la cuenta principal de Administrador</p>
</div>

<form method="post">
<div class="row g-3">
<div class="col-md-12"><label class="form-label">Nombre completo *</label><input name="nombre" class="form-control" required value="{{ valores.get('nombre','') }}"></div>
<div class="col-md-6"><label class="form-label">DNI / CUIT *</label><input name="nro_doc" class="form-control" required value="{{ valores.get('nro_doc','') }}"></div>
<div class="col-md-6"><label class="form-label">Email (Gmail) *</label><input type="email" name="email" class="form-control" required value="{{ valores.get('email','') }}"></div>
<div class="col-md-6"><label class="form-label">Provincia</label><input name="provincia" class="form-control" value="{{ valores.get('provincia','') }}"></div>
<div class="col-md-6"><label class="form-label">Localidad</label><input name="localidad" class="form-control" value="{{ valores.get('localidad','') }}"></div>
<div class="col-md-6"><label class="form-label">Codigo Postal</label><input name="codigo_postal" class="form-control" value="{{ valores.get('codigo_postal','') }}"></div>
<div class="col-md-6"><label class="form-label">Telefono</label><input name="telefono" class="form-control" value="{{ valores.get('telefono','') }}"></div>
<div class="col-12 mt-4">
<label class="form-label">Contrasena * <span class="text-muted fw-normal">(min 8 caracteres, 1 numero)</span></label>
<input type="password" name="password" class="form-control" required>
</div>
</div>
<div class="mt-4">
<button type="submit" class="btn btn-dark w-100" style="padding:.8rem;">Generar codigo de verificacion</button>
</div>
</form>
</div>
</div>
</div>
</div>
{% endblock %}
'''

SETUP_VERIFICAR_HTML = r'''{% extends "base.html" %}
{% block title %}Verificar codigo - Sistema FZ{% endblock %}
{% block content %}
<div class="row justify-content-center" style="margin-top:10vh;">
<div class="col-md-4">
<div class="card shadow-sm" style="border-radius:20px;">
<div class="card-body p-5 text-center">
<i class="bi bi-envelope-check" style="font-size:3rem; color:#4f46e5; display:block; margin-bottom:1rem;"></i>
<h4 class="mb-2" style="font-weight:800;">Verifica tu correo</h4>
<p class="text-muted small mb-4">Ingresa el codigo de 6 digitos que enviamos a tu email.</p>

<form method="post">
<div class="mb-4">
<input type="text" name="codigo" class="form-control text-center" style="font-size:2rem; letter-spacing:1rem; padding:.5rem;" maxlength="6" required autofocus placeholder="000000">
</div>
<button type="submit" class="btn btn-dark w-100">Verificar y Crear Cuenta</button>
</form>
</div>
</div>
</div>
</div>
{% endblock %}
'''

RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; app48.app.register_blueprint(catalogo_bp); app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''

def main():
    print("=== Upgrade 131: Setup visual de Admin y verificacion por email ===")
    escribir('app131.py', APP131_PY)
    escribir('templates/login.html', LOGIN_HTML)
    escribir('templates/setup.html', SETUP_HTML)
    escribir('templates/setup_verificar.html', SETUP_VERIFICAR_HTML)
    
    with open(os.path.join(BASE, 'run.bat'), 'w', encoding='utf-8') as f:
        f.write(RUN_BAT)
        
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()