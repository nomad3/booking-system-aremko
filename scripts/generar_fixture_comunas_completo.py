"""
Genera fixture JSON completo con las 346 comunas oficiales de Chile

Este script genera el archivo ventas/fixtures/comunas_chile_completo.json
con todas las comunas de Chile organizadas por región.

USO:
    python scripts/generar_fixture_comunas_completo.py
"""
import json

# Las 16 regiones ya existen, solo agregamos las comunas faltantes

# Datos completos de comunas por región
COMUNAS_POR_REGION = {
    1: {  # XV - Arica y Parinacota
        'existentes': ['Arica'],
        'nuevas': ['Camarones', 'General Lagos', 'Putre']
    },
    2: {  # I - Tarapacá
        'existentes': ['Iquique'],
        'nuevas': ['Alto Hospicio', 'Camiña', 'Colchane', 'Huara', 'Pica', 'Pozo Almonte']
    },
    3: {  # II - Antofagasta
        'existentes': ['Antofagasta', 'Calama'],
        'nuevas': ['María Elena', 'Mejillones', 'Ollagüe', 'San Pedro de Atacama', 'Sierra Gorda', 'Taltal', 'Tocopilla']
    },
    4: {  # III - Atacama
        'existentes': [],
        'nuevas': ['Alto del Carmen', 'Caldera', 'Chañaral', 'Copiapó', 'Diego de Almagro', 'Freirina', 'Huasco', 'Tierra Amarilla', 'Vallenar']
    },
    5: {  # IV - Coquimbo
        'existentes': ['La Serena'],
        'nuevas': ['Andacollo', 'Canela', 'Combarbalá', 'Coquimbo', 'Illapel', 'La Higuera', 'Los Vilos', 'Monte Patria', 'Ovalle', 'Paiguano', 'Punitaqui', 'Río Hurtado', 'Salamanca', 'Vicuña']
    },
    6: {  # V - Valparaíso
        'existentes': ['Valparaíso', 'Viña del Mar', 'Concón', 'Quilpué', 'San Antonio', 'Santo Domingo'],
        'nuevas': ['Algarrobo', 'Cabildo', 'Calera', 'Calle Larga', 'Cartagena', 'Casablanca', 'Catemu', 'El Quisco', 'El Tabo', 'Hijuelas', 'Isla de Pascua', 'Juan Fernández', 'La Cruz', 'La Ligua', 'Limache', 'Llaillay', 'Los Andes', 'Nogales', 'Olmué', 'Panquehue', 'Papudo', 'Petorca', 'Puchuncaví', 'Putaendo', 'Quillota', 'Quintero', 'Rinconada', 'San Esteban', 'San Felipe', 'Santa María', 'Villa Alemana', 'Zapallar']
    },
    7: {  # RM - Región Metropolitana
        'existentes': ['Santiago'],
        'nuevas': ['Alhué', 'Buin', 'Calera de Tango', 'Cerrillos', 'Cerro Navia', 'Colina', 'Conchalí', 'Curacaví', 'El Bosque', 'El Monte', 'Estación Central', 'Huechuraba', 'Independencia', 'Isla de Maipo', 'La Cisterna', 'La Florida', 'La Granja', 'La Pintana', 'La Reina', 'Lampa', 'Las Condes', 'Lo Barnechea', 'Lo Espejo', 'Lo Prado', 'Macul', 'Maipú', 'María Pinto', 'Melipilla', 'Ñuñoa', 'Padre Hurtado', 'Paine', 'Pedro Aguirre Cerda', 'Peñaflor', 'Peñalolén', 'Pirque', 'Providencia', 'Pudahuel', 'Puente Alto', 'Quilicura', 'Quinta Normal', 'Recoleta', 'Renca', 'San Bernardo', 'San Joaquín', 'San José de Maipo', 'San Miguel', 'San Pedro', 'San Ramón', 'Talagante', 'Tiltil', 'Vitacura']
    },
    8: {  # VI - O'Higgins
        'existentes': ['Rancagua', 'Santa Cruz'],
        'nuevas': ['Chépica', 'Chimbarongo', 'Codegua', 'Coinco', 'Coltauco', 'Doñihue', 'Graneros', 'La Estrella', 'Las Cabras', 'Litueche', 'Lolol', 'Machalí', 'Malloa', 'Marchihue', 'Mostazal', 'Nancagua', 'Navidad', 'Olivar', 'Palmilla', 'Paredones', 'Peralillo', 'Peumo', 'Pichidegua', 'Pichilemu', 'Placilla', 'Pumanque', 'Quinta de Tilcoco', 'Rengo', 'Requínoa', 'San Fernando', 'San Vicente']
    },
    9: {  # VII - Maule
        'existentes': [],
        'nuevas': ['Cauquenes', 'Chanco', 'Colbún', 'Constitución', 'Curepto', 'Curicó', 'Empedrado', 'Hualañé', 'Licantén', 'Linares', 'Longaví', 'Maule', 'Molina', 'Parral', 'Pelarco', 'Pelluhue', 'Pencahue', 'Rauco', 'Retiro', 'Río Claro', 'Romeral', 'Sagrada Familia', 'San Clemente', 'San Javier', 'San Rafael', 'Talca', 'Teno', 'Vichuquén', 'Villa Alegre', 'Yerbas Buenas']
    },
    10: {  # XVI - Ñuble
        'existentes': ['Chillán'],
        'nuevas': ['Bulnes', 'Chillán Viejo', 'Cobquecura', 'Coelemu', 'Coihueco', 'El Carmen', 'Ninhue', 'Ñiquén', 'Pemuco', 'Pinto', 'Portezuelo', 'Quillón', 'Quirihue', 'Ránquil', 'San Carlos', 'San Fabián', 'San Ignacio', 'San Nicolás', 'Treguaco', 'Yungay']
    },
    11: {  # VIII - Biobío
        'existentes': ['Concepción', 'Los Ángeles'],
        'nuevas': ['Alto Biobío', 'Antuco', 'Arauco', 'Cabrero', 'Cañete', 'Chiguayante', 'Contulmo', 'Coronel', 'Curanilahue', 'Florida', 'Hualpén', 'Hualqui', 'Laja', 'Lebu', 'Los Álamos', 'Lota', 'Mulchén', 'Nacimiento', 'Negrete', 'Penco', 'Quilaco', 'Quilleco', 'San Pedro de la Paz', 'San Rosendo', 'Santa Bárbara', 'Santa Juana', 'Talcahuano', 'Tirúa', 'Tomé', 'Tucapel', 'Yumbel']
    },
    12: {  # IX - La Araucanía
        'existentes': ['Temuco', 'Angol'],
        'nuevas': ['Carahue', 'Cholchol', 'Collipulli', 'Cunco', 'Curacautín', 'Curarrehue', 'Ercilla', 'Freire', 'Galvarino', 'Gorbea', 'Lautaro', 'Loncoche', 'Lonquimay', 'Los Sauces', 'Lumaco', 'Melipeuco', 'Nueva Imperial', 'Padre Las Casas', 'Perquenco', 'Pitrufquén', 'Pucón', 'Purén', 'Renaico', 'Saavedra', 'Teodoro Schmidt', 'Toltén', 'Traiguén', 'Victoria', 'Vilcún', 'Villarrica']
    },
    13: {  # XIV - Los Ríos
        'existentes': ['Valdivia', 'La Unión', 'Río Bueno', 'Futrono'],
        'nuevas': ['Corral', 'Lago Ranco', 'Lanco', 'Los Lagos', 'Máfil', 'Mariquina', 'Paillaco', 'Panguipulli']
    },
    14: {  # X - Los Lagos
        'existentes': ['Puerto Montt', 'Puerto Varas', 'Osorno', 'Castro', 'Ancud', 'Frutillar', 'Llanquihue', 'Calbuco', 'Puerto Octay', 'Cochamó', 'Hornopirén', 'Purranque', 'Fresia', 'Río Negro', 'Puyehue', 'Maullín'],
        'nuevas': ['Chaitén', 'Chonchi', 'Curaco de Vélez', 'Dalcahue', 'Futaleufú', 'Hualaihué', 'Los Muermos', 'Palena', 'Puqueldón', 'Queilén', 'Quellón', 'Quemchi', 'Quinchao', 'San Juan de la Costa', 'San Pablo']
    },
    15: {  # XI - Aysén
        'existentes': ['Puerto Aysén', 'Coyhaique'],
        'nuevas': ['Aysén', 'Chile Chico', 'Cisnes', 'Cochrane', 'Guaitecas', 'Lago Verde', "O'Higgins", 'Río Ibáñez', 'Tortel']
    },
    16: {  # XII - Magallanes
        'existentes': ['Punta Arenas'],
        'nuevas': ['Antártica', 'Cabo de Hornos', 'Laguna Blanca', 'Natales', 'Porvenir', 'Primavera', 'Río Verde', 'San Gregorio', 'Timaukel', 'Torres del Paine']
    },
}

# Generar fixture completo
fixture = []
pk_counter = 43  # Empezamos después de las 42 existentes

print("Generando fixture de comunas completo...")
print("="*80)

for region_pk, data in COMUNAS_POR_REGION.items():
    nuevas = data['nuevas']
    if nuevas:
        print(f"\nRegión {region_pk}: Agregando {len(nuevas)} comunas nuevas")
        for comuna_nombre in sorted(nuevas):
            fixture.append({
                "model": "ventas.comuna",
                "pk": pk_counter,
                "fields": {
                    "region": region_pk,
                    "nombre": comuna_nombre
                }
            })
            pk_counter += 1

# Guardar fixture
output_path = 'ventas/fixtures/comunas_chile_nuevas.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(fixture, f, indent=2, ensure_ascii=False)

print("\n" + "="*80)
print(f"✅ Fixture generado: {output_path}")
print(f"   • Comunas nuevas agregadas: {len(fixture)}")
print(f"   • Total comunas en BD después de cargar: {42 + len(fixture)}")
print()
print("Para cargar en producción:")
print("   python manage.py loaddata comunas_chile_nuevas")
print("="*80 + "\n")
