"""Seed del Post #1 del blog Aremko: "Tinas calientes en Puerto Varas".

Patrón paralelo al seed DPV `seed_blog_pilot_que_hacer.py`:
- Idempotente (update_or_create por slug)
- Por defecto crea como borrador (is_published=False)
- Flag --publish opcional para publicar al instante con published_at=now()

Voz: anfitrión / dueño en primera persona. Humor + voz personal en
primeras 50 palabras (decisión #7 DPV-SEO-002, aplica también a Aremko).

Uso:
    python manage.py seed_blog_post_tinas_aremko          # borrador
    python manage.py seed_blog_post_tinas_aremko --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "tinas-calientes-puerto-varas"
TITLE = "Tinas calientes en Puerto Varas: la guía que tu lumbar ya estaba pidiendo"
KEYWORD_ROOT = "tinas calientes puerto varas"
META_DESCRIPTION = (
    "Guía práctica de tinas calientes en Puerto Varas: temperatura, tiempo, "
    "ritual y por qué la tinaja chilena le saca tres cuerpos al jacuzzi de hotel."
)
CLUSTER = BlogCluster.TINAS
CTA_TEXT = "Reserva tu cabaña con tina caliente"
CTA_URL = "/tinas/"

INTRO = (
    "Si llegaste acá buscando \"tinas calientes en Puerto Varas\" es porque hace "
    "tiempo tu cuerpo decidió que las sillas de oficina son enemigas. Tranquilo, "
    "esta no es la guía donde te explican que el agua caliente relaja (sí, "
    "también descubriste el fuego, felicitaciones): es la guía donde el dueño "
    "del spa te cuenta qué pedir, cuánto rato, a qué temperatura y por qué la "
    "tinaja chilena le saca tres cuerpos al jacuzzi de hotel."
)

BODY_MD = """\
## Qué es una tina caliente (y por qué no es lo que crees)

Spoiler: una tina caliente **no es un jacuzzi**. No tiene chorros que te masajean
con la sutileza de un lavarropas en centrifugado, no tiene panel digital con LED
azules, y no se calienta con un calefactor eléctrico que sube tu cuenta de la luz
mientras intenta llegar a 38°C.

Una tina caliente, en su versión sur de Chile, es una **tinaja de madera** —
generalmente alerce, raulí o ciprés— calentada con **fuego de leña**. Sí: leña
de verdad, la que cruje y huele. El fuego va abajo, el agua arriba, la madera
hace de aislante térmico, y tú adentro pensando por qué nadie te avisó antes
que esto existía.

> El término "hot tub" es la versión gringa, "jacuzzi" es la marca registrada
> que se nos quedó como sinónimo (igual que kleenex y confort), y "tinaja"
> es como le dicen los chilenos. Los tres pueden ser lo mismo o tres cosas
> distintas según quién te la venda. Hablaremos de las diferencias más abajo.

## La tinaja chilena: madera, leña y un fuego que va lento

La tinaja se demora. Eso ya descarta a cualquier persona que confunda relajación
con eficiencia. Desde que se prende el fuego hasta que está lista, pasan entre
**90 minutos y 2 horas**. Tiempo suficiente para que mires el [volcán Osorno](https://www.aremko.cl/),
te tomes algo, escuches el río Pescado al fondo, y te preguntes por qué decidiste
vivir en Santiago.

La leña le da algo que el agua eléctrica no tiene: **olor**. La cabaña, la
toalla y eventualmente tu pelo van a oler levemente a fogata. No es un bug,
es una feature. Los gringos pagarían 200 dólares extra en un retiro wellness
por esta exacta vibra; tú la tienes incluida.

## ¿A qué temperatura? La regla del 38-40, no del "hierve"

La temperatura ideal de una tinaja está entre **38°C y 40°C**. Punto.

- **Bajo 36°C** → tibio. No relaja, frustra.
- **38°C** → sweet spot. Te puedes quedar 25-40 minutos sin problema.
- **40°C** → ya empieza a ser intenso. 15-20 minutos máximo, sales rojo.
- **Sobre 41°C** → no es tina, es sopa. No lo hagas.

Antes de meterte, **pon la mano**. Si retiras la mano en menos de 3 segundos,
todavía no es tu turno. Esto suena obvio hasta que ves a alguien quemarse el
empeine porque "creí que estaba bien".

## ¿Cuánto rato? La trampa del "me quedo dos horas"

Acá viene el error clásico. La gente se mete pensando que mientras más rato,
más relajación. **Falso.** Tu cuerpo se calienta de adentro hacia afuera, y
después de cierto rato la cosa se invierte: empiezas a sentir el corazón en
las orejas, te transpira la frente y se te va la presión.

Regla práctica:

- **Sesión 1**: 15-20 minutos en la tinaja → 5 minutos afuera (al frío, sí, al
  frío, ese es el truco) → vuelves.
- **Sesión 2**: otros 15-20 minutos → afuera otra vez.
- **Sesión 3 (opcional)**: 10 minutos finales si todavía aguantas.

El ciclo caliente-frío-caliente es lo que de verdad descontractura. Quedarte
una hora seguida adentro es turismo de bañera, no terapia.

## ¿Solo o con compañía? Honestidad ante todo

La tinaja es de **2 a 4 personas** en su formato cabaña-romántica. Más de eso
y deja de ser tina, es piscina con público.

- **Solo**: contemplativo, leyendo, escuchando el río. Subestimado.
- **En pareja**: el clásico. Funciona si los dos entienden que la conversación
  sobre el trabajo se queda al otro lado de la puerta.
- **Con amigos**: bien, pero baja un poco la temperatura (37°C) porque van a
  estar más rato charlando que metidos al agua.
- **Con niños**: solo si hay supervisión adulta cercana, temperatura máxima
  37°C, y sesiones cortas. La tinaja **no es jacuzzi de hotel**: el agua sube
  más arriba, el calor es más persistente, y los niños deshidratan más rápido.

## El error más común: entrar congelado a 40°C

Si vienes de afuera con frío y te metes directo a 40°C, vas a sentir como si
el agua te estuviera quemando aunque esté en el rango correcto. **No está
quemando**: tu piel está reaccionando al shock térmico.

Solución: enjuágate los pies, las muñecas y la nuca con agua tibia primero.
30 segundos. Después entra. La diferencia es absurda.

Otro error de novato: **meterse después de un asado pesado**. La sangre está
trabajando en la digestión, le sumas calor, y mareo asegurado. Espera 1 hora
después de comer. Antes del asado o entre comidas funciona perfecto.

## Tina vs jacuzzi vs hot tub: por qué te están vendiendo lo mismo con tres nombres

Esto da para un post completo (lo escribiremos pronto), pero la versión corta:

| | Tinaja chilena | Jacuzzi (hotel) | Hot tub |
|---|---|---|---|
| Calefacción | Leña | Eléctrica | Eléctrica/gas |
| Material | Madera | Acrílico | Acrílico/madera |
| Chorros | No | Sí | Sí |
| Ambiente | Outdoor con vista | Indoor o terraza | Outdoor |
| Calienta en | 90-120 min | 30-60 min | 30-60 min |
| Vibra | Ritual | Spa de hotel | Spa portátil |

Los tres son válidos. Pero si vienes a Puerto Varas y eliges "jacuzzi de hotel",
estás pagando por algo que existe igual en Santiago. La tinaja es **la versión
del sur**: lenta, con leña, con olor, con el río de fondo.

## La excusa de Puerto Varas

Puerto Varas tiene un combo difícil de igualar: **frío suficiente** para que
la tina caliente tenga sentido emocional (no es lo mismo en febrero a 28°C),
**vista al volcán Osorno**, **río Pescado al lado**, y **kuchen alemán** a 5
minutos en auto. Es ridículo no usar esa combinación.

Si vas a hacerlo bien:

1. **Llega en la tarde**, no muy temprano — la magia de la tina está al
   atardecer, cuando empieza a oscurecer y el fuego se ve.
2. **Pide [masaje descontracturante](https://www.aremko.cl/masajes/) antes** —
   las primeras dos horas son el masaje, después la tina cierra el sello.
3. **Cena tarde** — vas a salir de la tina con hambre y sed. Calzona con
   reservar restaurante a las 21:00, no a las 19:30.
4. **Reserva domingo a jueves** si puedes — más tranquilo, suele haber tarifas
   mejores, y no compartes el sector con un grupo de despedida de soltera.

## Preguntas frecuentes

### ¿Cuánto cuesta una tina caliente en Puerto Varas?

Como servicio independiente (sin alojamiento) anda entre $25.000 y $50.000 por
sesión para 2 personas, dependiendo del lugar. Como combo con cabaña, viene
incluida en la mayoría de los alojamientos boutique con tinaja. En Aremko las
[cabañas con tina](https://www.aremko.cl/alojamientos/) la tienen incluida en
la tarifa nocturna.

### ¿Tengo que reservar con anticipación?

Sí. La tinaja necesita **90-120 minutos para calentar**, así que no es algo
que se prende cuando llegas. Reserva al menos 24 horas antes con horario
específico — el operador necesita saber a qué hora encender la leña.

### ¿Se puede usar en invierno con lluvia?

Es **mejor** en invierno con lluvia. Suena contraintuitivo, pero el contraste
entre agua caliente / aire frío / lluvia cayendo es el momento peak de la
experiencia. La mayoría de las tinajas tienen techo parcial o quincho cerca
para resguardarse al salir.

### ¿Es como un jacuzzi normal?

No. Ver la tabla más arriba. Resumen: la tinaja chilena calienta con leña, no
tiene chorros, y la sesión es 3-4 veces más larga (incluyendo calentamiento).
Es una experiencia, no un servicio express.

### ¿Necesito traje de baño?

Sí, recomendado. Aunque la tinaja sea privada, traer traje de baño te permite
salir al aire, caminar a la cabaña, volver a entrar — sin esa coreografía
incómoda de la toalla.

### ¿Puedo tomar alcohol en la tina?

**Una copa, no más.** El calor potencia el alcohol y deshidrata. Una copa de
vino o un espumante funciona. La cerveza fría afuera, entre sesiones, es
glorioso. La botella entera adentro, mala idea — terminas con dolor de cabeza
de tres días.

### ¿La tinaja viene con masaje?

No automáticamente, pero el combo masaje + tina es el clásico. En Aremko se
puede [reservar el combo](https://www.aremko.cl/masajes/): masaje primero
(45-60 min), tinaja después. El orden importa: la tinaja como cierre cuando
el cuerpo ya está suelto.
"""

# JSON-LD FAQPage para schema.org
FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta una tina caliente en Puerto Varas?",
        "answer": (
            "Como servicio independiente (sin alojamiento) anda entre $25.000 y "
            "$50.000 por sesión para 2 personas. Como combo con cabaña, viene "
            "incluida en la mayoría de los alojamientos boutique con tinaja."
        ),
    },
    {
        "question": "¿Tengo que reservar con anticipación?",
        "answer": (
            "Sí. La tinaja necesita 90-120 minutos para calentar, así que no es "
            "algo que se prende cuando llegas. Reserva al menos 24 horas antes "
            "con horario específico."
        ),
    },
    {
        "question": "¿Se puede usar en invierno con lluvia?",
        "answer": (
            "Es mejor en invierno con lluvia. El contraste entre agua caliente, "
            "aire frío y lluvia cayendo es el momento peak de la experiencia."
        ),
    },
    {
        "question": "¿Es como un jacuzzi normal?",
        "answer": (
            "No. La tinaja chilena calienta con leña, no tiene chorros, y la "
            "sesión es 3-4 veces más larga (incluyendo calentamiento). Es una "
            "experiencia, no un servicio express."
        ),
    },
    {
        "question": "¿Necesito traje de baño?",
        "answer": (
            "Sí, recomendado. Aunque la tinaja sea privada, el traje de baño "
            "te permite salir al aire, caminar a la cabaña y volver a entrar."
        ),
    },
    {
        "question": "¿Puedo tomar alcohol en la tina?",
        "answer": (
            "Una copa, no más. El calor potencia el alcohol y deshidrata. Una "
            "copa de vino o espumante funciona; la cerveza fría afuera entre "
            "sesiones, glorioso. La botella entera adentro, mala idea."
        ),
    },
    {
        "question": "¿La tinaja viene con masaje?",
        "answer": (
            "No automáticamente, pero el combo masaje + tina es clásico. El "
            "orden importa: la tinaja como cierre cuando el cuerpo ya está "
            "suelto por el masaje."
        ),
    },
]


def build_faq_schema_json() -> str:
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item["answer"],
                    },
                }
                for item in FAQ_ITEMS
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


class Command(BaseCommand):
    help = (
        "Seed del Post #1 Aremko 'Tinas calientes en Puerto Varas'. "
        "Idempotente: update_or_create por slug. Por defecto crea borrador; "
        "usa --publish para publicar al instante."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Si está, marca is_published=True y published_at=now().",
        )

    def handle(self, *args, **options):
        publish = options.get("publish", False)

        defaults = {
            "title": TITLE,
            "meta_description": META_DESCRIPTION,
            "keyword_root": KEYWORD_ROOT,
            "cluster": CLUSTER,
            "intro": INTRO,
            "body_md": BODY_MD,
            "cta_text": CTA_TEXT,
            "cta_url": CTA_URL,
            "faq_schema_json": build_faq_schema_json(),
        }

        if publish:
            defaults["is_published"] = True
            defaults["published_at"] = timezone.now()

        post, created = BlogPost.objects.update_or_create(
            slug=SLUG,
            defaults=defaults,
        )

        action = "Creado" if created else "Actualizado"
        status = (
            "PUBLICADO" if post.is_published and post.published_at else "borrador"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}: BlogPost '{post.title}' [{status}] "
                f"→ /blog/{post.slug}/"
            )
        )
