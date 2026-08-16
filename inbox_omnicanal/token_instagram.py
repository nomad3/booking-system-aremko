"""H-107: refresh automático del token de Instagram Login.

Contexto (caso real 2026-08-15): el token vivía SOLO como env var del backend Go en
Render y venció en silencio a los ~60 días — OAuthException 190 en plena conversación
con un cliente. Ahora la fuente de verdad es `InstagramTokenConfig` (editable en
admin) y el refresh es OPORTUNISTA: cuando el backend Go pide el token (lo hace todo
el día, la bandeja consulta constantemente) y el último refresh tiene más de
`UMBRAL_REFRESH_DIAS`, se refresca contra Meta antes de responder. Sin cron nuevo.

Reglas de Meta para `refresh_access_token` (ruta Instagram Login, graph.instagram.com):
- Solo refresca un token VÁLIDO (vencido no se puede: hay que generar uno nuevo en
  developers.facebook.com y pegarlo en el admin).
- El token debe tener al menos 24 h de antigüedad → por eso el umbral parte del
  momento en que se pegó (`token_actualizado_at`), nunca antes de 7 días.
- Devuelve un token NUEVO de ~60 días (`expires_in`); el viejo sigue válido hasta su
  vencimiento original, así que un refresh concurrente no rompe nada.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

UMBRAL_REFRESH_DIAS = 7   # refrescar cuando el token/refresh tiene más de esto
REINTENTO_HORAS = 6       # si el refresh falla, no martillar a Meta: reintentar cada 6 h
AVISO_CADA_HORAS = 24     # email de alerta como máximo 1 vez al día


def token_vigente_refrescando():
    """Devuelve (token, cfg). Refresca contra Meta si corresponde (best-effort:
    un fallo de refresh NUNCA impide devolver el token guardado)."""
    from .models import InstagramTokenConfig

    cfg = InstagramTokenConfig.get_solo()
    token = (cfg.token or '').strip()
    if not token:
        return '', cfg

    ahora = timezone.now()
    base = cfg.ultimo_refresh_at or cfg.token_actualizado_at
    necesita = base is None or (ahora - base) >= timedelta(days=UMBRAL_REFRESH_DIAS)
    puede_reintentar = (cfg.ultimo_intento_at is None
                        or (ahora - cfg.ultimo_intento_at) >= timedelta(hours=REINTENTO_HORAS))
    if necesita and puede_reintentar:
        _refrescar(cfg, ahora)
    return (cfg.token or '').strip(), cfg


def _refrescar(cfg, ahora):
    """Un intento de refresh. Actualiza cfg y lo persiste; nunca lanza."""
    import requests

    cfg.ultimo_intento_at = ahora
    try:
        r = requests.get(
            'https://graph.instagram.com/refresh_access_token',
            params={'grant_type': 'ig_refresh_token', 'access_token': (cfg.token or '').strip()},
            timeout=15,
        )
        try:
            data = r.json()
        except ValueError:
            data = {}
        nuevo = (data.get('access_token') or '').strip()
        if r.ok and nuevo:
            cfg.token = nuevo
            try:
                cfg.expira_estimado = ahora + timedelta(seconds=int(data.get('expires_in')))
            except (TypeError, ValueError):
                cfg.expira_estimado = None
            cfg.ultimo_refresh_at = ahora
            cfg.ultimo_error = ''
            logger.info('[token IG] refresh OK — vence ~%s', cfg.expira_estimado)
        else:
            cfg.ultimo_error = f'HTTP {r.status_code}: {str(data)[:400]}'
            logger.warning('[token IG] refresh FALLÓ: %s', cfg.ultimo_error)
            _avisar_si_corresponde(cfg, ahora)
    except Exception as exc:  # noqa: BLE001 — el refresh es best-effort
        cfg.ultimo_error = str(exc)[:400]
        logger.warning('[token IG] refresh reventó: %s', cfg.ultimo_error)
        _avisar_si_corresponde(cfg, ahora)
    finally:
        cfg.save()


def _avisar_si_corresponde(cfg, ahora):
    """Email de alerta a Jorge cuando el refresh falla (máx 1/día, best-effort)."""
    if cfg.ultimo_aviso_at and (ahora - cfg.ultimo_aviso_at) < timedelta(hours=AVISO_CADA_HORAS):
        return
    try:
        from django.core.mail import send_mail
        send_mail(
            '⚠️ Aremko: el refresh del token de Instagram está fallando',
            'El refresh automático del token de Instagram falló.\n\n'
            f'Error: {cfg.ultimo_error}\n\n'
            'Si el token venció, hay que generar uno nuevo en developers.facebook.com '
            '(app de Instagram → Configuración de la API con inicio de sesión de '
            'Instagram → Generar token para @aremkospa) y pegarlo en el admin: '
            'www.aremko.cl/admin/inbox_omnicanal/instagramtokenconfig/\n\n'
            'Mientras tanto, la bandeja puede seguir respondiendo desde la app de '
            'Instagram del teléfono.',
            None,
            ['ecolonco@gmail.com'],
            fail_silently=True,
        )
        cfg.ultimo_aviso_at = ahora
    except Exception:  # noqa: BLE001 — el aviso jamás rompe el flujo
        logger.exception('[token IG] no se pudo enviar el email de aviso')
