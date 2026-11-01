# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

def restaurar_configuracion():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        print("[upgrade130] no existe sistema.db")
        return
        
    conn = sqlite3.connect(db)
    
    # 1. Restaurar Canal "Tienda online"
    if not conn.execute("SELECT id FROM canales_venta WHERE lower(nombre)='tienda online'").fetchone():
        conn.execute("INSERT INTO canales_venta (nombre, activo, es_sistema) VALUES ('Tienda online', 1, 1)")
        print("[upgrade130] Canal 'Tienda online' restaurado y protegido.")
    
    # 2. Restaurar Medios de Pago por defecto
    medios = [
        ('Efectivo', 0),
        ('Transferencia', 0),
        ('Tarjeta de debito', 0),
        ('Tarjeta de credito', 0),
        ('Mercado Pago', 0),
        ('QR', 0)
    ]
    for nombre, comision in medios:
        if not conn.execute("SELECT id FROM medios_pago WHERE lower(nombre)=lower(?)", (nombre,)).fetchone():
            conn.execute("INSERT INTO medios_pago (nombre, comision_pct, activo) VALUES (?, ?, 1)", (nombre, comision))
            print(f"[upgrade130] Medio de pago '{nombre}' restaurado.")

    # 3. Restaurar Categorias de Gastos
    categorias = ['Fijos', 'Variables', 'Logistica', 'Marketing', 'Impuestos', 'Insumos', 'Otros']
    for cat in categorias:
        if not conn.execute("SELECT id FROM categorias_gastos WHERE lower(nombre)=lower(?)", (cat,)).fetchone():
            conn.execute("INSERT INTO categorias_gastos (nombre, activo) VALUES (?, 1)", (cat,))
            print(f"[upgrade130] Categoria de gasto '{cat}' restaurada.")

    conn.commit(); conn.close()
    print("\n[upgrade130] Base de datos preparada. Todo listo para crear tu usuario Admin.")

if __name__ == '__main__':
    restaurar_configuracion()