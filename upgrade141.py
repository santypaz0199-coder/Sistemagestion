# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

PLANTILLAS_DEFAULT = {
    'confirmacion': {
        'asunto': 'Recibimos tu pedido {{numero_orden}} - Familia Zaragoza',
        'cuerpo': '''Hola {{cliente_nombre}},

¡Gracias por tu compra! Recibimos tu pedido {{numero_orden}} con fecha {{fecha}}.

Detalle:
{{detalle_productos}}

Total: ${{total}}

{{datos_envio}}

Te vamos a avisar apenas lo despachemos.

{{firma}}'''
    },
    'pago': {
        'asunto': 'Pago acreditado - Pedido {{numero_orden}}',
        'cuerpo': '''Hola {{cliente_nombre}},

Te confirmamos que el pago de tu pedido {{numero_orden}} fue acreditado con éxito.

Total abonado: ${{total}}

A la brevedad vamos a estar despachando tu pedido y te avisaremos cuando esté en camino.

{{firma}}'''
    },
    'envio': {
        'asunto': 'Tu pedido {{numero_orden}} está en camino 🚚',
        'cuerpo': '''Hola {{cliente_nombre}},

Tu pedido {{numero_orden}} fue despachado.

{{info_seguimiento}}

{{datos_envio}}

Gracias por elegirnos.

{{firma}}'''
    },
    'entrega': {
        'asunto': 'Tu pedido {{numero_orden}} fue entregado',
        'cuerpo': '''Hola {{cliente_nombre}},

Tu pedido {{numero_orden}} fue entregado con éxito. Esperamos que lo disfrutes.

¡Gracias por elegirnos!

{{firma}}'''
    },
    'factura': {
        'asunto': 'Factura de tu pedido {{numero_orden}}',
        'cuerpo': '''Hola {{cliente_nombre}},

Adjuntamos la factura correspondiente a tu pedido {{numero_orden}}.

Total: ${{total}}

Cualquier consulta, estamos a disposición.

{{firma}}'''
    },
    'cancelacion': {
        'asunto': 'Tu pedido {{numero_orden}} fue cancelado',
        'cuerpo': '''Hola {{cliente_nombre}},

Te avisamos que tu pedido {{numero_orden}} fue cancelado automáticamente luego de 24 hs sin registrar el pago.

Recorda que las ordenes estan sujetas a cambios de precios por la desregulación del mercado en Argentina.

Si quieres retomar la compra, podes responder este email y te ayudamos.

{{firma}}'''
    }
}

def restaurar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    for tipo, p in PLANTILLAS_DEFAULT.items():
        for campo, valor in p.items():
            k = f'plantilla_{tipo}_{campo}'
            # Insertar o actualizar si está vacío
            conn.execute("INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor "
                         "WHERE configuracion.valor IS NULL OR configuracion.valor = ''", (k, valor))
            
    # Firma por defecto por si también se borró
    firma_default = '''Familia Zaragoza ®
📞 +54 9 3755 53-1691
✉ hola@familiazaragoza.com
🌐 familiazaragoza.com

Gracias por elegirnos'''
    
    conn.execute("INSERT INTO configuracion (clave, valor) VALUES ('firma_email', ?) "
                 "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor "
                 "WHERE configuracion.valor IS NULL OR configuracion.valor = ''", (firma_default,))
                 
    conn.commit(); conn.close()
    print("[upgrade141] Plantillas de correo y firma restauradas.")

if __name__ == '__main__':
    print("=== Upgrade 141: Restaurando plantillas de correo ===")
    restaurar()
    print("=== LISTO === Ejecuta run.bat")