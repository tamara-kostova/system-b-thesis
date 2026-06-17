from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.db import get_db
from shared.suppression import suppress

router = APIRouter(prefix="/counts", tags=["counts"])


class CountResult(BaseModel):
    concept_id: int
    concept_name: str | None
    patient_count: int | str  # int or "<10"


@router.get("/{concept_id}", response_model=CountResult)
def count_patients(concept_id: int, db: Session = Depends(get_db)):
    """
    Count distinct patients with any condition, drug exposure, or measurement
    matching this concept or any of its descendants.
    """
    sql = """
        WITH descendants AS (
            SELECT descendant_concept_id AS cid
            FROM cdm.concept_ancestor
            WHERE ancestor_concept_id = :concept_id
        ),
        matched_persons AS (
            SELECT DISTINCT person_id FROM cdm.condition_occurrence
            WHERE condition_concept_id IN (SELECT cid FROM descendants)
            UNION
            SELECT DISTINCT person_id FROM cdm.drug_exposure
            WHERE drug_concept_id IN (SELECT cid FROM descendants)
            UNION
            SELECT DISTINCT person_id FROM cdm.measurement
            WHERE measurement_concept_id IN (SELECT cid FROM descendants)
        )
        SELECT COUNT(*) AS n FROM matched_persons
    """
    count = db.execute(text(sql), {"concept_id": concept_id}).scalar()

    concept_name = db.execute(
        text("SELECT concept_name FROM cdm.concept WHERE concept_id = :id"),
        {"id": concept_id},
    ).scalar()

    return CountResult(
        concept_id=concept_id,
        concept_name=concept_name,
        patient_count=suppress(count),
    )
