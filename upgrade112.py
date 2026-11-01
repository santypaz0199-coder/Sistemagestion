# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_catalogo_base():
    ruta = os.path.join(BASE, 'templates', 'catalogo', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade112] no existe catalogo/base.html")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Si ya lo pusimos, no lo duplicamos
    if 'neon-dorado-btn' in contenido:
        print("[upgrade112] El estilo neón ya estaba aplicado")
        return

    # El CSS mágico para el efecto neón óxido y arreglar el texto
    css_extra = '''
/* === NEON DORADO / MARRÓN ÓXIDO PARA BOTONES === */
.cat-btn, .cat-btn-outline, button.cat-btn, .cat-btn.text-center {
    transition: all 0.3s ease-in-out !important;
    position: relative;
}

/* Botón sólido (Ir a pagar, etc) */
.cat-btn:not(.cat-btn-outline):hover {
    background: #c9a96e !important;
    color: #0a0a0a !important;
    box-shadow: 0 0 10px #c9a96e, 0 0 20px rgba(201, 169, 110, 0.6), inset 0 0 5px #fff !important;
    transform: translateY(-2px);
}

/* Botón outline (Seguir comprando, Vaciar carrito, etc) */
.cat-btn-outline {
    color: var(--cat-accent) !important;
    border: 1px solid var(--cat-accent) !important;
}
.cat-btn-outline:hover {
    background: rgba(201, 169, 110, 0.1) !important;
    color: #e5c07b !important; /* Dorado más brillante */
    border-color: #e5c07b !important;
    box-shadow: 0 0 12px rgba(201, 169, 110, 0.8), inset 0 0 8px rgba(201, 169, 110, 0.4) !important;
    text-shadow: 0 0 5px rgba(201, 169, 110, 0.5);
    transform: translateY(-2px);
}

/* Botón eliminar (la X) */
button[title="Quitar"]:hover, button[title="Eliminar"]:hover {
    color: #ff6b6b !important;
    text-shadow: 0 0 8px rgba(255, 107, 107, 0.8);
    transform: scale(1.1);
}

/* Botón actualizar cantidad */
button[title="Actualizar"]:hover {
    color: #e5c07b !important;
    text-shadow: 0 0 8px rgba(201, 169, 110, 0.8);
    transform: scale(1.1);
}
'''
    
    # Inyectar el CSS justo antes del cierre de </style>
    contenido = contenido.replace('</style>', css_extra + '\n</style>')
    
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    
    print("[upgrade112] Efecto Neón Dorado aplicado a los botones del catálogo")


def main():
    print("=== Upgrade 112: Efecto Neón Dorado en botones ===")
    patch_catalogo_base()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")


if __name__ == '__main__':
    main()