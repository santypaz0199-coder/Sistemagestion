
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
