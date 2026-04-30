"""Seed del primer post piloto del blog DPV-SEO-002.

Crea (o actualiza) el BlogPost "Qué hacer en Puerto Varas: guía completa con
25+ panoramas". Idempotente — se puede correr varias veces. Se carga como
*draft* (`is_published=False`) para revisión en admin antes de publicar.

Uso:
    python manage.py seed_blog_pilot_que_hacer

El comando NO publica el post automáticamente. Tras correrlo:
1. Ir a admin /admin/destino_puerto_varas/blogpost/
2. Editar el post, revisar contenido, agregar hero_image si se quiere
3. Marcar is_published=True + published_at=ahora
4. Guardar → ya en /blog/que-hacer-en-puerto-varas/
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from destino_puerto_varas.enums import BlogCluster
from destino_puerto_varas.models import BlogPost


SLUG = "que-hacer-en-puerto-varas"
TITLE = "Qué hacer en Puerto Varas: guía completa con 25+ panoramas"
META_DESCRIPTION = (
    "Guía editorial completa de qué hacer en Puerto Varas: naturaleza, "
    "ciudad, gastronomía, cultura y excursiones. 25+ panoramas seleccionados."
)
KEYWORD_ROOT = "qué hacer en puerto varas"
CLUSTER = BlogCluster.GUIDES
INTRO = (
    "Si llegaste acá buscando \"qué hacer en Puerto Varas\" probablemente ya "
    "viste cinco listas idénticas con las mismas seis fotos. Esta es la "
    "número seis, pero al menos te avisamos: vas a llover, vas a comer "
    "demasiado kuchen y vas a tomar más fotos del volcán Osorno de las que "
    "tu nube tiene espacio. Aquí tienes 25+ panoramas curados, itinerarios "
    "que sí caben en un día real y los tips que nadie te dice."
)


BODY_MD = """\
## ¿Por qué Puerto Varas?

Imagínate una ciudad chiquita, ordenada, con casas de madera pintadas en
colores de caja de chocolates, una iglesia neogótica que parece sacada de un
cuento de los hermanos Grimm, y todo eso mirando un lago azul del tamaño de
una región pequeña con un volcán perfecto al fondo. Eso es Puerto Varas.
Sí, parece postal. Es que **es** una postal: los alemanes que llegaron en
1853 venían con buena cámara mental.

A escala humana —se recorre caminando, los acentos se entienden, no hay
metro—, con buena gastronomía y como puerta de entrada a casi todo lo
interesante del sur de Chile. Desde acá llegas en menos de una hora a:

- **Parque Nacional Vicente Pérez Rosales** (Saltos del Petrohué + Volcán
  Osorno; el parque nacional más antiguo del país y todavía no lo arruinan)
- **Frutillar**, el pueblo bávaro con teatro de clase mundial sobre el lago
- **Cochamó**, valle de granito que la prensa internacional bautizó "el
  Yosemite chileno" antes de que algún influencer terminara de arruinarlo
- **Chiloé**, sus iglesias patrimonio UNESCO y un curanto que se cocina bajo
  tierra (sí, debajo, con piedras calientes)

## Cómo llegar y mejor época para visitar

**En avión:** vuelos diarios al aeropuerto **El Tepual** (ZOS) en Puerto
Montt desde Santiago, ~2h. De ahí, 30 minutos en bus, taxi o transfer y ya
estás en Puerto Varas mirando el Osorno como turista nuevo (todos lo
miramos así la primera vez, no te avergüences).

**En bus:** servicios cama desde Santiago, 12-14 horas. Ideal si te gustan
las películas malas con audífonos, las paradas técnicas y reflexionar sobre
tus decisiones.

**En auto:** Ruta 5 Sur, ~1.000 km desde Santiago. Es la mejor opción si
quieres flexibilidad real para Petrohué, Frutillar y Cochamó. La carretera
es tranquila salvo en febrero y feriados largos, donde se transforma en
una larga reflexión sobre la paciencia.

**Mejor época:**

- **Octubre a marzo (primavera-verano):** mejor clima, días largos, lago
  cálido (relativamente; sigue siendo agua de glaciar). Temporada alta:
  reserva con anticipación o duerme en el auto.
- **Abril a junio (otoño):** colores cobrizos, menos turistas, precios más
  bajos, algo más de lluvia. Honestamente la mejor relación calidad/precio.
- **Julio a septiembre (invierno):** ski en el volcán Osorno, planes
  indoor, termas, kuchen y café junto a la chimenea. La lluvia no es un
  bug, es una feature. Si esperas a que pare de llover, te quedas a vivir.

## Qué hacer en Puerto Varas: 25+ panoramas por categoría

### Naturaleza imperdible

#### 1. Saltos del Petrohué
Cataratas turquesa esculpidas por la lava del volcán Osorno, a 60 km de
Puerto Varas. Sí, **turquesa**, como si alguien hubiese puesto colorante
para piscina. No lo hicieron: es el sedimento glaciar y los minerales del
volcán. Senderos cortos, miradores, administra CONAF, entrada pagada. Ver
el [circuito Las Cascadas y el Salto](/circuitos/las-cascadas-y-salto/).

#### 2. Volcán Osorno
Cono nevado de 2.652 m, perfectamente simétrico, conocido cariñosamente como
"el Fuji-Yama del sur" por gente que probablemente nunca ha visto el Fuji.
En invierno, [centro de ski Volcán Osorno](/lugares/centro-ski-volcan-osorno/).
En verano, ascenso al cráter con guía obligatorio (no, no se sube en
zapatillas, no insistas). Los andariveles llegan a 1.420 m con cero
esfuerzo, ideal si tu plan es solo sacar fotos.

#### 3. Lago Todos los Santos
También llamado *lago Esmeralda* por los colonos alemanes que evidentemente
no exageraban. Verde intenso, rodeado de bosque y volcanes. Punto de
partida del **Cruce Andino** lacustre hacia Bariloche, Argentina, una de
las experiencias de viaje más bonitas que se hacen sin tocar tierra.

#### 4. Parque Nacional Vicente Pérez Rosales
El parque nacional más antiguo de Chile (1926) y todavía no lo
echaron a perder. Concentra Petrohué + Osorno + lago Todos los Santos.
Si solo tienes un día para naturaleza, este es el lugar.

#### 5. Mirador Manuel Montt
A pasos del centro, vista panorámica gratis del lago, la ciudad y el
Osorno. Ideal al atardecer (la luz dorada hace ver todo mejor, incluido
ese amigo que insiste en aparecer en todas las fotos). Ver [Mirador Manuel
Montt](/lugares/mirador-manuel-montt/).

### En la ciudad

#### 6. Iglesia Sagrado Corazón de Jesús
Réplica neogótica de una iglesia alemana de la Selva Negra, construida en
1918 con devoción y excelente sentido del marketing visual. Monumento
Nacional. Sí, sale en todas las postales. Por algo será. Ver [Iglesia
Sagrado Corazón](/lugares/iglesia-sagrado-corazon-puerto-varas/).

#### 7. Barrio patrimonial alemán
Casas de tejuela del siglo XIX y XX en colores caramelo, varias declaradas
Monumento Nacional. Recorrido autoguiado de ~1 hora. Plus: descubrirás que
los alemanes pintaron sus casas para distinguirlas a la distancia, no
porque les pareciera bonito. La estética es un efecto secundario. Ver
[Barrio Patrimonial Alemán](/lugares/barrio-patrimonial-aleman-puerto-varas/).

#### 8. Costanera Vicente Pérez Rosales
Caminata frente al lago, esculturas, miradores y cafés. Mejor al amanecer
(rosado pastel) o al atardecer (rosado intenso). Si ves a alguien
corriendo a las 7 AM con cara de iluminado, no es atleta, es alguien que
descubrió la luz del lago a esa hora.

#### 9. Plaza de Armas y Casino Enjoy
Espacio cívico, eventos en temporada y un casino con shows y restaurantes.
Plan B perfecto para los días en que la lluvia decide ser protagonista.

### Excursiones de día

#### 10. Frutillar y el Teatro del Lago
A 28 km, pueblo bávaro con casas pintadas, un teatro de clase mundial
construido literalmente sobre el agua y, en febrero, las **Semanas
Musicales de Frutillar**. Es el plan culto-elegante por excelencia, pero
también puedes ir solo a comer kuchen y mirar el lago, eso también cuenta.

#### 11. Chiloé en un día
Ruta clásica: Ancud → Castro → iglesias patrimoniales. Día largo (10-12 h),
mejor partir muy temprano. Vas a comer curanto. Vas a ver palafitos. Vas a
preguntarte por qué nadie te dijo antes que existían los chilotes y su
sentido del humor. Ver [circuito Imperdibles de
Chiloé](/circuitos/imperdibles-chiloe/) o [Chiloé Central
Patrimonial](/circuitos/chiloe-central-patrimonial/).

#### 12. Cochamó
Valle de granito que comparan con Yosemite. La comparación es válida pero
omiten un detalle: aquí no hay multitudes, no hay app de reservas y no hay
cobertura. Cabalgatas, trekking, escalada en big walls. Ve antes de que
algún ranking en inglés lo arruine. Ver [circuito Cochamó pueblo y
Ralún](/circuitos/cochamo-pueblo-ralun/) y [Valle Cochamó cascada
escondida](/circuitos/valle-cochamo-cascada-escondida/).

#### 13. Termas de Puyehue
A 1h45m. Termales calientes en plena selva valdiviana, dentro del parque
nacional homónimo. Sumergirse en agua a 38°C mientras llueve a cántaros
afuera es una de las pocas experiencias del sur de Chile que justifica el
término "espiritual". Ver [circuito Puyehue Aguas
Calientes](/circuitos/puyehue-aguas-calientes/).

### Aventura y outdoor

#### 14. Trekking en el Parque Vicente Pérez Rosales
Senderos como **Salto La Picada** (corto, fácil, ideal para no-deportistas)
y **El Solitario** (medio, ya con cara de lo estoy intentando). Ver [Salto
La Picada](/lugares/salto-la-picada/).

#### 15. Kayak en el lago Llanquihue
Salidas guiadas desde la playa de Puerto Varas o desde Ensenada. El lago
es enorme y tranquilo cerca de la costa, ideal para principiantes; mar
adentro ya es harina de otro costal y, sin chaleco salvavidas, también es
mala idea.

#### 16. Cicloruta del lago Llanquihue
Tramos asfaltados y otros de ripio. El más popular es Puerto Varas–Frutillar
(~28 km). Pro tip: los 28 km de ida son más fáciles que los 28 de vuelta,
sobre todo si comiste kuchen en el medio.

#### 17. Vuelta al lago Llanquihue en auto
~196 km, día completo, una de las rutas escénicas más bonitas de Chile.
Pasas por Frutillar, Puerto Octay, Las Cascadas, Ensenada. Hacerla sin auto
es una experiencia espiritual que no recomendamos. Ver [circuito Vuelta
este Llanquihue](/circuitos/vuelta-este-llanquihue/) y [Las Cascadas y el
Salto](/circuitos/las-cascadas-y-salto/).

### Gastronomía

#### 18. Cazuela y curanto
La cazuela es plato típico chileno. El curanto chilote (en hoyo) es plato
nivel arqueológico: mariscos, carnes y papas cocinados bajo tierra con
piedras al rojo, tapados con hojas de pangue. Si te lo sirven y no
preguntas qué es, eres oficialmente local.

#### 19. Cervezas artesanales
La Región de Los Lagos tiene escena de cerveza craft fuerte. Varias
cervecerías abren sus salas. Si te gusta la cerveza, prepárate a tomar
notas. Si no te gusta la cerveza, prepárate a que te conviertan.

#### 20. Kuchen y pastelería alemana
Herencia colonial. *Kuchen de frambuesa, manjar, nuez, murta, ruibarbo*.
Hay quienes vienen a Puerto Varas oficialmente por la naturaleza pero
extraoficialmente por el kuchen. Ambos motivos son válidos.

### Cultura y patrimonio

#### 21. Teatro del Lago, Frutillar
Sala de conciertos sobre el lago, con programación todo el año (clásica,
jazz, ballet, ópera). Sí, ópera. En medio del campo. En el sur de Chile.
Y el sonido es excelente. Acéptalo.

#### 22. Museo Antonio Felmer (Nueva Braunau)
Colección etnográfica de la colonización alemana, a 30 minutos. Don Antonio
fue acumulando cosas durante décadas y armó esto él solito. Es el museo
hecho con más cariño que conocerás este año.

#### 23. Lahuén Ñadi: bosque alerce milenario
Monumento Natural. Pasarelas elevadas para no dañar el bosque (los alerces
de 3.000 años no necesitan que alguien los pise). Ver [circuito Lahuén
Ñadi](/circuitos/lahuen-nadi/).

### Relax y bienestar

#### 24. Termas urbanas con tina caliente
Varios alojamientos boutique en Puerto Varas y Ensenada ofrecen tinas
calientes a leña con vista al lago o al río. Es la versión "tengo solo
una tarde" de las termas naturales. Y honestamente, no le pierde mucho.

#### 25. Spa con vista al lago
Hoteles con spa frente al Llanquihue. Plan estrella para días lluviosos
(o sea, gran parte del año). Combinación ganadora: piscina temperada +
ventanal + vista al volcán + lluvia afuera.

#### 26. Picnic en la costanera
Plan simple, barato y subestimado: compras kuchen y café local, te sientas
frente al lago, miras el Osorno. Cero costo de entrada, cero filas, cero
horario. La gente paga miles de pesos por experiencias peores.

## Itinerarios sugeridos

- **Si tienes 1 día:** Saltos del Petrohué + barrio patrimonial + atardecer
  en costanera. Ambicioso pero factible. Sale del corredor turístico y vas
  a comer rápido.
- **Si tienes 2 días:** Día 1 ciudad + Frutillar; Día 2 Petrohué + Volcán
  Osorno. Dormir bien antes de Petrohué, manejas tú.
- **Si tienes 3 días:** *(recomendado)* Día 1 ciudad + costanera + Mirador
  Manuel Montt para aclimatar; Día 2 PN Vicente Pérez Rosales (Petrohué +
  Osorno + Lago Todos los Santos), día estrella; Día 3 Frutillar (modo
  cultural) o Chiloé (modo aventura).
- **Si tienes 4+ días:** Suma Cochamó (1-2 días, idealmente con guía) o
  Chiloé en profundidad. Si tienes 7 días, ya estás en territorio sabbatical.

## Tips prácticos

- **El clima es un troll:** lleva siempre cortavientos impermeable y zapatos
  cómodos, **incluso en verano**. Especialmente en verano. La regla local:
  si no te gusta el clima, espera 20 minutos.
- **Auto:** facilita mucho. Ensenada, Petrohué y Cochamó tienen poca
  conectividad de transporte público. Sin auto, te vas a frustrar.
- **Reservas:** en temporada alta (diciembre-marzo, fines de semana
  largos), reserva alojamiento y restaurantes con anticipación. La gente
  duerme en el auto cuando no lo hace, no es leyenda urbana.
- **Presupuesto:** Puerto Varas tiene desde hostales económicos hasta
  hoteles boutique de envidia. Gastronomía buena pero no barata: agenda
  presupuesto extra para los kuchen no programados.
- **Conectividad:** wifi y señal móvil buenos en la ciudad; pueden fallar
  en Cochamó, lago Todos los Santos y partes del Parque Vicente Pérez
  Rosales. Acéptalo como detox digital o llora un rato, tú decides.

## Preguntas frecuentes

**¿Cuántos días son suficientes para Puerto Varas?**
Tres días es el sweet spot honesto: alcanzas el corazón del destino
(ciudad + Petrohué + Osorno) más una excursión a Frutillar o Chiloé. Con 5
días incluyes Cochamó. Con 7 ya empiezas a tener favoritos entre los kuchen.

**¿Es caro Puerto Varas?**
Es uno de los destinos más cotizados del sur de Chile, pero hay opciones
para todos los presupuestos. La temporada baja (mayo-octubre, salvo
vacaciones de invierno) tiene precios significativamente más bajos. Pro
tip: viajar en otoño o primavera te ahorra hasta 40% y el paisaje sigue
siendo el mismo. Los precios se mueven; los volcanes no.

**¿Qué hacer en Puerto Varas con lluvia?**
Mucho más de lo que parece. Teatro del Lago en Frutillar, museos de la
colonización, cafés y pastelerías (vamos, era obvio que íbamos a recomendar
kuchen otra vez), spas con tina o piscina temperada, el casino, compras de
artesanía, terapia de mirar el lago desde un sillón. La lluvia es parte
del personaje del lugar; resistirla es perder tiempo.

**¿Conviene tener auto?**
Sí. Las atracciones más espectaculares (Petrohué, Osorno, Cochamó, vuelta
al lago) se aprovechan mucho mejor con vehículo propio o arrendado. Sin
auto puedes tener un buen viaje urbano, pero te perderás el 70% del lugar.

**¿Puerto Varas o Pucón?**
Pregunta clásica. Pucón es más volcán-céntrico, más fiestero, más
intensamente turístico. Puerto Varas tiene lago, dos volcanes, patrimonio
alemán, gastronomía elaborada y sirve de base para Chiloé y la Patagonia
norte. Ambos son excelentes; Puerto Varas suele ser preferido por
viajeros que valoran arquitectura, gastronomía y un ritmo un poco más
calmado. Pucón es preferido por viajeros que duermen poco.

**¿Es seguro?**
Sí. La región tiene índices de seguridad altos comparado con grandes
ciudades chilenas. Las precauciones básicas de cualquier destino turístico
aplican (no dejes nada visible en el auto, etc.), pero en general es un
lugar tranquilo, donde el mayor peligro es comer demasiado kuchen.
"""


FAQ_SCHEMA_JSON = """\
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "¿Cuántos días son suficientes para Puerto Varas?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Tres días es el sweet spot: alcanzas el corazón del destino (ciudad + Petrohué + Osorno) más una excursión a Frutillar o Chiloé. Con 5 días puedes incluir Cochamó."
      }
    },
    {
      "@type": "Question",
      "name": "¿Es caro Puerto Varas?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Es uno de los destinos más cotizados del sur de Chile, pero hay opciones para distintos presupuestos. La temporada baja (mayo-octubre, salvo vacaciones de invierno) tiene precios significativamente más bajos."
      }
    },
    {
      "@type": "Question",
      "name": "¿Qué hacer en Puerto Varas con lluvia?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Teatro del Lago en Frutillar, museos de la colonización, cafés y pastelerías, spas con tina o piscina temperada, el casino, y compras de artesanía local."
      }
    },
    {
      "@type": "Question",
      "name": "¿Conviene tener auto?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Sí. Las atracciones más espectaculares (Petrohué, Osorno, Cochamó, vuelta al lago) se aprovechan mucho mejor con vehículo propio o arrendado."
      }
    },
    {
      "@type": "Question",
      "name": "¿Puerto Varas o Pucón?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Pucón es más volcán-céntrico y más turístico. Puerto Varas tiene lago, dos volcanes accesibles, patrimonio alemán y sirve de base para Chiloé y la Patagonia. Ambos son excelentes; Puerto Varas suele ser preferido por viajeros que valoran arquitectura colonial y gastronomía."
      }
    },
    {
      "@type": "Question",
      "name": "¿Es seguro Puerto Varas?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Sí. La región tiene índices de seguridad altos comparado con grandes ciudades chilenas. Se recomienda tomar precauciones básicas como en cualquier destino turístico."
      }
    }
  ]
}"""


class Command(BaseCommand):
    help = (
        "Seed del primer post piloto del blog DPV (DPV-SEO-002). "
        "Crea/actualiza el post 'Qué hacer en Puerto Varas' como draft."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Si se pasa, marca el post como published con published_at=ahora.",
        )

    def handle(self, *args, **opts):
        publish = opts["publish"]

        defaults = {
            "title": TITLE,
            "meta_description": META_DESCRIPTION,
            "keyword_root": KEYWORD_ROOT,
            "cluster": CLUSTER,
            "intro": INTRO,
            "body_md": BODY_MD,
            "faq_schema_json": FAQ_SCHEMA_JSON,
        }

        if publish:
            defaults["is_published"] = True
            defaults["published_at"] = timezone.now()

        post, created = BlogPost.objects.update_or_create(
            slug=SLUG,
            defaults=defaults,
        )

        action = "Creado" if created else "Actualizado"
        status = "PUBLISHED" if post.is_published else "DRAFT"
        self.stdout.write(self.style.SUCCESS(
            f"{action}: BlogPost id={post.pk} slug={post.slug} [{status}]"
        ))
        self.stdout.write(
            f"  Title: {post.title}"
        )
        self.stdout.write(
            f"  Cluster: {post.cluster}  Keyword: {post.keyword_root}"
        )
        self.stdout.write(
            f"  Body length: {len(post.body_md)} chars"
        )
        self.stdout.write("")
        self.stdout.write("Próximo paso:")
        if post.is_published:
            self.stdout.write(
                f"  → Verificar en https://destinopuertovaras.cl/blog/{post.slug}/"
            )
        else:
            self.stdout.write(
                f"  → Revisar en /admin/destino_puerto_varas/blogpost/{post.pk}/change/"
            )
            self.stdout.write(
                "  → Marcar is_published=True + published_at=ahora cuando esté ok"
            )
