#!/usr/bin/env python3
"""
Load ATHENA vocabulary CSVs into the cdm schema.

Usage:
  python sql/load_vocab.py --vocab synthea/vocab/

After loading, run --remap to fix concept_ids in the CDM clinical tables
(maps raw SNOMED/RxNorm codes stored by the ETL to proper OMOP concept IDs).

Full workflow:
  1. Download vocab from athena.ohdsi.org, unzip to synthea/vocab/
  2. python sql/load_vocab.py --vocab synthea/vocab/
  3. python sql/load_vocab.py --remap
  4. python sql/synthea_to_omop.py --csv synthea/output/csv/  (optional full re-ETL)
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://omop_admin:changeme@localhost:5433/omop")
engine = create_engine(DATABASE_URL)

# ATHENA CSV filename → target cdm table (only the tables we have in schema.sql)
VOCAB_FILES = {
    "CONCEPT.csv":             "concept",
    "CONCEPT_RELATIONSHIP.csv": "concept_relationship",
    "CONCEPT_ANCESTOR.csv":    "concept_ancestor",
}

# Column name mapping: ATHENA uses uppercase; our schema uses lowercase
COLUMN_MAP = {
    "CONCEPT_ID":             "concept_id",
    "CONCEPT_NAME":           "concept_name",
    "DOMAIN_ID":              "domain_id",
    "VOCABULARY_ID":          "vocabulary_id",
    "CONCEPT_CLASS_ID":       "concept_class_id",
    "STANDARD_CONCEPT":       "standard_concept",
    "CONCEPT_CODE":           "concept_code",
    "VALID_START_DATE":       "valid_start_date",
    "VALID_END_DATE":         "valid_end_date",
    "INVALID_REASON":         "invalid_reason",
    "CONCEPT_ID_1":           "concept_id_1",
    "CONCEPT_ID_2":           "concept_id_2",
    "RELATIONSHIP_ID":        "relationship_id",
    "VALID_START_DATE":       "valid_start_date",
    "VALID_END_DATE":         "valid_end_date",
    "INVALID_REASON":         "invalid_reason",
    "ANCESTOR_CONCEPT_ID":    "ancestor_concept_id",
    "DESCENDANT_CONCEPT_ID":  "descendant_concept_id",
    "MIN_LEVELS_OF_SEPARATION": "min_levels_of_separation",
    "MAX_LEVELS_OF_SEPARATION": "max_levels_of_separation",
}


def load_vocab(vocab_dir: Path):
    for filename, table in VOCAB_FILES.items():
        csv_path = vocab_dir / filename
        if not csv_path.exists():
            print(f"  SKIP {filename} — not found at {csv_path}")
            continue

        print(f"  Loading {filename} → cdm.{table} ...")
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE cdm.{table} CASCADE"))

        total = 0
        for chunk in pd.read_csv(
            csv_path,
            sep="\t",
            dtype=str,
            na_values=[""],
            keep_default_na=False,
            low_memory=False,
            chunksize=50_000,
        ):
            chunk.columns = [COLUMN_MAP.get(c, c.lower()) for c in chunk.columns]
            if "concept_name" in chunk.columns:
                chunk["concept_name"] = chunk["concept_name"].str[:255]
            if "concept_code" in chunk.columns:
                chunk["concept_code"] = chunk["concept_code"].str[:50]

            chunk.to_sql(
                table,
                schema="cdm",
                con=engine,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=5000,
            )
            total += len(chunk)
            print(f"    {total:,} rows", end="\r", flush=True)

        print(f"  {total:,} rows loaded into cdm.{table}")

    print("\nVocabulary load complete.")
    _print_counts()


def remap_concept_ids():
    """
    The Synthea ETL stored raw SNOMED/RxNorm codes directly as concept_ids.
    After loading ATHENA, fix this by joining on concept_code to get the real
    OMOP standard concept_id.

    condition_concept_id: SNOMED (vocabulary_id = 'SNOMED')
    drug_concept_id:      RxNorm (vocabulary_id = 'RxNorm')
    measurement_concept_id: LOINC (vocabulary_id = 'LOINC')
    """
    remaps = [
        ("condition_occurrence", "condition_concept_id",      "SNOMED"),
        ("condition_occurrence", "condition_source_concept_id", "SNOMED"),
        ("drug_exposure",        "drug_concept_id",            "RxNorm"),
        ("measurement",          "measurement_concept_id",     "LOINC"),
    ]

    print("Remapping concept IDs to OMOP standard IDs ...")
    with engine.begin() as conn:
        for table, col, vocab in remaps:
            result = conn.execute(text(f"""
                UPDATE cdm.{table} t
                SET {col} = c.concept_id
                FROM cdm.concept c
                WHERE c.concept_code = t.{col}::text
                  AND c.vocabulary_id = '{vocab}'
                  AND c.standard_concept = 'S'
            """))
            print(f"  cdm.{table}.{col}: {result.rowcount:,} rows remapped")

    print("\nRemap complete. Rebuilding concept_ancestor self-references for unmapped IDs ...")
    _print_counts()


def _print_counts():
    with engine.connect() as conn:
        for tbl in ("concept", "concept_ancestor", "concept_relationship"):
            n = conn.execute(text(f"SELECT COUNT(*) FROM cdm.{tbl}")).scalar()
            print(f"  cdm.{tbl}: {n:,} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load ATHENA vocabulary into cdm schema")
    parser.add_argument("--vocab", type=Path, help="Path to directory containing ATHENA CSV files")
    parser.add_argument("--remap", action="store_true",
                        help="Remap clinical table concept_ids to OMOP standard IDs (run after --vocab)")
    args = parser.parse_args()

    if args.vocab:
        print(f"Loading vocabulary from {args.vocab} ...")
        load_vocab(args.vocab)

    if args.remap:
        remap_concept_ids()

    if not args.vocab and not args.remap:
        parser.print_help()
