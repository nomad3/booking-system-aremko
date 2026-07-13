"""Revisor IA del material que sube el community manager (Fase 2).

Recibe las imágenes (URLs públicas de Cloudinary) de una pieza + su copy +
el checklist derivado del playbook, y devuelve correcciones estructuradas —
mismo formato que la guía de Angélica: aspecto, severidad, qué encontró,
qué corregir.

Modelo con visión vía OpenRouter (SDK de OpenAI, mismo camino que el brief).
Configurable con MARKETING_REVISION_LLM_MODEL (default: un Gemini flash con
visión, barato). Best-effort: si falla, se devuelve un veredicto de error y
la pieza queda 'sin_revisar' — nunca rompe el flujo de subida.

Alcance Fase 2: fotos, carruseles e historias (imágenes). El video (reels)
es una fase posterior (extracción de fotogramas).
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


def _run_review(copy_para_revisar, image_urls, material_meta, titulo, canal, tipo) -> dict:
    """Llama al modelo con visión y devuelve {veredicto, resumen, correcciones}.
    Best-effort: cualquier fallo devuelve un veredicto 'sin_revisar'. No persiste
    nada — el caller decide dónde guardar (publicación o segmento)."""
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    # Modelo de MÁXIMA calidad visual, dedicado SOLO a esta revisión (no lo
    # comparte con el brief ni con Luna). Gemini 2.5 Pro es el más fuerte en
    # razonamiento espacial/composición vía OpenRouter; el costo a ~10-20
    # fotos/semana es de centavos. Override por env si algún día se quiere
    # cambiar sin tocar código.
    model = getattr(settings, 'MARKETING_REVISION_LLM_MODEL', 'google/gemini-2.5-pro')

    if not api_key:
        logger.warning('_run_review: OPENROUTER_API_KEY no configurada')
        return {"veredicto": "sin_revisar", "resumen": "Revisión no disponible (falta configuración).", "correcciones": []}

    content = _build_user_content(copy_para_revisar, image_urls, titulo, canal, tipo, material_meta=material_meta or [])

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': REVISION_SYSTEM_PROMPT},
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
        logger.error(f'_run_review: falló la revisión IA ({exc})')
        return {"veredicto": "sin_revisar",
                "resumen": "No se pudo completar la revisión automática. Puedes publicar igual o volver a intentar.",
                "correcciones": []}

    veredicto = data.get('veredicto') or 'con_observaciones'
    if veredicto not in ('aprobado', 'con_observaciones'):
        veredicto = 'con_observaciones'
    return {"veredicto": veredicto, "resumen": data.get('resumen') or '', "correcciones": data.get('correcciones') or []}


def revisar_material(publicacion) -> dict:
    """Revisa las imágenes ya subidas de una publicación (nivel publicación,
    piezas de una sola imagen). Persiste en revision_*. Best-effort."""
    from django.utils import timezone

    image_urls = [u for u in (publicacion.material_urls or []) if isinstance(u, str) and u.startswith('http')]
    if not image_urls:
        return {"veredicto": "sin_revisar", "resumen": "No hay material para revisar.", "correcciones": []}

    r = _run_review(
        publicacion.copy_json or {}, image_urls, publicacion.material_meta or [],
        publicacion.titulo or publicacion.pieza_key, publicacion.canal, publicacion.tipo,
    )
    _guardar(publicacion, r['veredicto'], r['resumen'], r['correcciones'], timezone)
    return r


def revisar_segmento(publicacion, indice: int) -> dict:
    """Revisa la foto de UNA historia contra el texto de ESA historia (evalúa
    correspondencia foto↔contenido de ese segmento). Persiste en el segmento."""
    from django.utils import timezone

    segmentos = publicacion.segmentos or []
    seg = next((s for s in segmentos if isinstance(s, dict) and s.get('indice') == indice), None)
    if seg is None:
        return {"veredicto": "sin_revisar", "resumen": "Segmento no encontrado.", "correcciones": []}

    image_urls = [u for u in (seg.get('material_urls') or []) if isinstance(u, str) and u.startswith('http')]
    if not image_urls:
        return {"veredicto": "sin_revisar", "resumen": "No hay material para revisar.", "correcciones": []}

    titulo_seg = seg.get('titulo') or f'#{indice}'
    copy_seg = {
        'segmento': titulo_seg,
        'texto_de_este_segmento': seg.get('texto') or '',
        '_nota': f'Revisa SOLO este segmento ({titulo_seg}): si la foto corresponde a lo que '
                 'dice este texto, el formato correcto para el canal (usa las dimensiones reales) '
                 'y la calidad. No la juzgues contra otros segmentos.',
    }
    r = _run_review(
        copy_seg, image_urls, seg.get('material_meta') or [],
        f"{publicacion.titulo or publicacion.pieza_key} · {titulo_seg}",
        publicacion.canal, publicacion.tipo,
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
