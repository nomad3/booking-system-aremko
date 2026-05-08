"""Seed del Post #3 del blog Aremko: "Masajes en Puerto Varas".

Patrón paralelo al seed de tinas (`seed_blog_post_tinas_aremko.py`):
- Idempotente (update_or_create por slug)
- Por defecto crea como borrador (is_published=False)
- Flag --publish opcional para publicar al instante con published_at=now()

Voz: anfitrión / dueño en primera persona. Humor + voz personal en
primeras 50 palabras (decisión #7 DPV-SEO-002).

Target SEO:
- Keyword P0: "masajes puerto varas"
- Página /masajes/ tiene 135 sesiones/sem sin contenido editorial — gap detectado
  por brief automático del 2026-05-06.

Uso:
    python manage.py seed_blog_post_masajes_aremko          # borrador
    python manage.py seed_blog_post_masajes_aremko --publish  # publicado
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from aremko_blog.models import BlogCluster, BlogPost


SLUG = "masajes-puerto-varas"
TITLE = "Masajes en Puerto Varas entre semana: el plan after-work que te corta el lunes a jueves"
KEYWORD_ROOT = "masajes puerto varas"
META_DESCRIPTION = (
    "Masajes en Puerto Varas de lunes a viernes (martes cerrado): "
    "after-work + tina caliente al lado del río Pescado. Descontracturante, "
    "relajación, piedras calientes, deportivo, tui-na, drenaje linfático."
)
CLUSTER = BlogCluster.MASAJES
CTA_TEXT = "Reserva tu masaje after-work"
CTA_URL = "/masajes/"

INTRO = (
    "La idea de masaje en Chile sigue ligada al fin de semana, como si el "
    "lumbar entendiera de calendario. La verdad es la opuesta: el masaje "
    "rinde más en mitad de la semana, cuando el lunes ya cobró factura y "
    "el viernes todavía no llegó. En Aremko abrimos lunes, miércoles, "
    "jueves y viernes (martes cerramos para mantención) y la mejor franja "
    "horaria es la **after-work**: salís de la pega, manejás 20 minutos "
    "desde el centro de Puerto Varas, te recibe el sonido del río Pescado "
    "y entrás al masaje con el cuerpo todavía caliente del día. Esta es la "
    "guía honesta de cuál pedir."
)

BODY_MD = """\
## Por qué entre semana es mejor que el sábado

Dos razones operativas, una experiencial:

1. **Disponibilidad real**: el sábado se llena con anticipación, hay que
   reservar con días. Lunes, miércoles, jueves y viernes podés agendar el
   mismo día casi siempre. Si te decidís en la oficina a las 17:00,
   alcanzás a entrar a una sesión de las 18:30 o 19:30.
2. **Tu cuerpo lo necesita más el miércoles que el sábado**: el sábado ya
   cortaste, el cuerpo viene bajando solo. El miércoles es cuando el
   cortisol está alto, los hombros pegados a las orejas y la noche se
   complica. Ahí el masaje rinde el doble.
3. **El recinto está más vacío y suena solo el río Pescado.** Esto es
   nuestro diferencial real: estamos a metros del único río de Puerto
   Varas que suena los 365 días del año, sin pausa. Entre semana no hay
   grupos, no hay despedidas de soltera, no hay ruido humano: el masaje
   sucede con la frecuencia constante del agua corriendo como única banda
   sonora. Es la diferencia entre "spa con música ambiente" y spa real.

> Días de atención: **lunes, miércoles, jueves, viernes y fin de semana**.
> Martes cerrado por mantención de tinas y descanso del equipo. Si tenías
> agendado un martes, ese día no operamos.

## Diagnóstico rápido: qué pedir según cómo llegaste

Antes de irte al detalle de cada tipo, un atajo. Buscá la línea que mejor
te describa este miércoles a las 18:00:

- **"Llegué con un nudo en el cuello que me duele al girar la cabeza"** →
  pedí **descontracturante**. Es masaje terapéutico, presión profunda en
  zonas tensas. No es relajante, te puede doler durante. Sale rico al
  día siguiente.
- **"Llegué simplemente cansado, sin dolor pero sin pila"** →
  **relajación**. Presión suave a media, ritmo lento, intención sedante.
  El que más se vende para parejas y para gente que busca cortar el loop
  mental.
- **"Llegué con frío hasta los huesos, julio en Puerto Varas pesa"** →
  **piedras calientes**. La temperatura penetra mejor que cualquier crema,
  baja el tono muscular y te deja en otro plano. En invierno, el más
  pedido.
- **"Vengo de entrenar / corrí media maratón / hice trekking en Cochamó"**
  → **deportivo**. Trabaja recuperación muscular, cadenas específicas,
  prevención de lesiones. Más técnico, menos "spa" en el sentido clásico.
- **"Vengo arrastrando estrés y dolores difusos que no sé explicar"** →
  **tui-na**. Masaje terapéutico chino, trabaja meridianos energéticos
  además de tejido. Distinto a todo lo demás. Quien lo prueba, vuelve.
- **"Tengo las piernas hinchadas, retención, mucho tiempo sentada"** →
  **drenaje linfático**. Movimientos suaves rítmicos que activan el
  sistema linfático. No te va a doler ni te va a dar sueño profundo, pero
  bajás la hinchazón en serio.

Si estás entre dos, casi siempre conviene el más profundo. Es más fácil
pedir "menos presión, por favor" en el momento que arrepentirse de un
masaje suave cuando lo que tenías era un nudo de verdad.

## Los 6 tipos de masaje que hacemos en Aremko

Todos duran **50 minutos** y cuestan entre **$40.000 y $45.000** según
tipo. Los hacemos en **domos de madera nativa**, no en una sala con
músiquita de ascensor. Te cuento cada uno con detalle.

### 1. Masaje descontracturante

El más pedido y, sin sorpresa, el más necesario. Trabaja con presión
profunda en zonas con contracturas — cuello, trapecios, lumbar son las
clásicas. El masajista identifica las bolas y las trabaja con técnica
combinada: presión sostenida, fricción transversal, estiramiento
miofascial.

**Cuándo pedirlo:** dolor muscular localizado, posturas fijas, tensión
crónica de oficina o de carga (gente que entrena pesado, papás de
guagua, mamás cargando niño).

**Aviso honesto:** te puede doler durante. Es masaje terapéutico, no
sedante. El alivio real lo sentís 24-48 horas después, cuando el
músculo terminó de soltar.

### 2. Masaje de relajación

El que la gente imagina cuando dice "quiero un masaje". Presión suave a
media, movimientos largos y lentos, foco en bajar el sistema nervioso.
No busca soltar nudos — busca apagar el ruido mental.

**Cuándo pedirlo:** llegaste agotado pero sin dolor específico,
necesitás cortar el ritmo, vienes con tu pareja a desconectar, querés
una experiencia de spa más que un tratamiento.

**Combinación clásica:** relajación + tina caliente + cabaña. Si vas a
hacer el ritual completo, este es el masaje que mejor le entra a la
secuencia.

### 3. Piedras calientes

Piedras de basalto volcánico calentadas a 50-55°C que se aplican y
deslizan sobre el cuerpo. La temperatura penetra hasta capas más
profundas que la mano sola, suelta el tono muscular y deja una
sensación particular: pesadez relajada, no hipnosis.

**Cuándo pedirlo:** invierno crudo en Puerto Varas (julio-agosto, mayo
también), gente que llega "fría" estructuralmente, contracturas
asociadas a frío. También funciona para personas a las que el masaje
profundo les incomoda — el calor hace gran parte del trabajo.

**El que más se vende en invierno.** No es coincidencia.

### 4. Masaje deportivo

Para quien entrena en serio o llega de actividad física exigente —
trekking, running, ciclismo, escalada en Cochamó, día completo de
caminata por Petrohué. Trabaja con técnicas de recuperación: drenaje
muscular, estiramientos asistidos, presión específica en cadenas
contractadas (isquiotibiales, gemelos, glúteos, cuádriceps).

**Cuándo pedirlo:** post-actividad o pre-actividad. Después rinde más
para recuperación; antes, para preparar tejido si vas a hacer algo
exigente al día siguiente.

**No es el masaje "relax"**: es trabajo técnico. Pero si entrenás, lo
agradecés.

### 5. Tui-na

Masaje terapéutico chino, parte de la medicina tradicional china. Trabaja
**meridianos energéticos** además de tejido muscular. Mezcla presión
puntual (digitopresión), movilizaciones articulares, fricciones,
estiramientos. La cabeza atrás del tui-na es que el dolor físico tiene
un componente energético que conviene atender en paralelo al muscular.

**Cuándo pedirlo:** dolores difusos que no se explican con un tirón
puntual, fatiga crónica, sensación de "estar desconectado del cuerpo",
gente curiosa que quiere algo distinto a lo occidental.

**Lo más distinto de la carta.** Quien lo prueba, suele pedirlo de
nuevo en visitas siguientes.

### 6. Drenaje linfático

Movimientos lentos, rítmicos, suaves. Activan el sistema linfático para
eliminar líquidos retenidos y toxinas. **No es un masaje muscular** — es
un masaje vascular. La presión es deliberadamente baja porque más
presión rompe el efecto.

**Cuándo pedirlo:** retención de líquidos, piernas hinchadas (mujeres
que pasan muchas horas sentadas, embarazo en trimestres tempranos previa
consulta médica, post-vuelo largo), recuperación post cirugía estética
con autorización médica.

**Aviso honesto:** si lo que querés es "que me masajeen fuerte", este
NO es. Pedí descontracturante. El drenaje es otro objetivo.

## Domos de madera nativa, al lado del río Pescado

Los masajes en Aremko se hacen en **domos** — estructuras circulares de
madera nativa metidas en el bosque. No es una sala con paredes pintadas
y aroma artificial: es un domo a metros del **río Pescado**, donde escuchás
el agua corriendo y nada más.

¿Por qué importa? Porque el contexto sensorial **es parte del masaje**. Tu
sistema nervioso baja distinto cuando lo único que escuchás es un río real
corriendo, comparado con música ambiente de spa por parlante. La frecuencia
constante del río Pescado es **ruido blanco natural**: baja cortisol, ayuda
a desconectar y le pone freno al loop mental antes de que el masajista te
toque.

Importa el detalle del río porque **es nuestro diferencial real**. Hay
muchos spas en la zona; ninguno está al lado de un río que suena 365 días
al año. Otros usan parlantes con sonido de río pregrabado. Acá el río es el
que está afuera del domo, sin loop, sin pausa, sin volumen ajustable.
Quien viene una vez lo recuerda como "ese spa donde se oye el río".

Por eso no hacemos masajes en cabaña: la cabaña queda para descansar
después. El masaje pertenece al domo, donde el sonido del río Pescado
trabaja contigo desde antes de subirte a la camilla.

## El plan after-work: masaje + tina al cierre del día

Acá está el caso de uso que pocos descubrieron: **martes cerrado, pero
lunes/miércoles/jueves/viernes podés salir de la pega y armar el siguiente
plan en una tarde**, sin reservar cabaña, sin pedir el día libre.

**Secuencia recomendada de día de semana** (~2 horas total, 18:00 a 20:00):

1. **18:00 — Salís de la oficina** en Puerto Varas, Puerto Montt o
   alrededores. Manejás 20 minutos hasta Aremko.
2. **18:30 — Masaje 50 minutos** en domo. Mientras dura, escuchás el río
   Pescado afuera. Tu jefe ya no existe.
3. **19:30 — Tina caliente 1 hora** (con tu pareja o solo). El agua a
   38-40°C cierra el trabajo del masaje, el río sigue sonando, y al
   atardecer el bosque cambia de color.
4. **20:30 — Cena en Puerto Varas** o vuelta a casa. Tu cuerpo recibió un
   reset que no te da una noche de pésimo dormir.

¿Con quién funciona este plan?

- **Pareja en burnout**: ambos salen de trabajar, se encuentran en
  Aremko, masaje uno al lado del otro o por separado, tina juntos. Sin
  programar fin de semana, sin pedir guagua a abuela. Mitad de la semana
  ya cortó.
- **Persona sola post-pega**: si vivís el ciclo gym-trabajo-cama, romper
  con un masaje + tina entre semana hace lo que el sábado no puede hacer
  (porque el sábado ya está saturado de pendientes domésticos).
- **Empresa que cierra trato**: cliente importante de visita, en lugar de
  llevarlo a un restaurant más, lo invitás a una experiencia de 2 horas.
  La conversación que cierra negocios pasa antes en una tina escuchando
  el río Pescado.

Total estimado: $40-45.000 (masaje) + $25-30.000 (tina por persona). El
plan after-work es el mejor relación valor/tiempo del calendario Aremko.

## Si querés quedarte: combo masaje + tina + cabaña

Cuando podés agregarle alojamiento, el **3-en-1 de Aremko** (masaje + tina +
cabaña) es nuestra propuesta principal. Hay un detalle que casi nadie te
dice: **el orden correcto es masaje primero, tina después, cabaña al
final.**

¿Por qué?

- **Masaje primero** suelta los nudos cuando el cuerpo aún está "en
  ritmo de viaje". El masajista trabaja mejor con tejido que todavía
  responde, no con uno ya entibiado por el agua caliente.
- **Tina después** sella el trabajo del masaje. El calor mantiene el
  músculo suelto, hidrata, profundiza la relajación. Es el cierre
  físico del masaje. Y como las cabañas miran al bosque, se sigue
  escuchando el río Pescado de fondo desde la tina.
- **Cabaña al final** es para dormir. No para ir a relajarse — ya estás
  relajado. Es para tener dónde caer.

Hacer la secuencia al revés (tina primero, masaje después) **no arruina la
experiencia, pero la deja más floja**. Es la diferencia entre una cena
bien armada y un buffet aleatorio.

## Tus masajistas tienen nombre: Sandra, Carolina, Diana y Paul

En la mayoría de spas el masajista es invisible: te entregan a "alguien"
que está disponible. Acá no. Cada cliente termina pidiendo a su
masajista por nombre, y eso pasa porque hay **diferencias reales de
estilo y técnica**.

- **Sandra** — descontracturante de presión profunda, lectura rápida
  del cuerpo. Si querés que te encuentren los nudos, Sandra los
  encuentra.
- **Carolina** — relajación y piedras calientes. Ritmo lento sostenido,
  manos cálidas, la mejor para gente ansiosa.
- **Diana** — tui-na y drenaje linfático. Especializada en lo
  energético-funcional. La pedís cuando querés algo distinto a lo
  típico.
- **Paul** — descontracturante, deportivo. Presión fuerte, técnica
  precisa para gente que entrena o llega de actividad física exigente.

¿Podés elegir? **Sí.** Al reservar te preguntamos por preferencia o por
qué buscás. Si no tenés referencia, agendamos según el tipo de masaje y
disponibilidad del día. Si te gustó alguno, podés pedirlo en visitas
siguientes — la mayoría lo hace.

## Preguntas frecuentes

### ¿Cuánto cuesta un masaje en Puerto Varas?

En Aremko, **entre $40.000 y $45.000 por persona** según tipo, todos de
**50 minutos**. El precio es por persona, no por sesión. Si vienen los
dos al masaje en pareja (mismo domo, dos masajistas), se cobra por las
dos personas.

### ¿Cuánto dura un masaje?

**50 minutos** efectivos en camilla. Sumá unos 5-10 min antes (cambiarte,
acostarte, conversar lo justo con el masajista para que entienda qué
necesitás) y 5 min después para incorporarte sin saltar de golpe.
Reservá 1 hora total por seguridad.

### ¿Qué días atienden?

**Lunes, miércoles, jueves, viernes, sábado y domingo.** Martes cerrado
por mantención de tinas y descanso del equipo. Lo más fácil para
agendar es entre semana (lunes/miércoles/jueves/viernes); el sábado se
llena con anticipación.

### ¿Cuál es el mejor horario para venir?

Si venís entre semana, la franja **after-work entre 18:00 y 20:30** es
la más rica: el recinto está vacío, el río Pescado se escucha más fuerte
y el atardecer en el bosque vale por sí mismo. Si venís fin de semana,
mediodía o primera tarde funciona mejor para combinar masaje + tina sin
apuro.

### ¿Tengo que reservar con anticipación?

**Entre semana podés agendar el mismo día casi siempre** (lunes,
miércoles, jueves o viernes). Para sábados conviene reservar con 24-48
horas de anticipación. La reserva la hacés en
[aremko.cl/masajes/](https://www.aremko.cl/masajes/) o por WhatsApp.

### ¿Puedo elegir masajista?

Sí. Al reservar te preguntamos por preferencia. Si querés algo
específico (ej: "presión muy fuerte" o "alguien con manos cálidas"),
contanos y agendamos a quien mejor calce. Si te gustó alguno, podés
pedirlo en visitas siguientes.

### ¿Tengo que estar desnudo?

No. La camilla viene con sábana, te quedás en ropa interior y el
masajista descubre solo la zona que está trabajando en cada momento. Si
te incomoda quedar en ropa interior, podés mantener algo más — el
masaje se adapta. Lo importante es que el aceite no manche tu ropa de
calle.

### ¿Sirve durante embarazo?

Algunos sí, algunos no. **Drenaje linfático y relajación suave** se
pueden hacer con autorización médica desde el segundo trimestre.
**Descontracturante profundo y piedras calientes NO**. Avisanos al
reservar para agendar a la masajista correcta y adaptar la sesión.

### ¿Atienden a niños?

A partir de 12 años con autorización del adulto responsable y solo
relajación. Para menores, conviene venir como acompañantes a la tina y
cabaña, no al masaje.

### ¿Pueden atendernos en pareja en la misma sala?

Sí, se hace. Reservás **masaje pareja** y los atendemos al mismo tiempo
en el mismo domo, con dos masajistas. Es uno de los formatos más
pedidos para aniversario, cumpleaños o "necesitamos desconectar
juntos". El tipo de masaje (descontracturante, relajación, piedras
calientes) lo eligen por separado: cada uno pide lo suyo.

### ¿Qué traigo / qué me prestan?

Nosotros ponemos sábana, toalla, aceite, sala. Vos venís con ganas y
ropa cómoda. Si querés combinar con tina después, traé traje de baño.
Si vas a quedarte en cabaña, traé lo de dormir — la cabaña tiene
toallas y blancos.

### ¿Dónde queda exactamente?

Aremko Spa Boutique está a **20 minutos del centro de Puerto Varas**,
junto al **río Pescado**. Coordenadas: 41°16'39.4"S 72°46'07.0"W.
Acceso por camino pavimentado hasta la entrada, después 200 metros de
ripio bien mantenido.

### ¿Y si quiero masaje + tina + cabaña?

Es nuestro **pack 3-en-1**, la propuesta principal. Reservás el combo
en [aremko.cl](https://www.aremko.cl/) o por WhatsApp. El orden
recomendado es masaje primero, tina después, cabaña al final. Domingo a
jueves el pack tiene mejor precio que en fin de semana.
"""

# JSON-LD FAQPage para schema.org
FAQ_ITEMS = [
    {
        "question": "¿Cuánto cuesta un masaje en Puerto Varas?",
        "answer": (
            "En Aremko, entre $40.000 y $45.000 por persona según tipo, "
            "todos de 50 minutos. El precio es por persona, no por sesión."
        ),
    },
    {
        "question": "¿Cuánto dura un masaje?",
        "answer": (
            "50 minutos efectivos en camilla. Sumá unos 5-10 minutos antes "
            "para cambiarte y conversar con el masajista, y 5 minutos "
            "después para incorporarte. Reservá 1 hora total."
        ),
    },
    {
        "question": "¿Qué tipos de masaje ofrecen?",
        "answer": (
            "Descontracturante, relajación, piedras calientes, deportivo, "
            "tui-na (medicina tradicional china) y drenaje linfático. Los "
            "6 con duración estándar de 50 minutos."
        ),
    },
    {
        "question": "¿Qué días atienden masajes en Aremko?",
        "answer": (
            "Lunes, miércoles, jueves, viernes, sábado y domingo. "
            "Martes cerrado por mantención de tinas y descanso del equipo."
        ),
    },
    {
        "question": "¿Cuál es el mejor horario para venir entre semana?",
        "answer": (
            "La franja after-work entre 18:00 y 20:30 es la más rica: "
            "recinto vacío, el río Pescado se escucha más fuerte y el "
            "atardecer en el bosque vale por sí mismo. Lunes, miércoles, "
            "jueves y viernes."
        ),
    },
    {
        "question": "¿Tengo que reservar con anticipación?",
        "answer": (
            "Entre semana (lun/mié/jue/vie) podés agendar el mismo día "
            "casi siempre. Para sábados conviene reservar con 24-48 "
            "horas de anticipación."
        ),
    },
    {
        "question": "¿Puedo elegir masajista?",
        "answer": (
            "Sí. Al reservar te preguntamos por preferencia. Los "
            "masajistas Aremko son Sandra, Carolina, Diana y Paul, cada "
            "uno con técnicas y estilos distintos."
        ),
    },
    {
        "question": "¿Dónde se hacen los masajes?",
        "answer": (
            "En domos de madera nativa metidos en el bosque, junto al río "
            "Pescado. No usamos salas convencionales — el sonido del río "
            "y el bosque son parte de la experiencia."
        ),
    },
    {
        "question": "¿Atienden masaje en pareja?",
        "answer": (
            "Sí. Se hace en el mismo domo con dos masajistas al mismo "
            "tiempo. Cada persona elige su tipo de masaje por separado "
            "(descontracturante, relajación, piedras calientes, etc.)."
        ),
    },
    {
        "question": "¿El masaje sirve durante embarazo?",
        "answer": (
            "Drenaje linfático y relajación suave se pueden hacer con "
            "autorización médica desde el segundo trimestre. "
            "Descontracturante profundo y piedras calientes no se "
            "recomiendan durante embarazo."
        ),
    },
    {
        "question": "¿Tengo que estar desnudo durante el masaje?",
        "answer": (
            "No. Te quedás en ropa interior bajo la sábana. El masajista "
            "descubre solo la zona que trabaja en cada momento. Si te "
            "incomoda, podés mantener algo más — el masaje se adapta."
        ),
    },
    {
        "question": "¿Tienen masaje a domicilio o en cabaña?",
        "answer": (
            "No. Los masajes Aremko se hacen únicamente en los domos de "
            "madera nativa del recinto, junto al río Pescado. La cabaña "
            "es para descansar después, no para el masaje."
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
        "Seed del Post #3 Aremko 'Masajes en Puerto Varas'. "
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
