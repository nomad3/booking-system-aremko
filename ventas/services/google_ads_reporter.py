"""Google Ads API client (campaña Refugio - Search + futuras campañas Aremko).

Consulta Google Ads API v17 para Aremko. Cubre:
- Campañas activas con métricas (impressions, clicks, spend, conversions, CPL)
- Detalle por ad group y por anuncio individual
- Search Terms Report (búsquedas reales que dispararon anuncios — único de Search)
- Keywords performance + Quality Score
- Conversion actions configuradas
- Saldo de pagos manuales (prepago)

Autenticacion: OAuth 2.0 con refresh token (a diferencia de Meta que usa System User Token).

NO usa SDK google-ads para evitar agregar 50MB de dependencias. Implementa directo
contra la REST API con requests + intercambio refresh_token → access_token via
https://oauth2.googleapis.com/token. Access token se cachea en memoria (TTL 50min).

Credenciales requeridas (env vars Render):
    GOOGLE_ADS_DEVELOPER_TOKEN  # de un MCC aprobado por Google (no test token)
    GOOGLE_ADS_CLIENT_ID        # OAuth 2.0 client de Google Cloud Console
    GOOGLE_ADS_CLIENT_SECRET    # del mismo OAuth client
    GOOGLE_ADS_REFRESH_TOKEN    # generado via OAuth Playground (scope adwords)
    GOOGLE_ADS_CUSTOMER_ID      # cuenta Aremko sin guiones (ej. 5399750827)
    GOOGLE_ADS_LOGIN_CUSTOMER_ID  # opcional, ID del MCC si la cuenta lo tiene

Setup local (Mac, dev):
    Usar mismas env vars en .env local, o exportar antes de correr management commands.

Estado al 2026-05-30:
    - Scaffolding listo (este archivo)
    - Credenciales OAuth pendientes (Jorge debe solicitar Developer Token, demora 1-3d)
    - Mientras tanto, get_snapshot_safe() retorna None sin romper el brief semanal
"""
import logging
import os
import time
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ============================================================================
# API config
# ============================================================================

GOOGLE_ADS_API_VERSION = "v17"
GOOGLE_ADS_API_BASE = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"
OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# IDs operativos Aremko (constantes, no son secretos)
# Cuenta principal Refugio - cuenta nueva 2026-05-29 (ecolonco1@gmail.com)
CUSTOMER_ID_AREMKO = "5399750827"  # 539-975-0827 sin guiones

# Conversion tracking (compartido con código del sitio)
CONVERSION_ID = "AW-18196625156"  # gtag id en base_public.html
CONVERSION_LABEL = "2z2aCNrR4rUcEITu6eRD"  # label en refugio_landing.html

# ============================================================================
# Token resolution (graceful — retorna None si falta cualquier credencial)
# ============================================================================


def _get_credentials() -> Optional[dict]:
    """Lee las 6 credenciales necesarias de env vars.

    Returns:
        dict con keys: developer_token, client_id, client_secret, refresh_token,
        customer_id, login_customer_id (puede ser None).
        None si falta alguna obligatoria.
    """
    required = {
        "developer_token": os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.environ.get("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.environ.get("GOOGLE_ADS_REFRESH_TOKEN"),
        "customer_id": os.environ.get("GOOGLE_ADS_CUSTOMER_ID") or CUSTOMER_ID_AREMKO,
    }
    optional = {
        "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.debug(
            f"Google Ads credenciales incompletas, faltan: {missing}. "
            f"Reporter retornará None hasta que Jorge configure env vars."
        )
        return None

    return {**required, **optional}


# Cache simple del access_token (válido por 1h, cacheo por 50min para margen)
_ACCESS_TOKEN_CACHE = {"token": None, "expires_at": 0}


def _get_access_token(creds: dict) -> Optional[str]:
    """Intercambia refresh_token por access_token (válido 1h). Cachea en memoria."""
    now = time.time()
    if _ACCESS_TOKEN_CACHE["token"] and _ACCESS_TOKEN_CACHE["expires_at"] > now:
        return _ACCESS_TOKEN_CACHE["token"]

    try:
        response = requests.post(
            OAUTH_TOKEN_ENDPOINT,
            data={
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": creds["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            logger.error(f"OAuth response sin access_token: {data}")
            return None
        # Cachear con TTL 50min (Google da 1h, dejamos margen 10min)
        _ACCESS_TOKEN_CACHE["token"] = access_token
        _ACCESS_TOKEN_CACHE["expires_at"] = now + 50 * 60
        return access_token
    except requests.RequestException as e:
        logger.error(f"Error intercambiando refresh_token: {e}")
        return None


# ============================================================================
# GAQL query helper (Google Ads Query Language)
# ============================================================================


def _gaql_search(query: str, creds: Optional[dict] = None) -> Optional[list]:
    """Ejecuta una query GAQL y retorna la lista de rows.

    Args:
        query: string GAQL (ej. "SELECT campaign.id FROM campaign")
        creds: dict de credenciales (si None, las obtiene de env)

    Returns:
        Lista de dicts (rows). None si falla.
    """
    if creds is None:
        creds = _get_credentials()
    if not creds:
        return None

    access_token = _get_access_token(creds)
    if not access_token:
        return None

    url = f"{GOOGLE_ADS_API_BASE}/customers/{creds['customer_id']}/googleAds:search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": creds["developer_token"],
        "Content-Type": "application/json",
    }
    if creds.get("login_customer_id"):
        headers["login-customer-id"] = creds["login_customer_id"]

    try:
        # statement_timeout local 8s (consistente con meta_reporter)
        response = requests.post(
            url, json={"query": query}, headers=headers, timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        # API devuelve {"results": [...], "fieldMask": "..."}
        return data.get("results", [])
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text[:300] if e.response is not None else ""
        logger.warning(f"Google Ads API error {status}: {body}")
        return None
    except requests.RequestException as e:
        logger.warning(f"Google Ads network error: {e}")
        return None


# ============================================================================
# Helpers de extracción (manejo de tipos Google Ads)
# ============================================================================


def _micros_to_clp(micros) -> float:
    """Google Ads devuelve montos en micros (1 CLP = 1_000_000 micros)."""
    if micros is None:
        return 0.0
    try:
        return float(micros) / 1_000_000
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ============================================================================
# Queries: campañas, ad groups, anuncios, keywords, search terms
# ============================================================================


def get_account_summary() -> Optional[dict]:
    """Resumen de la cuenta: nombre, currency, status, saldo prepagado."""
    query = """
        SELECT
          customer.id, customer.descriptive_name,
          customer.currency_code, customer.time_zone,
          customer.status, customer.manager
        FROM customer
        LIMIT 1
    """
    rows = _gaql_search(query)
    if not rows:
        return None
    c = rows[0].get("customer", {})
    return {
        "id": c.get("id"),
        "name": c.get("descriptiveName"),
        "currency": c.get("currencyCode"),
        "timezone": c.get("timeZone"),
        "status": c.get("status"),
        "is_manager": c.get("manager"),
    }


def get_campaigns_summary(days: int = 28) -> Optional[list]:
    """Listado de campañas con métricas agregadas del periodo.

    Args:
        days: ventana temporal (default 28, alineado con meta_reporter).

    Returns:
        Lista de dicts por campaña con id, name, status, métricas.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()
    query = f"""
        SELECT
          campaign.id, campaign.name, campaign.status,
          campaign.advertising_channel_type,
          campaign.bidding_strategy_type,
          campaign_budget.amount_micros,
          metrics.impressions, metrics.clicks,
          metrics.cost_micros, metrics.ctr,
          metrics.average_cpc, metrics.conversions,
          metrics.conversions_value, metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date BETWEEN '{since}' AND '{until}'
        ORDER BY metrics.cost_micros DESC
        LIMIT 50
    """
    rows = _gaql_search(query)
    if rows is None:
        return None

    campaigns = []
    for row in rows:
        c = row.get("campaign", {})
        m = row.get("metrics", {})
        b = row.get("campaignBudget", {})
        campaigns.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "status": c.get("status"),
            "channel_type": c.get("advertisingChannelType"),
            "bidding_strategy": c.get("biddingStrategyType"),
            "daily_budget_clp": _micros_to_clp(b.get("amountMicros")),
            "impressions": _safe_int(m.get("impressions")),
            "clicks": _safe_int(m.get("clicks")),
            "spend_clp": _micros_to_clp(m.get("costMicros")),
            "ctr": round(_safe_float(m.get("ctr")) * 100, 2),  # API devuelve fracción
            "cpc_clp": _micros_to_clp(m.get("averageCpc")),
            "conversions": _safe_float(m.get("conversions")),
            "conversions_value_clp": _safe_float(m.get("conversionsValue")),
            "cpl_clp": _micros_to_clp(m.get("costPerConversion")),
        })
    return campaigns


def get_campaign_ad_groups(campaign_id: str, days: int = 7) -> Optional[list]:
    """Detalle por ad group de una campaña (para análisis intra-campaña)."""
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()
    query = f"""
        SELECT
          ad_group.id, ad_group.name, ad_group.status,
          metrics.impressions, metrics.clicks,
          metrics.cost_micros, metrics.ctr,
          metrics.conversions, metrics.cost_per_conversion
        FROM ad_group
        WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{since}' AND '{until}'
        ORDER BY metrics.cost_micros DESC
    """
    rows = _gaql_search(query)
    if rows is None:
        return None

    out = []
    for row in rows:
        g = row.get("adGroup", {})
        m = row.get("metrics", {})
        out.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "status": g.get("status"),
            "impressions": _safe_int(m.get("impressions")),
            "clicks": _safe_int(m.get("clicks")),
            "spend_clp": _micros_to_clp(m.get("costMicros")),
            "ctr": round(_safe_float(m.get("ctr")) * 100, 2),
            "conversions": _safe_float(m.get("conversions")),
            "cpl_clp": _micros_to_clp(m.get("costPerConversion")),
        })
    return out


def get_keywords_performance(campaign_id: str, days: int = 28, limit: int = 50) -> Optional[list]:
    """Performance por keyword + Quality Score (único de Google Ads).

    Quality Score 1-10 afecta directamente el CPC. <5 es señal de problema.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()
    query = f"""
        SELECT
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.quality_info.quality_score,
          metrics.impressions, metrics.clicks,
          metrics.cost_micros, metrics.ctr,
          metrics.conversions, metrics.cost_per_conversion
        FROM keyword_view
        WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{since}' AND '{until}'
          AND ad_group_criterion.status = 'ENABLED'
        ORDER BY metrics.impressions DESC
        LIMIT {limit}
    """
    rows = _gaql_search(query)
    if rows is None:
        return None

    out = []
    for row in rows:
        k = row.get("adGroupCriterion", {}).get("keyword", {})
        q = row.get("adGroupCriterion", {}).get("qualityInfo", {})
        m = row.get("metrics", {})
        out.append({
            "text": k.get("text"),
            "match_type": k.get("matchType"),
            "quality_score": q.get("qualityScore"),  # null si <100 impresiones
            "impressions": _safe_int(m.get("impressions")),
            "clicks": _safe_int(m.get("clicks")),
            "spend_clp": _micros_to_clp(m.get("costMicros")),
            "ctr": round(_safe_float(m.get("ctr")) * 100, 2),
            "conversions": _safe_float(m.get("conversions")),
            "cpl_clp": _micros_to_clp(m.get("costPerConversion")),
        })
    return out


def get_search_terms_report(campaign_id: str, days: int = 7, limit: int = 50) -> Optional[list]:
    """Search Terms Report: búsquedas REALES que dispararon anuncios.

    Esto es único de Google Search Ads — Meta no tiene equivalente. Permite
    detectar negative keywords (búsquedas con muchos clicks pero 0 conversions).
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    until = date.today().isoformat()
    query = f"""
        SELECT
          search_term_view.search_term,
          segments.search_term_match_type,
          metrics.impressions, metrics.clicks,
          metrics.cost_micros, metrics.ctr,
          metrics.conversions, metrics.cost_per_conversion
        FROM search_term_view
        WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{since}' AND '{until}'
        ORDER BY metrics.impressions DESC
        LIMIT {limit}
    """
    rows = _gaql_search(query)
    if rows is None:
        return None

    out = []
    for row in rows:
        s = row.get("searchTermView", {})
        seg = row.get("segments", {})
        m = row.get("metrics", {})
        clicks = _safe_int(m.get("clicks"))
        convs = _safe_float(m.get("conversions"))
        out.append({
            "term": s.get("searchTerm"),
            "match_type_used": seg.get("searchTermMatchType"),
            "impressions": _safe_int(m.get("impressions")),
            "clicks": clicks,
            "spend_clp": _micros_to_clp(m.get("costMicros")),
            "ctr": round(_safe_float(m.get("ctr")) * 100, 2),
            "conversions": convs,
            "cpl_clp": _micros_to_clp(m.get("costPerConversion")),
            # Flag: muchos clicks pero 0 conversions => candidate a negative keyword
            "candidate_negative": clicks >= 5 and convs == 0,
        })
    return out


def get_active_campaigns_detail(days: int = 7, max_campaigns: int = 5) -> Optional[list]:
    """Detalle granular de campañas ACTIVE (espejo del meta_reporter).

    Para cada campaña ENABLED: trae métricas totales + breakdown por ad group +
    keywords top + search terms top. Análogo a meta_reporter.get_active_campaigns_detail.

    Args:
        days: ventana 7d por default (alineado con ciclo brief semanal).
        max_campaigns: top N por spend.

    Returns:
        Lista de dicts por campaña activa, o None si falla / sin credenciales.
    """
    campaigns = get_campaigns_summary(days=days)
    if campaigns is None:
        return None

    active = [c for c in campaigns if c.get("status") == "ENABLED"]
    if not active:
        return []
    active = active[:max_campaigns]

    result = []
    for c in active:
        cid = c.get("id")
        if not cid:
            continue
        ad_groups = get_campaign_ad_groups(cid, days=days) or []
        keywords = get_keywords_performance(cid, days=days, limit=30) or []
        search_terms = get_search_terms_report(cid, days=days, limit=30) or []

        # Flag candidatos a negative keywords (sirve al LLM para sugerencias)
        negative_candidates = [
            st for st in search_terms if st.get("candidate_negative")
        ]
        # Keywords con Quality Score bajo (<5)
        low_qs = [
            kw for kw in keywords
            if kw.get("quality_score") and kw["quality_score"] < 5
        ]

        result.append({
            "campaign_id": cid,
            "name": c.get("name"),
            "channel_type": c.get("channel_type"),
            "bidding_strategy": c.get("bidding_strategy"),
            "daily_budget_clp": c.get("daily_budget_clp"),
            "totals": {
                "impressions": c.get("impressions"),
                "clicks": c.get("clicks"),
                "spend_clp": c.get("spend_clp"),
                "ctr": c.get("ctr"),
                "cpc_clp": c.get("cpc_clp"),
                "conversions": c.get("conversions"),
                "cpl_clp": c.get("cpl_clp"),
            },
            "by_ad_group": ad_groups,
            "top_keywords": keywords[:20],
            "top_search_terms": search_terms[:20],
            "negative_keyword_candidates": negative_candidates,
            "low_quality_score_keywords": low_qs,
        })

    return result


# ============================================================================
# Snapshot consolidado (para brief semanal)
# ============================================================================


def get_full_snapshot(days: int = 28) -> dict:
    """Snapshot consolidado para alimentar el brief semanal.

    Tolerante a fallas parciales: si una sección falla, se loguea y se
    devuelve {} para esa sección.
    """
    snapshot = {"period_days": days, "errors": {}}

    try:
        snapshot["account"] = get_account_summary()
    except Exception as e:
        snapshot["errors"]["account"] = str(e)
        logger.exception("Error en account summary")

    try:
        snapshot["campaigns_period"] = get_campaigns_summary(days=days)
    except Exception as e:
        snapshot["errors"]["campaigns_period"] = str(e)
        logger.exception("Error en campaigns_summary")

    try:
        snapshot["active_campaigns_detail"] = get_active_campaigns_detail(days=7)
    except Exception as e:
        snapshot["errors"]["active_campaigns_detail"] = str(e)
        logger.exception("Error en active_campaigns_detail")

    return snapshot


def get_snapshot_safe(days: int = 28) -> Optional[dict]:
    """Como get_full_snapshot pero retorna None si:
       - credenciales no configuradas (típico hoy)
       - todas las secciones fallan
       - hay un error fatal.

    NO rompe el brief si Google Ads no está disponible. El brief seguirá
    funcionando con Meta + GA4 + GSC.
    """
    creds = _get_credentials()
    if not creds:
        logger.info(
            "Google Ads reporter: credenciales no configuradas, "
            "retornando None (brief seguirá funcionando sin Google Ads)."
        )
        return None

    try:
        snapshot = get_full_snapshot(days=days)
        # Si TODAS las secciones fallaron, retornar None
        if snapshot.get("errors") and not snapshot.get("account"):
            logger.warning(
                f"Google Ads snapshot vacío. Errores: {snapshot['errors']}"
            )
            return None
        return snapshot
    except Exception as e:
        logger.exception(f"Google Ads snapshot failed: {e}")
        return None
