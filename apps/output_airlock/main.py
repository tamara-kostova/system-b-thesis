"""
Phase 4 — Output Airlock FastAPI service (port 8005).

Researchers submit output candidates from SPEs; automated checks run immediately.
Files that pass go to a human reviewer queue. Approved files can be downloaded.

EHDS Articles 50 (output checking) and 73 (audit).
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from apps.output_airlock.checks import all_passed, run_checks
from apps.output_airlock.models import AirlockSubmissionDB, create_tables
from shared.audit import log_event
from shared.db import get_db


@asynccontextmanager
async def lifespan(app):
    create_tables()
    yield


app = FastAPI(
    title="Output Airlock",
    description="Disclosure-control gateway for SPE output candidates. EHDS Articles 50 & 73.",
    version="0.1.0",
    lifespan=lifespan,
)

REVIEWER_PASSWORD = os.getenv("REVIEWER_PASSWORD")
if not REVIEWER_PASSWORD:
    raise RuntimeError(
        "REVIEWER_PASSWORD environment variable is not set. "
        "Add it to your .env file before starting the airlock service."
    )


# ── Pydantic response models ──────────────────────────────────────────────────


class CheckResultOut(BaseModel):
    name: str
    passed: bool
    reason: str


class SubmissionOut(BaseModel):
    submission_id: str
    permit_id: str
    filename: str
    content_type: str
    justification: str | None
    automated_checks: list[CheckResultOut]
    all_checks_passed: bool
    state: str
    reviewer: str | None
    reviewer_comment: str | None
    submitted_at: str
    reviewed_at: str | None


def _to_out(s: AirlockSubmissionDB) -> SubmissionOut:
    return SubmissionOut(
        submission_id=str(s.submission_id),
        permit_id=s.permit_id,
        filename=s.filename,
        content_type=s.content_type,
        justification=s.justification,
        automated_checks=[CheckResultOut(**c) for c in s.automated_checks],
        all_checks_passed=s.all_checks_passed,
        state=s.state,
        reviewer=s.reviewer,
        reviewer_comment=s.reviewer_comment,
        submitted_at=s.submitted_at.isoformat(),
        reviewed_at=s.reviewed_at.isoformat() if s.reviewed_at else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.post("/submissions", response_model=SubmissionOut, status_code=201)
async def submit(
    permit_id: str = Form(...),
    justification: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    checks = run_checks(file.filename or "unknown", content)
    checks_json = [{"name": n, "passed": p, "reason": r} for n, p, r in checks]
    passed = all_passed(checks)

    submission = AirlockSubmissionDB(
        permit_id=permit_id,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        file_content=content,
        justification=justification or None,
        automated_checks=checks_json,
        all_checks_passed=passed,
        state="pending_review" if passed else "blocked",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    log_event(
        "airlock.submitted",
        actor=permit_id,
        resource_id=str(submission.submission_id),
        details={"filename": submission.filename, "all_checks_passed": passed},
    )

    return _to_out(submission)


@app.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(state: str | None = None, db: Session = Depends(get_db)):
    q = db.query(AirlockSubmissionDB)
    if state:
        q = q.filter(AirlockSubmissionDB.state == state)
    return [_to_out(s) for s in q.order_by(AirlockSubmissionDB.submitted_at.desc()).all()]


@app.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: str, db: Session = Depends(get_db)):
    s = db.get(AirlockSubmissionDB, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    return _to_out(s)


class ReviewBody(BaseModel):
    reviewer: str
    password: str
    comment: str = ""


@app.post("/submissions/{submission_id}/approve", response_model=SubmissionOut)
def approve(submission_id: str, body: ReviewBody, db: Session = Depends(get_db)):
    if body.password != REVIEWER_PASSWORD:
        raise HTTPException(403, "Invalid reviewer password")
    s = db.get(AirlockSubmissionDB, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    if s.state != "pending_review":
        raise HTTPException(
            400, f"Submission is '{s.state}', only 'pending_review' can be approved"
        )

    s.state = "approved"
    s.reviewer = body.reviewer
    s.reviewer_comment = body.comment or None
    s.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(s)

    log_event(
        "airlock.approved",
        actor=body.reviewer,
        resource_id=submission_id,
        details={"filename": s.filename, "comment": body.comment},
    )
    return _to_out(s)


@app.post("/submissions/{submission_id}/reject", response_model=SubmissionOut)
def reject(submission_id: str, body: ReviewBody, db: Session = Depends(get_db)):
    if body.password != REVIEWER_PASSWORD:
        raise HTTPException(403, "Invalid reviewer password")
    s = db.get(AirlockSubmissionDB, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    if s.state not in ("pending_review", "approved"):
        raise HTTPException(400, f"Submission is '{s.state}', cannot reject")

    s.state = "rejected"
    s.reviewer = body.reviewer
    s.reviewer_comment = body.comment or None
    s.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(s)

    log_event(
        "airlock.rejected",
        actor=body.reviewer,
        resource_id=submission_id,
        details={"filename": s.filename, "comment": body.comment},
    )
    return _to_out(s)


@app.get("/submissions/{submission_id}/download")
def download(submission_id: str, requester: str = "anonymous", db: Session = Depends(get_db)):
    s = db.get(AirlockSubmissionDB, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    if s.state != "approved":
        raise HTTPException(403, "Only approved submissions can be downloaded")

    log_event(
        "airlock.downloaded",
        actor=requester,
        resource_id=submission_id,
        details={"filename": s.filename},
    )

    return Response(
        content=s.file_content,
        media_type=s.content_type,
        headers={"Content-Disposition": f'attachment; filename="{s.filename}"'},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
