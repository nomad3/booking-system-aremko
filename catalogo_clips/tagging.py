"""Etiquetado IA del Catálogo de Clips (H-070 §2).

REUSA el núcleo de visión existente `marketing_briefs.revision_service._chat_vision`
(OpenRouter + MARKETING_REVISION_LLM_MODEL). Dada la imagen ya subida a Cloudinary,
PROPONE la taxonomía completa como borrador (draft). No persiste nada: el patrón es
"IA propone, humano cura" — el operador confirma/corrige y recién ahí se guarda.

Regla de oro (brief §2): NO inventar. Si el modelo duda del área o del nombre,
`nombre_comercial=""` y `estado="revisar"`.
"""
import logging

logger = logging.getLogger(__name__)

# Valores permitidos (lista blanca del saneo — el modelo no puede salirse de esto).
AREAS = {'tina', 'masaje', 'cabaña', 'entorno', 'detalle', 'aereo', 'recepcion', 'entorno_region'}
MOMENTOS = {'dia', 'atardecer', 'noche', 'indistinto'}
ESTACIONES = {'invierno', 'verano', 'indistinto'}
VAPOR = {'no', 'sí', 'sí (IA)'}
DECORACION = {'con', 'sin', ''}
PERMISOS = {'libre', 'revisar_derechos'}
CALIDADES = {'alta', 'media'}
ESTADOS = {'ok', 'revisar', 'descartado'}

# Taxonomía Aremko (brief H-070 §3, LITERAL) para el prompt de etiquetado.
TAGGING_SYSTEM_PROMPT = """Eres el catalogador del banco de fotos de Aremko Spa Boutique \
(Puerto Varas, Chile): tinas calientes junto al río, cabañas y masajes en un entorno de \
bosque nativo. Tu trabajo: mirar UNA foto y proponer su taxonomía EXACTA como JSON.

TAXONOMÍA AREMKO (memoriza y aplica):
- TINAS — el nombre se deduce por FORMA + hidromasaje:
  · redonda + hidromasaje → "Villarrica-Llaima"
  · octagonal (8 lados) sin hidromasaje → "Tronador-Calbuco"
  · rectangular sin hidromasaje → "Osorno-Hornopirén"
  · rectangular con hidromasaje → "Puyehue-Puntiagudo"
  · rectangular interior azul (agua fría) → "Yates"
  (Son gemelas idénticas → propone el nombre-par; el humano decide el individual.)
- CABAÑAS — hay 5: "Torre" (la única redonda y de 2 pisos, tipo domo) · "Laurel" (moderna \
de vidrio / palafito) · "Acantilado" · "Tepa" · "Arrayán". Las 4 de un piso son difíciles \
de distinguir por foto → si no es Torre ni Laurel, propone nombre_comercial="" y que el \
humano la nombre.
- OTROS ESPACIOS: el domo de masajes se llama "Sala Sol"; existen "Recepción Aremko" y \
"Recepción domos masajes"; las pasarelas de madera (+300 m) van como area="entorno" con \
etiqueta "pasarela".
- decoracion: si se ve ambientación (velas / vino / flores / bandeja) es un SERVICIO \
ADICIONAL → "con"; si la tina/espacio está en su estado base → "sin".
- vapor: SOLO en tinas calientes con agua. NUNCA en la Yates (es fría) ni en tinas vacías.
- personas: si aparecen clientes reconocibles → personas=true y permiso="revisar_derechos".
- keeper: true solo si es una foto hero (sin personas, nítida, distinta, no duplicado).
- Guarda de marca: SOLO material real; si la imagen parece sintética/generada, \
estado="descartado" y anótalo en nota.

REGLAS DE SALIDA:
- Responde SOLO un JSON (sin markdown, sin texto extra) con EXACTAMENTE estas claves:
  {"area": "tina|masaje|cabaña|entorno|detalle|aereo|recepcion|entorno_region",
   "nombre_comercial": "string o vacío",
   "momento": "dia|atardecer|noche|indistinto",
   "estacion": "invierno|verano|indistinto",
   "vapor": "no|sí",
   "decoracion": "con|sin|",
   "personas": true/false,
   "permiso": "libre|revisar_derechos",
   "calidad": "alta|media",
   "keeper": true/false,
   "descripcion": "una frase corta y concreta de lo que se ve",
   "orientacion": "horizontal|vertical|cuadrada",
   "estado": "ok|revisar",
   "etiquetas": ["3-6 palabras clave en minúscula"],
   "apto_para": ["subconjunto de: hero, blog, instagram_feed, historia, gbp, ads"]}
- NO inventes: si dudas del área o del nombre, nombre_comercial="" y estado="revisar".
- El JSON debe ser válido. Nada más que el JSON."""

# Campos que la IA propone y el draft expone (los demás los pone el operador/el sistema).
_CAMPOS_DRAFT = ('area', 'nombre_comercial', 'momento', 'estacion', 'vapor', 'decoracion',
                 'personas', 'permiso', 'calidad', 'keeper', 'descripcion', 'orientacion',
                 'estado', 'etiquetas', 'apto_para')


def _lista_str(v, maximo=12, largo=60):
    """Normaliza a lista de strings cortos (defensa: el modelo puede devolver cualquier cosa)."""
    if not isinstance(v, list):
        return []
    out = []
    for x in v[:maximo]:
        s = str(x).strip()[:largo]
        if s:
            out.append(s)
    return out


def sanear_draft(data):
    """Valida el JSON del modelo contra la lista blanca → draft seguro para el front.

    Cualquier valor fuera de rango cae a un default conservador y marca
    estado='revisar' (patrón defense-in-depth IA→ORM). Función pura (testeable).
    """
    d = data if isinstance(data, dict) else {}
    dudoso = not isinstance(data, dict) or 'area' not in d

    def _elige(campo, permitidos, default):
        nonlocal dudoso
        v = str(d.get(campo, '') or '').strip().lower()
        if campo == 'decoracion' and v == '':
            return ''
        if v not in permitidos:
            dudoso = True
            return default
        return v

    draft = {
        'area': _elige('area', AREAS, 'detalle'),
        'nombre_comercial': str(d.get('nombre_comercial', '') or '').strip()[:100],
        'momento': _elige('momento', MOMENTOS, 'indistinto'),
        'estacion': _elige('estacion', ESTACIONES, 'indistinto'),
        'vapor': _elige('vapor', VAPOR, 'no'),
        'decoracion': _elige('decoracion', DECORACION, ''),
        'personas': bool(d.get('personas', False)),
        'permiso': _elige('permiso', PERMISOS, 'libre'),
        'calidad': _elige('calidad', CALIDADES, 'media'),
        'keeper': bool(d.get('keeper', False)),
        'descripcion': str(d.get('descripcion', '') or '').strip()[:300],
        'orientacion': str(d.get('orientacion', '') or '').strip()[:12],
        'estado': _elige('estado', ESTADOS, 'revisar'),
        'etiquetas': _lista_str(d.get('etiquetas')),
        'apto_para': _lista_str(d.get('apto_para'), maximo=8),
    }
    # Coherencia dura (las reglas del negocio mandan sobre el modelo):
    if draft['personas']:
        draft['permiso'] = 'revisar_derechos'
        draft['keeper'] = False
    if dudoso:
        draft['estado'] = 'revisar'
    return draft


def etiquetar_imagen(cloud_url):
    """Corre la visión sobre la imagen (ya en Cloudinary) → draft saneado.

    Best-effort: si la visión falla o devuelve basura, el draft sale con defaults
    conservadores y estado='revisar' — la ingesta nunca se cae por el etiquetado.
    """
    from marketing_briefs.revision_service import _chat_vision

    content = [
        {"type": "text", "text": "Cataloga esta foto de Aremko según la taxonomía. Responde SOLO el JSON."},
        {"type": "image_url", "image_url": {"url": cloud_url}},
    ]
    try:
        data = _chat_vision(TAGGING_SYSTEM_PROMPT, content)
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la ingesta por la IA
        logger.error('etiquetar_imagen: visión falló (%s)', exc)
        data = {}
    return sanear_draft(data)
