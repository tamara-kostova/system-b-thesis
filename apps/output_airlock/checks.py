"""
Phase 4 — Output Airlock disclosure checks.

Each check returns (check_name, passed, reason).
run_checks() dispatches by file extension and returns all applicable checks.

EHDS Article 50: output checking before release from SPE.
"""

import csv
import io
import json
import re

from shared.suppression import THRESHOLD

CheckResult = tuple[str, bool, str]


def check_csv_small_cells(content: bytes) -> CheckResult:
    """Every numeric integer value in the CSV must be ≥ 10 (THRESHOLD)."""
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        return ("small_cell", False, f"Could not parse CSV: {e}")

    if len(rows) < 2:
        return ("small_cell", True, "CSV has no data rows — nothing to check")

    headers = rows[0]
    for row_idx, row in enumerate(rows[1:], 2):
        for col_idx, cell in enumerate(row):
            cell = cell.strip()
            try:
                f = float(cell)
                if f == int(f) and 0 < int(f) < THRESHOLD:
                    col_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                    return (
                        "small_cell",
                        False,
                        f"Row {row_idx}, column '{col_name}': value {int(f)} violates "
                        f"small-cell suppression (must be ≥ 10)",
                    )
            except (ValueError, TypeError):
                pass

    return ("small_cell", True, "All numeric values ≥ 10")


def check_csv_id_columns(content: bytes) -> CheckResult:
    """Reject CSV columns that look like patient identifiers (all-unique values + ID-like name)."""
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        return ("id_column", False, f"Could not parse CSV: {e}")

    if not rows or len(rows) < 5:
        return ("id_column", True, "Insufficient rows for identifier detection")

    id_keywords = {"id", "identifier", "pseudo", "key", "patient", "person", "subject", "hash"}

    for col in (rows[0].keys() if rows else []):
        col_lower = col.lower().strip()
        if not any(kw in col_lower for kw in id_keywords):
            continue
        values = [row.get(col, "").strip() for row in rows]
        values = [v for v in values if v]
        if len(values) > 1 and len(set(values)) == len(values):
            return (
                "id_column",
                False,
                f"Column '{col}' has all-unique values ({len(values)} rows) "
                f"and appears to be a patient identifier",
            )

    return ("id_column", True, "No patient identifier columns detected")


def check_image_ocr(content: bytes) -> CheckResult:
    """OCR heuristic: extracted text must not contain > 100 unique numbers."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(img)
        unique_numbers = set(re.findall(r"\b\d+\b", text))
        if len(unique_numbers) > 100:
            return (
                "image_ocr",
                False,
                f"Image contains {len(unique_numbers)} unique numbers — potential data exfiltration",
            )
        return ("image_ocr", True, f"OCR found {len(unique_numbers)} unique numbers (≤ 100)")
    except ImportError:
        return (
            "image_ocr",
            False,
            "OCR unavailable (pytesseract not installed) — flagged for manual review",
        )
    except Exception as e:
        return ("image_ocr", False, f"OCR check failed ({e}) — flagged for manual review")


def check_json_schema(content: bytes) -> CheckResult:
    """JSON must be an aggregate object, not a list or nested array of row objects."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return ("json_schema", False, f"Invalid JSON: {e}")

    if isinstance(data, list):
        return ("json_schema", False, "JSON arrays are not allowed (potential row-level data)")

    if not isinstance(data, dict):
        return ("json_schema", False, "JSON must be an aggregate object")

    def _has_row_data(obj) -> bool:
        if isinstance(obj, list):
            if any(isinstance(x, dict) for x in obj):
                return True
        elif isinstance(obj, dict):
            return any(_has_row_data(v) for v in obj.values())
        return False

    if _has_row_data(data):
        return (
            "json_schema",
            False,
            "JSON contains arrays of objects — potential row-level data",
        )

    return ("json_schema", True, "JSON structure is aggregate-safe")


def run_checks(filename: str, content: bytes) -> list[CheckResult]:
    """Dispatch checks by file extension. Returns list of (name, passed, reason)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        return [
            check_csv_small_cells(content),
            check_csv_id_columns(content),
        ]
    elif ext in ("png", "jpg", "jpeg", "gif", "bmp", "tiff"):
        return [check_image_ocr(content)]
    elif ext == "json":
        return [check_json_schema(content)]
    else:
        return [
            ("unknown_format", False, f"Unsupported file type '.{ext}' — manual review required")
        ]


def all_passed(results: list[CheckResult]) -> bool:
    return all(passed for _, passed, _ in results)
