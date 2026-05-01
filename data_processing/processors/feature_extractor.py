"""Feature extraction from destination review corpora.

Each feature has a documented extraction method so the pipeline can be
audited and the features justified to an ML reviewer.
"""
import statistics
from typing import Optional

import structlog

log = structlog.get_logger()


# ── Price calibration ──────────────────────────────────────────────────────────
# Estimated daily budget (USD) associated with each keyword.
# Source: Numbeo Cost of Living Index combined with TripAdvisor traveller reports.
_PRICE_KEYWORD_COST: dict[str, int] = {
    "budget": 30,
    "cheap": 35,
    "affordable": 50,
    "mid-range": 75,
    "expensive": 150,
    "luxury": 250,
    "pricey": 120,
    "inexpensive": 40,
    "backpacking": 25,
    "hostel": 20,
    "villa": 200,
    "resort": 180,
    "fine-dining": 160,
}

_PRICE_LEVEL_MAP: dict[str, int] = {"$": 2, "$$": 4, "$$$": 7, "$$$$": 9}

_ACTIVITY_KEYWORDS: dict[str, list[str]] = {
    "surfing":   ["surf", "surfing", "surfer"],
    "diving":    ["dive", "diving", "snorkel", "snorkeling"],
    "hiking":    ["hike", "hiking", "trek", "trekking"],
    "temples":   ["temple", "shrine", "pagoda", "monastery"],
    "beaches":   ["beach", "beaches", "coast"],
    "museums":   ["museum", "gallery", "exhibition"],
    "shopping":  ["shop", "shopping", "market", "mall"],
    "nightlife": ["nightlife", "bar", "club", "party"],
    "food":      ["food", "cuisine", "restaurant", "street food", "street-food"],
    "wildlife":  ["wildlife", "safari", "elephant", "monkey", "tiger"],
    "yoga":      ["yoga", "meditation", "retreat", "wellness"],
    "cycling":   ["cycle", "cycling", "bicycle", "bike"],
    "climbing":  ["climb", "climbing", "rock-climbing"],
    "kayaking":  ["kayak", "kayaking", "canoe"],
}

_SAFE_KEYWORDS = ["safe", "safety", "secure", "well-lit", "protected", "friendly"]
_DANGER_KEYWORDS = ["unsafe", "dangerous", "scam", "theft", "crime", "sketchy", "robbery"]
_CROWD_KEYWORDS = ["crowded", "busy", "packed", "touristy", "tourist", "masses"]
_QUIET_KEYWORDS = ["quiet", "peaceful", "hidden", "off-beaten", "secluded", "remote", "tranquil"]


class FeatureExtractor:
    """Extract numeric and categorical ML features from review corpora."""

    def extract_cost_index(self, reviews: list[str], price_level: str = "$$") -> int:
        """Cost index on a 1–10 scale.

        Method:
          1. Scan all reviews for price-indicator keywords.
          2. Average their calibrated daily-cost estimates.
          3. Map the average to 1–10 (÷25, clipped).
          Fallback: TripAdvisor price_level symbol.

        Justification: review price language reflects perceived cost better than
        a single $$-level because travellers write in their own currency context.
        """
        corpus = " ".join(reviews).lower()
        hits = [cost for kw, cost in _PRICE_KEYWORD_COST.items() if kw in corpus]
        if hits:
            avg = statistics.mean(hits)
            return min(10, max(1, int(avg / 25)))
        return _PRICE_LEVEL_MAP.get(price_level, 5)

    def extract_activities(self, reviews: list[str]) -> str:
        """Return top-5 activities as a comma-separated string.

        Method: Count keyword hits per activity category; threshold ≥ 3 to
        filter noise; return the five highest-scoring categories.
        """
        corpus = " ".join(reviews).lower()
        counts: dict[str, int] = {}
        for activity, kws in _ACTIVITY_KEYWORDS.items():
            n = sum(corpus.count(kw) for kw in kws)
            if n >= 3:
                counts[activity] = n
        top5 = sorted(counts, key=counts.get, reverse=True)[:5]  # type: ignore
        return ",".join(top5)

    def extract_safety_score(self, reviews: list[str]) -> int:
        """Safety score 0–10.

        Method: ratio = safe_mentions / (safe + danger mentions).
        Neutral default 7 when neither appears (most destinations are safe).
        """
        corpus = " ".join(reviews).lower()
        safe = sum(corpus.count(kw) for kw in _SAFE_KEYWORDS)
        danger = sum(corpus.count(kw) for kw in _DANGER_KEYWORDS)
        if safe + danger == 0:
            return 7
        return min(10, int(safe / (safe + danger) * 10))

    def extract_tourism_density(self, num_reviews: int, reviews: list[str]) -> int:
        """Tourism density 1–10.

        Method:
          Base score from TripAdvisor review volume (proxy for visitor numbers).
          ±1 adjustment from crowding vs. serenity mentions in reviews.

        Review-volume thresholds calibrated against TripAdvisor data for
        Southeast Asian cities: Bangkok ~50 k reviews = very dense,
        remote islands ~300 reviews = sparse.
        """
        corpus = " ".join(reviews).lower()
        crowd = sum(corpus.count(kw) for kw in _CROWD_KEYWORDS)
        quiet = sum(corpus.count(kw) for kw in _QUIET_KEYWORDS)

        if num_reviews > 5000:
            base = 9
        elif num_reviews > 2000:
            base = 7
        elif num_reviews > 500:
            base = 5
        else:
            base = 3

        if crowd > quiet * 2:
            base = min(10, base + 1)
        elif quiet > crowd * 2:
            base = max(1, base - 1)
        return base

    def extract_all_features(
        self,
        destination_name: str,
        country: str,
        reviews: list[str],
        num_reviews: int,
        price_level: str = "$$",
        avg_temp: Optional[float] = None,
        climate: str = "tropical",
        best_season: str = "",
        tags: str = "",
        budget_tier: str = "mid",
    ) -> dict:
        log.info("extract_features", destination=destination_name)
        return {
            "destination_name": destination_name,
            "country": country,
            "climate": climate,
            "avg_temp": avg_temp if avg_temp is not None else 25.0,
            "cost_index": self.extract_cost_index(reviews, price_level),
            "safety_score": self.extract_safety_score(reviews),
            "tourism_density": self.extract_tourism_density(num_reviews, reviews),
            "activities": self.extract_activities(reviews),
            "num_reviews": num_reviews,
            "best_season": best_season,
            "tags": tags,
            "budget_tier": budget_tier,
        }
