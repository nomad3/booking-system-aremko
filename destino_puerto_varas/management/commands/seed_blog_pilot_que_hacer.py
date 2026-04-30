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
    "Puerto Varas es la base perfecta para descubrir el sur de Chile: lago "
    "Llanquihue al frente, volcán Osorno al horizonte y dos parques nacionales "
    "a menos de una hora. Esta guía reúne más de 25 panoramas seleccionados "
    "por tipo, con itinerarios sugeridos y tips prácticos para que armes el "
    "viaje a tu medida."
)


BODY_MD = """\
## ¿Por qué Puerto Varas?

Fundada por colonos alemanes a mediados del siglo XIX, Puerto Varas conserva
casas patrimoniales de tejuela, una iglesia neogótica icónica y una costanera
con vista directa al volcán Osorno reflejándose en el lago Llanquihue. A
escala humana —se recorre caminando— y con buena oferta gastronómica, es la
puerta de entrada natural a la **Región de Los Lagos** y a la Patagonia
norte.

Desde aquí se acceden en menos de una hora a:

- **Parque Nacional Vicente Pérez Rosales** (Saltos del Petrohué + Volcán Osorno)
- **Frutillar**, con su Teatro del Lago sobre el agua
- **Cochamó**, valle granítico considerado *el Yosemite chileno*
- **Chiloé**, con sus iglesias patrimonio UNESCO

## Cómo llegar y mejor época para visitar

**En avión:** vuelos diarios al aeropuerto **El Tepual** (ZOS) en Puerto Montt
desde Santiago (~2h). De ahí 30 minutos en bus, taxi o transfer hasta Puerto
Varas.

**En bus:** servicios cama desde Santiago (~12-14 horas) con varias salidas
por día.

**En auto:** Ruta 5 Sur, ~1.000 km desde Santiago. Es la opción ideal si
quieres flexibilidad para Petrohué, Frutillar y Cochamó.

**Mejor época:**

- **Octubre a marzo (primavera-verano):** mejor clima, más horas de luz, lago
  cálido. Es temporada alta —reserva con anticipación.
- **Abril a junio (otoño):** colores cobrizos, menos turistas, precios más
  bajos. Algo de lluvia.
- **Julio a septiembre (invierno):** ski en el volcán Osorno, planes indoor,
  termas. La lluvia es parte del viaje.

## Qué hacer en Puerto Varas: 25+ panoramas por categoría

### Naturaleza imperdible

#### 1. Saltos del Petrohué
Cataratas turquesa esculpidas por la lava del volcán Osorno, a 60 km de
Puerto Varas. Senderos cortos con miradores. Administra CONAF, entrada
pagada. Ver el [circuito Las Cascadas y el Salto](/circuitos/las-cascadas-y-salto/).

#### 2. Volcán Osorno
Cono perfecto, 2.652 m. En invierno, [centro de ski Volcán
Osorno](/lugares/centro-ski-volcan-osorno/); en verano, ascenso al cráter con
guía. Andariveles llegan a 1.420 m sin esfuerzo.

#### 3. Lago Todos los Santos
Color esmeralda intenso, rodeado de bosque y volcanes. Punto de partida del
cruce lacustre **Cruce Andino** hacia Bariloche, Argentina.

#### 4. Parque Nacional Vicente Pérez Rosales
El parque nacional más antiguo de Chile (1926). Senderos, miradores y
acceso al volcán Osorno y los Saltos del Petrohué.

#### 5. Mirador Manuel Montt
A pasos del centro, vista panorámica del lago, la ciudad y el Osorno. Ideal
al atardecer. Ver [Mirador Manuel
Montt](/lugares/mirador-manuel-montt/).

### En la ciudad

#### 6. Iglesia Sagrado Corazón de Jesús
Réplica neogótica de una iglesia de la Selva Negra. Monumento Nacional. Ver
[Iglesia Sagrado Corazón](/lugares/iglesia-sagrado-corazon-puerto-varas/).

#### 7. Barrio patrimonial alemán
Casas de tejuela del siglo XIX y XX, varias declaradas Monumento Nacional.
Recorrido autoguiado de ~1 hora. Ver [Barrio Patrimonial
Alemán](/lugares/barrio-patrimonial-aleman-puerto-varas/).

#### 8. Costanera Vicente Pérez Rosales
Caminata frente al lago, esculturas, miradores y cafés. Mejor al amanecer o
atardecer.

#### 9. Plaza de Armas y Casino Enjoy
Espacio cívico con eventos en temporada. El casino tiene shows y gastronomía.

### Excursiones de día

#### 10. Frutillar y el Teatro del Lago
A 28 km. Pueblo bávaro con casas patinadas y un teatro de clase mundial sobre
el agua. En febrero, **Semanas Musicales de Frutillar**.

#### 11. Chiloé en un día
Ruta clásica: Ancud → Castro → iglesias patrimoniales. Día largo (10-12 h),
mejor partir temprano. Ver [circuito Imperdibles de
Chiloé](/circuitos/imperdibles-chiloe/) o [Chiloé Central
Patrimonial](/circuitos/chiloe-central-patrimonial/).

#### 12. Cochamó
Valle de granito comparado con Yosemite. Cabalgatas, trekking y escalada en
big walls. Ver [circuito Cochamó pueblo y
Ralún](/circuitos/cochamo-pueblo-ralun/) y [Valle Cochamó cascada
escondida](/circuitos/valle-cochamo-cascada-escondida/).

#### 13. Termas de Puyehue
A 1h45m. Termales calientes en plena selva valdiviana, parque nacional
adyacente. Ver [circuito Puyehue Aguas
Calientes](/circuitos/puyehue-aguas-calientes/).

### Aventura y outdoor

#### 14. Trekking en el Parque Vicente Pérez Rosales
Senderos como **Salto La Picada** (corto, fácil) y **El Solitario** (medio).
Ver [Salto La Picada](/lugares/salto-la-picada/).

#### 15. Kayak en el lago Llanquihue
Salidas guiadas desde la playa de Puerto Varas o desde Ensenada (calmo,
buen agua para principiantes).

#### 16. Cicloruta del lago Llanquihue
Hay tramos asfaltados y otros de ripio. Tramo Puerto Varas–Frutillar (~28 km)
es el más recorrido.

#### 17. Vuelta al lago Llanquihue en auto
~196 km, día completo. Ver [circuito Vuelta este
Llanquihue](/circuitos/vuelta-este-llanquihue/) y [Las Cascadas y el
Salto](/circuitos/las-cascadas-y-salto/).

### Gastronomía

#### 18. Cazuela y curanto
Platos típicos del sur de Chile. El curanto en hoyo es plato chilote por
excelencia (mariscos, carnes y papas cocidos bajo tierra).

#### 19. Cervezas artesanales
La Región de Los Lagos tiene una fuerte escena de cerveza craft. Varias
cervecerías abren sus salas.

#### 20. Kuchen y pastelería alemana
Herencia colonial. *Kuchen de frambuesa, manjar y nuez* son clásicos.

### Cultura y patrimonio

#### 21. Teatro del Lago, Frutillar
Sala de conciertos sobre el lago, con programación todo el año (clásica,
jazz, ballet, ópera).

#### 22. Museo Antonio Felmer (Nueva Braunau)
Colección etnográfica de la colonización alemana, a 30 minutos.

#### 23. Lahuén Ñadi: bosque alerce milenario
Monumento Natural. Pasarelas elevadas para no dañar el bosque. Ver [circuito
Lahuén Ñadi](/circuitos/lahuen-nadi/).

### Relax y bienestar

#### 24. Termas urbanas con tina caliente
Varios alojamientos boutique en Puerto Varas y Ensenada ofrecen tinas
calientes a leña con vista al lago o al río. Buena alternativa a las termas
naturales si vas con poco tiempo.

#### 25. Spa con vista al lago
Hoteles con spa frente al Llanquihue. Ideal para días lluviosos.

#### 26. Picnic en la costanera
Plan simple y barato: comprar kuchen y café local, sentarse frente al lago.

## Itinerarios sugeridos

- **Si tienes 1 día:** Saltos del Petrohué + barrio patrimonial + atardecer
  en costanera.
- **Si tienes 2 días:** Día 1 ciudad + Frutillar; Día 2 Petrohué + Volcán
  Osorno.
- **Si tienes 3 días:** *(recomendado)* Día 1 ciudad + costanera + Mirador
  Manuel Montt; Día 2 PN Vicente Pérez Rosales (Petrohué + Osorno + Lago
  Todos los Santos); Día 3 Frutillar o Chiloé.
- **Si tienes 4+ días:** Suma Cochamó (1-2 días) o Chiloé en profundidad.

## Tips prácticos

- **Clima impredecible:** lleva siempre cortavientos impermeable y zapatos
  cómodos, incluso en verano.
- **Auto:** facilita mucho. Ensenada, Petrohué y Cochamó tienen poca
  conectividad de transporte público.
- **Reservas:** en temporada alta (diciembre-marzo, fines de semana largos),
  reserva alojamiento y restaurantes con anticipación.
- **Presupuesto:** Puerto Varas tiene desde hostales hasta hoteles boutique.
  La gastronomía es buena pero no barata.
- **Conectividad:** wifi y señal móvil son buenos en la ciudad; pueden
  fallar en Cochamó, lago Todos los Santos y partes del Parque Vicente Pérez
  Rosales.

## Preguntas frecuentes

**¿Cuántos días son suficientes para Puerto Varas?**
Tres días es el sweet spot: alcanzas el corazón del destino (ciudad +
Petrohué + Osorno) más una excursión a Frutillar o Chiloé. Con 5 días puedes
incluir Cochamó.

**¿Es caro Puerto Varas?**
Es uno de los destinos más cotizados del sur de Chile, pero hay opciones
para distintos presupuestos. La temporada baja (mayo-octubre, salvo
vacaciones de invierno) tiene precios significativamente más bajos.

**¿Qué hacer en Puerto Varas con lluvia?**
Teatro del Lago en Frutillar, museos de la colonización, cafés y
pastelerías, spas con tina o piscina temperada, el casino, y compras de
artesanía local.

**¿Conviene tener auto?**
Sí. Las atracciones más espectaculares (Petrohué, Osorno, Cochamó, vuelta al
lago) se aprovechan mucho mejor con vehículo propio o arrendado.

**¿Puerto Varas o Pucón?**
Pucón es más volcán-céntrico y más turístico. Puerto Varas tiene lago, dos
volcanes accesibles, patrimonio alemán y sirve de base para Chiloé y la
Patagonia. Ambos son excelentes; Puerto Varas suele ser preferido por
viajeros que valoran arquitectura colonial y gastronomía.

**¿Es seguro?**
Sí. La región tiene índices de seguridad altos comparado con grandes
ciudades chilenas. Tomar precauciones básicas en cualquier destino
turístico.
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
