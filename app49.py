
from flask import Blueprint, render_template, abort, request
from database import get_db

catalogo_bp = Blueprint('catalogo', __name__, url_prefix='/catalogo',
                         template_folder='templates/catalogo')

def _categorias_arbol(conn):
    cats = conn.execute("SELECT * FROM categorias_productos WHERE activo=1 ORDER BY nombre").fetchall()
    padres = [c for c in cats if not c['parent_id']]
    hijos = {}
    for c in cats:
        if c['parent_id']:
            hijos.setdefault(c['parent_id'], []).append(c)
    return padres, hijos

@catalogo_bp.route('/')
def index():
    conn = get_db()
    padres, hijos = _categorias_arbol(conn)
    categoria_id = request.args.get('categoria', type=int)
    busqueda = request.args.get('q', '').strip()

    # Datos para el encabezado de la tarjeta de subcategorías (si aplica)
    padre_actual = None
    subcats_actuales = []

    if categoria_id:
        cat = conn.execute("SELECT * FROM categorias_productos WHERE id=? AND activo=1", (categoria_id,)).fetchone()
        if not cat:
            conn.close(); abort(404)
            
        if cat['parent_id']:
            # Si tocó una subcategoría, buscamos los datos del padre para el título
            padre_actual = conn.execute("SELECT * FROM categorias_productos WHERE id=?", (cat['parent_id'],)).fetchone()
            subcats_actuales = hijos.get(cat['parent_id'], [])
        else:
            # Si tocó el padre, mostramos sus subcategorías
            padre_actual = cat
            subcats_actuales = hijos.get(cat['id'], [])
            
        ids = [categoria_id] + [h['id'] for h in hijos.get(categoria_id, [])]
        placeholders = ','.join(['?'] * len(ids))
        query = f"""
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1 AND p.categoria_id IN ({placeholders})
        """
        params = ids
    else:
        query = """
            SELECT p.*, c.nombre as categoria_nombre
            FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
            WHERE p.activo=1 AND p.mostrar_en_catalogo=1
        """
        params = []

    if busqueda:
        query += " AND (p.nombre LIKE ? OR p.sku LIKE ?)"
        params.extend([f'%{busqueda}%', f'%{busqueda}%'])

    query += " ORDER BY p.nombre"
    productos = conn.execute(query, params).fetchall()

    # Obtener config de portada
    portada_imagen = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_imagen'").fetchone()
    portada_imagen = portada_imagen['valor'] if portada_imagen and portada_imagen['valor'] else None
    portada_titulo = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_titulo'").fetchone()
    portada_titulo = portada_titulo['valor'] if portada_titulo and portada_titulo['valor'] else 'Yerba Mate Premium'
    portada_subtitulo = conn.execute("SELECT valor FROM configuracion WHERE clave='portada_subtitulo'").fetchone()
    portada_subtitulo = portada_subtitulo['valor'] if portada_subtitulo and portada_subtitulo['valor'] else ''

    conn.close()
    return render_template('catalogo/index.html', 
                           productos=productos, 
                           padres=padres, 
                           hijos=hijos, 
                           categoria_actual=categoria_id,
                           padre_actual=padre_actual,
                           subcats_actuales=subcats_actuales,
                           busqueda=busqueda, portada_imagen=portada_imagen, portada_titulo=portada_titulo, portada_subtitulo=portada_subtitulo)

@catalogo_bp.route('/producto/<int:id>')
def producto_detalle(id):
    conn = get_db()
    producto = conn.execute("""
        SELECT p.*, c.nombre as categoria_nombre
        FROM productos p LEFT JOIN categorias_productos c ON c.id = p.categoria_id
        WHERE p.id=? AND p.activo=1 AND p.mostrar_en_catalogo=1
    """, (id,)).fetchone()
    if not producto:
        conn.close(); abort(404)
        
    relacionados = []
    if producto['mostrar_carrusel_recomendados'] == 1:
        relacionados = conn.execute("""
            SELECT p.* FROM productos p
            JOIN productos_relacionados pr ON pr.relacionado_id = p.id
            WHERE pr.producto_id = ? AND p.activo=1 AND p.mostrar_en_catalogo=1
        """, (id,)).fetchall()
    
    conn.close()
    return render_template('catalogo/producto.html', producto=producto, relacionados=relacionados)

from app51 import registro, login, logout, mi_cuenta
