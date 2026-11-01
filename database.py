
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sistema.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  rol TEXT NOT NULL DEFAULT 'vendedor',
  activo INTEGER DEFAULT 1,
  creado TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS permisos_usuario (
  usuario_id INTEGER NOT NULL,
  modulo TEXT NOT NULL,
  PRIMARY KEY (usuario_id, modulo),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS configuracion (
  clave TEXT PRIMARY KEY,
  valor TEXT
);
CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre_completo TEXT NOT NULL,
  tipo_doc TEXT,
  nro_doc TEXT,
  provincia TEXT,
  localidad TEXT,
  codigo_postal TEXT,
  email TEXT,
  telefono TEXT,
  es_minorista INTEGER DEFAULT 0,
  es_mayorista INTEGER DEFAULT 0,
  notas TEXT,
  activo INTEGER DEFAULT 1,
  creado TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS productos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT UNIQUE,
  nombre TEXT NOT NULL,
  costo REAL DEFAULT 0,
  precio REAL DEFAULT 0,
  stock_actual REAL DEFAULT 0,
  stock_minimo REAL DEFAULT 0,
  activo INTEGER DEFAULT 1,
  creado TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS proveedores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  cuit TEXT,
  contacto TEXT,
  telefono TEXT,
  email TEXT,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS compras (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  proveedor_id INTEGER,
  fecha TEXT NOT NULL,
  total REAL DEFAULT 0,
  usuario_id INTEGER,
  notas TEXT,
  creado TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS compra_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  compra_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL,
  cantidad REAL NOT NULL,
  costo_unitario REAL NOT NULL,
  FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
  FOREIGN KEY (producto_id) REFERENCES productos(id)
);
CREATE TABLE IF NOT EXISTS canales_venta (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS transportistas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  url_seguimiento TEXT,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS medios_pago (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  comision_pct REAL DEFAULT 0,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ordenes_venta (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_interno TEXT UNIQUE NOT NULL,
  cliente_id INTEGER NOT NULL,
  usuario_id INTEGER NOT NULL,
  canal_id INTEGER,
  tipo TEXT NOT NULL,
  fecha TEXT NOT NULL,
  estado TEXT NOT NULL DEFAULT 'pendiente_pago',
  estado_facturacion TEXT DEFAULT 'no_requiere',
  nro_factura_arca TEXT,
  fecha_factura TEXT,
  subtotal REAL DEFAULT 0,
  descuento REAL DEFAULT 0,
  total REAL DEFAULT 0,
  transportista_id INTEGER,
  nro_guia TEXT,
  destinatario_nombre TEXT,
  destinatario_provincia TEXT,
  destinatario_localidad TEXT,
  destinatario_cp TEXT,
  destinatario_calle TEXT,
  destinatario_detalles TEXT,
  notas TEXT,
  creado TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (cliente_id) REFERENCES clientes(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
  FOREIGN KEY (canal_id) REFERENCES canales_venta(id),
  FOREIGN KEY (transportista_id) REFERENCES transportistas(id)
);
CREATE TABLE IF NOT EXISTS orden_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER NOT NULL,
  producto_id INTEGER NOT NULL,
  cantidad REAL NOT NULL,
  precio_unitario REAL NOT NULL,
  subtotal REAL NOT NULL,
  FOREIGN KEY (orden_id) REFERENCES ordenes_venta(id) ON DELETE CASCADE,
  FOREIGN KEY (producto_id) REFERENCES productos(id)
);
CREATE TABLE IF NOT EXISTS pagos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER NOT NULL,
  fecha TEXT NOT NULL,
  medio_pago_id INTEGER,
  monto REAL NOT NULL,
  comision REAL DEFAULT 0,
  monto_neto REAL NOT NULL,
  usuario_id INTEGER,
  notas TEXT,
  FOREIGN KEY (orden_id) REFERENCES ordenes_venta(id) ON DELETE CASCADE,
  FOREIGN KEY (medio_pago_id) REFERENCES medios_pago(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS movimientos_stock (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto_id INTEGER NOT NULL,
  tipo TEXT NOT NULL,
  cantidad REAL NOT NULL,
  referencia TEXT,
  usuario_id INTEGER,
  fecha TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (producto_id) REFERENCES productos(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS categorias_gastos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT UNIQUE NOT NULL,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS gastos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha TEXT NOT NULL,
  categoria_id INTEGER,
  descripcion TEXT,
  monto REAL NOT NULL,
  usuario_id INTEGER,
  creado TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (categoria_id) REFERENCES categorias_gastos(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);
CREATE TABLE IF NOT EXISTS impuestos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  tipo TEXT,
  porcentaje REAL DEFAULT 0,
  activo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cierres (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tipo TEXT NOT NULL,
  fecha_desde TEXT NOT NULL,
  fecha_hasta TEXT NOT NULL,
  stock_unidades REAL,
  saldo_inicial REAL,
  total_vendido REAL,
  total_gastado REAL,
  saldo_actual REAL,
  a_cobrar REAL,
  a_pagar REAL,
  creado TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS emails_enviados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  destinatario TEXT,
  asunto TEXT,
  tipo TEXT,
  orden_id INTEGER,
  fecha TEXT DEFAULT CURRENT_TIMESTAMP,
  estado TEXT
);
CREATE TABLE IF NOT EXISTS archivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  orden_id INTEGER,
  tipo TEXT,
  nombre_original TEXT,
  ruta_local TEXT,
  fecha TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (orden_id) REFERENCES ordenes_venta(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS campanas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  filtros_json TEXT,
  cuerpo_html TEXT,
  creado TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS auditoria (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario_id INTEGER,
  accion TEXT,
  entidad TEXT,
  entidad_id INTEGER,
  detalle TEXT,
  fecha TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

MEDIOS_PAGO = ['Efectivo', 'Transferencia', 'Tarjeta debito', 'Tarjeta credito', 'Mercado Pago', 'QR', 'Otro']
CANALES = ['Web', 'Mercado Libre', 'Instagram', 'WhatsApp', 'Presencial']
CATEGORIAS_GASTO = ['Fijos', 'Variables', 'Logistica', 'Marketing', 'Impuestos', 'Otros']

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript(SCHEMA)

    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='admin'")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO usuarios (nombre,email,password_hash,rol) VALUES (?,?,?,?)",
            ('Admin', 'admin@local', generate_password_hash('admin123'), 'admin')
        )

    for m in MEDIOS_PAGO:
        c.execute("INSERT OR IGNORE INTO medios_pago (nombre) VALUES (?)", (m,))
    for ch in CANALES:
        c.execute("INSERT OR IGNORE INTO canales_venta (nombre) VALUES (?)", (ch,))
    for cat in CATEGORIAS_GASTO:
        c.execute("INSERT OR IGNORE INTO categorias_gastos (nombre) VALUES (?)", (cat,))

    conn.commit()
    conn.close()
