# -*- coding: utf-8 -*-
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def escribir(relpath, contenido):
    ruta = os.path.join(BASE, relpath)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print(f"[upgrade38] escrito: {relpath}")


def patch_base_html():
    ruta = os.path.join(BASE, 'templates', 'base.html')
    if not os.path.exists(ruta):
        print("[upgrade38] no existe base.html"); return
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'block extra_head' in contenido:
        print("[upgrade38] base.html ya tiene extra_head"); return
    if '</head>' not in contenido:
        print("[upgrade38] no se encontro </head>"); return
    contenido = contenido.replace('</head>', '{% block extra_head %}{% endblock %}\n</head>', 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(contenido)
    print("[upgrade38] bloque extra_head agregado a base.html")


VENTAS_FORM = r'''{% extends "base.html" %}
{% block title %}Nueva orden{% endblock %}

{% block extra_head %}
<link href="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/css/tom-select.bootstrap5.min.css" rel="stylesheet">
<style>
.ts-wrapper { width: 100%; }
.ts-control{ border-radius:9px !important; border:1px solid #e8ecf3 !important; padding:.5rem .75rem !important; font-size:.94rem; min-height:40px; box-shadow:none !important; }
.ts-wrapper.focus .ts-control{ border-color:#3b5bdb !important; box-shadow:0 0 0 3px rgba(59,91,219,.12) !important; }
.ts-control input{ font-size:.94rem !important; }
.ts-dropdown{ border-radius:10px !important; border:1px solid #e8ecf3 !important; box-shadow:0 8px 24px rgba(16,24,40,.10) !important; margin-top:4px; overflow:hidden; }
.ts-dropdown .option{ padding:.55rem .85rem !important; cursor:pointer; }
.ts-dropdown .option.active{ background:#eef2ff !important; color:#3b5bdb !important; }
.ts-dropdown .option.selected{ background:#3b5bdb !important; color:#fff !important; }
.ts-dropdown-content{ max-height:280px; }
.ts-wrapper.single .ts-control:after{ border-color:#6b7280 transparent transparent !important; }
.ts-wrapper.focus .ts-control:after{ border-color:#3b5bdb transparent transparent !important; }
.ts-wrapper .ts-control > div{ cursor:text; }
.producto-ts.ts-control{ min-height:32px !important; padding:.35rem .6rem !important; font-size:.85rem !important; }
</style>
{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
<h4 class="mb-0">Nueva orden de venta</h4>
<a href="{{ url_for('ventas_lista') }}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
</div>
<form method="post" id="form-venta">
<div class="card shadow-sm mb-3"><div class="card-body"><div class="row g-3">
<div class="col-md-6">
<label class="form-label">Cliente * <small class="text-muted">(buscar por nombre, doc, tel o provincia)</small></label>
<select name="cliente_id" id="cliente-select" class="form-select" required>
<option value="">-- Buscar cliente --</option>
{% for c in clientes %}<option value="{{ c.id }}" data-provincia="{{ c.provincia or '' }}" data-tel="{{ c.telefono or '' }}" data-doc="{{ c.nro_doc or '' }}">{{ c.nombre_completo }}{% if c.provincia %} ({{ c.provincia }}){% endif %}</option>{% endfor %}
</select>
</div>
<div class="col-md-3"><label class="form-label">Tipo *</label><select name="tipo" class="form-select" required><option value="minorista">Minorista</option><option value="mayorista">Mayorista</option></select></div>
<div class="col-md-3"><label class="form-label">Canal</label><select name="canal_id" class="form-select"><option value="">--</option>{% for ch in canales %}<option value="{{ ch.id }}">{{ ch.nombre }}</option>{% endfor %}</select></div>
<div class="col-md-3"><label class="form-label">Fecha</label><input type="date" name="fecha" class="form-control" value="{{ hoy }}"></div>
<div class="col-md-9"><label class="form-label">Notas</label><input name="notas" class="form-control" placeholder="Notas internas"></div>
</div></div></div>

<div class="card shadow-sm mb-3"><div class="card-body">
<div class="d-flex justify-content-between align-items-center mb-2"><h6 class="mb-0">Productos</h6><button type="button" class="btn btn-sm btn-outline-secondary" onclick="addItem()"><i class="bi bi-plus-lg"></i> Agregar</button></div>
<table class="table table-sm align-middle mb-0"><thead><tr><th>Producto</th><th width="100">Cant.</th><th width="130">Precio</th><th width="110" class="text-end">Subtotal</th><th width="40"></th></tr></thead><tbody id="items-body"></tbody></table>
</div></div>

<div class="card shadow-sm mb-3"><div class="card-body"><div class="row"><div class="col-md-6 offset-md-6">
<table class="table table-sm mb-0">
<tr><td>Subtotal:</td><td class="text-end" id="subtotal-view">$0.00</td></tr>
<tr><td>Descuento:</td><td><input type="number" step="0.01" min="0" name="descuento" id="descuento" value="0" class="form-control form-control-sm text-end" onchange="updateTotals()"></td></tr>
<tr class="fw-bold"><td>Total:</td><td class="text-end" id="total-view">$0.00</td></tr>
</table></div></div></div></div>

<button class="btn btn-dark btn-lg">Crear orden</button>
</form>

<template id="item-template"><tr class="item-row">
<td><select name="producto_id" class="producto-select" required><option value="">--</option>{% for p in productos %}<option value="{{ p.id }}" data-precio="{{ p.precio }}">{{ p.nombre }} (stock: {{ '%g'|format(p.stock_actual) }})</option>{% endfor %}</select></td>
<td><input type="number" step="0.01" min="0.01" name="cantidad" class="form-control form-control-sm" value="1" onchange="updateTotals()" required></td>
<td><input type="number" step="0.01" min="0" name="precio" class="form-control form-control-sm" value="0" onchange="updateTotals()" required></td>
<td class="text-end subtotal">$0.00</td>
<td><button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(this)"><i class="bi bi-trash"></i></button></td>
</tr></template>

<script src="https://cdn.jsdelivr.net/npm/tom-select@2.3.1/dist/js/tom-select.complete.min.js"></script>
<script>
function initProductTomSelect(sel) {
  if (sel.tomselect) return;
  new TomSelect(sel, {
    placeholder: 'Buscar producto...',
    maxOptions: 200,
    onChange: function(value) {
      const opt = sel.querySelector('option[value="' + value + '"]');
      if (opt) {
        const precio = opt.dataset.precio || 0;
        const row = sel.closest('tr');
        if (row) {
          row.querySelector('[name="precio"]').value = precio;
          updateTotals();
        }
      }
    }
  });
}

function addItem(){
  const t = document.getElementById('item-template');
  document.getElementById('items-body').appendChild(t.content.cloneNode(true));
  const rows = document.querySelectorAll('#items-body .item-row');
  const last = rows[rows.length - 1];
  const sel = last.querySelector('[name="producto_id"]');
  initProductTomSelect(sel);
}

function removeItem(b){ 
  const sel = b.closest('tr').querySelector('[name="producto_id"]');
  if (sel && sel.tomselect) { sel.tomselect.destroy(); }
  b.closest('tr').remove(); 
  updateTotals(); 
}

function updateTotals(){
  let sub = 0;
  document.querySelectorAll('.item-row').forEach(r => {
    const c = parseFloat(r.querySelector('[name="cantidad"]').value) || 0;
    const p = parseFloat(r.querySelector('[name="precio"]').value) || 0;
    const s = c * p;
    r.querySelector('.subtotal').textContent = '$' + s.toFixed(2);
    sub += s;
  });
  const d = parseFloat(document.getElementById('descuento').value) || 0;
  document.getElementById('subtotal-view').textContent = '$' + sub.toFixed(2);
  document.getElementById('total-view').textContent = '$' + Math.max(0, sub - d).toFixed(2);
}

document.addEventListener('DOMContentLoaded', () => {
  const clienteSel = document.getElementById('cliente-select');
  new TomSelect(clienteSel, {
    placeholder: 'Buscar cliente por nombre, doc, tel o provincia...',
    maxOptions: 200,
    sortField: { field: 'text', direction: 'asc' },
    render: {
      option: function(data, escape) {
        const el = clienteSel.querySelector('option[value="' + data.value + '"]');
        const prov = el ? el.dataset.provincia : '';
        const tel = el ? el.dataset.tel : '';
        const doc = el ? el.dataset.doc : '';
        const extras = [doc, prov, tel].filter(Boolean).join(' · ');
        const nombre = data.text.split(' (')[0];
        return '<div><strong>' + escape(nombre) + '</strong>' + (extras ? '<br><small style="color:#9ca3af;font-size:.72rem;">' + escape(extras) + '</small>' : '') + '</div>';
      }
    }
  });

  addItem();

  const params = new URLSearchParams(window.location.search);
  const cid = params.get('cliente_id');
  if (cid && clienteSel.tomselect) {
    clienteSel.tomselect.setValue(cid);
  }

  document.getElementById('form-venta').addEventListener('submit', function(e) {
    if (!clienteSel.value) {
      e.preventDefault();
      clienteSel.tomselect.focus();
      alert('Tenés que elegir un cliente.');
      return false;
    }
  });
});
</script>
{% endblock %}
'''


RUN_BAT = '''@echo off
cd /d "%~dp0"
call venv\\Scripts\\activate
python -c "import app37; app37.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
'''


def main():
    print("=== Upgrade 38: Buscador con Tom Select en Nueva Orden ===")
    patch_base_html()
    escribir('templates/ventas/form.html', VENTAS_FORM)
    escribir('run.bat', RUN_BAT)
    print("")
    print("=== LISTO ===")
    print("Ejecuta: run.bat")


if __name__ == '__main__':
    main()