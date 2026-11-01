# -*- coding: utf-8 -*-
import os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))

PROVINCIAS = [
    'Ciudad Autónoma de Buenos Aires', 'Buenos Aires', 'Catamarca', 'Chaco', 'Chubut',
    'Córdoba', 'Corrientes', 'Entre Ríos', 'Formosa', 'Jujuy', 'La Pampa', 'La Rioja',
    'Mendoza', 'Misiones', 'Neuquén', 'Río Negro', 'Salta', 'San Juan', 'San Luis',
    'Santa Cruz', 'Santa Fe', 'Santiago del Estero', 'Tierra del Fuego', 'Tucumán',
]

LOCALIDADES = {
    'Ciudad Autónoma de Buenos Aires': ['Ciudad Autónoma de Buenos Aires'],
    'Buenos Aires': [
        'La Plata','Mar del Plata','Bahía Blanca','San Isidro','Vicente López','San Martín','Morón',
        'San Justo','Lomas de Zamora','Lanús','Avellaneda','Quilmes','Berazategui','Almirante Brown',
        'Ezeiza','Tigre','San Fernando','San Miguel','José C. Paz','Malvinas Argentinas','Pilar',
        'Escobar','Moreno','Merlo','Ituzaingó','Hurlingham','Tres de Febrero','San Nicolás',
        'Pergamino','Junín','Olavarría','Tandil','Azul','Luján','Chivilcoy','Bragado','Pehuajó',
        'Necochea','Coronel Suárez','Trenque Lauquen','Bolívar','Saladillo','Chascomús','Dolores',
        'Villa Gesell','Pinamar','Monte Hermoso','San Pedro','Zárate','Campana','Lobos','Cañuelas',
        'Mercedes','Chacabuco','Lincoln','General Villegas','Rojas','Colón','San Antonio de Areco',
    ],
    'Catamarca': ['San Fernando del Valle de Catamarca','Andalgalá','Tinogasta','Belén','Recreo','Santa María'],
    'Chaco': ['Resistencia','Presidencia Roque Sáenz Peña','Villa Ángela','Barranqueras','Charata',
              'General José de San Martín','Quitilipi','Machagai','Juan José Castelli'],
    'Chubut': ['Rawson','Trelew','Puerto Madryn','Comodoro Rivadavia','Esquel','Sarmiento','Rada Tilly','Gaiman'],
    'Córdoba': [
        'Córdoba','Villa María','Río Cuarto','San Francisco','Villa Carlos Paz','Alta Gracia',
        'Río Tercero','Villa Dolores','Jesús María','Cruz del Eje','Cosquín','La Falda','Deán Funes',
        'Marcos Juárez','Bell Ville','Laboulaye','Villa Nueva','Hernando','Oliva','Oncativo',
        'Arroyito','Morteros','Leones','Río Segundo','Villa Allende','Mendiolaza','Unquillo','Salsipuedes',
    ],
    'Corrientes': ['Corrientes','Goya','Paso de los Libres','Curuzú Cuatiá','Mercedes','Santo Tomé',
                   'Esquina','Bella Vista','Saladas','Monte Caseros','Ituzaingó'],
    'Entre Ríos': ['Paraná','Concordia','Gualeguaychú','Concepción del Uruguay','Colón','Gualeguay',
                   'Villaguay','Victoria','La Paz','Chajarí','Crespo','Federal','Villaguay','San José'],
    'Formosa': ['Formosa','Clorinda','Pirané','El Colorado','Las Lomitas','Ibarreta'],
    'Jujuy': ['San Salvador de Jujuy','Palpalá','San Pedro de Jujuy','Libertador General San Martín',
              'Humahuaca','Tilcara','La Quiaca','El Carmen'],
    'La Pampa': ['Santa Rosa','General Pico','Realicó','Eduardo Castex','General Acha','25 de Mayo',
                 'Macachín','Guatraché'],
    'La Rioja': ['La Rioja','Chilecito','Aimogasta','Chamical','Villa Unión','Aimogasta','Famatina'],
    'Mendoza': ['Mendoza','San Rafael','Godoy Cruz','Guaymallén','Las Heras','Maipú','Luján de Cuyo',
                'San Martín','Rivadavia','Tunuyán','Tupungato','General Alvear','Malargüe','Santa Rosa','La Paz'],
    'Misiones': ['Posadas','Oberá','Eldorado','Puerto Iguazú','San Vicente','Apóstoles',
                 'Leandro N. Alem','Jardín América','Montecarlo','Bernardo de Irigoyen'],
    'Neuquén': ['Neuquén','Plottier','Centenario','Cutral-Có','Zapala','San Martín de los Andes',
                'Junín de los Andes','Plaza Huincul','Chos Malal','Rincón de los Sauces'],
    'Río Negro': ['Viedma','San Carlos de Bariloche','General Roca','Cipolletti','Villa Regina',
                  'Cinco Saltos','Allen','El Bolsón','San Antonio Oeste','Ingeniero Jacobacci'],
    'Salta': ['Salta','San Ramón de la Nueva Orán','Tartagal','Metán','Rosario de la Frontera',
              'General Güemes','Cafayate','Cachi','Embarcación'],
    'San Juan': ['San Juan','Rawson','Rivadavia','Chimbas','Pocito','Caucete','San Martín',
                 'Santa Lucía','Albardón','Iglesia'],
    'San Luis': ['San Luis','Villa Mercedes','Merlo','Juana Koslay','La Punta','Quines','Concarán'],
    'Santa Cruz': ['Río Gallegos','Caleta Olivia','El Calafate','Pico Truncado','Puerto Deseado',
                   'Río Turbio','Las Heras','Puerto San Julián'],
    'Santa Fe': ['Santa Fe','Rosario','Rafaela','Venado Tuerto','Reconquista','Santo Tomé',
                 'Villa Gobernador Gálvez','San Lorenzo','Casilda','Cañada de Gómez',
                 'Villa Constitución','Esperanza','San Justo','Avellaneda','Villa Ocampo',
                 'Ceres','Tostado','Firmat','Rufino'],
    'Santiago del Estero': ['Santiago del Estero','La Banda','Termas de Río Hondo','Frías',
                            'Añatuya','Quimilí','Clodomira','Monte Quemado'],
    'Tierra del Fuego': ['Ushuaia','Río Grande','Tolhuin'],
    'Tucumán': ['San Miguel de Tucumán','Yerba Buena','Tafí Viejo','Concepción','Aguilares',
                'Bella Vista','Lules','Monteros','Banda del Río Salí','Alderetes','Famaillá','Simoca'],
}

def restaurar():
    db = os.path.join(BASE, 'sistema.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    
    # Asegurar que las tablas existan
    conn.execute("CREATE TABLE IF NOT EXISTS provincias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS localidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provincia_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (provincia_id) REFERENCES provincias(id)
        )
    """)
    
    # Insertar Provincias
    for p in PROVINCIAS:
        conn.execute("INSERT OR IGNORE INTO provincias (nombre) VALUES (?)", (p,))
    
    # Obtener IDs y insertar Localidades
    prov_map = {r[1]: r[0] for r in conn.execute("SELECT id, nombre FROM provincias").fetchall()}
    total = 0
    for prov, locs in LOCALIDADES.items():
        pid = prov_map.get(prov)
        if pid:
            for l in locs:
                # Evitar duplicados exactos
                existe = conn.execute("SELECT id FROM localidades WHERE provincia_id=? AND nombre=?", (pid, l)).fetchone()
                if not existe:
                    conn.execute("INSERT INTO localidades (provincia_id, nombre) VALUES (?, ?)", (pid, l))
                    total += 1
                    
    conn.commit(); conn.close()
    print(f"[upgrade138] {len(PROVINCIAS)} provincias y {total} localidades restauradas con exito.")

if __name__ == '__main__':
    print("=== Upgrade 138: Restaurando Provincias y Ciudades ===")
    restaurar()
    print("=== LISTO === Ejecuta run.bat")