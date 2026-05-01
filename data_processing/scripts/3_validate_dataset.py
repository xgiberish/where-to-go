"""Script 3: Validate labeled dataset and export to ML training format.

Reads:   data/clean/destinations_labeled.csv
Writes:  ml/data/raw/destinations.csv  (ML training format)
         data/metadata/validation_report.json
"""
import csv
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

import structlog
from pydantic import ValidationError

from data_processing.config import get_config
from data_processing.utils.validation import LabeledDestinationRow, MLTrainingRow

log = structlog.get_logger()

_ML_OUTPUT_DIR = _PROJECT_ROOT / "ml" / "data" / "raw"


def run_validation() -> None:
    cfg = get_config()
    labeled_path = cfg.CLEAN_DATA_DIR / "destinations_labeled.csv"
    if not labeled_path.exists():
        log.error("labeled_csv_missing", path=str(labeled_path))
        sys.exit(1)

    with labeled_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    log.info("loaded_labeled", count=len(rows))

    valid: list[LabeledDestinationRow] = []
    invalid: list[dict] = []

    for row in rows:
        # coerce numeric strings
        for int_field in ("cost_index", "safety_score", "tourism_density", "num_reviews"):
            if int_field in row:
                try:
                    row[int_field] = int(float(row[int_field]))
                except (ValueError, TypeError):
                    pass
        for float_field in ("avg_temp",):
            if float_field in row:
                try:
                    row[float_field] = float(row[float_field])
                except (ValueError, TypeError):
                    pass

        try:
            valid.append(LabeledDestinationRow(**row))
        except ValidationError as exc:
            invalid.append({"destination": row.get("destination_name"), "errors": exc.errors()})
            log.warning(
                "schema_validation_failed",
                destination=row.get("destination_name"),
                errors=str(exc),
            )

    log.info("validation_complete", valid=len(valid), invalid=len(invalid))

    # ── Export ML training CSV ─────────────────────────────────────────────────
    _ML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ml_path = _ML_OUTPUT_DIR / "destinations.csv"

    ml_rows: list[MLTrainingRow] = []
    for row in valid:
        ml_rows.append(
            MLTrainingRow(
                name=row.destination_name,
                country=row.country,
                climate=row.climate,
                travel_style=row.travel_style,
                budget_tier=row.budget_tier,
                best_season=row.best_season,
                tags=row.tags,
            )
        )

    ml_fieldnames = ["name", "country", "climate", "travel_style", "budget_tier", "best_season", "tags"]
    with ml_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ml_fieldnames)
        writer.writeheader()
        for r in ml_rows:
            writer.writerow(r.model_dump())

    log.info("wrote_ml_csv", path=str(ml_path), rows=len(ml_rows))

    # ── Write validation report ────────────────────────────────────────────────
    report = {
        "total_input": len(rows),
        "valid": len(valid),
        "invalid": len(invalid),
        "ml_export_path": str(ml_path),
        "schema_errors": invalid,
        "coverage": {
            "travel_styles": _count_field(valid, "travel_style"),
            "budget_tiers": _count_field(valid, "budget_tier"),
            "climates": _count_field(valid, "climate"),
            "countries": _count_field(valid, "country"),
        },
    }

    report_path = cfg.METADATA_DIR / "validation_report.json"
    cfg.METADATA_DIR.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    log.info("wrote_validation_report", path=str(report_path))

    # ── Print summary ──────────────────────────────────────────────────────────
    print("\n=== Validation Summary ===")
    print(f"  Input rows:      {len(rows)}")
    print(f"  Valid:           {len(valid)}")
    print(f"  Invalid:         {len(invalid)}")
    print(f"  ML export:       {ml_path}")

    print("\n=== Travel Style Coverage ===")
    for style, count in sorted(report["coverage"]["travel_styles"].items(), key=lambda x: -x[1]):
        print(f"  {style:<14} {count:>4}")

    print("\n=== Budget Tier Coverage ===")
    for tier, count in sorted(report["coverage"]["budget_tiers"].items(), key=lambda x: -x[1]):
        print(f"  {tier:<10} {count:>4}")

    if invalid:
        print(f"\n  {len(invalid)} rows failed schema validation — see {report_path}")

    if len(valid) < 100:
        print(f"\n  WARNING: only {len(valid)} valid rows; ML training needs ≥ 100.")


def _count_field(rows: list[LabeledDestinationRow], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        val = str(getattr(row, field, ""))
        counts[val] = counts.get(val, 0) + 1
    return counts


if __name__ == "__main__":
    run_validation()
