#!/usr/bin/env python3
"""
Convert Synthea CSV output to OMOP CDM v5.4 and load into Postgres.

Synthea outputs its own CSV schema; this maps the key tables to OMOP.
Concept IDs are mapped via the included lookup tables (SNOMED, RxNorm, LOINC).

Usage:
  python sql/synthea_to_omop.py --csv synthea/output/csv/
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Standard OMOP type concept IDs
# ---------------------------------------------------------------------------
VISIT_TYPE_EHR       = 9202    # Outpatient Visit
CONDITION_TYPE_EHR   = 32020   # EHR encounter diagnosis
DRUG_TYPE_RX         = 38000177
MEAS_TYPE_EHR        = 5001

# Fallback concept IDs when no mapping found
UNKNOWN = 0
INT_MAX = 2_147_483_647


def _safe_int(val) -> int:
    """Convert to int, returning 0 if non-numeric or out of Postgres INTEGER range."""
    try:
        v = int(float(val))
        return v if 0 <= v <= INT_MAX else UNKNOWN
    except (ValueError, TypeError):
        return UNKNOWN

# ---------------------------------------------------------------------------
# Minimal concept vocabulary built from whatever Synthea data we load
# ---------------------------------------------------------------------------

_concepts: dict[int, dict] = {}

def _register_concept(concept_id, name, domain, vocabulary, concept_class="Clinical Finding"):
    if concept_id and concept_id != UNKNOWN and concept_id not in _concepts:
        _concepts[concept_id] = {
            "concept_id":       concept_id,
            "concept_name":     str(name)[:255],
            "domain_id":        domain,
            "vocabulary_id":    vocabulary,
            "concept_class_id": concept_class,
            "standard_concept": "S",
            "concept_code":     str(concept_id),
            "valid_start_date": "1970-01-01",
            "valid_end_date":   "2099-12-31",
            "invalid_reason":   None,
        }

# ---------------------------------------------------------------------------
# Transform functions
# ---------------------------------------------------------------------------

def transform_persons(df: pd.DataFrame) -> pd.DataFrame:
    gender_map = {"M": 8507, "F": 8532}
    race_map = {
        "white":                                  8527,
        "black":                                  8516,
        "asian":                                  8515,
        "native":                                 8657,
        "other":                                  8522,
    }

    out = pd.DataFrame()
    out["person_id"]             = range(1, len(df) + 1)
    out["gender_concept_id"]     = df["GENDER"].str.upper().map(gender_map).fillna(UNKNOWN).astype(int)
    out["year_of_birth"]         = pd.to_datetime(df["BIRTHDATE"]).dt.year
    out["month_of_birth"]        = pd.to_datetime(df["BIRTHDATE"]).dt.month
    out["day_of_birth"]          = pd.to_datetime(df["BIRTHDATE"]).dt.day
    out["race_concept_id"]       = df["RACE"].str.lower().map(race_map).fillna(UNKNOWN).astype(int)
    out["ethnicity_concept_id"]  = df["ETHNICITY"].str.lower().map(
        {"nonhispanic": 38003564, "hispanic": 38003563}
    ).fillna(UNKNOWN).astype(int)
    out["person_source_value"]   = df["Id"]
    out["gender_source_value"]   = df["GENDER"]
    out["gender_source_concept_id"]    = out["gender_concept_id"]
    out["race_source_value"]           = df["RACE"]
    out["race_source_concept_id"]      = out["race_concept_id"]
    out["ethnicity_source_value"]      = df["ETHNICITY"]
    out["ethnicity_source_concept_id"] = out["ethnicity_concept_id"]

    # Register gender/race concepts
    for cid, name, domain, vocab in [
        (8507, "Male",   "Gender",    "Gender"),
        (8532, "Female", "Gender",    "Gender"),
        (8527, "White",  "Race",      "Race"),
        (8516, "Black or African American", "Race", "Race"),
        (8515, "Asian",  "Race",      "Race"),
        (38003564, "Non-Hispanic", "Ethnicity", "Ethnicity"),
        (38003563, "Hispanic",     "Ethnicity", "Ethnicity"),
    ]:
        _register_concept(cid, name, domain, vocab, domain)

    # Build patient_id lookup: Synthea UUID → our integer person_id
    id_map = dict(zip(df["Id"], out["person_id"]))
    return out, id_map


def transform_visits(df: pd.DataFrame, id_map: dict) -> pd.DataFrame:
    out = pd.DataFrame()
    out["visit_occurrence_id"]   = range(1, len(df) + 1)
    out["person_id"]             = df["PATIENT"].map(id_map)
    out["visit_concept_id"]      = VISIT_TYPE_EHR
    out["visit_start_date"]      = pd.to_datetime(df["START"]).dt.date
    out["visit_end_date"]        = pd.to_datetime(df["STOP"]).dt.date
    out["visit_type_concept_id"] = VISIT_TYPE_EHR
    out["visit_source_value"]    = df.get("ENCOUNTERCLASS", pd.Series(dtype=str)).str[:50]
    out = out.dropna(subset=["person_id"])
    out["person_id"] = out["person_id"].astype(int)

    # Build encounter_id → visit_occurrence_id lookup
    enc_map = dict(zip(df["Id"], out["visit_occurrence_id"]))
    _register_concept(VISIT_TYPE_EHR, "Outpatient Visit", "Visit", "Visit", "Visit")
    return out, enc_map


def transform_conditions(df: pd.DataFrame, id_map: dict, enc_map: dict) -> pd.DataFrame:
    out = pd.DataFrame()
    out["condition_occurrence_id"]    = range(1, len(df) + 1)
    out["person_id"]                  = df["PATIENT"].map(id_map)
    out["condition_start_date"]       = pd.to_datetime(df["START"]).dt.date
    out["condition_end_date"]         = pd.to_datetime(df["STOP"]).dt.date if "STOP" in df.columns else None
    out["condition_type_concept_id"]  = CONDITION_TYPE_EHR
    out["visit_occurrence_id"]        = df["ENCOUNTER"].map(enc_map)
    out["condition_source_value"]     = df["DESCRIPTION"].str[:50]
    # Synthea provides SNOMED codes in CODE column
    out["condition_concept_id"]        = df["CODE"].apply(_safe_int)
    out["condition_source_concept_id"] = out["condition_concept_id"]
    out = out.dropna(subset=["person_id"])
    out["person_id"] = out["person_id"].astype(int)

    for _, row in df.iterrows():
        cid = _safe_int(row["CODE"])
        _register_concept(cid, row["DESCRIPTION"], "Condition", "SNOMED")
    _register_concept(CONDITION_TYPE_EHR, "EHR encounter diagnosis", "Type Concept", "Type Concept", "Type Concept")
    return out


def transform_drugs(df: pd.DataFrame, id_map: dict, enc_map: dict) -> pd.DataFrame:
    out = pd.DataFrame()
    out["drug_exposure_id"]             = range(1, len(df) + 1)
    out["person_id"]                    = df["PATIENT"].map(id_map)
    out["drug_exposure_start_date"]     = pd.to_datetime(df["START"]).dt.date
    out["drug_exposure_end_date"]       = pd.to_datetime(df["STOP"]).dt.date if "STOP" in df.columns else None
    out["drug_type_concept_id"]         = DRUG_TYPE_RX
    out["visit_occurrence_id"]          = df["ENCOUNTER"].map(enc_map)
    out["drug_source_value"]            = df["DESCRIPTION"].str[:50]
    out["drug_concept_id"]              = df["CODE"].apply(_safe_int)
    out["drug_source_concept_id"]       = out["drug_concept_id"]
    out = out.dropna(subset=["person_id"])
    out["person_id"] = out["person_id"].astype(int)

    for _, row in df.iterrows():
        cid = _safe_int(row["CODE"])
        _register_concept(cid, row["DESCRIPTION"], "Drug", "RxNorm", "Ingredient")
    _register_concept(DRUG_TYPE_RX, "Prescription written", "Type Concept", "Type Concept", "Type Concept")
    return out


def transform_observations(df: pd.DataFrame, id_map: dict, enc_map: dict) -> pd.DataFrame:
    # Synthea observations → OMOP measurement
    numeric = pd.to_numeric(df["VALUE"], errors="coerce")
    df_num  = df[numeric.notna()].copy()
    df_num["_value"] = numeric[numeric.notna()]

    out = pd.DataFrame()
    out["measurement_id"]               = range(1, len(df_num) + 1)
    out["person_id"]                    = df_num["PATIENT"].map(id_map)
    out["measurement_date"]             = pd.to_datetime(df_num["DATE"]).dt.date
    out["measurement_type_concept_id"]  = MEAS_TYPE_EHR
    out["visit_occurrence_id"]          = df_num["ENCOUNTER"].map(enc_map)
    out["measurement_source_value"]     = df_num["DESCRIPTION"].str[:50]
    out["value_as_number"]              = df_num["_value"]
    out["unit_source_value"]            = df_num.get("UNITS", pd.Series(dtype=str))
    out["measurement_concept_id"]        = df_num["CODE"].apply(_safe_int)
    out["measurement_source_concept_id"] = out["measurement_concept_id"]
    out["unit_concept_id"]              = UNKNOWN
    out = out.dropna(subset=["person_id"])
    out["person_id"] = out["person_id"].astype(int)

    for _, row in df_num.iterrows():
        cid = _safe_int(row["CODE"])
        _register_concept(cid, row["DESCRIPTION"], "Measurement", "LOINC", "Lab Test")
    _register_concept(MEAS_TYPE_EHR, "Test ordered through EHR order entry", "Type Concept", "Type Concept", "Type Concept")
    return out


def make_concept_ancestor() -> list[dict]:
    rows = []
    for cid in _concepts:
        rows.append({
            "ancestor_concept_id":      cid,
            "descendant_concept_id":    cid,
            "min_levels_of_separation": 0,
            "max_levels_of_separation": 0,
        })
    return rows


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load(engine, table: str, df: pd.DataFrame):
    if df.empty:
        print(f"  {table:<30} 0 rows (empty)")
        return
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE cdm.{table} CASCADE"))
    df.to_sql(table, schema="cdm", con=engine, if_exists="append",
              index=False, chunksize=5000, method="multi")
    print(f"  {table:<30} {len(df):>8,} rows")


def read_csv(base: Path, name: str) -> pd.DataFrame:
    candidates = list(base.glob(f"{name}.csv")) + list(base.glob(f"{name.upper()}.csv"))
    if not candidates:
        print(f"  [warn] {name}.csv not found in {base}")
        return pd.DataFrame()
    return pd.read_csv(candidates[0], dtype=str, low_memory=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, metavar="DIR", help="Synthea output/csv/ directory")
    parser.add_argument("--db-url", default=None)
    args = parser.parse_args()

    db_url = args.db_url or os.getenv("DATABASE_URL", "postgresql://omop_admin:changeme@localhost:5433/omop")
    engine = create_engine(db_url)
    base   = Path(args.csv)

    schema_sql = (Path(__file__).parent / "schema.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    print("Schema applied.\n")

    print("Reading Synthea CSVs...")
    raw_patients     = read_csv(base, "patients")
    raw_encounters   = read_csv(base, "encounters")
    raw_conditions   = read_csv(base, "conditions")
    raw_medications  = read_csv(base, "medications")
    raw_observations = read_csv(base, "observations")

    print("Transforming...")
    persons, id_map  = transform_persons(raw_patients)
    visits,  enc_map = transform_visits(raw_encounters, id_map)
    conditions       = transform_conditions(raw_conditions,  id_map, enc_map)
    drugs            = transform_drugs(raw_medications,  id_map, enc_map)
    measurements     = transform_observations(raw_observations, id_map, enc_map)
    concepts_df      = pd.DataFrame(list(_concepts.values()))
    ancestors_df     = pd.DataFrame(make_concept_ancestor())

    print("\nLoading into Postgres:")
    load(engine, "concept",              concepts_df)
    load(engine, "concept_ancestor",     ancestors_df)
    load(engine, "person",               persons)
    load(engine, "visit_occurrence",     visits)
    load(engine, "condition_occurrence", conditions)
    load(engine, "drug_exposure",        drugs)
    load(engine, "measurement",          measurements)

    print("\nDone. Save these for your thesis evaluation chapter:")
    with engine.connect() as conn:
        for t in ["person", "condition_occurrence", "drug_exposure", "measurement"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM cdm.{t}")).scalar()
            print(f"  {t}: {n:,}")


if __name__ == "__main__":
    main()
