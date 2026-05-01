"""Data cleaning and validation for the labeling pipeline."""
import re
from typing import Any

import structlog

log = structlog.get_logger()

_VALID_STYLES = {"adventure", "relaxation", "culture", "budget", "luxury", "family"}
_VALID_TIERS = {"budget", "mid", "luxury"}
_VALID_CLIMATES = {"tropical", "subtropical", "temperate", "continental", "highland", "arid"}


def clean_text(text: str) -> str:
    """Normalise a string: strip, collapse whitespace, lowercase for comparisons."""
    return re.sub(r"\s+", " ", text.strip())


def clean_raw_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw CSV row; return the cleaned dict."""
    cleaned = {k: clean_text(str(v)) if isinstance(v, str) else v for k, v in row.items()}

    # Normalise numeric fields
    for field in ("rating", "num_reviews"):
        if field in cleaned:
            try:
                cleaned[field] = float(cleaned[field]) if field == "rating" else int(cleaned[field])
            except (ValueError, TypeError):
                cleaned[field] = 0

    return cleaned


def validate_labeled_row(row: dict[str, Any]) -> list[str]:
    """Return a list of validation error strings (empty = valid)."""
    errors: list[str] = []

    if not row.get("destination_name"):
        errors.append("missing destination_name")

    if not row.get("country"):
        errors.append("missing country")

    style = row.get("travel_style", "")
    if style not in _VALID_STYLES:
        errors.append(f"invalid travel_style '{style}' (must be one of {sorted(_VALID_STYLES)})")

    tier = row.get("budget_tier", "")
    if tier not in _VALID_TIERS:
        errors.append(f"invalid budget_tier '{tier}' (must be one of {sorted(_VALID_TIERS)})")

    climate = row.get("climate", "")
    if climate not in _VALID_CLIMATES:
        errors.append(f"invalid climate '{climate}' (must be one of {sorted(_VALID_CLIMATES)})")

    for field in ("cost_index", "safety_score", "tourism_density"):
        val = row.get(field)
        try:
            v = int(val)
            if not (1 <= v <= 10):
                errors.append(f"{field}={v} out of range [1, 10]")
        except (TypeError, ValueError):
            errors.append(f"{field} is not an integer: {val!r}")

    return errors


def deduplicate(rows: list[dict]) -> list[dict]:
    """Remove rows with duplicate destination_name (keep first occurrence)."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        key = row.get("destination_name", "").lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(row)
        else:
            log.warning("duplicate_dropped", destination=key)
    return out
