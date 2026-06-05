"""
Phase 4 — Output Airlock disclosure check tests.

These are the adversarial exfiltration attempt tests required for thesis evaluation.
Each test documents an attack and which check catches it.
"""

import json
import pytest
from apps.output_airlock.checks import (
    check_csv_small_cells,
    check_csv_id_columns,
    check_image_ocr,
    check_json_schema,
    run_checks,
    all_passed,
)


# ── CSV small-cell suppression ────────────────────────────────────────────────

def test_csv_small_cell_rejected():
    """Attack: export aggregate counts with a cell value of 3 (reveals < 10 patients)."""
    csv = b"condition,count\nDiabetes,3\nHypertension,45"
    _, passed, reason = check_csv_small_cells(csv)
    assert not passed
    assert "3" in reason


def test_csv_small_cell_value_1_rejected():
    """Attack: value of 1 reveals exactly one patient."""
    csv = b"year,patients\n2020,1\n2021,120"
    _, passed, _ = check_csv_small_cells(csv)
    assert not passed


def test_csv_all_large_values_pass():
    """Legitimate aggregate: all counts ≥ 10."""
    csv = b"condition,count\nDiabetes,45\nHypertension,120\nAsthma,10"
    _, passed, _ = check_csv_small_cells(csv)
    assert passed


def test_csv_zero_not_flagged():
    """Zero is not a small cell — it means no patients, not a disclosure."""
    csv = b"condition,count\nRare disease,0\nDiabetes,200"
    _, passed, _ = check_csv_small_cells(csv)
    assert passed


def test_csv_float_values_ignored():
    """Float values (e.g. mean HbA1c = 7.2) are not counts and should not be flagged."""
    csv = b"metric,value\nmean_hba1c,7.2\nstd_hba1c,1.4"
    _, passed, _ = check_csv_small_cells(csv)
    assert passed


def test_csv_empty_file_passes():
    csv = b"condition,count\n"
    _, passed, _ = check_csv_small_cells(csv)
    assert passed


# ── CSV ID column detection ───────────────────────────────────────────────────

def test_csv_pseudo_id_column_rejected():
    """Attack: export pseudo_id with data — reveals linkable patient identifiers."""
    rows = "\n".join(
        f"patient_{i:03d},Diabetes,2022-01-01" for i in range(10)
    )
    csv = f"pseudo_id,condition,date\n{rows}".encode()
    _, passed, reason = check_csv_id_columns(csv)
    assert not passed
    assert "pseudo_id" in reason


def test_csv_person_id_column_rejected():
    """Attack: column named 'person_id' with unique hashes."""
    rows = "\n".join(f"hash{i:040d},Diabetes" for i in range(10))
    csv = f"person_id,condition\n{rows}".encode()
    _, passed, _ = check_csv_id_columns(csv)
    assert not passed


def test_csv_no_id_column_passes():
    """Legitimate CSV with no identifier columns."""
    csv = b"condition,count,mean_age\nDiabetes,120,58.3\nHypertension,200,62.1"
    _, passed, _ = check_csv_id_columns(csv)
    assert passed


def test_csv_id_column_with_duplicates_passes():
    """Column named 'id' but values repeat — not an individual-level leak."""
    csv = b"id,condition,count\ngroup_a,Diabetes,120\ngroup_a,Hypertension,45\ngroup_b,Diabetes,88"
    # Only 3 rows — below the 5-row threshold anyway
    _, passed, _ = check_csv_id_columns(csv)
    assert passed


# ── JSON schema check ─────────────────────────────────────────────────────────

def test_json_list_rejected():
    """Attack: export a list of patient records as JSON."""
    data = [{"patient_id": "abc", "condition": "Diabetes"}, {"patient_id": "def", "condition": "Asthma"}]
    _, passed, reason = check_json_schema(json.dumps(data).encode())
    assert not passed
    assert "array" in reason.lower()


def test_json_nested_list_of_objects_rejected():
    """Attack: nest row data inside an aggregate-looking dict."""
    data = {"summary": {"total": 100}, "rows": [{"id": "x", "val": 1}, {"id": "y", "val": 2}]}
    _, passed, reason = check_json_schema(json.dumps(data).encode())
    assert not passed
    assert "array" in reason.lower()


def test_json_aggregate_dict_passes():
    """Legitimate: aggregate stats as a flat dict."""
    data = {"mean_hba1c": 7.4, "std": 1.2, "n": 120, "year": 2023}
    _, passed, _ = check_json_schema(json.dumps(data).encode())
    assert passed


def test_json_nested_aggregate_passes():
    """Legitimate: nested dicts of aggregate stats."""
    data = {"2022": {"mean": 7.1, "n": 80}, "2023": {"mean": 7.4, "n": 120}}
    _, passed, _ = check_json_schema(json.dumps(data).encode())
    assert passed


def test_json_invalid_rejected():
    _, passed, _ = check_json_schema(b"not json {")
    assert not passed


# ── run_checks dispatch ───────────────────────────────────────────────────────

def test_run_checks_csv_dispatches_both():
    csv = b"condition,count\nDiabetes,120"
    results = run_checks("results.csv", csv)
    names = [r[0] for r in results]
    assert "small_cell" in names
    assert "id_column" in names


def test_run_checks_json_dispatches():
    results = run_checks("stats.json", b'{"n": 100}')
    assert results[0][0] == "json_schema"


def test_run_checks_unknown_extension_fails():
    results = run_checks("model.pkl", b"\x80\x04\x95")
    assert not results[0][1]


def test_all_passed_helper():
    assert all_passed([("a", True, "ok"), ("b", True, "ok")])
    assert not all_passed([("a", True, "ok"), ("b", False, "fail")])
