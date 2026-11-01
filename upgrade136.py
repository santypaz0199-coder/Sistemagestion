# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_app39():
    ruta = os.path.join(BASE, 'app39.py')
    if not os.path.exists(ruta):
        print("[upgrade136] no existe app39.py")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Función para buscar el bloque de _remitentes_disponibles y reemplazarlo
    patron = re.compile(r'def _remitentes_disponibles\(conn\):.*?(?=def _remitente_por_email)', re.DOTALL)
    
    nueva_funcion = '''def _remitentes_disponibles(conn):
    """Lista de remitentes que el usuario actual puede usar."""
    remitentes = []
    if current_user.es_admin:
        # 1. Leer de la tabla oficial de remitentes (Configuración -> Remitentes y SMTP)
        try:
            rows = conn.execute("SELECT email, nombre FROM remitentes WHERE activo=1 ORDER BY id").fetchall()
            for r in rows:
                remitentes.append({'email': r['email'], 'nombre': r['nombre'], 'label': r['nombre']})
        except Exception:
            pass
            
        # 2. Fallback: si la tabla está vacía, usamos lo que dice la configuración vieja
        if not remitentes:
            emp_email = get_config('empresa_email')
            if emp_email:
                remitentes.append({'email': emp_email, 'nombre': get_config('empresa_nombre') or 'Familia Zaragoza', 'label': 'Trato general'})
            notif_email = get_config('smtp_remitente_email')
            if notif_email and notif_email.lower() != (emp_email or '').lower():
                remitentes.append({'email': notif_email, 'nombre': get_config('smtp_remitente_nombre') or 'Familia Zaragoza', 'label': 'Notificaciones'})
                
    else:
        # Para vendedores: solo su propio remitente
        row = conn.execute("SELECT email_remitente, nombre_remitente, nombre FROM usuarios WHERE id=?", (current_user.id,)).fetchone()
        if row and row['email_remitente']:
            remitentes.append({
                'email': row['email_remitente'],
                'nombre': row['nombre_remitente'] or row['nombre'],
                'label': f"{row['nombre']}",
            })
        else:
            # Fallback al default
            remitentes.append({
                'email': get_config('smtp_remitente_email'),
                'nombre': get_config('smtp_remitente_nombre', 'Familia Zaragoza'),
                'label': 'Notificaciones',
            })
    return remitentes


'''
    
    contenido, n = patron.subn(nueva_funcion, contenido)
    if n > 0:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade136] Función _remitentes_disponibles actualizada en app39.py")
    else:
        print("[upgrade136] ADVERTENCIA: no se encontró la función en app39.py")

def main():
    print("=== Upgrade 136: Fix remitentes en Campañas ===")
    patch_app39()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()