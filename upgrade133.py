# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def limpieza_profunda():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade133] No existe sistema.db, salteando.")
        return
        
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    
    # 1. Obtener todas las tablas (excepto sqlite_sequence)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tablas = [row[0] for row in cursor.fetchall()]
    
    # 2. Vaciar todas las tablas y resetear los IDs
    for tabla in tablas:
        try:
            cursor.execute(f"DELETE FROM {tabla};")
            print(f"[upgrade133] Tabla '{tabla}' vaciada.")
        except Exception as e:
            print(f"[upgrade133] Error al vaciar {tabla}: {e}")
            
    # Resetear los contadores de ID autoincremental
    try:
        cursor.execute("DELETE FROM sqlite_sequence;")
        print("[upgrade133] IDs reseteados a 1.")
    except Exception:
        pass
        
    # 3. Reinsertar SOLO el canal "Tienda online" para que el sistema no falle
    try:
        cursor.execute("INSERT INTO canales_venta (nombre, activo, es_sistema) VALUES ('Tienda online', 1, 1)")
        print("[upgrade133] Canal 'Tienda online' recreado como base.")
    except Exception as e:
        print(f"[upgrade133] Error al crear canal: {e}")

    conn.commit()
    conn.close()
    print("\n[upgrade133] Base de datos formateada. Todo listo para el primer registro visual.")

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade133] escrito: {relpath}")

LOGIN_HTML = r'''{% extends "base.html" %}
{% block title %}Ingresar o Registrarse - Familia Zaragoza{% endblock %}
{% block content %}
<div class="row justify-content-center" style="margin-top:5vh;">
<div class="col-md-5 col-lg-4">
<div class="card shadow-sm" style="border-radius:20px;">
<div class="card-body p-5">
<div class="text-center mb-4">
<div style="width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg, #4f46e5, #8b5cf6);display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:1.6rem;font-weight:800;box-shadow:0 8px 24px rgba(79,70,229,.3);margin-bottom:1rem;">
<i class="bi bi-shop"></i>
</div>
<h3 class="mb-1" style="font-weight:800;letter-spacing:-.03em;">Familia Zaragoza ®</h3>
<p class="text-muted mb-0" style="font-size:.9rem;">Portal de Clientes y Administración</p>
</div>

{% if not hay_usuarios %}
<div class="text-center mb-4">
<p class="text-muted small">Bienvenido. Como es la primera vez que se inicia el sistema, por favor creá la cuenta de Administrador principal.</p>
<a href="{{ url_for('setup_admin') }}" class="btn btn-dark w-100 mt-2" style="padding:.7rem;">Crear Cuenta de Administrador</a>
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
<button type="submit" class="btn btn-dark w-100" style="padding:.7rem;">Ingresar <i class="bi bi-arrow-right"></i></button>
</form>

<div class="text-center mt-4 pt-3 border-top">
<p class="text-muted small mb-2">¿No tenés cuenta todavía?</p>
<a href="{{ url_for('setup_admin') }}" class="btn btn-outline-dark w-100">Generar cuenta nueva</a>
</div>
{% endif %}
</div>
</div>
<p class="text-center text-muted mt-4" style="font-size:.82rem;">Sistema seguro</p>
</div>
</div>
{% endblock %}
'''

def main():
    print("=== Upgrade 133: Limpieza Profunda y Setup Visual ===")
    limpieza_profunda()
    escribir('templates/login.html', LOGIN_HTML)
    
    print("\n=== LISTO ===")
    print("Arranca el sistema con: run.bat")
    print("Entra a http://127.0.0.1:5000/login y crea tu cuenta desde la pantalla.")

if __name__ == '__main__':
    main()