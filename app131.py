
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, current_user
from app129 import app
from app45 import User_v3 as User  # Importamos la clase correcta de usuarios
from database import get_db
from app4 import enviar_email
import random

@app.route('/login', methods=['GET', 'POST'])
def login_v4():
    conn = get_db()
    hay_usuarios = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0
    conn.close()

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        identificador = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        
        conn = get_db()
        row = conn.execute("SELECT * FROM usuarios WHERE (lower(email)=? OR nro_doc=?) AND activo=1", (identificador, identificador)).fetchone()
        conn.close()
        
        if row and check_password_hash(row['password_hash'], pw):
            login_user(User(row['id'], row['nombre'], row['email'], row['rol'], [], row['solo_propio'] if 'solo_propio' in row.keys() else 0))
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
        except Exception as e:
            print(f"[setup email] {e}")
            
        if not ok:
            flash(f'Aviso: Mailrelay no esta configurado o fallo. Tu codigo es: {codigo}', 'warning')
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
