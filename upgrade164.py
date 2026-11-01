# -*- coding: utf-8 -*-
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))

def patch_form_html():
    ruta = os.path.join(BASE, 'templates', 'ventas', 'form.html')
    if not os.path.exists(ruta): return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # 1. Cambiar la función cargarCliente para que no use alert()
    buscar_js = r'''// --- CARGA DE CLIENTE ---
async function cargarCliente() {
  const cid = document.getElementById('cliente-select').value;
  if (!cid) return;
  
  try {
    const res = await fetch('/api/cliente/' + cid);
    const data = await res.json();
    
    // Autocompletar tipo
    document.getElementById('tipo-compra').value = data.tipo;
    
    // Autocompletar datos de envío
    document.getElementById('dest_nombre').value = data.nombre;
    document.getElementById('dest_doc').value = data.doc.replace(/[^0-9]/g, '');
    document.getElementById('dest_tel').value = data.tel;
    document.getElementById('dest_email').value = data.email;
    document.getElementById('dest_calle').value = data.calle;
    
    // Provincia y Localidad
    if (data.provincia) {
      document.getElementById('dest_prov').value = data.provincia;
      actualizarCiudades();
      if (data.localidad) {
        document.getElementById('dest_loc').value = data.localidad;
      }
    }
    
    if (!data.calle || !data.provincia) {
      alert('Faltan datos del cliente (Calle o Provincia). Por favor, tildá "Modificar datos de envío" y completalos.');
    }
  } catch(e) { console.error(e); }
}'''

    nuevo_js = r'''// --- CARGA DE CLIENTE ---
async function cargarCliente() {
  const cid = document.getElementById('cliente-select').value;
  if (!cid) return;
  
  try {
    const res = await fetch('/api/cliente/' + cid);
    const data = await res.json();
    
    // Autocompletar tipo
    document.getElementById('tipo-compra').value = data.tipo;
    
    // Autocompletar datos de envío
    document.getElementById('dest_nombre').value = data.nombre;
    document.getElementById('dest_doc').value = data.doc.replace(/[^0-9]/g, '');
    document.getElementById('dest_tel').value = data.tel;
    document.getElementById('dest_email').value = data.email;
    
    // Provincia y Localidad
    if (data.provincia) {
      document.getElementById('dest_prov').value = data.provincia;
      actualizarCiudades();
      if (data.localidad) {
        document.getElementById('dest_loc').value = data.localidad;
      }
    }

    // Si el cliente tiene calle, la autocompletamos
    if (data.calle) {
        document.getElementById('dest_calle').value = data.calle;
    } else {
        document.getElementById('dest_calle').value = '';
    }
    
    const chkModificar = document.getElementById('chk-modificar-datos');
    
    if (!data.calle || !data.provincia || !data.tel || !data.email) {
      // Si faltan datos, obligamos a tildar el check para que el vendedor los complete
      chkModificar.checked = true;
      toggleDatosEnvio();
      // Mostramos un aviso rojo sutil debajo del checkbox
      document.getElementById('aviso-faltan-datos').style.display = 'block';
    } else {
      chkModificar.checked = false;
      toggleDatosEnvio();
      document.getElementById('aviso-faltan-datos').style.display = 'none';
    }
    
  } catch(e) { console.error(e); }
}'''

    if buscar_js in contenido:
        contenido = contenido.replace(buscar_js, nuevo_js)
        print("[upgrade164] JS de carga de cliente actualizado (sin alert)")

    # 2. Agregar el div del aviso rojo en el HTML
    buscar_checkbox = '''<div class="form-check mb-3">
        <input class="form-check-input" type="checkbox" id="chk-modificar-datos" onchange="toggleDatosEnvio()">
        <label class="form-check-label fw-semibold text-danger" for="chk-modificar-datos">
          Modificar datos de envío / Enviar a otra persona (Regalo)
        </label>
      </div>'''
      
    nuevo_checkbox = '''<div class="form-check mb-2">
        <input class="form-check-input" type="checkbox" id="chk-modificar-datos" onchange="toggleDatosEnvio()">
        <label class="form-check-label fw-semibold text-danger" for="chk-modificar-datos">
          Modificar datos de envío / Enviar a otra persona (Regalo)
        </label>
      </div>
      <div id="aviso-faltan-datos" class="alert alert-warning py-2 small mb-3" style="display:none;">
        <i class="bi bi-exclamation-triangle"></i> El cliente no tiene la dirección completa. Por favor, completá los campos de abajo.
      </div>'''

    if buscar_checkbox in contenido:
        contenido = contenido.replace(buscar_checkbox, nuevo_checkbox)
        print("[upgrade164] Aviso visual agregado al HTML")

    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)

def main():
    print("=== Upgrade 164: Fix de alerta al cargar cliente ===")
    patch_form_html()
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat y apreta Ctrl+F5 en el navegador")

if __name__ == '__main__':
    main()