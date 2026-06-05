from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.db import get_db

router = APIRouter(prefix="/concepts", tags=["concepts"])


class ConceptResult(BaseModel):
    concept_id: int
    concept_name: str
    vocabulary_id: str
    domain_id: str
    concept_class_id: str


@router.get("/search", response_model=list[ConceptResult])
def search_concepts(
    q: str = Query(..., min_length=2, description="Search term"),
    domain: str | None = Query(None, description="Filter by domain, e.g. 'Drug', 'Condition'"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    sql = """
        SELECT concept_id, concept_name, vocabulary_id, domain_id, concept_class_id
        FROM cdm.concept
        WHERE concept_name ILIKE :pattern
          AND (:domain IS NULL OR domain_id = :domain)
          AND standard_concept = 'S'
        ORDER BY concept_name
        LIMIT :limit
    """
    rows = db.execute(text(sql), {"pattern": f"%{q}%", "domain": domain, "limit": limit})
    return [ConceptResult(**r._mapping) for r in rows]


@router.get("/{concept_id}/descendants", response_model=list[ConceptResult])
def get_descendants(concept_id: int, db: Session = Depends(get_db)):
    sql = """
        SELECT c.concept_id, c.concept_name, c.vocabulary_id, c.domain_id, c.concept_class_id
        FROM cdm.concept_ancestor ca
        JOIN cdm.concept c ON c.concept_id = ca.descendant_concept_id
        WHERE ca.ancestor_concept_id = :concept_id
        ORDER BY ca.min_levels_of_separation, c.concept_name
    """
    rows = db.execute(text(sql), {"concept_id": concept_id})
    return [ConceptResult(**r._mapping) for r in rows]
