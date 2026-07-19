"""Revisor IA del material que sube el community manager (Fase 2).

Recibe las imágenes (URLs públicas de Cloudinary) de una pieza + su copy +
el checklist derivado del playbook, y devuelve correcciones estructuradas —
mismo formato que la guía de Angélica: aspecto, severidad, qué encontró,
qué corregir.

Modelo con visión vía OpenRouter (SDK de OpenAI, mismo camino que el brief).
Configurable con MARKETING_REVISION_LLM_MODEL (default: un Gemini flash con
visión, barato). Best-effort: si falla, se devuelve un veredicto de error y
la pieza queda 'sin_revisar' — nunca rompe el flujo de subida.

Alcance: fotos, carruseles e historias (imágenes) y, desde H-065/H-066 F2,
video de reels — por clip de toma (segmento) o el reel completo. El video NO
se descarga ni se procesa: se derivan fotogramas por URL de Cloudinary
(transformación so_<segundos> + extensión .jpg) y esos fotogramas entran al
mismo modelo de visión con un prompt específico de reels.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

REVISION_SYSTEM_PROMPT = """Eres el revisor de contenido de Aremko Spa Boutique (Puerto Varas, Chile). Angélica, la community manager, te sube el material (foto o imágenes de un carrusel/historia) que preparó para una publicación, junto con el copy que debe acompañarla. Tu trabajo es revisarlo contra el manual de marca y devolverle correcciones CONCRETAS y accionables, como un director creativo que la quiere ayudar a publicar algo bueno — no elogios vacíos.

QUÉ REVISAR (checklist Aremko):
1. FORMATO SEGÚN EL CANAL (revísalo SIEMPRE, es de lo más importante): el contexto te dice el canal y tipo de la pieza. Te doy las DIMENSIONES REALES de cada foto (ancho×alto en px, medidas al subir) — ÚSALAS, son exactas; NO estimes la proporción a ojo.
   - "story" (Instagram Stories): DEBE ser VERTICAL, proporción 9:16 (1080×1920 aprox). Si las dimensiones reales dan horizontal o cuadrada, publicada como historia saldría con bandas o recortada — es una corrección CRÍTICA. Dile que la reencuadre o tome/elija una vertical.
   - "carrusel" o "post" (feed de Instagram): idealmente CUADRADA (1:1) o VERTICAL (4:5, 1080×1350). Una horizontal 16:9 se ve chica en el feed.
   - Si para alguna imagen dice "dimensiones no disponibles", ahí sí evalúa con cautela y dilo como observación, no como crítica tajante.
2. Espacio para el texto que va encima: esta pieza lleva un texto sobrepuesto (viene en el copy, campo texto_sugerido o caption). ¿Hay una zona despejada y de contraste suficiente en la foto para poner ese texto y que se lea? Si el texto caería sobre una zona cargada o clara donde no se leería, márcalo y sugiere dónde ubicarlo.
3. Gancho visual: ¿la imagen atrae en el primer vistazo? ¿lo más potente está a la vista o escondido? Una foto que abre con el logo o algo genérico "hace scrollear".
4. Texto legible: si la imagen ya lleva texto sobrepuesto, ¿se lee bien sobre el fondo? (texto claro sobre zonas claras = ilegible).
5. Foto real vs genérica: el manual EXIGE fotos reales del lugar (tina humeando, río Pescado, bosque, vapor). Stock genérico o fotos que podrían ser de cualquier spa = alerta.
6. Coherencia con el copy: ¿la imagen muestra lo que el copy promete? (si el copy habla del Ritual del Río de noche, una foto de día no calza).
7. Voz de marca en cualquier texto de la imagen: PROHIBIDO "experiencia única", "magia", "momentos inolvidables", "lujo inigualable". Datos exactos siempre (precios, 38-39°C, hasta medianoche).
8. Encuadre y calidad: ¿está derecha, enfocada, bien iluminada? ¿el sujeto principal se entiende?
9. Diferenciadores visibles: si aplica, ¿se ve lo que hace única a Aremko? (el río al lado, el vapor, la privacidad, la noche).

SEVERIDAD:
- "critico": rompe la publicación, hay que corregirlo sí o sí antes de publicar.
- "importante": la mejora bastante, muy recomendable.
- "menor": detalle fino, opcional.

REGLAS:
- Español latinoamericano, cercano, directo (le hablas a Angélica de "tú").
- Cada corrección debe ser ESPECÍFICA a lo que ves en la imagen, no genérica. "Mejorar la foto" es inútil; "la tina está a la izquierda y el texto la tapa, muévelo abajo" sirve.
- Si el material está bien, dilo — no inventes problemas. Un veredicto "aprobado" con 0 correcciones críticas es válido y deseable.
- Sé honesto pero alentador. Ella hizo el trabajo; tú la ayudas a pulirlo.

FORMATO DE SALIDA: JSON estricto, sin markdown, con esta forma EXACTA:
{
  "veredicto": "aprobado" | "con_observaciones",
  "resumen": "1-2 frases: qué tal quedó y el próximo paso.",
  "correcciones": [
    {"aspecto": "nombre corto del punto", "severidad": "critico|importante|menor", "encontrado": "qué viste en la imagen", "correccion": "qué hacer, específico"}
  ]
}
Si no hay nada que corregir, "correcciones" es una lista vacía y "veredicto" es "aprobado"."""


REVISION_VIDEO_SYSTEM_PROMPT = """Eres el revisor de reels de Aremko Spa Boutique (Puerto Varas, Chile). Angélica, la community manager, subió un CLIP DE VIDEO para una publicación — un micro-clip de una toma del reel, o el reel completo. Tú NO ves el video en movimiento: ves FOTOGRAMAS extraídos a segundos conocidos (te digo cuáles), en orden. Con eso la ayudas como director creativo a publicar algo bueno — correcciones concretas, no elogios vacíos.

CONTEXTO QUE RECIBES: el copy de la pieza y, si es el clip de una toma, la DESCRIPCIÓN de esa toma y el PROMPT DE VIDEO IA con que se generó (estos clips suelen ser una foto real del lugar animada por una IA image-to-video).

QUÉ REVISAR (checklist reels Aremko):
1. FORMATO (usa las dimensiones REALES que te doy, medidas al subir — NO las estimes): un reel DEBE ser VERTICAL 9:16 (1080×1920 aprox). Horizontal o cuadrado = corrección CRÍTICA (saldría con bandas o recortado).
2. MARCA DE AGUA — CRÍTICO, búscala en TODOS los fotogramas, especialmente esquinas:
   - Logo o watermark de OTRA red social: un reel para Instagram con marca de TikTok (o al revés — el contexto te dice el canal de ESTA pieza) es rechazo inmediato; el algoritmo entierra ese contenido.
   - Watermark de la herramienta de IA (Higgsfield, Kling, Veo, Sora u otra): también CRÍTICO — hay que regenerar o exportar sin marca.
3. FIDELIDAD A LA TOMA (cuando te doy descripción/prompt de la toma): ¿el clip muestra la escena pedida? El estilo Aremko PROHÍBE que la IA invente: si aparecen personas, objetos o elementos que no corresponden a la escena real, o el lugar no parece Aremko, márcalo CRÍTICO.
4. ARTEFACTOS DE IA: deformaciones, morphing raro, manos o caras derretidas, agua o vapor con física imposible, texturas que cambian sin sentido entre fotogramas. Di en qué fotograma (segundo) lo viste.
5. GANCHO: si es el clip 1 (apertura) o el reel completo, los fotogramas de los primeros 3 segundos deben atrapar — lo más potente a la vista (la tina humeando, el río, la noche), no un logo ni algo genérico que "hace scrollear".
6. TEXTO SOBREPUESTO: si hay overlays, ¿se leen bien sobre el fondo? ¿respetan las zonas seguras? (abajo va el caption y a la derecha los botones de IG/TikTok — texto pegado a esos bordes queda tapado).
7. LUGAR REAL: debe verse Aremko de verdad (tina humeando, río Pescado, bosque, vapor, la noche). Stock genérico o un spa cualquiera = alerta.
8. VOZ DE MARCA en cualquier texto visible: PROHIBIDO "experiencia única", "magia", "momentos inolvidables", "lujo inigualable". Datos exactos siempre (precios, 38-39°C, hasta medianoche).
9. COHERENCIA CON EL GUION: el reel tiene guion por bloques (gancho/contexto/moraleja/solución/CTA). ¿Lo que se ve calza con la parte que le toca a este clip?

LIMITACIÓN HONESTA: solo ves fotogramas — NO evalúes ritmo, transiciones, música ni audio, y no inventes problemas que no se puedan ver en un fotograma.

SEVERIDAD:
- "critico": rompe la publicación, hay que corregirlo sí o sí antes de publicar.
- "importante": la mejora bastante, muy recomendable.
- "menor": detalle fino, opcional.

REGLAS:
- Español latinoamericano, cercano, directo (le hablas a Angélica de "tú").
- Cada corrección ESPECÍFICA a lo que ves, citando el segundo del fotograma cuando aplique. "Mejorar el clip" es inútil; "en el fotograma del segundo 4 el vapor se deforma en espiral antinatural, regenera con el mismo prompt" sirve.
- Si el clip está bien, dilo — un veredicto "aprobado" con 0 correcciones es válido y deseable.
- Sé honesta pero alentadora. Ella hizo el trabajo; tú la ayudas a pulirlo.

FORMATO DE SALIDA: JSON estricto, sin markdown, con esta forma EXACTA:
{
  "veredicto": "aprobado" | "con_observaciones",
  "resumen": "1-2 frases: qué tal quedó y el próximo paso.",
  "correcciones": [
    {"aspecto": "nombre corto del punto", "severidad": "critico|importante|menor", "encontrado": "qué viste (y en qué segundo)", "correccion": "qué hacer, específico"}
  ]
}
Si no hay nada que corregir, "correcciones" es una lista vacía y "veredicto" es "aprobado"."""


# ---------------------------------------------------------------------------
# Video (H-065 / H-066 F2): fotogramas por transformación URL de Cloudinary.
# ---------------------------------------------------------------------------

_EXTENSIONES_VIDEO = ('.mp4', '.mov')


def _es_video_url(url) -> bool:
    """True si la URL apunta a un video (por extensión, ignorando querystring)."""
    if not isinstance(url, str):
        return False
    return url.lower().split('?')[0].endswith(_EXTENSIONES_VIDEO)


def _offsets_para(duration, nivel: str = 'clip') -> list:
    """Segundos a los que se extraen fotogramas. 'clip' (micro-video de una
    toma): 0, 1, mitad y final−0.5 — tope 5. 'reel' (video completo): 0, 1, 3
    (ventana del gancho, densa), luego cada 5s y el último medio segundo (el
    CTA) — tope 10; si hay que recortar, el último fotograma SIEMPRE queda.
    Sin duración conocida se muestrean solo los primeros segundos."""
    try:
        d = float(duration or 0)
    except (TypeError, ValueError):
        d = 0.0
    if d <= 0:
        return [0, 1, 3] if nivel == 'reel' else [0, 1]

    if nivel == 'reel':
        candidatos = [0, 1, 3] + [float(s) for s in range(5, int(d), 5)] + [d - 0.5]
        tope = 10
    else:
        candidatos = [0, 1, d / 2, d - 0.5]
        tope = 5

    vistos, offsets = set(), []
    for c in candidatos:
        c = round(max(0.0, min(c, max(d - 0.1, 0.0))), 1)
        if c not in vistos:
            vistos.add(c)
            offsets.append(c)
    offsets.sort()
    if len(offsets) > tope:
        offsets = offsets[:tope - 1] + [offsets[-1]]
    return offsets


def _urls_frames_video(video_url: str, duration, nivel: str = 'clip') -> tuple:
    """(urls_jpg, offsets): fotogramas derivados del video SIN ffmpeg — se
    inserta so_<segundos>,w_720,q_auto en /upload/ y se cambia la extensión a
    .jpg (mismo patrón que los posters de hero_video en templates). Solo aplica
    a URLs de Cloudinary con /upload/; para otras devuelve ([], [])."""
    if '/upload/' not in (video_url or ''):
        return [], []
    limpio = video_url.split('?')[0]
    base = limpio.rsplit('.', 1)[0] if _es_video_url(limpio) else limpio
    offsets = _offsets_para(duration, nivel)
    urls = [
        base.replace('/upload/', f'/upload/so_{off:g},w_720,q_auto/', 1) + '.jpg'
        for off in offsets
    ]
    return urls, offsets


def _describir_video(meta: dict, offsets: list) -> str:
    """Los HECHOS del video (medidos al subir, no estimados): dimensiones,
    orientación, duración y a qué segundo corresponde cada fotograma adjunto."""
    m = meta or {}
    lineas = []
    w, h = m.get('width'), m.get('height')
    if w and h:
        ratio = m.get('ratio') or f'{w / h:.2f}'
        orient = m.get('orientacion') or ''
        lineas.append(f'- Video: {w}×{h} px → {orient} ({ratio}).')
    else:
        lineas.append('- Video: dimensiones no disponibles (evalúa el formato con cautela y dilo como observación).')
    if m.get('duration'):
        lineas.append(f'- Duración real: {m["duration"]:g} segundos.')
    if offsets:
        lineas.append('- Fotogramas adjuntos (en orden), tomados a los segundos: '
                      + ', '.join(f'{o:g}' for o in offsets) + '.')
    return '\n'.join(lineas)


def _describir_formatos(image_urls: list, material_meta: list) -> str:
    """Texto con las dimensiones REALES de cada foto (medidas al subir, no a
    ojo). Para que el chequeo de formato del modelo sea exacto."""
    by_url = {m.get('url'): m for m in (material_meta or []) if isinstance(m, dict)}
    lineas = []
    for i, u in enumerate(image_urls, start=1):
        m = by_url.get(u) or {}
        w, h = m.get('width'), m.get('height')
        if w and h:
            ratio = m.get('ratio') or f'{w / h:.2f}'
            orient = m.get('orientacion') or ''
            lineas.append(f'- Imagen {i}: {w}×{h} px → {orient} ({ratio}).')
        else:
            lineas.append(f'- Imagen {i}: dimensiones no disponibles (evalúa el formato a ojo con cautela).')
    return '\n'.join(lineas)


def _build_user_content(copy_json: dict, image_urls: list, titulo: str, canal: str,
                        tipo: str, material_meta: list = None) -> list:
    """Arma el content multimodal: texto del contexto + las imágenes."""
    contexto = {
        "pieza": titulo,
        "canal": canal,
        "tipo": tipo,
        "copy_que_acompaña": copy_json,
    }
    content = [
        {
            "type": "text",
            "text": (
                "Revisa el material que subió Angélica para esta publicación. "
                "Contexto y copy de la pieza:\n\n"
                + json.dumps(contexto, ensure_ascii=False, indent=2)
                + "\n\nDIMENSIONES REALES de cada foto (medidas al subir — usa ESTO para el "
                  "chequeo de formato, NO lo estimes a ojo):\n"
                + _describir_formatos(image_urls, material_meta)
                + f"\n\nSe adjuntan {len(image_urls)} imagen(es). Devuelve el JSON de revisión."
            ),
        }
    ]
    for u in image_urls:
        content.append({"type": "image_url", "image_url": {"url": u}})
    return content


def _chat_vision(system_prompt: str, content: list) -> dict:
    """Núcleo compartido foto/video: llamada al modelo con visión + parseo del
    JSON de revisión. Best-effort: cualquier fallo devuelve 'sin_revisar' — la
    revisión nunca rompe la subida. No persiste nada."""
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    # Modelo dedicado SOLO a esta revisión (no lo comparte con el brief ni con
    # Luna); debe soportar visión. Override por env sin tocar código.
    model = getattr(settings, 'MARKETING_REVISION_LLM_MODEL', 'google/gemini-2.5-pro')

    if not api_key:
        logger.warning('_chat_vision: OPENROUTER_API_KEY no configurada')
        return {"veredicto": "sin_revisar", "resumen": "Revisión no disponible (falta configuración).", "correcciones": []}

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': content},
            ],
            temperature=0.4,
            max_tokens=2000,
            response_format={'type': 'json_object'},
        )
        raw = resp.choices[0].message.content or ''
        cleaned = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        data = json.loads(cleaned)
    except Exception as exc:  # noqa: BLE001 — la revisión nunca rompe la subida
        logger.error(f'_chat_vision: falló la revisión IA ({exc})')
        return {"veredicto": "sin_revisar",
                "resumen": "No se pudo completar la revisión automática. Puedes publicar igual o volver a intentar.",
                "correcciones": []}

    veredicto = data.get('veredicto') or 'con_observaciones'
    if veredicto not in ('aprobado', 'con_observaciones'):
        veredicto = 'con_observaciones'
    return {"veredicto": veredicto, "resumen": data.get('resumen') or '', "correcciones": data.get('correcciones') or []}


def _run_review(copy_para_revisar, image_urls, material_meta, titulo, canal, tipo) -> dict:
    """Revisión de FOTOS: arma el content multimodal y llama al modelo. Devuelve
    {veredicto, resumen, correcciones}; no persiste nada — el caller decide
    dónde guardar (publicación o segmento)."""
    content = _build_user_content(copy_para_revisar, image_urls, titulo, canal, tipo, material_meta=material_meta or [])
    return _chat_vision(REVISION_SYSTEM_PROMPT, content)


def _run_review_video(contexto: dict, video_url: str, meta: dict, titulo: str,
                      canal: str, tipo: str, nivel: str = 'clip') -> dict:
    """Revisión de VIDEO (H-065/H-066 F2) vía sus fotogramas derivados por URL.
    `contexto` es el dict específico del caller (toma+prompt del clip, o el copy
    completo del reel); `meta` el item de material_meta del video (trae la
    duración). Mismo modelo y formato de salida que las fotos; no persiste."""
    frame_urls, offsets = _urls_frames_video(video_url, (meta or {}).get('duration'), nivel)
    if not frame_urls:
        return {"veredicto": "sin_revisar",
                "resumen": "No se pudieron derivar fotogramas del video (URL no reconocida).",
                "correcciones": []}

    contexto_full = {"pieza": titulo, "canal": canal, "tipo": tipo, **(contexto or {})}
    content = [
        {
            "type": "text",
            "text": (
                "Revisa este clip de video que subió Angélica (ves sus fotogramas, en orden). "
                "Contexto y copy de la pieza:\n\n"
                + json.dumps(contexto_full, ensure_ascii=False, indent=2)
                + "\n\nHECHOS DEL VIDEO (medidos al subir — usa ESTO para el chequeo de formato "
                  "y duración, NO lo estimes a ojo):\n"
                + _describir_video(meta, offsets)
                + f"\n\nSe adjuntan {len(frame_urls)} fotograma(s). Devuelve el JSON de revisión."
            ),
        }
    ]
    for u in frame_urls:
        content.append({"type": "image_url", "image_url": {"url": u}})
    return _chat_vision(REVISION_VIDEO_SYSTEM_PROMPT, content)


def _meta_de_url(material_meta, url: str) -> dict:
    """El item de material_meta que corresponde a `url` (el más reciente)."""
    for m in reversed(list(material_meta or [])):
        if isinstance(m, dict) and m.get('url') == url:
            return m
    return {}


def revisar_material(publicacion) -> dict:
    """Revisa el material ya subido de una publicación (nivel publicación).
    Fotos → rama de imágenes; si lo último subido es un video (reel completo,
    H-065) → rama de fotogramas. Persiste en revision_*. Best-effort."""
    from django.utils import timezone

    urls = [u for u in (publicacion.material_urls or []) if isinstance(u, str) and u.startswith('http')]
    if not urls:
        return {"veredicto": "sin_revisar", "resumen": "No hay material para revisar.", "correcciones": []}

    titulo = publicacion.titulo or publicacion.pieza_key
    if _es_video_url(urls[-1]):
        # El último video subido es la versión vigente del reel; los anteriores
        # (fotos o videos viejos) no se re-revisan.
        video_url = urls[-1]
        contexto = {
            'copy_que_acompaña': publicacion.copy_json or {},
            '_nota': 'Es el reel COMPLETO (no un clip suelto): revisa el gancho de los '
                     'primeros segundos, el formato, la marca de agua y la coherencia '
                     'con el guion completo.',
        }
        r = _run_review_video(
            contexto, video_url, _meta_de_url(publicacion.material_meta, video_url),
            titulo, publicacion.canal, publicacion.tipo, nivel='reel',
        )
    else:
        image_urls = [u for u in urls if not _es_video_url(u)]
        r = _run_review(
            publicacion.copy_json or {}, image_urls, publicacion.material_meta or [],
            titulo, publicacion.canal, publicacion.tipo,
        )
    _guardar(publicacion, r['veredicto'], r['resumen'], r['correcciones'], timezone)
    return r


def revisar_segmento(publicacion, indice: int) -> dict:
    """Revisa el material de UN segmento contra su propio contenido: la foto de
    una historia contra su texto, o (H-066 F2) el micro-clip de una toma de reel
    contra su descripción y su prompt_video_ia. Persiste en el segmento."""
    from django.utils import timezone

    segmentos = publicacion.segmentos or []
    seg = next((s for s in segmentos if isinstance(s, dict) and s.get('indice') == indice), None)
    if seg is None:
        return {"veredicto": "sin_revisar", "resumen": "Segmento no encontrado.", "correcciones": []}

    urls = [u for u in (seg.get('material_urls') or []) if isinstance(u, str) and u.startswith('http')]
    if not urls:
        return {"veredicto": "sin_revisar", "resumen": "No hay material para revisar.", "correcciones": []}

    titulo_seg = seg.get('titulo') or f'#{indice}'
    titulo = f"{publicacion.titulo or publicacion.pieza_key} · {titulo_seg}"
    if _es_video_url(urls[-1]):
        # Rama video: el último video subido es la versión vigente del clip.
        video_url = urls[-1]
        copy_json = publicacion.copy_json or {}
        contexto = {
            'clip': titulo_seg,
            'descripcion_de_esta_toma': seg.get('texto') or '',
            'prompt_video_ia_de_esta_toma': seg.get('prompt_video_ia') or '',
            'duracion_objetivo_reel_segundos': copy_json.get('duracion_objetivo_segundos'),
            'guion_del_reel': copy_json.get('guion') or [],
            '_nota': f'Revisa SOLO este clip ({titulo_seg}), una de las tomas que componen el '
                     'reel: fidelidad a su descripción y su prompt, formato, marca de agua y '
                     'artefactos de IA. No lo juzgues contra las otras tomas.',
        }
        r = _run_review_video(
            contexto, video_url, _meta_de_url(seg.get('material_meta'), video_url),
            titulo, publicacion.canal, publicacion.tipo, nivel='clip',
        )
    else:
        image_urls = [u for u in urls if not _es_video_url(u)]
        copy_seg = {
            'segmento': titulo_seg,
            'texto_de_este_segmento': seg.get('texto') or '',
            '_nota': f'Revisa SOLO este segmento ({titulo_seg}): si la foto corresponde a lo que '
                     'dice este texto, el formato correcto para el canal (usa las dimensiones reales) '
                     'y la calidad. No la juzgues contra otros segmentos.',
        }
        r = _run_review(
            copy_seg, image_urls, seg.get('material_meta') or [],
            titulo, publicacion.canal, publicacion.tipo,
        )
    seg['revision_veredicto'] = r['veredicto']
    seg['revision_resumen'] = r['resumen']
    seg['revision_json'] = r['correcciones']
    seg['revision_at'] = timezone.now().isoformat()
    publicacion.segmentos = segmentos
    publicacion.save(update_fields=['segmentos', 'updated_at'])
    return r


def _guardar(publicacion, veredicto, resumen, correcciones, timezone):
    publicacion.revision_veredicto = veredicto
    publicacion.revision_resumen = resumen
    publicacion.revision_json = correcciones
    publicacion.revision_at = timezone.now()
    publicacion.save(update_fields=[
        'revision_veredicto', 'revision_resumen', 'revision_json', 'revision_at', 'updated_at',
    ])
