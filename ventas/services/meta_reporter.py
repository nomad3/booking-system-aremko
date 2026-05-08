"""Meta Graph API client (Tarea de diagnostico organico + historico paid).

Consulta Meta Graph API v21.0 para Aremko. Cubre:
- Pagina de Facebook organica (alcance, fans, top posts, engagement)
- Cuenta business de Instagram organica (alcance, followers, top media)
- Cuentas publicitarias historico (campañas, gasto, ROAS, top creativos)

Autenticacion: System User Access Token (no expira mientras la App exista).

Resolucion del token en orden:
1. Env var META_SYSTEM_USER_TOKEN (Render production)
2. macOS Keychain servicio 'aremko-meta', cuenta 'system_user_token' (dev local)

IDs configurados (Aremko):
- Page ID FB: 555157687911449 (53k fans)
- Instagram Business Account ID: 17841400756478364 (@aremkospa, ~59k followers)
- Cuenta publicitaria principal: act_455070225054110 (CLP)
- Cuenta publicitaria secundaria: act_43311853 (USD)
- Business owner ID: 2135035316743281

Setup en Render:
    META_SYSTEM_USER_TOKEN=<token>

Setup local (Mac):
    security add-generic-password -U -a 'system_user_token' -s 'aremko-meta' -w '<token>'
"""
import logging
import os
import subprocess
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# IDs Aremko (constantes operativas, no son secretos)
PAGE_ID_FB = "555157687911449"
INSTAGRAM_BUSINESS_ACCOUNT_ID = "17841400756478364"
AD_ACCOUNT_PRINCIPAL = "act_455070225054110"  # CLP, 39 campañas historicas
AD_ACCOUNT_SECUNDARIA = "act_43311853"  # USD
BUSINESS_OWNER_ID = "2135035316743281"


# ============================================================================
# Token resolution
# ============================================================================


def _keychain_get(account: str, service: str = "aremko-meta") -> str:
    """Lee token desde macOS Keychain (solo macOS local). Devuelve '' si falla."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return ""


def resolve_token() -> str:
    """Devuelve el system user token. Lanza ValueError si no encuentra."""
    token = os.environ.get("META_SYSTEM_USER_TOKEN", "").strip()
    if token:
        return token
    token = _keychain_get("system_user_token")
    if token:
        return token
    raise ValueError(
        "META_SYSTEM_USER_TOKEN no configurado. "
        "Set env var en Render o ejecuta: "
        "security add-generic-password -U -a 'system_user_token' "
        "-s 'aremko-meta' -w '<token>'"
    )


# ============================================================================
# Helpers HTTP
# ============================================================================


def _get(path: str, params: Optional[dict] = None, token: Optional[str] = None) -> dict:
    """GET a Graph API. Lanza si error HTTP o si Meta devuelve {error: ...}.

    Si token=None usa el system user token. Para endpoints de Page que
    requieran Page Access Token, pasar el token explicitamente.
    """
    params = dict(params or {})
    params["access_token"] = token or resolve_token()
    url = f"{GRAPH_API_BASE}{path if path.startswith('/') else '/' + path}"

    response = requests.get(url, params=params, timeout=30)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"Meta Graph API: respuesta no-JSON ({response.status_code})")

    if "error" in data:
        err = data["error"]
        raise RuntimeError(
            f"Meta Graph API error {err.get('code')}: {err.get('message')} "
            f"(type={err.get('type')})"
        )

    return data


# Cache para Page Access Token (vive por proceso, se renueva al reiniciar)
_PAGE_TOKEN_CACHE: dict = {}


def get_page_access_token(page_id: str = PAGE_ID_FB) -> str:
    """Obtiene el Page Access Token para llamadas a /posts e insights.

    Las APIs de FB Page requieren Page Access Token (no system user token).
    Se cachea por proceso. Si el system user esta vinculado a la pagina con
    los permisos adecuados, el token se hereda.
    """
    if page_id in _PAGE_TOKEN_CACHE:
        return _PAGE_TOKEN_CACHE[page_id]

    data = _get(f"/{page_id}", {"fields": "access_token"})
    token = data.get("access_token", "")
    if not token:
        raise RuntimeError(
            f"No se pudo obtener Page Access Token para {page_id}. "
            f"Verificar que el system user tenga acceso a la pagina con "
            f"permisos suficientes (Estadisticas, Contenido, Anuncios)."
        )
    _PAGE_TOKEN_CACHE[page_id] = token
    return token


# ============================================================================
# Facebook Page (organico)
# ============================================================================


def get_facebook_page_overview() -> dict:
    """Datos basicos de la pagina FB Aremko."""
    data = _get(f"/{PAGE_ID_FB}", {
        "fields": "id,name,fan_count,followers_count,about,category,link,verification_status",
    })
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "fan_count": data.get("fan_count"),
        "followers_count": data.get("followers_count"),
        "category": data.get("category"),
        "link": data.get("link"),
        "verification_status": data.get("verification_status"),
    }


def get_facebook_page_insights(days: int = 28) -> dict:
    """Resumen de engagement de la pagina FB calculado desde los posts.

    Meta deprecó la mayoria de Page Insights API en v21.0+ (errores
    persistentes "The value must be a valid insights metric"). En vez de
    pelearnos con metricas legacy, calculamos engagement a partir de los
    posts mismos (endpoint /posts con reactions.summary) — eso si funciona
    consistentemente y da insights mas accionables.

    Devuelve totales y promedios de reacciones, comentarios, shares,
    cantidad de posts publicados, top post del periodo, frecuencia de
    publicacion (posts/dia).

    El endpoint /posts requiere Page Access Token (no system user token),
    que obtenemos automaticamente via get_page_access_token().
    """
    until = date.today()
    since = until - timedelta(days=days)
    page_token = get_page_access_token()

    data = _get(f"/{PAGE_ID_FB}/posts", {
        "fields": "id,created_time,message,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares",
        "since": since.isoformat(),
        "limit": 100,
    }, token=page_token)

    posts = data.get("data", [])
    total_reactions = 0
    total_comments = 0
    total_shares = 0
    top_post = None
    top_engagement = -1

    for p in posts:
        r = (p.get("reactions") or {}).get("summary", {}).get("total_count", 0) or 0
        c = (p.get("comments") or {}).get("summary", {}).get("total_count", 0) or 0
        s = (p.get("shares") or {}).get("count", 0) or 0
        total_reactions += r
        total_comments += c
        total_shares += s
        eng = r + c + s
        if eng > top_engagement:
            top_engagement = eng
            top_post = {
                "id": p.get("id"),
                "created_time": p.get("created_time"),
                "message_excerpt": (p.get("message") or "")[:160],
                "reactions": r,
                "comments": c,
                "shares": s,
                "engagement": eng,
            }

    posts_count = len(posts)
    total_engagement = total_reactions + total_comments + total_shares

    return {
        "period_days": days,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "posts_publicados": posts_count,
        "frecuencia_posts_por_dia": round(posts_count / days, 2) if days else 0,
        "total_reactions": total_reactions,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_engagement": total_engagement,
        "engagement_por_post_promedio": round(total_engagement / posts_count, 2) if posts_count else 0,
        "top_post_periodo": top_post,
        "_nota": (
            "Calculado desde /posts (Page Insights API v21+ deprecada). "
            "No incluye alcance/impresiones porque esos endpoints requieren "
            "metricas que ya no estan disponibles publicamente."
        ),
    }


def get_facebook_top_posts(limit: int = 10, days: int = 28) -> list:
    """Top posts de la pagina FB del periodo, ordenados por engagement."""
    since = date.today() - timedelta(days=days)
    page_token = get_page_access_token()
    data = _get(f"/{PAGE_ID_FB}/posts", {
        "fields": "id,message,created_time,permalink_url,reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares",
        "since": since.isoformat(),
        "limit": 50,
    }, token=page_token)

    posts = []
    for p in data.get("data", []):
        reactions = (p.get("reactions") or {}).get("summary", {}).get("total_count", 0)
        comments = (p.get("comments") or {}).get("summary", {}).get("total_count", 0)
        shares = (p.get("shares") or {}).get("count", 0)
        engagement = reactions + comments + shares
        posts.append({
            "id": p.get("id"),
            "message_excerpt": (p.get("message") or "")[:200],
            "created_time": p.get("created_time"),
            "permalink_url": p.get("permalink_url"),
            "reactions": reactions,
            "comments": comments,
            "shares": shares,
            "engagement": engagement,
        })
    posts.sort(key=lambda x: x["engagement"], reverse=True)
    return posts[:limit]


# ============================================================================
# Instagram Business (organico)
# ============================================================================


def get_instagram_overview() -> dict:
    """Datos basicos de la cuenta business de IG @aremkospa."""
    data = _get(f"/{INSTAGRAM_BUSINESS_ACCOUNT_ID}", {
        "fields": "username,name,biography,followers_count,follows_count,media_count,profile_picture_url,website",
    })
    return data


def get_instagram_insights(days: int = 28) -> dict:
    """Insights organicos de la cuenta IG en el periodo dado.

    Algunas metricas requieren metric_type=total_value (Meta v21.0+).
    """
    until = date.today()
    since = until - timedelta(days=days)

    summary = {
        "period_days": days,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "metrics": {},
    }

    # Metricas de tiempo (period=day)
    try:
        data = _get(f"/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/insights", {
            "metric": "reach,follower_count",
            "period": "day",
            "since": since.isoformat(),
            "until": until.isoformat(),
        })
        for entry in data.get("data", []):
            name = entry.get("name")
            values = entry.get("values", [])
            total = sum((v.get("value") or 0) for v in values if isinstance(v.get("value"), (int, float)))
            summary["metrics"][name] = {
                "total": total,
                "daily_avg": (total / days) if days else 0,
                "data_points": len(values),
            }
    except RuntimeError as e:
        logger.warning(f"IG insights time-series failed: {e}")
        summary["metrics"]["_error_time_series"] = str(e)

    # Metricas total_value (interactions, profile_views, etc.)
    try:
        data = _get(f"/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/insights", {
            "metric": "total_interactions,profile_views",
            "metric_type": "total_value",
            "period": "day",
            "since": since.isoformat(),
            "until": until.isoformat(),
        })
        for entry in data.get("data", []):
            name = entry.get("name")
            tv = entry.get("total_value", {})
            summary["metrics"][name] = {
                "total": tv.get("value", 0) if isinstance(tv, dict) else tv,
            }
    except RuntimeError as e:
        logger.warning(f"IG insights total_value failed: {e}")
        summary["metrics"]["_error_total_value"] = str(e)

    return summary


def get_instagram_top_media(limit: int = 10, days: int = 28) -> list:
    """Top posts de IG del periodo, ordenados por engagement."""
    since_dt = date.today() - timedelta(days=days)
    data = _get(f"/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media", {
        "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
        "limit": 50,
    })

    posts = []
    for m in data.get("data", []):
        ts = m.get("timestamp", "")
        # Filtrar por periodo
        if ts and ts[:10] < since_dt.isoformat():
            continue
        likes = m.get("like_count", 0) or 0
        comments = m.get("comments_count", 0) or 0
        engagement = likes + comments
        posts.append({
            "id": m.get("id"),
            "caption_excerpt": (m.get("caption") or "")[:200],
            "media_type": m.get("media_type"),
            "permalink": m.get("permalink"),
            "timestamp": ts,
            "likes": likes,
            "comments": comments,
            "engagement": engagement,
        })
    posts.sort(key=lambda x: x["engagement"], reverse=True)
    return posts[:limit]


# ============================================================================
# Cuentas publicitarias (paid history)
# ============================================================================


def get_ad_account_summary(account_id: str = AD_ACCOUNT_PRINCIPAL) -> dict:
    """Resumen general de una cuenta publicitaria."""
    data = _get(f"/{account_id}", {
        "fields": "name,amount_spent,balance,currency,account_status,disable_reason,age,timezone_name",
    })
    return data


def get_ad_account_insights(account_id: str = AD_ACCOUNT_PRINCIPAL, days: int = 30) -> dict:
    """Insights agregados de la cuenta publicitaria en el periodo."""
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()

    data = _get(f"/{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,cpm,reach,actions,action_values",
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "level": "account",
    })

    if not data.get("data"):
        return {
            "since": since, "until": until,
            "spend": 0, "impressions": 0, "clicks": 0,
            "_message": "Sin datos en el periodo",
        }

    row = data["data"][0]
    return {
        "account_id": account_id,
        "since": since,
        "until": until,
        "spend": float(row.get("spend") or 0),
        "impressions": int(row.get("impressions") or 0),
        "clicks": int(row.get("clicks") or 0),
        "ctr": float(row.get("ctr") or 0),
        "cpc": float(row.get("cpc") or 0),
        "cpm": float(row.get("cpm") or 0),
        "reach": int(row.get("reach") or 0),
        "actions": row.get("actions", []),
        "action_values": row.get("action_values", []),
    }


def get_campaigns_summary(account_id: str = AD_ACCOUNT_PRINCIPAL, limit: int = 50) -> list:
    """Listado de campañas con sus stats agregados.

    Util para analisis historico de las 39 campañas.
    """
    data = _get(f"/{account_id}/campaigns", {
        "fields": (
            "id,name,status,objective,created_time,start_time,stop_time,"
            "insights{spend,impressions,clicks,ctr,cpc,actions}"
        ),
        "limit": limit,
    })

    campaigns = []
    for c in data.get("data", []):
        insights = (c.get("insights") or {}).get("data", [])
        ins = insights[0] if insights else {}
        campaigns.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "status": c.get("status"),
            "objective": c.get("objective"),
            "created_time": c.get("created_time"),
            "start_time": c.get("start_time"),
            "stop_time": c.get("stop_time"),
            "spend": float(ins.get("spend") or 0),
            "impressions": int(ins.get("impressions") or 0),
            "clicks": int(ins.get("clicks") or 0),
            "ctr": float(ins.get("ctr") or 0),
            "cpc": float(ins.get("cpc") or 0),
        })
    return campaigns


def get_campaign_detail(campaign_id: str, days: int = 30) -> dict:
    """Detalle de una campaña especifica con metricas dia a dia."""
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()

    base = _get(f"/{campaign_id}", {
        "fields": "id,name,status,objective,created_time,start_time,stop_time,daily_budget,lifetime_budget",
    })

    insights = _get(f"/{campaign_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,reach,actions,action_values",
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "time_increment": 1,
    })

    return {
        "campaign": base,
        "daily_insights": insights.get("data", []),
        "since": since,
        "until": until,
    }


# ============================================================================
# Snapshot consolidado (para guardar en BD via MetaSnapshot)
# ============================================================================


def get_full_snapshot(days: int = 28) -> dict:
    """Snapshot consolidado de Facebook + Instagram + Ads."""
    snapshot = {"period_days": days, "errors": {}}

    try:
        snapshot["facebook"] = {
            "overview": get_facebook_page_overview(),
            "insights": get_facebook_page_insights(days=days),
            "top_posts": get_facebook_top_posts(limit=10, days=days),
        }
    except Exception as e:
        snapshot["errors"]["facebook"] = str(e)
        logger.exception("Error en facebook snapshot")

    try:
        snapshot["instagram"] = {
            "overview": get_instagram_overview(),
            "insights": get_instagram_insights(days=days),
            "top_media": get_instagram_top_media(limit=10, days=days),
        }
    except Exception as e:
        snapshot["errors"]["instagram"] = str(e)
        logger.exception("Error en instagram snapshot")

    try:
        snapshot["ads_principal"] = {
            "account": get_ad_account_summary(AD_ACCOUNT_PRINCIPAL),
            "insights": get_ad_account_insights(AD_ACCOUNT_PRINCIPAL, days=days),
            "campaigns": get_campaigns_summary(AD_ACCOUNT_PRINCIPAL, limit=50),
        }
    except Exception as e:
        snapshot["errors"]["ads_principal"] = str(e)
        logger.exception("Error en ads principal snapshot")

    return snapshot


def get_snapshot_safe(days: int = 28) -> Optional[dict]:
    """Como get_full_snapshot pero devuelve None si falla todo (no-op para brief)."""
    try:
        snapshot = get_full_snapshot(days=days)
        # Si todo fallo, devolver None
        if snapshot.get("errors") and len(snapshot.get("errors", {})) >= 3:
            return None
        return snapshot
    except Exception as e:
        logger.exception(f"Meta snapshot failed: {e}")
        return None
