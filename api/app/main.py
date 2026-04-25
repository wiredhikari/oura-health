"""oura-health API — entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, migrations
from .config import settings
from .routes import auth, chat, digest, health, log


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    try:
        migrations.apply()
    except Exception as e:  # pragma: no cover — log & continue
        import logging
        logging.getLogger("api").warning(f"migration failed (continuing): {e}")
    yield
    db.close_pool()


app = FastAPI(
    title="oura-health API",
    version="2.0.0",
    description="Self-hosted Oura analytics + AI assistant.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().cors_origin] if settings().cors_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness probe — does NOT touch the DB."""
    return {"ok": True}


@app.get("/readyz", tags=["meta"])
def readyz() -> dict:
    """Readiness probe — touches the DB."""
    try:
        rows = db.fetch_all("SELECT 1 AS ok")
        return {"ok": rows[0]["ok"] == 1}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}


app.include_router(auth.router)
app.include_router(health.router)
app.include_router(log.router)
app.include_router(chat.router)
app.include_router(digest.router)
