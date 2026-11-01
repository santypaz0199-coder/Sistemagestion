# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_detalle_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'detalle.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Eliminar el botón de "Notificar entrega" de la barra de botones principal
    buscar_btn = r'<button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#mail-entrega"><i class="bi bi-box-seam"></i> Notificar entrega</button>\n?'
    contenido = re.sub(buscar_btn, '', contenido)

    # 2. Eliminar el bloque colapsable (el formulario) de "Notificar entrega"
    patron_colapso = re.compile(r'<div class="collapse mt-3" id="mail-entrega">.*?</div>\s*</div>\s*</div>', re.DOTALL)
    # Es complicado con regex por los divs anidados, así que buscaremos por los textos
    buscar_colapso = '''<div class="collapse mt-3" id="mail-entrega">
<div class="border rounded p-3 bg-light">
<h6 class="mb-2">Notificar entrega</h6>
<form method="post" action="{{ url_for('ventas_email_enviar', id=orden.id, tipo='entrega') }}">
<div class="mb-2">
<label class="form-label small">Destinatario</label>
<input name="destinatario" type="email" class="form-control form-control-sm" value="{{ orden.cliente_email or '' }}" required>
</div>
<button class="btn btn-primary btn-sm"><i class="bi bi-send"></i> Enviar</button>
</form>
</div>
</div>'''
    contenido = contenido.replace(buscar_colapso, '')

    # 3. Arreglar el diseño de los formularios colapsables de email (fondo blanco, letra clara)
    # Cambiamos el bg-light por un color más acorde y aseguramos que las letras se lean
    buscar_estilos = '''<style>
/* Estilos para el modal de emails */
#emailModal .modal-content {
    background-color: #f8f9fc;
}
</style>'''
    
    # Buscamos si ya hay un bloque <style> al final del archivo para inyectar ahí
    if '#emailModal' not in contenido:
        contenido = contenido.replace('{% endblock %}', buscar_estilos + '\n{% endblock %}')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade149] Botón y bloque de 'Notificar entrega' eliminados. Estilos aplicados.")


def patch_app4():
    """Quitamos el tipo 'entrega' de los correos válidos para que no se pueda forzar por URL."""
    ruta = os.path.join(BASE, 'app4.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
    buscar = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}"
    nuevo = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura'}"
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade149] Tipo 'entrega' eliminado de app4.py")

def patch_app145():
    """Quitamos el tipo 'entrega' de los correos válidos en app145."""
    ruta = os.path.join(BASE, 'app145.py')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
        
    buscar = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'entrega', 'factura'}"
    nuevo = "TIPOS_VALIDOS = {'confirmacion', 'pago', 'envio', 'factura'}"
    
    if buscar in contenido:
        contenido = contenido.replace(buscar, nuevo)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("[upgrade149] Tipo 'entrega' eliminado de app145.py")

def main():
    print("=== Upgrade 149: Limpieza de 'Notificar entrega' ===")
    patch_detalle_html()
    patch_app4()
    patch_app145()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()