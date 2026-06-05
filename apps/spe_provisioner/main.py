import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from shared.db import get_db
from apps.permit_service.models import PermitDB, create_tables
from apps.spe_provisioner.projection import create_projection, teardown_projection
from apps.spe_provisioner.provisioner import provision, teardown, get_status

create_tables()

SALT = os.getenv("PROJECTION_SALT", "change-this-salt-in-production")

app = FastAPI(
    title="SPE Provisioner",
    description="Launches and tears down Secure Processing Environments for granted permits.",
    version="0.1.0",
)


class ProvisionRequest(BaseModel):
    permit_id: str


class SPEInfo(BaseModel):
    permit_id: str
    jupyter_url: str
    status: str


@app.post("/spe", response_model=SPEInfo, status_code=201)
def provision_spe(body: ProvisionRequest, db: Session = Depends(get_db)):
    permit = db.get(PermitDB, body.permit_id)
    if not permit:
        raise HTTPException(404, "Permit not found")
    if permit.state != "granted":
        raise HTTPException(400, f"Permit is '{permit.state}', must be 'granted' to provision SPE")

    db_user, db_password = create_projection(permit, db, SALT)
    info = provision(permit.permit_id, db_user, db_password)

    return SPEInfo(
        permit_id=permit.permit_id,
        jupyter_url=info["jupyter_url"],
        status="running",
    )


@app.get("/spe/{permit_id}", response_model=SPEInfo)
def spe_status(permit_id: str):
    status = get_status(permit_id)
    return SPEInfo(
        permit_id=permit_id,
        jupyter_url=status.get("jupyter_url") or "",
        status=status["status"],
    )


@app.delete("/spe/{permit_id}", status_code=204)
def teardown_spe(permit_id: str, db: Session = Depends(get_db)):
    teardown(permit_id)
    teardown_projection(permit_id, db)


@app.get("/health")
def health():
    return {"status": "ok"}
