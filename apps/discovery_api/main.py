from fastapi import FastAPI
from apps.discovery_api.routers import datasets, concepts, counts

app = FastAPI(
    title="Discovery API",
    description="Public read-only catalogue for the SecureHealth OMOP dataset. No authentication required.",
    version="0.1.0",
)

app.include_router(datasets.router)
app.include_router(concepts.router)
app.include_router(counts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
