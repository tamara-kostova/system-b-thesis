from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

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
    # Split into tokens and require each to appear anywhere in the concept name.
    # This handles word-order differences between the query and OMOP concept names
    # e.g. "type 2 diabetes" matches "Diabetes mellitus type 2 (disorder)".
    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens:
        tokens = [q]

    word_clauses = " AND ".join(f"concept_name ILIKE :w{i}" for i in range(len(tokens)))
    word_params = {f"w{i}": f"%{t}%" for i, t in enumerate(tokens)}

    sql = f"""
        SELECT concept_id, concept_name, vocabulary_id, domain_id, concept_class_id
        FROM cdm.concept
        WHERE ({word_clauses})
          AND (:domain IS NULL OR LOWER(domain_id) = LOWER(:domain))
          AND standard_concept = 'S'
        ORDER BY concept_name
        LIMIT :limit
    """
    rows = db.execute(text(sql), {"domain": domain, "limit": limit, **word_params})
    return [ConceptResult(**r._mapping) for r in rows]


@router.get("/{concept_id}", response_model=ConceptResult)
def get_concept(concept_id: int, db: Session = Depends(get_db)):
    sql = """
        SELECT concept_id, concept_name, vocabulary_id, domain_id, concept_class_id
        FROM cdm.concept
        WHERE concept_id = :concept_id
    """
    row = db.execute(text(sql), {"concept_id": concept_id}).fetchone()
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")
    return ConceptResult(**row._mapping)


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
