"""Preguntarle a un modelo que decide, no que escribe (encargo PROMPT_JEV_AREMKO.md, etapa 2).

Un modelo de decisión (hoy Jev, `typesafe/jev-1.13`) recibe un estado —un texto, una
estructura— y un mapa de preguntas con su tipo, y devuelve la opción elegida con su
probabilidad. No conversa ni redacta: para eso está el modelo de Luna.

Portado de Datamatic Hospitality (`apps/decisiones/decidir.py`, en producción). Sin
empresa ni funcionalidades por cliente: Aremko no es multi-tenant.

Tres reglas que hacen que se pueda enchufar sin miedo:

1. **Nunca rompe lo que ya funciona.** Si el proveedor no responde, tarda de más,
   cambia de formato, falta la llave o algo explota, `decidir()` devuelve None y quien
   llama sigue exactamente como antes. None no es un error: es «hoy no hay opinión».
2. **Un solo lugar sabe con quién hablamos.** El resto del código llama a `decidir()`.
3. **Lo mismo no se pregunta dos veces.** Misma entrada y mismas preguntas → caché de
   12 h. Barato igual, pero sobre todo estable: la misma corrección no puede quedar
   clasificada distinto en dos pasadas de la misma corrida.
"""
import hashlib
import json
import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

# La ruta está en ALFA: el nombre del modelo y la URL van a cambiar. Por eso los tres
# valores se leen en cada llamada y no al importar: cambiarlos es tocar una variable de
# entorno en Render, no desplegar.
RUTA_POR_DEFECTO = 'https://openrouter.ai/api/alpha/decisions'
MODELO_POR_DEFECTO = 'typesafe/jev-1.13'
ESPERA_POR_DEFECTO = 2.0
HORAS_CACHE = 12


def _ruta():
    return getattr(settings, 'DECISIONES_RUTA', '') or RUTA_POR_DEFECTO


def _modelo():
    return getattr(settings, 'DECISIONES_MODELO', '') or MODELO_POR_DEFECTO


def _espera():
    try:
        return float(getattr(settings, 'DECISIONES_ESPERA_SEG', 0) or ESPERA_POR_DEFECTO)
    except (TypeError, ValueError):
        return ESPERA_POR_DEFECTO


class Respuesta:
    """Lo que decidió el modelo, ya usable: `.opcion()`, `.numero()`, `.si_no()`."""

    def __init__(self, datos):
        self.crudo = datos or {}
        self.respuestas = self.crudo.get('answers') or {}
        self.modelo = self.crudo.get('model') or ''
        self.costo = (self.crudo.get('usage') or {}).get('cost')

    def opcion(self, clave, por_defecto=None):
        return (self.respuestas.get(clave) or {}).get('choice', por_defecto)

    def numero(self, clave, por_defecto=None):
        return (self.respuestas.get(clave) or {}).get('score', por_defecto)

    def si_no(self, clave, por_defecto=None):
        """La probabilidad de que la respuesta sea que sí, de 0 a 1."""
        return (self.respuestas.get(clave) or {}).get('noul', por_defecto)

    def confianza(self, clave):
        return (self.respuestas.get(clave) or {}).get('confidence')

    @property
    def confianza_media(self):
        valores = [r.get('confidence') for r in self.respuestas.values()
                   if isinstance(r, dict) and r.get('confidence') is not None]
        return sum(valores) / len(valores) if valores else None

    def resumen(self):
        """Lo que vale la pena guardar: la respuesta de cada pregunta, sin el ruido."""
        return {clave: {k: v for k, v in r.items()
                        if k in ('type', 'choice', 'score', 'noul', 'confidence')}
                for clave, r in self.respuestas.items() if isinstance(r, dict)}


def esta_disponible():
    """Si se puede decidir: hay llave de OpenRouter."""
    return bool(getattr(settings, 'OPENROUTER_API_KEY', ''))


def _clave_cache(estado, preguntas):
    crudo = json.dumps([estado, preguntas], ensure_ascii=False, sort_keys=True, default=str)
    return 'decision:' + hashlib.sha256(crudo.encode()).hexdigest()[:40]


def _llamar(estado, preguntas):
    """(datos, error). Nunca lanza. `datos` es None si no hubo una decisión legible."""
    try:
        r = requests.post(_ruta(), json={'model': _modelo(), 'state': estado,
                                         'questions': preguntas},
                          timeout=_espera(), headers={
                              'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                              'Content-Type': 'application/json'})
        if r.status_code >= 400:
            return None, f'HTTP {r.status_code}'
        datos = r.json()
    except requests.Timeout:
        return None, 'se demoró más de lo aceptable'
    except ValueError:
        return None, 'respuesta ilegible'
    except requests.RequestException as e:
        return None, type(e).__name__
    except Exception as e:  # noqa: BLE001 — nunca lanza: «hoy no hay opinión»
        return None, type(e).__name__
    # Un JSON válido pero sin decisiones es un cambio de formato (la ruta está en alfa):
    # se trata igual que una falla, no como una respuesta vacía.
    if not isinstance(datos, dict) or not isinstance(datos.get('answers'), dict) \
            or not datos['answers']:
        return None, 'respuesta sin decisiones'
    return datos, ''


def decidir(estado, preguntas, *, uso='', referencia='', guardar=True):
    """Devuelve una `Respuesta`, o None si no se pudo decidir. Nunca lanza.

    `estado` es lo que se mira (un texto o una estructura; conviene el contexto completo:
    con fragmentos sueltos la confianza cae a 0,45-0,55). `preguntas` es un mapa
    {clave: {type, instructions, criteria}} con tipos `choice`, `score` o `noul`.
    """
    if not preguntas or not esta_disponible():
        return None
    clave = _clave_cache(estado, preguntas)
    try:
        guardado = cache.get(clave)
    except Exception:  # noqa: BLE001
        guardado = None
    if guardado is not None:
        return Respuesta(guardado)

    inicio = time.monotonic()
    datos, error = _llamar(estado, preguntas)
    ms = int((time.monotonic() - inicio) * 1000)
    respuesta = Respuesta(datos) if datos else None
    if respuesta is not None:
        try:
            cache.set(clave, datos, HORAS_CACHE * 3600)
        except Exception:  # noqa: BLE001
            pass
        logger.info('Decisiones: %s · %s · confianza %.2f · %d ms', uso, respuesta.resumen(),
                    respuesta.confianza_media or 0, ms)
    else:
        logger.warning('Decisiones: %s sin decisión (%s, %d ms)', uso, error, ms)
    if guardar:
        _anotar(uso, referencia, respuesta, error, ms)
    return respuesta


def _anotar(uso, referencia, respuesta, error, ms):
    """Deja constancia. Nunca interrumpe: una decisión no se pierde por el registro. Va en
    su propio punto de guardado para no envenenar una transacción que esté abierta."""
    from .models import DecisionAgente

    try:
        with transaction.atomic():
            DecisionAgente.objects.create(
                uso=(uso or '')[:60], referencia=str(referencia or '')[:60],
                respuestas=respuesta.resumen() if respuesta else {},
                confianza=respuesta.confianza_media if respuesta else None,
                modelo=((respuesta.modelo if respuesta else '') or _modelo())[:80],
                costo_usd=respuesta.costo if respuesta and respuesta.costo is not None else None,
                duracion_ms=ms, error=(error or '')[:200])
    except Exception:  # noqa: BLE001
        logger.exception('Decisiones: no se pudo anotar la decisión de %s', uso)
