# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_base_interno():
    """Agrega el menú hamburguesa y adapta el sistema interno a celulares."""
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'mobile-topbar' in contenido: return # Ya parcheado

    css_mobile = """
/* ===== RESPONSIVE INTERNO (CELULARES) ===== */
.mobile-topbar { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 60px; background: #111827; z-index: 1050; align-items: center; padding: 0 1rem; justify-content: space-between; color: white; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
.btn-menu { background: none; border: none; color: white; font-size: 1.5rem; cursor: pointer; padding: 0; }
.sidebar-backdrop { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1055; }

@media (max-width: 991px) {
  .sidebar { transform: translateX(-100%); transition: transform 0.3s ease; z-index: 1060; }
  .sidebar.show { transform: translateX(0); }
  .content { margin-left: 0 !important; padding: 80px 1rem 1rem 1rem !important; }
  .mobile-topbar { display: flex; }
  .sidebar-backdrop.show { display: block; }
  
  /* Ajustes de tablas y formularios en celular */
  .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .row { flex-direction: column; }
  .col-md-3, .col-md-4, .col-md-6, .col-md-8 { width: 100%; margin-bottom: 1rem; }
  .card-kpi { margin-bottom: 1rem; }
}
"""
    
    html_mobile = """
<!-- BARRA SUPERIOR MOVIL -->
<div class="mobile-topbar">
  <div class="d-flex align-items-center gap-2">
    <button class="btn-menu" onclick="toggleSidebar()"><i class="bi bi-list"></i></button>
    <span class="fw-bold fs-6">Familia Zaragoza ®</span>
  </div>
  <a href="{{ url_for('logout') }}" class="text-danger"><i class="bi bi-box-arrow-right fs-5"></i></a>
</div>
<div class="sidebar-backdrop" id="sidebar-backdrop" onclick="toggleSidebar()"></div>
"""
    
    js_mobile = """
<script>
function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('show');
  document.getElementById('sidebar-backdrop').classList.toggle('show');
}
</script>
"""
    # Insertar CSS
    contenido = contenido.replace('</style>', css_mobile + '\n</style>')
    # Insertar HTML justo despues de <body>
    contenido = contenido.replace('<body>', '<body>\n' + html_mobile)
    # Insertar JS
    contenido = contenido.replace('</body>', js_mobile + '\n</body>')

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade135] base.html (interno) ahora es responsive")


def patch_base_catalogo():
    """Ajusta el catálogo público a celulares."""
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'mobile-catalog-fix' in contenido: return # Ya parcheado

    css_mobile = """
/* ===== RESPONSIVE CATALOGO (CELULARES) ===== */
@media (max-width: 768px) {
  .cat-header { padding: 1rem 0; }
  .cat-header .container { flex-direction: column; gap: 1rem; text-align: center; }
  .cat-nav { display: none !important; } /* Ocultamos los links en el celu, ya estan las pildoras abajo */
  .cat-header .d-flex { justify-content: center; width: 100%; }
  
  .hero-title h1 { font-size: 2rem; }
  .hero-title p { font-size: 1rem; }
  
  .cat-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)) !important; gap: 1rem; }
  .cat-card-body { padding: 1rem; }
  .cat-card-title { font-size: 0.95rem; }
  
  .pills-container { gap: 0.5rem; }
  .cat-pill { padding: 0.5rem 1rem; font-size: 0.85rem; }
  
  /* Ajustes del carrito y checkout */
  .cat-form-card { padding: 1rem !important; }
  .row { flex-direction: column; }
}
"""
    contenido = contenido.replace('</style>', css_mobile + '\n</style>')
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade135] base.html (catalogo) ahora es responsive")


def patch_tablas_responsive():
    """Asegura que los modulos con tablas tengan la clase table-responsive."""
    archivos = [
        'templates/ventas/lista.html',
        'templates/productos/lista.html',
        'templates/clientes/lista.html',
        'templates/gastos/lista.html',
        'templates/mayoristas/lista.html',
        'templates/mayoristas/lista_pagos.html'
    ]
    for arch in archivos:
        ruta = os.path.join(BASE, arch)
        if not os.path.exists(ruta): continue
        with open(ruta, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Si la tabla no está dentro de un div responsive, lo envolvemos
        if '<div class="table-responsive">' not in contenido and '<table' in contenido:
            contenido = contenido.replace('<table', '<div class="table-responsive"><table')
            contenido = contenido.replace('</table>', '</table></div>')
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print(f"[upgrade135] Tablas adaptadas en {arch}")


def main():
    print("=== Upgrade 135: Modo Responsive (Celulares y PC) ===")
    patch_base_interno()
    patch_base_catalogo()
    patch_tablas_responsive()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()