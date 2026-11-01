
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
