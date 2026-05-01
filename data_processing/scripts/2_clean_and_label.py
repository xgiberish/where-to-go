"""Script 2: Clean raw CSV, label destinations, extract features.

Reads:   data/raw/destinations_raw.csv
Writes:  data/clean/destinations_labeled.csv
         data/metadata/labeling_rules.json
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

import structlog

from data_processing.config import get_config
from data_processing.processors.cleaner import clean_raw_row, deduplicate, validate_labeled_row
from data_processing.processors.feature_extractor import FeatureExtractor
from data_processing.processors.labeler import TravelStyleLabeler

log = structlog.get_logger()


def run_pipeline() -> None:
    cfg = get_config()
    raw_path = cfg.RAW_DATA_DIR / "destinations_raw.csv"
    if not raw_path.exists():
        log.error("raw_csv_missing", path=str(raw_path))
        sys.exit(1)

    cfg.CLEAN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg.METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load raw rows ──────────────────────────────────────────────────────────
    with raw_path.open(newline="", encoding="utf-8") as fh:
        raw_rows = list(csv.DictReader(fh))

    log.info("loaded_raw", count=len(raw_rows))

    cleaned = [clean_raw_row(r) for r in raw_rows]
    cleaned = deduplicate(cleaned)
    log.info("after_dedup", count=len(cleaned))

    # ── Label + extract features ───────────────────────────────────────────────
    labeler = TravelStyleLabeler()
    extractor = FeatureExtractor()

    labeled_rows: list[dict] = []
    density_log: dict[str, dict] = {}
    validation_errors: list[dict] = []

    for row in cleaned:
        name = row.get("destination_name", "")
        country = row.get("country", "")
        reviews_raw = row.get("reviews", "")
        reviews = [r.strip() for r in reviews_raw.split("|") if r.strip()]
        num_reviews = int(row.get("num_reviews", 0))

        budget_tier = row.get("budget_tier", "mid")
        label_result = labeler.label_destination(name, reviews, budget_tier=budget_tier)
        features = extractor.extract_all_features(
            destination_name=name,
            country=country,
            reviews=reviews,
            num_reviews=num_reviews,
            price_level=row.get("price_level", "$$"),
            avg_temp=float(row.get("avg_temp", 25)),
            climate=row.get("climate", "tropical"),
            best_season=row.get("best_season", ""),
            tags=row.get("tags", ""),
            budget_tier=row.get("budget_tier", "mid"),
        )

        # Source label: authoritative assignment from Lonely Planet, TripAdvisor
        # categories, and UNESCO designations recorded in the DESTINATIONS catalogue.
        # This is the training target because keyword-density on Wikivoyage guide text
        # has ~44% agreement with expert labels (inflated by "Budget accommodation"
        # section headers appearing on every page regardless of destination type).
        source_style = row.get("travel_style", "")
        keyword_style = label_result["primary_label"]
        training_style = source_style if source_style else keyword_style

        labeled = {
            **features,
            "travel_style": training_style,
            "keyword_label": keyword_style,       # stored for audit — not used in training
            "secondary_styles": ",".join(label_result["secondary_labels"]),
            "labeling_confidence": label_result["confidence"],
        }

        errors = validate_labeled_row(labeled)
        if errors:
            validation_errors.append({"destination": name, "errors": errors})
            log.warning("validation_failed", destination=name, errors=errors)
        else:
            labeled_rows.append(labeled)

        density_log[name] = {
            "densities": label_result["densities"],
            "primary_label": label_result["primary_label"],
            "secondary_labels": label_result["secondary_labels"],
            "confidence": label_result["confidence"],
        }

    log.info("labeled", total=len(labeled_rows), validation_failures=len(validation_errors))

    # ── Write destinations_labeled.csv ─────────────────────────────────────────
    out_path = cfg.CLEAN_DATA_DIR / "destinations_labeled.csv"
    if labeled_rows:
        fieldnames = list(labeled_rows[0].keys())
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(labeled_rows)
        log.info("wrote_labeled_csv", path=str(out_path), rows=len(labeled_rows))

    # ── Write labeling_rules.json ──────────────────────────────────────────────
    rules = {
        "algorithm": {
            "description": (
                "Keyword-density labeling. "
                "density = total_keyword_occurrences / num_reviews. "
                "Primary label = style with highest density >= KEYWORD_THRESHOLD. "
                "Secondary labels = other styles above threshold (up to 2). "
                "Fallback = 'budget' when no style clears threshold."
            ),
            "keyword_threshold": cfg.KEYWORD_THRESHOLD,
            "min_reviews_for_labeling": cfg.MIN_REVIEWS_FOR_LABELING,
        },
        "keyword_sets": {
            "adventure": cfg.ADVENTURE_KEYWORDS,
            "relaxation": cfg.RELAXATION_KEYWORDS,
            "culture": cfg.CULTURE_KEYWORDS,
            "budget": cfg.BUDGET_KEYWORDS,
            "luxury": cfg.LUXURY_KEYWORDS,
            "family": cfg.FAMILY_KEYWORDS,
        },
        "per_destination": density_log,
        "validation_errors": validation_errors,
    }
    rules_path = cfg.METADATA_DIR / "labeling_rules.json"
    with rules_path.open("w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=2)
    log.info("wrote_labeling_rules", path=str(rules_path))

    # ── Class distribution summary ─────────────────────────────────────────────
    style_counts: Counter = Counter(r["travel_style"] for r in labeled_rows)
    print("\n=== Travel Style Distribution ===")
    for style, count in sorted(style_counts.items(), key=lambda x: -x[1]):
        pct = count / len(labeled_rows) * 100 if labeled_rows else 0
        print(f"  {style:<14} {count:>4}  ({pct:.1f}%)")
    print(f"\n  Total labeled:  {len(labeled_rows)}")
    print(f"  Validation fails: {len(validation_errors)}")

    confidence_counts: Counter = Counter(r["labeling_confidence"] for r in labeled_rows)
    print("\n=== Confidence Distribution ===")
    for conf in ("high", "medium", "low"):
        print(f"  {conf:<8} {confidence_counts[conf]:>4}")


if __name__ == "__main__":
    run_pipeline()
