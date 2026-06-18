import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apps.permit_service.models import create_tables
from apps.permit_service.routers import permits, audit

logger = logging.getLogger(__name__)


async def _expiry_loop():
    """Check for expired permits once per hour and expire them automatically."""
    while True:
        await asyncio.sleep(3600)
        from shared.db import SessionLocal
        from apps.permit_service.routers.permits import _expire_due
        db = SessionLocal()
        try:
            n = _expire_due(db)
            if n:
                logger.info("Auto-expired %d permit(s)", n)
        except Exception as exc:
            logger.error("Expiry loop error: %s", exc)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Permit Service",
    description="EHDS Articles 67-68 — data access permit workflow.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(permits.router)
app.include_router(audit.router)


@app.get("/health")
def health():
    return {"status": "ok"}
