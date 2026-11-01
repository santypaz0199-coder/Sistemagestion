# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_ventas_lista():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'lista.html')
    if not os.path.exists(ruta):
        print("[upgrade73] no existe ventas/lista.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Reemplazar el boton de dropdown por un boton que abre un modal
    import re
    patron_boton = re.compile(
        r'<div class="dropdown">.*?<i class="bi bi-three-dots-vertical"></i>\s*</button>\s*<ul class="dropdown-menu dropdown-menu-end">.*?</ul>\s*</div>',
        re.DOTALL
    )
    
    nuevo_boton = '''<button type="button" class="btn btn-sm btn-outline-secondary" onclick="openAcciones({{ v.id }}, '{{ v.numero_interno }}', '{{ v.wa_url or "" }}')" title="Acciones">
<i class="bi bi-three-dots-vertical"></i>
</button>'''

    contenido, n = patron_boton.subn(nuevo_boton, contenido)
    if n > 0:
        print("[upgrade73] Botones reemplazados por modal de acciones")
    else:
        print("[upgrade73] ADVERTENCIA: no se encontro el dropdown para reemplazar")

    # 2. Agregar el Modal de acciones antes de {% endblock %}
    modal_html = '''
<!-- Modal Acciones (reemplaza al dropdown) -->
<div class="modal fade" id="accionesModal" tabindex="-1">
<div class="modal-dialog modal-sm modal-dialog-centered">
<div class="modal-content">
<div class="modal-header py-2">
<h6 class="modal-title">Acciones <span id="acciones-num" class="text-muted"></span></h6>
<button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>
<div class="modal-body p-2 d-grid gap-2">
<a id="acc-ver" href="#" class="btn btn-outline-secondary text-start"><i class="bi bi-eye"></i> Ver / Editar</a>
<a id="acc-imprimir" href="#" target="_blank" class="btn btn-outline-secondary text-start"><i class="bi bi-printer"></i> Imprimir / PDF</a>
<button type="button" class="btn btn-outline-secondary text-start" onclick="ejecutarCompartir()"><i class="bi bi-share"></i> Compartir</button>
<hr class="my-1">
<a id="acc-wa" href="#" target="_blank" class="btn btn-outline-success text-start"><i class="bi bi-whatsapp"></i> WhatsApp</a>
<button type="button" class="btn btn-outline-primary text-start" onclick="ejecutarEmail()"><i class="bi bi-envelope"></i> Enviar email</button>
<hr class="my-1">
<button type="button" class="btn btn-outline-danger text-start" onclick="ejecutarBorrar()"><i class="bi bi-trash"></i> Borrar orden</button>
</div>
</div></div></div>

<script>
let _accionId = null;
let _accionNum = null;

function openAcciones(id, num, waUrl) {
  _accionId = id;
  _accionNum = num;
  
  document.getElementById('acciones-num').textContent = num;
  document.getElementById('acc-ver').href = '/ventas/' + id;
  document.getElementById('acc-imprimir').href = '/ventas/' + id + '/imprimir';
  
  const waBtn = document.getElementById('acc-wa');
  if (waUrl && waUrl !== '') {
    waBtn.href = waUrl;
    waBtn.classList.remove('disabled', 'text-muted');
  } else {
    waBtn.href = '#';
    waBtn.classList.add('disabled', 'text-muted');
  }
  
  new bootstrap.Modal(document.getElementById('accionesModal')).show();
}

function ejecutarCompartir() {
  bootstrap.Modal.getInstance(document.getElementById('accionesModal')).hide();
  setTimeout(() => openCompartir(_accionId), 300);
}

function ejecutarEmail() {
  bootstrap.Modal.getInstance(document.getElementById('accionesModal')).hide();
  setTimeout(() => openEmail(_accionId), 300);
}

function ejecutarBorrar() {
  bootstrap.Modal.getInstance(document.getElementById('accionesModal')).hide();
  setTimeout(() => openBorrar(_accionId, _accionNum), 300);
}
</script>
'''

    if 'accionesModal' not in contenido:
        contenido = contenido.replace('{% endblock %}', modal_html + '\n{% endblock %}', 1)
        print("[upgrade73] Modal de acciones agregado al HTML")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade73] ventas/lista.html actualizado")


def main():
    print("=== Upgrade 73: Menu de acciones como ventana flotante (nunca se corta) ===")
    patch_ventas_lista()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5")


if __name__ == '__main__':
    main()