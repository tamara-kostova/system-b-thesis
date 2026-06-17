from fastapi import FastAPI
from apps.permit_service.models import create_tables
from apps.permit_service.routers import permits

app = FastAPI(
    title="Permit Service",
    description="EHDS Articles 67-68 — data access permit workflow.",
    version="0.1.0",
)

create_tables()
app.include_router(permits.router)


@app.get("/health")
def health():
    return {"status": "ok"}
