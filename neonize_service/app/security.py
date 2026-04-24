from fastapi import Header, HTTPException, Query
from .config import get_settings


async def verify_token_header(x_auth_token: str = Header(None)):
    """Verifica token solo via header. Para endpoints que NO se abren desde browser."""
    s = get_settings()
    if not s.neonize_service_token:
        raise HTTPException(status_code=500, detail="Service token not configured")
    if not x_auth_token or x_auth_token != s.neonize_service_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True


async def verify_token_flexible(
    x_auth_token: str = Header(None),
    token: str | None = Query(None),
):
    """Verifica token via header o query. Para /qr (se abre desde browser)."""
    s = get_settings()
    if not s.neonize_service_token:
        raise HTTPException(status_code=500, detail="Service token not configured")
    provided = x_auth_token or token
    if not provided or provided != s.neonize_service_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return True
