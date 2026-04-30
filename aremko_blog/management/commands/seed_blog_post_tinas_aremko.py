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
    "ritual, aerotermia + paneles solares, río Pescado al lado y horarios "
    "hasta medianoche."
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
## Qué es una tina caliente (y qué no)

**No es la tinaja-con-leña que probablemente te imaginabas.** La tinaja
chilena clásica se calienta quemando leña abajo. Funciona, sí, pero
también: humea, ensucia el cielo de Puerto Varas, y se come bosque nativo
a un ritmo que en 2026 ya cuesta defender.

Una tina caliente bien hecha es una **tinaja de madera nativa** —alerce,
ciprés— con agua a 38-40°C, ritual largo, vista al río Pescado y olor a
sur de Chile. La pregunta interesante es **cómo la calientas**. Ahí es
donde empieza a divergir el cuento.

> El término "hot tub" es la versión gringa, "jacuzzi" es la marca
> registrada que se nos quedó como sinónimo (igual que kleenex y confort),
> y "tinaja" es como le dicen los chilenos. Los tres pueden ser lo mismo o
> tres cosas distintas según quién te la venda. Hablaremos de las
> diferencias más abajo.

## Cómo se calientan las tinas Aremko (y por qué no quemamos un solo palo)

Las tinas Aremko se calientan con **aerotermia**. Suena a palabra de
folleto, pero es simple: una **bomba de calor** extrae calor del aire
ambiente —incluso del aire frío de Puerto Varas en julio— y lo transfiere
al agua. La electricidad que necesita la bomba no genera el calor: solo
mueve el calor que ya está afuera. Por eso es 3-5 veces más eficiente que
un calentador eléctrico tradicional. Es el mismo principio que un
refrigerador, pero al revés.

¿Y de dónde sale esa electricidad? De **48 paneles solares** instalados en
Aremko Spa Boutique, **funcionando hace más de un año**. Energía renovable
propia, sin red, sin combustión, sin humo.

Traducido a lo que importa:

- **Cero leña**: no quemamos bosque nativo, ni eucalipto, ni nada. El cielo
  de Puerto Varas no se nubla por nuestra culpa.
- **Cero CO₂ directo**: la combustión no existe. Lo único que se mueve es
  el compresor de la bomba.
- **Energía propia**: el sol calienta tu tina, en serio. Si los paneles no
  alcanzan en un día gris, hay red de respaldo, pero el grueso del año el
  motor es el cielo.
- **Sensores de temperatura**: el sistema **no permite que el agua pase de
  40°C**. No hay olla quemada, no hay "se nos pasó la mano con la leña", no
  hay riesgo de meterse a 45°C porque el operador se distrajo. La
  temperatura está controlada electrónicamente todo el tiempo.

Sí, los gringos cobran 200 dólares extra por esto en sus retiros
"eco-luxury". Nosotros lo hicimos porque vivimos al lado del río Pescado
y nos da rabia ver bosque nativo arder por algo que ya se puede resolver
con un panel solar y una bomba de calor.

## La garantía de los 37°C: si está fría, es gratis

Esto no lo hace nadie más en Puerto Varas, así que vale la pena decirlo
directo: **si tu tina llega y está a 37°C o menos, te devolvemos el dinero
o el servicio es gratis**. Sin discusión, sin "es que el operador", sin
"está calentando todavía".

¿Por qué la garantía? Porque la queja silenciosa más común en spas y
termas de Chile es justamente esa: **llegas, te metes, y el agua está
tibia**. Te jode, no reclamas porque "para qué", y nunca vuelves. Pasa
todo el rato. Nosotros decidimos que en vez de pedir disculpas, mejor
asumimos el costo.

¿Cómo lo logramos sin perder plata cada semana? Por la combinación de
arriba: **aerotermia + sensores + agenda con tiempos reales de
calentamiento**. Si el sistema dice que la tina está lista, está a
38-40°C, no "casi". Y si por alguna razón excepcional eso falla, el costo
lo asumimos nosotros, no tú.

Es la única forma honesta de decir "tina caliente": que esté caliente.

## A metros del río Pescado: la única tina con esa banda sonora

Esto es lo que hace que las tinas Aremko **no se puedan replicar en
ningún otro spa de Puerto Varas**: estamos a metros del **río Pescado**,
que suena —no exagero— **365 días al año**.

No es un riachuelo estacional ni un canal artificial. Es un río de verdad
que pasa fuerte, hace su rumor, y no se detiene en invierno ni cuando
todos los influencers terminaron de fotografiarlo. Cuando entras a la
tina, lo que escuchas no es música ambiente de Spotify ni un fuente
artificial: es agua corriente real, en la frecuencia exacta del **ruido
blanco natural**.

Y eso —spoiler científico— **te baja el cortisol, te ayuda a dormir
mejor, y le pone freno al loop mental** que arrastras desde el lunes. No
es esoterismo, es fisiología: el cerebro humano evolucionó cerca de ríos
y arroyos. Reconoce el sonido como "zona segura" y suelta tensiones que
no sabías que tenías.

Hazle la prueba: cualquier otra tina o sauna o termas en Puerto Varas las
escuchas en silencio o con música de fondo. La nuestra suena a río. Es
una diferencia que **no necesita explicación, solo necesita estar ahí**.

## Abierto hasta medianoche: la única tina nocturna de Puerto Varas

Acá viene el otro diferencial práctico: **funcionamos hasta las 00:00**.

Suena anecdótico hasta que lo piensas. **Termas de Puyehue, Cascadas, los
spas urbanos**: todos cierran entre las 18:00 y las 20:00. Si saliste de
tu trabajo a las 19:00, tu única opción para terminar el día con una tina
caliente era… ninguna.

Aremko Spa Boutique abre sesiones de tina **hasta las 12 de la noche**. A
20 minutos del centro de Puerto Varas. La logística cambia totalmente:

- **Sales del trabajo a las 18:00 o 19:00.**
- Pasas a la casa, dejas el celular, te tomas un café.
- **A las 21:30 entras a la tinaja**, mientras afuera ya está oscuro y el
  río suena más fuerte porque la ciudad bajó el volumen.
- A las 22:30 sales, cenas, duermes.

Es la única manera —en Puerto Varas— de meter una tina caliente dentro
de un día normal sin pedir vacaciones. Para residentes de la zona y para
quien viene en escapada corta, es una ventana que ningún otro lugar te da.

## ¿A qué temperatura? La regla del 38-40, no del "hierve"

La temperatura ideal de una tinaja está entre **38°C y 40°C**. Punto.

- **Bajo 36°C** → tibio. No relaja, frustra.
- **38°C** → sweet spot. Te puedes quedar 25-40 minutos sin problema.
- **40°C** → ya empieza a ser intenso. 15-20 minutos máximo, sales rojo.
- **Sobre 41°C** → no es tina, es sopa. No lo hagas.

En tinajas leñeras tradicionales tenías que poner la mano antes de
meterte para asegurarte que no estaba demasiado caliente —el operador
podía haberse pasado de leña. En Aremko Spa Boutique los **sensores no
dejan que el agua suba de 40°C**, así que ese paso ya no aplica. Pero si alguna vez te
metes a una tinaja leñera y el agua quema en el primer segundo, retírate:
no es tu turno todavía.

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

## Tinaja leñera vs Aremko Spa Boutique vs jacuzzi de hotel: tres caminos al mismo destino

Esto da para un post completo (lo escribiremos pronto), pero la versión corta:

<div class="aremko-compare">
  <div class="aremko-compare__col">
    <h4>Tinaja leñera tradicional</h4>
    <dl>
      <dt>Calefacción</dt><dd>Leña</dd>
      <dt>Huella ambiental</dt><dd>Humo + bosque nativo</dd>
      <dt>Control de temperatura</dt><dd>Manual (juicio del operador)</dd>
      <dt>Garantía si llega fría</dt><dd>Te jodiste</dd>
      <dt>Material</dt><dd>Madera</dd>
      <dt>Chorros</dt><dd>No</dd>
      <dt>Banda sonora</dt><dd>Crepitar de leña</dd>
      <dt>Horario</dt><dd>Cierra al anochecer</dd>
      <dt>Vibra</dt><dd>Ritual rústico</dd>
    </dl>
  </div>
  <div class="aremko-compare__col aremko-compare__col--featured">
    <h4>Tinaja Aremko</h4>
    <dl>
      <dt>Calefacción</dt><dd>Aerotermia + solar (48 paneles)</dd>
      <dt>Huella ambiental</dt><dd>Cero combustión, energía propia</dd>
      <dt>Control de temperatura</dt><dd>Sensores, máx 40°C garantizado</dd>
      <dt>Garantía si llega fría</dt><dd>Servicio gratis si ≤ 37°C</dd>
      <dt>Material</dt><dd>Madera nativa</dd>
      <dt>Chorros</dt><dd>No (es ritual, no centrifugado)</dd>
      <dt>Banda sonora</dt><dd>Río Pescado, 365 días/año</dd>
      <dt>Horario</dt><dd>Hasta las 00:00</dd>
      <dt>Vibra</dt><dd>Ritual + sostenible + nocturno</dd>
    </dl>
  </div>
  <div class="aremko-compare__col">
    <h4>Jacuzzi / hot tub de hotel</h4>
    <dl>
      <dt>Calefacción</dt><dd>Eléctrica o gas</dd>
      <dt>Huella ambiental</dt><dd>Red eléctrica/gas</dd>
      <dt>Control de temperatura</dt><dd>Termostato</dd>
      <dt>Garantía si llega fría</dt><dd>Reclamo a recepción</dd>
      <dt>Material</dt><dd>Acrílico</dd>
      <dt>Chorros</dt><dd>Sí</dd>
      <dt>Banda sonora</dt><dd>Música ambiente</dd>
      <dt>Horario</dt><dd>Hasta las 22:00</dd>
      <dt>Vibra</dt><dd>Spa de hotel</dd>
    </dl>
  </div>
</div>

Los tres son válidos. Pero si vienes a Puerto Varas y eliges "jacuzzi de hotel",
estás pagando por algo que existe igual en Santiago. Y si eliges tinaja leñera,
te llevas el ritual pero le sumas humo al cielo. La opción Aremko es la que
mantiene **el ritual del sur sin el costo ambiental** — y le suma el río.

## La excusa de Puerto Varas

Puerto Varas tiene un combo difícil de igualar: **frío suficiente** para que
la tina caliente tenga sentido emocional (no es lo mismo en febrero a 28°C),
**río Pescado al lado** que suena todo el año, y **kuchen alemán** a 5
minutos en auto. Es ridículo no usar esa combinación.

Y a diferencia del resto de la oferta de la zona, en Aremko Spa Boutique
puedes hacerlo **de noche, después del trabajo, sin pedir vacaciones**.
Estás a 20 minutos del centro, abrimos hasta medianoche, y el río suena
más fuerte cuando la ciudad bajó el volumen.

Si vas a hacerlo bien:

1. **Reserva en la tarde-noche** — la magia de la tina está cuando ya
   oscureció y el río es lo único que se escucha.
2. **Pide [masaje descontracturante](https://www.aremko.cl/masajes/) antes** —
   primero el masaje, después la tina cierra el sello.
3. **Cena tarde** — vas a salir con hambre. Reserva en restaurante a las
   22:30, no a las 20:00. O cocina simple en tu casa o pide una pizza en la
   cabaña si alojas en Aremko.
4. **Reserva domingo a jueves** si puedes — más tranquilo, suele haber tarifas
   mejores, y no compartes el sector con un grupo de despedida de soltera.

## Preguntas frecuentes

### ¿Cuánto cuesta una tina caliente en Puerto Varas?

Como servicio independiente (sin alojamiento), $50.000 por sesión para 2
personas. Como combo con cabaña, viene incluida: en Aremko Spa Boutique
[la cabaña con tina caliente](https://www.aremko.cl/alojamientos/)
**domingo a jueves cuesta $110.000**, una de las mejores relaciones
precio/experiencia del lago.

### ¿Cómo se calientan las tinas si no usan leña?

Con **aerotermia**: una bomba de calor extrae calor del aire y lo transfiere
al agua. La electricidad que mueve la bomba sale de **48 paneles solares
propios** que llevan más de un año funcionando. Cero combustión, cero leña,
cero humo en el cielo de Puerto Varas.

### ¿Y si llego y la tina está fría?

Es gratis. **Si la tina está a 37°C o menos al momento de tu llegada, te
devolvemos el dinero o el servicio no se cobra.** Es la única garantía de
temperatura en spas de Puerto Varas. Pasa que casi nunca aplica: los
sensores del sistema no permiten que el agua se entregue bajo el rango
38-40°C, así que la garantía es más promesa estructural que algo que
estés esperando ejecutar.

### ¿No me puedo quemar si los sensores fallan?

Los sensores tienen un **tope físico de 40°C**. El sistema no permite
calentar más allá de ese punto, así que el escenario "agua hirviendo"
que sí puede pasar en una tinaja leñera mal calibrada, acá no existe. Si
te llega más caliente de lo que esperabas, tu cuerpo está reaccionando al
shock térmico (entrar congelado a 38°C), no a que el agua esté a 45°C.

### ¿Hasta qué hora puedo reservar tina?

**Hasta las 00:00.** Es el único spa con tinas en Puerto Varas que opera de
noche. Termas y spas de la zona cierran entre 18:00 y 20:00. Si saliste de
trabajar a las 19:00, igual alcanzas a tener una sesión completa.

### ¿Por qué importa estar al lado del río Pescado?

Porque el río suena los 365 días del año. Esa frecuencia constante es
**ruido blanco natural**: baja el cortisol, ayuda a dormir y le pone freno
al loop mental. No es lo mismo escuchar música ambiente de spa que escuchar
un río real corriendo a metros.

### ¿Tengo que reservar con anticipación?

Sí, pero **no porque la tina demore en calentarse**. El agua ya la tenemos
caliente todo el día (gracias al combo aerotermia + paneles solares): es
llegar, llenar, usar. La razón para reservar es la **demanda**: los
sábados se llenan rápido, así que si quieres asegurar horario, reserva al
menos 24 horas antes.

### ¿Se puede usar en invierno con lluvia?

Es **mejor** en invierno con lluvia. Suena contraintuitivo, pero el contraste
entre agua caliente / aire frío / lluvia cayendo es el momento peak de la
experiencia. Las tinajas en Aremko tienen **techo total** y quincho cerca
para resguardarse al salir.

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

No automáticamente, pero el combo masaje + tina es el clásico. En Aremko
Spa Boutique se puede [reservar el combo](https://www.aremko.cl/masajes/):
masaje primero (45-60 min), tinaja después. El orden importa: la tinaja
como cierre cuando el cuerpo ya está suelto.
"""

# JSON-LD FAQPage para schema.org
FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta una tina caliente en Puerto Varas?",
        "answer": (
            "Como servicio independiente (sin alojamiento), $50.000 por sesión "
            "para 2 personas. En Aremko Spa Boutique la cabaña con tina caliente "
            "domingo a jueves cuesta $110.000."
        ),
    },
    {
        "question": "¿Cómo se calientan las tinas si no usan leña?",
        "answer": (
            "Con aerotermia: una bomba de calor extrae calor del aire y lo "
            "transfiere al agua. La electricidad que mueve la bomba sale de 48 "
            "paneles solares propios que llevan más de un año funcionando. "
            "Cero combustión, cero leña, cero humo."
        ),
    },
    {
        "question": "¿Y si llego y la tina está fría?",
        "answer": (
            "Es gratis. Si la tina está a 37°C o menos al momento de tu "
            "llegada, devolvemos el dinero o el servicio no se cobra. Es la "
            "única garantía de temperatura en spas de Puerto Varas."
        ),
    },
    {
        "question": "¿Me puedo quemar si los sensores fallan?",
        "answer": (
            "Los sensores tienen tope físico de 40°C: el sistema no permite "
            "calentar más allá. El escenario de agua hirviendo que sí puede "
            "pasar en tinajas leñeras mal calibradas, acá no existe."
        ),
    },
    {
        "question": "¿Hasta qué hora puedo reservar tina?",
        "answer": (
            "Hasta las 00:00. Aremko es el único spa con tinas en Puerto Varas "
            "que opera de noche. Termas y spas de la zona cierran entre 18:00 "
            "y 20:00, así que si saliste de trabajar a las 19:00 igual alcanzas "
            "una sesión completa."
        ),
    },
    {
        "question": "¿Por qué importa estar al lado del río Pescado?",
        "answer": (
            "Porque el río suena los 365 días del año. Esa frecuencia constante "
            "es ruido blanco natural: baja el cortisol, ayuda a dormir y frena "
            "el loop mental. No es lo mismo escuchar música ambiente de spa que "
            "un río real corriendo a metros."
        ),
    },
    {
        "question": "¿Tengo que reservar con anticipación?",
        "answer": (
            "Sí, pero no porque la tina demore en calentarse: el agua ya está "
            "caliente todo el día (aerotermia + paneles solares). Se reserva "
            "porque hay demanda, sobre todo los sábados; con 24 horas de "
            "anticipación aseguras horario."
        ),
    },
    {
        "question": "¿Se puede usar en invierno con lluvia?",
        "answer": (
            "Es mejor en invierno con lluvia. El contraste entre agua caliente, "
            "aire frío y lluvia cayendo es el momento peak. Las tinajas en "
            "Aremko tienen techo total."
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
