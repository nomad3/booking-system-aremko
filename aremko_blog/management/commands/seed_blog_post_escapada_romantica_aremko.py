"""Seed del Post #4 del blog Aremko: "Escapada romántica al sur de Chile".

Patrón paralelo a seeds anteriores (tinas, masajes). Idempotente:
update_or_create por slug. Por defecto borrador. Flag --publish para
publicar al instante.

Voz: anfitrión chileno + humor (top-funnel + comparación). Calibrado
con la skill /blog-aremko v2: humor distribuido, asides en paréntesis
en H3 técnicas, 2 FAQ con humor liviano.

Target SEO:
- Keyword P0: "escapada romántica sur de chile"
- Cluster: ROMANCE
- Buyer persona principal: pareja en burnout (70%+ del público)

Uso:
    python manage.py seed_blog_post_escapada_romantica_aremko          # borrador
    python manage.py seed_blog_post_escapada_romantica_aremko --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "escapada-romantica-sur-de-chile"
TITLE = "Escapada romántica al sur de Chile: dos días aquí valen una semana de vacaciones"
KEYWORD_ROOT = "escapada romántica sur de chile"
META_DESCRIPTION = (
    "Escapada romántica al sur de Chile en Aremko Spa: pack cabaña + "
    "tina caliente + masaje desde $190.000, junto al río Pescado. "
    "20 min de Puerto Varas."
)
CLUSTER = BlogCluster.ROMANCE
CTA_TEXT = "Reserva tu escapada romántica en Aremko"
CTA_URL = "/alojamientos/"

INTRO = (
    "Una escapada romántica al sur de Chile no es un viaje: es un reset "
    "que tu cabeza venía pidiendo desde hace tres meses. La frase **\"dos "
    "días aquí valen una semana de vacaciones\"** la repetimos porque es "
    "real — vemos parejas que llegan el viernes hablando de Excel y se "
    "van el domingo recordando cómo se llamaba el personaje de la serie "
    "que dejaron a la mitad. Esto es la guía honesta del dueño: qué "
    "incluye una escapada en Aremko, cómo armar 24 o 48 horas que "
    "funcionen, y por qué el río Pescado afuera de tu ventana hace más "
    "trabajo que cualquier playlist de Spotify."
)

BODY_MD = """\
## Por qué el sur de Chile (y no el norte, ni Santiago "a dos horas")

Te ahorro la lista turística que ya googleaste. El sur de Chile gana
para una escapada romántica por **una razón fisiológica concreta**: la
combinación de bosque, agua y temperatura te baja el cortisol antes de
que decidas relajarte. Es como si el cuerpo entendiera el mapa antes que
la cabeza.

El norte tiene desierto y hoteles que cobran sol como si fuera valor
agregado. Santiago a "dos horas" es una mentira optimista (las dos horas
son cuatro con tráfico, y no sales del valle central). Pucón funciona,
sí, pero comparte el lago con un pueblo que en temporada parece tienda
de Santa Claus en diciembre.

**Puerto Varas tiene otra economía sensorial**:

- **Lago Llanquihue** sin la masa de gente. Volcán Osorno enfrente, no
  de fondo en una postal.
- **Bosque nativo** que rodea las cabañas (no un parque temático
  manicurado). En Aremko, el ingreso es por una calle que se vuelve
  ripio bien mantenido — la transición visual ya es parte del reset.
- **Río Pescado** corriendo a metros del recinto, sin pausa, sin loop,
  sin volumen ajustable.
- **Distancia mental real**: 20 minutos del centro de Puerto Varas, pero
  la sensación al llegar es de estar a 2 horas de cualquier ciudad.

> El detalle del río importa más de lo que crees. Es el único spa de
> Puerto Varas al lado de un río que suena los 365 días del año. Los
> demás usan parlantes (sí, hay parlantes con sonido de río pregrabado;
> es 2026 y todavía pasa).

## Qué incluye una escapada romántica en Aremko

Vendemos un **pack 3-en-1**: cabaña + tinas calientes + masajes. Tres
servicios, una sola reserva, un solo precio. La idea es que no tengas
que armar la logística — vienes, llegas, te encuentras todo en su lugar.

**Precios actualizados:**

- **Día de semana** (lunes, miércoles, jueves): **$190.000** por pareja
- **Fin de semana** (viernes, sábado, domingo): **$220.000** por pareja

Martes cerrado por mantención (ese día no operamos, ni tinas ni masajes).
La diferencia entre semana / fin de semana es real: si puedes mover el
plan a un miércoles, ahorrás $30.000 y el recinto está más vacío. La
matemática termina favoreciendo cortar la semana, no el sábado.

### El alojamiento

Cabañas privadas (no habitaciones de hotel, no hay pasillo común con
extraños haciendo check-in a las 3 AM) rodeadas de bosque. Cada cabaña
tiene su mirador al bosque, baño completo, calefacción, y la
fundamental: silencio relativo. Lo único que vas a escuchar de noche es
el río Pescado y, si tienes mala suerte, una rana entusiasmada.

Check-in 16:00, check-out 11:00 — horarios que ya se acomodaron al
ritmo de pareja (entrar tarde, salir tarde). Si llegan el viernes a las
18:00 y no tienen cena resuelta, te recomendamos pedir algo en Puerto
Varas a la ida; las cabañas tienen kitchenette pero la idea de una
escapada NO es cocinar.

### Las tinas calientes

Tina caliente privada por cabaña, agua a 38-40°C (los sensores no dejan
pasar de 40°C, así que el escenario "agua hirviendo" no existe — en una
tinaja a leña mal calibrada sí pasa). Las tinas en Aremko se calientan
con **aerotermia + 48 paneles solares propios**: cero leña, cero humo en
el cielo de Puerto Varas, cero combustión.

Garantía 38°C: **si la tina llega a 37°C o menos al momento de tu llegada,
el servicio es gratis**. Es la única garantía de temperatura en spas de
la zona. La garantía casi nunca aplica (los sensores no permiten que
salga de rango), pero existe escrita y firmada.

Las tinas tienen techo total. **El mejor escenario para usarlas es
invierno con lluvia** (sí, contraintuitivo): el contraste entre agua
caliente, aire frío y lluvia cayendo sobre el techo es el momento peak
de la experiencia. La gente que viene en julio agradece más que la que
viene en enero.

### Los masajes

50 minutos cada uno, en **domos de madera nativa** metidos en el
bosque (no son salas con paredes pintadas y aroma artificial — el
contexto sensorial es parte del masaje). Los hace el equipo titular:
Sandra, Carolina, Diana o Paul, cada uno con técnicas distintas.
Podés elegir entre 6 tipos: descontracturante, relajación, piedras
calientes, deportivo, tui-na, drenaje linfático.

Para detalle de qué pedir según cómo lleguen, lee la
[guía de masajes](https://www.aremko.cl/blog/masajes-puerto-varas/) —
es un post completo.

> **Aviso honesto:** el masaje "para parejas" no es un masaje
> diferente. Es el mismo masaje (el que cada uno elija) hecho al mismo
> tiempo en el mismo domo, con dos masajistas. Si uno quiere
> descontracturante y el otro relajación, perfecto, se puede.

## El orden importa: cómo se ven 24-48 horas que funcionan

Después de varios años recibiendo parejas, la secuencia que más
agradecen es esta:

**Día 1 — Llegada (16:00 o más tarde)**

1. **16:00** — Check-in en cabaña. Dejen las cosas, no se vayan a
   instalar todavía. Salgan a caminar 15 min por el sendero al río.
2. **17:30** — Masaje 50 min en domo. Mientras dura, escuchan el río
   Pescado afuera. El que llegó con el cuello pegado al hombro se da
   cuenta de cuánto.
3. **19:00** — Tina caliente 1 hora con espumante (si trajeron) o sin.
   El agua a 38-40°C cierra el trabajo del masaje. Atardecer en el
   bosque cambia el color del cielo y vale por sí mismo.
4. **20:30** — Cena. Si trajeron algo de Puerto Varas, lo comen en la
   cabaña. Si no, hay restaurantes a 20 min en el centro. **Pro tip:
   pedir delivery de algún restaurant a la cabaña funciona** — pídanlo
   antes de la tina.
5. **22:30** — A dormir con la ventana entreabierta para escuchar el
   río. Vas a dormir como hace meses no duermes (la sensación de "no
   tengo que escuchar nada importante a las 7 AM" es parte del reset).

**Día 2 — Mañana sin reloj**

1. **9:00** — Despertar sin alarma. Hacer desayuno en la cabaña o
   pedirlo (si lo agendaron al reservar).
2. **10:30** — Caminar 30 min por el bosque. Sin celular si es posible,
   con celular si necesitan fotos para mostrar a la familia que sí
   están descansando.
3. **11:00** — Check-out flexible si reservaron solo una noche, o
   segunda tina caliente si reservaron dos. La segunda tina al mediodía
   con luz natural es **otra experiencia** comparada con la del
   atardecer.

¿La diferencia entre 24 y 48 horas? Las primeras 24 cortan la semana.
Las siguientes 24 te hacen olvidar que tenías una semana. Si pueden
hacer las 48, hacelas.

## Para aniversario, cumpleaños o "porfa"

Tres ocasiones en las que Aremko se llena rápido:

- **Aniversarios** (fecha exacta): reservar con al menos 2 semanas de
  anticipación. Día de semana siempre es más fácil de conseguir.
- **Cumpleaños**: tenemos **decoraciones especiales** disponibles (se
  ven en la página). Pétalos, mensajes, espumante con torta — la
  ambientación temática es uno de nuestros diferenciales reales (es
  raro encontrarla en spas de la zona, casi todos venden el mismo
  paquete plano).
- **"Porfa, necesitamos cortar"** (la categoría más vendida en
  realidad): no celebrás nada en particular, solo te das cuenta que
  llevan tres meses cruzándose en el pasillo. Esta es la categoría
  que más rinde — la pareja viene sin expectativa de "fecha
  importante" y se va con una.

Para ver las opciones de decoración disponibles, mira
[productos y decoraciones](https://www.aremko.cl/productos/). Si quieres
una propuesta de matrimonio armada de cero (música, momento, foto), nos
contactás por WhatsApp con tiempo y lo coordinamos.

## El río Pescado: por qué nadie se duerme en Aremko sin abrir la ventana

Ya lo mencionamos arriba pero merece su propia sección porque es el
diferencial sensorial real del recinto. **El río Pescado corre a metros
de las cabañas, los domos de masaje y las tinas. Suena los 365 días
del año, sin pausa, sin volumen ajustable, sin loop**.

¿Qué hace fisiológicamente?

- **Ruido blanco natural**: la frecuencia constante baja cortisol, ayuda
  a desconectar y le pone freno al loop mental que mantiene la cabeza
  ocupada con pendientes.
- **Mejora el sueño**: tu cerebro deja de buscar señales (gritos,
  motores, perros, alarmas) porque el río ocupa todo el espectro
  auditivo bajo.
- **Reduce la ansiedad de fondo**: la versión moderna del "white noise"
  que se compra en máquinas de Amazon, pero auténtica.

Otros spas de la zona usan **parlantes con sonido de río pregrabado**.
Es 2026 y todavía pasa. La diferencia entre un parlante con loop de 4
minutos y un río real de verdad es la misma que entre un perfume con
"esencia de bosque" y caminar dentro de un bosque.

Por eso te decimos: **abrí la ventana al dormir**. La calefacción
compensa, la cabaña no se enfría, y vas a descubrir que llevas años
durmiendo con sonidos que tu cuerpo quería que dejaras de escuchar.

## Preguntas frecuentes

### ¿Cuánto cuesta una escapada romántica en Aremko?

El pack pareja (cabaña + tina caliente + masajes para los dos) cuesta
**$190.000 día de semana** (lunes, miércoles, jueves) y **$220.000 fin
de semana** (viernes, sábado, domingo). Martes no operamos.

### ¿Cuántas noches incluye?

El pack base es **una noche** (check-in 16:00, check-out 11:00). Si
quieren dos noches, se cotiza al reservar; suele tener mejor precio que
2 packs separados.

### ¿Con cuánta anticipación hay que reservar?

Día de semana puedes agendar con 2-3 días de anticipación casi siempre.
**Fin de semana, aniversario o cumpleaños se llenan con 2-3 semanas
mínimo**. Para fechas críticas (14 de febrero, fin de año) reservar con
1 mes de anticipación.

### ¿Dónde queda exactamente?

A 20 minutos del centro de Puerto Varas, junto al río Pescado.
Coordenadas 41°16'39.4"S 72°46'07.0"W. Acceso pavimentado hasta la
entrada y después 200 metros de ripio bien mantenido (no necesitan auto
4x4).

### ¿Y si nunca nos hemos hecho un masaje en la vida?

Tranquilos, esa es la mayoría de la gente que viene. **Pidan masaje de
relajación si tienen cero referencia** — es el más amable, presión
suave, ritmo lento. Si quieren probar algo más específico, escriban al
WhatsApp y les recomendamos según cómo lleguen.

### ¿Tienen decoraciones especiales para cumpleaños o aniversarios?

Sí. **Decoración temática, pétalos, mensajes, torta y espumante** se
agendan al reservar (algunas se ven en la
[página de productos](https://www.aremko.cl/productos/)). Si tienes
algo muy específico (propuesta de matrimonio, sorpresa concreta) nos
contactás por WhatsApp **con al menos 5 días de anticipación**. No
hacemos magia el mismo día.

### ¿Qué llevamos? (la pregunta que más nos hacen)

- **Traje de baño** (las tinas son privadas pero igual conviene tener
  cómo salir al aire entre sesiones).
- **Ropa cómoda** para la cabaña — vinieron a relajarse, no a una boda.
- **Algo más abrigado** del que crees que necesitas, especialmente de
  abril a octubre. La temperatura cae en la noche y la cabaña tiene
  calefacción pero el deck exterior no.
- **Lo que NO hace falta**: ropa de gala, zapatos finos, ni los 4
  outfits que tu pareja ya empacó. Es spa boutique, no Viña del Mar.

### ¿Pueden venir hijos chicos?

El pack romántico está pensado para parejas. **Los chicos no son la idea
del plan** (ni para ustedes ni para los demás huéspedes que también
vinieron a desconectar). Si necesitan venir con familia, tenemos otras
opciones — escriban por WhatsApp y vemos.

### ¿Qué pasa si llueve todo el fin de semana?

**Mejor.** En serio. Las tinas tienen techo total, las cabañas son
privadas, y la combinación de lluvia afuera + agua caliente + río + nada
de planes es exactamente el escenario que estás pagando. La gente que
viene en julio agradece más que la que viene en enero.

### ¿Sirve durante embarazo?

**Tina caliente NO se recomienda durante embarazo** (la temperatura del
agua es muy alta para feto). Masaje de drenaje linfático o relajación
suave sí, con autorización médica desde el 2do trimestre. Avísanos al
reservar para adaptar el pack — podemos cambiar la tina por sesión
extendida en domos o por desayuno en cama, según cómo se quiera armar.

### ¿Política de cancelación?

Si avisas con **48 horas** o más, sin costo. Con menos de 48 horas se
cobra el 50%. **Si la cancelación es por motivo de fuerza mayor**
(emergencia médica, fallecimiento familiar, viaje cancelado por causa
externa) generalmente lo manejamos caso a caso — preferimos un cliente
que vuelve a uno que sintió que abusamos.
"""

# JSON-LD FAQPage para schema.org
FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta una escapada romántica en Aremko Spa?",
        "answer": (
            "El pack pareja (cabaña + tina caliente + masajes para los "
            "dos) cuesta $190.000 día de semana (lunes, miércoles, "
            "jueves) y $220.000 fin de semana. Martes no operamos."
        ),
    },
    {
        "question": "¿Cuántas noches incluye el pack romántico?",
        "answer": (
            "El pack base es una noche (check-in 16:00, check-out 11:00). "
            "Si se reservan dos noches, suele tener mejor precio que dos "
            "packs separados."
        ),
    },
    {
        "question": "¿Con cuánta anticipación hay que reservar?",
        "answer": (
            "Día de semana se puede agendar con 2-3 días de anticipación. "
            "Fin de semana, aniversarios y cumpleaños requieren 2-3 "
            "semanas mínimo. Fechas críticas como 14 de febrero o fin de "
            "año, 1 mes."
        ),
    },
    {
        "question": "¿Dónde queda Aremko Spa?",
        "answer": (
            "A 20 minutos del centro de Puerto Varas, junto al río "
            "Pescado. Coordenadas 41°16'39.4\"S 72°46'07.0\"W. Acceso "
            "pavimentado y 200 metros de ripio bien mantenido al final."
        ),
    },
    {
        "question": "¿Tienen decoraciones especiales para cumpleaños o aniversarios?",
        "answer": (
            "Sí. Decoración temática, pétalos, mensajes, torta y "
            "espumante se agendan al reservar. Para sorpresas específicas "
            "como propuestas de matrimonio, contactar por WhatsApp con al "
            "menos 5 días de anticipación."
        ),
    },
    {
        "question": "¿Qué incluye el pack romántico de Aremko?",
        "answer": (
            "Una noche en cabaña privada con bosque alrededor, una "
            "sesión de tina caliente privada (38-40°C), y un masaje de "
            "50 minutos por persona en domos de madera nativa. Pueden "
            "elegir entre 6 tipos de masaje."
        ),
    },
    {
        "question": "¿Qué llevar a una escapada romántica en Aremko?",
        "answer": (
            "Traje de baño, ropa cómoda y algo más abrigado del esperado "
            "(especialmente abril a octubre). No hace falta ropa de gala "
            "ni zapatos finos — es spa boutique, no evento social."
        ),
    },
    {
        "question": "¿Pueden venir niños al pack romántico?",
        "answer": (
            "El pack romántico está pensado para parejas y no incluye "
            "niños. Para opciones familiares Aremko tiene otros "
            "formatos — consultar por WhatsApp."
        ),
    },
    {
        "question": "¿La tina caliente sirve durante embarazo?",
        "answer": (
            "La tina caliente no se recomienda durante embarazo por la "
            "temperatura del agua. Masaje de relajación suave o drenaje "
            "linfático sí, con autorización médica desde el 2do "
            "trimestre. El pack se puede adaptar al avisar al reservar."
        ),
    },
    {
        "question": "¿Cuál es la política de cancelación?",
        "answer": (
            "Sin costo con 48 horas o más de anticipación. Menos de 48 "
            "horas, se cobra el 50%. Casos de fuerza mayor (emergencia "
            "médica, fallecimiento familiar) se manejan caso a caso."
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
        "Seed del Post #4 Aremko 'Escapada romántica al sur de Chile'. "
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

        action = "creado" if created else "actualizado"
        status = "publicado" if publish else "borrador"
        self.stdout.write(
            self.style.SUCCESS(
                f"Post {action} ({status}): {post.title}\n"
                f"  Slug: {post.slug}\n"
                f"  URL: {post.get_absolute_url()}\n"
                f"  Cluster: {post.cluster}\n"
                f"  Keyword: {post.keyword_root}\n"
                f"  CTA: {post.cta_text} → {post.cta_url}"
            )
        )
