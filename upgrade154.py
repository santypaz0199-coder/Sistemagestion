# -*- coding: utf-8 -*-
import os, sqlite3, re

BASE = os.path.dirname(os.path.abspath(__file__))

def arreglar_base_de_datos():
    """Registra los pagos faltantes en ordenes que ya estan pagadas."""
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db): return
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    
    # Buscar ordenes pagadas que no tengan registro de pago
    ordenes = conn.execute("""
        SELECT id, total FROM ordenes_venta 
        WHERE estado IN ('pagado_sin_enviar', 'pagado_enviado')
        AND total > 0
        AND (SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id = ordenes_venta.id) < total
    """).fetchall()
    
    if not ordenes:
        print("[upgrade154] No hay ordenes pagadas sin registro de pago.")
        conn.close()
        return

    for o in ordenes:
        pagado = conn.execute("SELECT COALESCE(SUM(monto),0) FROM pagos WHERE orden_id=?", (o['id'],)).fetchone()[0]
        falta = o['total'] - pagado
        
        medio = conn.execute("SELECT id FROM medios_pago LIMIT 1").fetchone()
        medio_id = medio['id'] if medio else None
        
        conn.execute("""INSERT INTO pagos 
            (orden_id, fecha, medio_pago_id, monto, comision, monto_neto, usuario_id, notas)
            VALUES (?, date('now'), ?, ?, 0, ?, 1, 'Pago retroactivo (cuadre de caja)')""",
            (o['id'], medio_id, falta, falta))
        print(f"[upgrade154] Pago retroactivo de ${falta} registrado para la Orden #{o['id']}")
        
    conn.commit()
    conn.close()
    print("[upgrade154] Base de datos cuadrada.")


def patch_app152():
    """Quitamos los decoradores @app.route de app152 para que use view_functions."""
    ruta = os.path.join(BASE, 'app152.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Quitar decoradores de ruta en app152 para evitar conflictos
    buscar1 = """@app.route('/ventas/<int:id>/estado', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_estado_v4(id):"""
    nuevo1 = """@login_required
@permiso_required('ventas')
def ventas_estado_v4(id):"""
    
    buscar2 = """@app.route('/ventas/<int:id>/email/<tipo>', methods=['POST'])
@login_required
@permiso_required('ventas')
def ventas_email_enviar_v4(id, tipo):"""
    nuevo2 = """@login_required
@permiso_required('ventas')
def ventas_email_enviar_v4(id, tipo):"""

    if buscar1 in contenido:
        contenido = contenido.replace(buscar1, nuevo1)
    if buscar2 in contenido:
        contenido = contenido.replace(buscar2, nuevo2)
        
    # Asegurarnos de que se inyecten al final
    if "app.view_functions['ventas_estado']" not in contenido:
        contenido += "\napp.view_functions['ventas_estado'] = ventas_estado_v4\n"
    if "app.view_functions['ventas_email_enviar']" not in contenido:
        contenido += "\napp.view_functions['ventas_email_enviar'] = ventas_email_enviar_v4\n"

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade154] app152.py limpiado y enlazado correctamente.")

def main():
    print("=== Upgrade 154: Fix Caja y Pagos Retroactivos ===")
    arreglar_base_de_datos()
    patch_app152()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()