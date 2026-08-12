# -*- coding: utf-8 -*-
"""Capturas del celular → líneas para pegar (P-22, pedido de Jorge 2026-08-12).

La CuentaRUT no da export: sus movimientos se pegan a mano. Hasta hoy eso
significaba que Jorge me mandaba la captura por chat y yo le devolvía el
bloque de texto. Esto hace el mismo trabajo dentro del sistema.

DECISIÓN DE DISEÑO: la captura NO escribe movimientos. Llena el mismo cuadro
de texto que se pega a mano, y de ahí sigue el circuito de dos golpes que ya
existe (propuesta con estados → confirmación). Motivos:

  · Un modelo leyendo números puede equivocarse en un dígito, y el lugar más
    fácil para cazar eso es el texto, antes de que sea un movimiento.
  · Jorge corrige la línea ahí mismo si hace falta.
  · Nada nuevo que aprender: es la pantalla que ya usa.

El riesgo real no es que invente un movimiento, es que lea mal un monto: en
Chile «$22.316» son veintidós mil, no veintidós con decimales. Eso está dicho
en el prompt con todas las letras y verificado con capturas reales.
"""
import base64
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

MAX_BYTES = 8 * 1024 * 1024          # una captura de celular pesa ~1-3 MB
MAX_CAPTURAS = 8                     # una cartola larga son varias pantallas
EXTENSIONES = ('.png', '.jpg', '.jpeg', '.webp', '.heic')

_PROMPT = """Eres un lector de cartolas bancarias chilenas. Te paso capturas de
pantalla de la app del banco y devuelves SOLO los movimientos, uno por línea,
en este formato exacto:

DD-MM-AAAA ; glosa ; monto

Reglas que no puedes romper:

1. FORMATO CHILENO DE MONTOS: el punto es separador de MILES, no decimal.
   «$22.316» es 22316. «-$119.443» es -119443. «$588.136» es 588136.
   Nunca escribas puntos ni comas en el monto que devuelves: solo dígitos y,
   si corresponde, el signo menos.
2. SIGNO: los cargos (dinero que SALE, en rojo o con menos) van NEGATIVOS.
   Los abonos (dinero que ENTRA, en verde) van POSITIVOS, sin signo.
3. FECHA: la app agrupa los movimientos bajo un encabezado de fecha
   («martes, 4 de agosto de 2026»). Cada movimiento hereda la fecha del
   encabezado que tiene encima. Devuélvela como DD-MM-AAAA.
4. GLOSA: copia la descripción TAL CUAL aparece, sin traducir, sin abreviar y
   sin agregarle la hora ni el saldo.
5. NO INVENTES. Si una línea está cortada, borrosa o no estás seguro del
   monto, NO la incluyas: agrégala al final como comentario empezando con
   «# dudosa: ». Es preferible que falte un movimiento a que entre uno mal.
6. Ignora todo lo que no sea un movimiento: saldos, botones, filtros,
   encabezados de la app, la hora del teléfono, la batería.
7. Si la misma captura muestra un movimiento dos veces (por el scroll), va
   UNA sola vez. Pero dos movimientos iguales el mismo día a horas distintas
   son DOS movimientos reales: van los dos.

Devuelve únicamente las líneas. Sin explicaciones, sin encabezados, sin
markdown, sin ```."""

# Una línea válida: fecha ; algo ; número entero con signo opcional.
_LINEA = re.compile(r'^\s*\d{2}-\d{2}-\d{4}\s*;[^;]+;\s*-?\d+\s*$')


def _modelo():
    """Modelo con visión. Override por env, sin tocar código."""
    return getattr(settings, 'FINANZAS_VISION_MODEL',
                   getattr(settings, 'MARKETING_REVISION_LLM_MODEL',
                           'google/gemini-2.5-pro'))


def validar_capturas(archivos):
    """(ok, error). Rechaza antes de gastar una llamada al modelo."""
    if not archivos:
        return False, 'No subiste ninguna captura.'
    if len(archivos) > MAX_CAPTURAS:
        return False, (f'Son {len(archivos)} capturas y el tope es '
                       f'{MAX_CAPTURAS}. Subilas en dos tandas.')
    for f in archivos:
        nombre = (f.name or '').lower()
        if not nombre.endswith(EXTENSIONES):
            return False, (f'«{f.name}» no parece una imagen. Se esperan '
                           f'{", ".join(EXTENSIONES)}.')
        if f.size > MAX_BYTES:
            return False, (f'«{f.name}» pesa {f.size // (1024 * 1024)} MB y el '
                           f'tope es {MAX_BYTES // (1024 * 1024)} MB.')
    return True, ''


def _a_data_uri(archivo):
    archivo.seek(0)
    crudo = archivo.read()
    archivo.seek(0)
    nombre = (archivo.name or '').lower()
    mime = 'image/png' if nombre.endswith('.png') else 'image/jpeg'
    return f'data:{mime};base64,{base64.b64encode(crudo).decode()}'


def limpiar_salida(texto):
    """Deja SOLO las líneas con forma de movimiento; el resto va como aviso.

    El modelo a veces agrega un «Aquí están los movimientos:» o envuelve todo
    en markdown. Filtrar acá —y no confiar en que obedeció— es lo que hace que
    la salida se pueda pegar sin editar.
    """
    lineas, descartes = [], []
    for cruda in (texto or '').splitlines():
        linea = cruda.strip().strip('`').strip()
        if not linea:
            continue
        if _LINEA.match(linea):
            lineas.append(linea)
        elif linea.startswith('#'):
            # «# dudosa: monto ilegible» → «monto ilegible»: el prefijo es el
            # protocolo con el modelo, no algo que Jorge tenga que leer.
            aviso = linea.lstrip('# ').strip()
            if aviso.lower().startswith('dudosa:'):
                aviso = aviso[len('dudosa:'):].strip()
            descartes.append(aviso)
    return '\n'.join(lineas), descartes


def leer_capturas(archivos):
    """Capturas → (texto_para_pegar, avisos, error).

    Nunca levanta: cualquier problema vuelve como `error` legible, porque esto
    corre dentro de una vista que Jorge usa desde el celular.
    """
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        return '', [], ('Falta configurar OPENROUTER_API_KEY: por ahora pegá '
                        'los movimientos a mano.')

    contenido = [{'type': 'text',
                  'text': 'Extrae los movimientos de estas capturas.'}]
    for archivo in archivos:
        contenido.append({'type': 'image_url',
                          'image_url': {'url': _a_data_uri(archivo)}})

    try:
        cliente = OpenAI(
            api_key=api_key,
            base_url=getattr(settings, 'OPENROUTER_BASE_URL',
                             'https://openrouter.ai/api/v1'))
        resp = cliente.chat.completions.create(
            model=_modelo(),
            messages=[{'role': 'system', 'content': _PROMPT},
                      {'role': 'user', 'content': contenido}],
            temperature=0,          # transcribir, no redactar
            max_tokens=3000,
        )
        crudo = (resp.choices[0].message.content or '').strip()
    except Exception as exc:  # noqa: BLE001
        logger.exception('[finanzas] no se pudo leer la captura: %s', exc)
        return '', [], ('No pude leer la captura. Probá de nuevo, o pegá los '
                        'movimientos a mano.')

    texto, dudosas = limpiar_salida(crudo)
    if not texto:
        return '', dudosas, ('No encontré movimientos en la captura. ¿Es la '
                             'pantalla de «Saldos y movimientos»?')
    logger.info('[finanzas] captura leída: %s líneas, %s dudosas',
                len(texto.splitlines()), len(dudosas))
    return texto, dudosas, ''
