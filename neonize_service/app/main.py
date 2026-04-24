import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .config import get_settings
from .wa_client import WAClient
from .routes import health, status, qr, send


def _configure_logging(level: str):
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    _configure_logging(s.neonize_log_level)
    log = logging.getLogger("main")
    log.info("Starting service; session_path=%s", s.neonize_session_path)

    wa = WAClient(s.neonize_session_path)
    app.state.wa_client = wa
    await wa.start()

    try:
        yield
    finally:
        log.info("Shutting down service")
        await wa.stop()


app = FastAPI(title="Neonize Aremko Service", lifespan=lifespan)
app.include_router(health.router)
app.include_router(status.router)
app.include_router(qr.router)
app.include_router(send.router)
