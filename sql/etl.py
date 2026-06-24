#!/usr/bin/env python3
"""
Phase 0 ETL — load synthetic OMOP data into Postgres.

Supports two input formats:
  --sqlite PATH   Eunomia SQLite file (.db / .sqlite)
  --csv   DIR     Directory of OMOP CSV files (Synthea ETL output)

Usage:
  python sql/etl.py --sqlite path/to/eunomia.db
  python sql/etl.py --csv    path/to/omop_csvs/
"""

import argparse
import os
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parent.parent / ".env")

# Tables to transfer, in dependency order
CLINICAL_TABLES = [
    "person",
    "visit_occurrence",
    "condition_occurrence",
    "drug_exposure",
    "measurement",
]
VOCAB_TABLES = [
    "concept",
    "concept_relationship",
    "concept_ancestor",
]
ALL_TABLES = CLINICAL_TABLES + VOCAB_TABLES

CHUNK_SIZE = 50_000


def get_engine(database_url: str):
    return create_engine(database_url)


def apply_schema(engine):
    schema_sql = (Path(__file__).parent / "schema.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    print("Schema applied.")


def load_from_sqlite(sqlite_path: str, engine):
    conn = sqlite3.connect(sqlite_path)
    available = {
        row[0].lower() for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    for table in ALL_TABLES:
        if table not in available:
            print(f"  skip {table} (not in SQLite)")
            continue
        _transfer_table(
            source=lambda t=table: pd.read_sql(f"SELECT * FROM {t}", conn),
            table=table,
            engine=engine,
        )

    conn.close()


def load_from_csv(csv_dir: str, engine):
    base = Path(csv_dir)
    for table in ALL_TABLES:
        candidates = list(base.glob(f"{table}*.csv")) + list(base.glob(f"{table.upper()}*.csv"))
        if not candidates:
            print(f"  skip {table} (no CSV found in {csv_dir})")
            continue
        path = candidates[0]
        _transfer_table(
            source=lambda p=path: pd.read_csv(p, dtype=str, keep_default_na=False),
            table=table,
            engine=engine,
        )


def _transfer_table(source, table: str, engine):
    print(f"  loading {table}... ", end="", flush=True)
    df: pd.DataFrame = source()

    # Lowercase all column names to match schema
    df.columns = [c.lower() for c in df.columns]

    # Replace empty strings with None so Postgres gets NULL
    df = df.replace("", None)

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE cdm.{table} CASCADE"))

    df.to_sql(
        name=table,
        schema="cdm",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=CHUNK_SIZE,
        method="multi",
    )
    print(f"{len(df):,} rows")


def verify(engine):
    print("\nRow counts:")
    with engine.connect() as conn:
        for table in ALL_TABLES:
            result = conn.execute(text(f"SELECT COUNT(*) FROM cdm.{table}"))
            count = result.scalar()
            print(f"  {table:<30} {count:>10,}")


def main():
    parser = argparse.ArgumentParser(description="Load synthetic OMOP data into Postgres")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sqlite", metavar="PATH", help="Eunomia SQLite file")
    group.add_argument("--csv", metavar="DIR", help="Directory of OMOP CSV files")
    parser.add_argument(
        "--db-url",
        default="postgresql://omop_admin:changeme@localhost:5432/omop",
        help="Postgres connection URL (default: from DATABASE_URL env or localhost)",
    )
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema creation")
    args = parser.parse_args()

    # Prefer DATABASE_URL from .env or environment
    db_url = os.getenv("DATABASE_URL", args.db_url)

    engine = get_engine(db_url)

    if not args.skip_schema:
        apply_schema(engine)

    print("\nLoading data...")
    if args.sqlite:
        load_from_sqlite(args.sqlite, engine)
    else:
        load_from_csv(args.csv, engine)

    verify(engine)
    print("\nDone.")


if __name__ == "__main__":
    main()
