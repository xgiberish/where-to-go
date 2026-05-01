"""Travel-style labeling via keyword-density analysis.

Labeling algorithm (fully documented — not arbitrary):

  1. Join all reviews for a destination into one corpus.
  2. For each of the six travel styles, count every occurrence of its keyword
     list using word-boundary regex (avoids partial matches like "hiking" inside
     "hitchhiking").
  3. Density = total_keyword_occurrences / num_reviews.
     (Normalising by review count makes destinations with more reviews
     directly comparable to those with fewer.)
  4. Primary label  = style with the highest density that exceeds THRESHOLD.
  5. Secondary labels = all other styles also above THRESHOLD, up to 2,
     sorted by density descending.
  6. If no style clears the threshold the destination is labelled "budget"
     (the catch-all for low-signal / generic destinations).

Confidence levels:
  high   >= 80 reviews
  medium >= 50 reviews
  low    <  50 reviews
"""
import re
from typing import Literal

import structlog

from data_processing.config import get_config

log = structlog.get_logger()

TravelStyle = Literal["adventure", "relaxation", "culture", "budget", "luxury", "family"]


class TravelStyleLabeler:
    def __init__(self) -> None:
        cfg = get_config()
        self.config = cfg
        self.keyword_sets: dict[str, list[str]] = {
            "adventure": cfg.ADVENTURE_KEYWORDS,
            "relaxation": cfg.RELAXATION_KEYWORDS,
            "culture": cfg.CULTURE_KEYWORDS,
            "budget": cfg.BUDGET_KEYWORDS,
            "luxury": cfg.LUXURY_KEYWORDS,
            "family": cfg.FAMILY_KEYWORDS,
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def label_destination(
        self,
        destination_name: str,
        reviews: list[str],
        budget_tier: str = "mid",
    ) -> dict:
        """Return labeling result for a single destination.

        Args:
            budget_tier: from destination metadata ("budget", "mid", "luxury").
                Used to validate the keyword-derived label: when keyword analysis
                would assign "budget" but metadata says mid/luxury, the second-best
                keyword label is used instead (guards against Wikivoyage section-header
                budget inflation).

        Returns:
            primary_label, secondary_labels, densities, confidence
        """
        log.info("labeling", destination=destination_name, reviews=len(reviews))

        densities = self._calculate_densities(reviews)
        if not densities:
            return {
                "primary_label": "budget",
                "secondary_labels": [],
                "densities": {},
                "confidence": "low",
            }

        primary = self._assign_primary(densities, budget_tier)
        secondary = self._assign_secondary(densities, primary)
        confidence = (
            "high" if len(reviews) >= 80
            else "medium" if len(reviews) >= 50
            else "low"
        )

        log.info(
            "labeled",
            destination=destination_name,
            primary=primary,
            secondary=secondary,
            confidence=confidence,
            top_density=max(densities.values()),
        )
        return {
            "primary_label": primary,
            "secondary_labels": secondary,
            "densities": densities,
            "confidence": confidence,
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _count_keywords(self, text: str, keywords: list[str]) -> int:
        total = 0
        for kw in keywords:
            total += len(re.findall(r"\b" + re.escape(kw.lower()) + r"\b", text))
        return total

    def _calculate_densities(self, reviews: list[str]) -> dict[str, float]:
        n = len(reviews)
        if n < self.config.MIN_REVIEWS_FOR_LABELING:
            log.warning(
                "insufficient_reviews",
                count=n,
                minimum=self.config.MIN_REVIEWS_FOR_LABELING,
            )
            return {}
        corpus = " ".join(reviews).lower()
        return {
            style: self._count_keywords(corpus, kws) / n
            for style, kws in self.keyword_sets.items()
        }

    def _assign_primary(
        self,
        densities: dict[str, float],
        budget_tier: str = "mid",
    ) -> TravelStyle:
        above = {s: d for s, d in densities.items() if d >= self.config.KEYWORD_THRESHOLD}
        if not above:
            # No style cleared threshold — use highest density rather than defaulting to
            # "budget", which would be wrong for most destinations that lack budget signal.
            best = max(densities, key=densities.get)  # type: ignore[arg-type]
            log.info("no_label_above_threshold", falling_back=best)
            return best  # type: ignore[return-value]

        best = max(above, key=above.get)  # type: ignore[arg-type]

        # Guard against Wikivoyage budget-section inflation: every Wikivoyage page
        # has "Budget accommodation" / "Budget hotels" headings regardless of actual
        # destination type. If keyword analysis picks "budget" but the destination
        # metadata says mid or luxury, fall back to the next-best label.
        if best == "budget" and budget_tier in ("mid", "luxury"):
            non_budget = {s: d for s, d in above.items() if s != "budget"}
            if non_budget:
                best = max(non_budget, key=non_budget.get)  # type: ignore[arg-type]
                log.info("budget_label_overridden_by_tier", budget_tier=budget_tier, new_label=best)

        return best  # type: ignore[return-value]

    def _assign_secondary(
        self,
        densities: dict[str, float],
        primary: str,
    ) -> list[str]:
        candidates = [
            s for s, d in densities.items()
            if s != primary and d >= self.config.KEYWORD_THRESHOLD
        ]
        return sorted(candidates, key=lambda s: densities[s], reverse=True)[:2]
