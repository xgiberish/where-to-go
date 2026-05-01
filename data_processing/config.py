"""Configuration for the data processing pipeline."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).parent


class DataProcessingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DP_", env_file=".env", extra="ignore")

    # ── Paths ──────────────────────────────────────────────────────────────────
    ROOT_DIR: Path = _ROOT
    RAW_DATA_DIR: Path = _ROOT / "data" / "raw"
    CLEAN_DATA_DIR: Path = _ROOT / "data" / "clean"
    METADATA_DIR: Path = _ROOT / "data" / "metadata"

    # ── Scraping ───────────────────────────────────────────────────────────────
    RATE_LIMIT_DELAY: float = 2.0
    MAX_REVIEWS_PER_DESTINATION: int = 100
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # ── Target regions ─────────────────────────────────────────────────────────
    TARGET_REGIONS: list[str] = [
        "Thailand", "Vietnam", "Indonesia", "Japan", "Cambodia",
        "Philippines", "Singapore", "Malaysia", "Laos", "Nepal",
        "Myanmar", "South Korea", "Bhutan", "Sri Lanka",
    ]

    # ── Travel-style keyword sets ──────────────────────────────────────────────
    # Each set determines what fraction of reviews mention that style.
    # See labeler.py for the density calculation logic.

    ADVENTURE_KEYWORDS: list[str] = [
        "trek", "trekking", "hike", "hiking", "adventure", "climb", "climbing",
        "mountain", "extreme", "rafting", "diving", "surf", "surfing",
        "snorkel", "snorkeling", "scuba",
        "wildlife", "expedition", "kayaking", "paragliding", "zip-line",
        "rappelling", "volcano", "mountaineering", "canyoning", "abseiling",
    ]

    RELAXATION_KEYWORDS: list[str] = [
        "relax", "relaxing", "spa", "massage", "peaceful",
        "quiet", "serene", "calm", "resort", "pool", "sunset",
        "paradise", "tranquil", "zen", "yoga", "hammock", "retreat",
        "hot-springs", "onsen", "wellness",
        # "beach" intentionally excluded — too generic, fires on adventure destinations
    ]

    CULTURE_KEYWORDS: list[str] = [
        "temple", "culture", "cultural", "history", "historical",
        "museum", "art", "traditional", "heritage", "ancient",
        "architecture", "palace", "ruins", "monument", "shrine",
        "monastery", "pagoda", "colonial", "UNESCO", "pilgrimage",
    ]

    BUDGET_KEYWORDS: list[str] = [
        "cheap", "affordable", "backpack", "backpacking",
        "hostel", "inexpensive", "value", "economical", "bargain",
        "street-food", "night-market", "guesthouse",
        # "budget" intentionally excluded — Wikivoyage uses it as a section header
        # ("Budget accommodation", "Budget hotels") on every page regardless of style
    ]

    LUXURY_KEYWORDS: list[str] = [
        "luxury", "luxurious", "high-end", "premium", "exclusive",
        "upscale", "5-star", "five-star", "elegant", "sophisticated",
        "gourmet", "fine-dining", "private", "villa", "butler",
        "rooftop", "infinity-pool",
    ]

    FAMILY_KEYWORDS: list[str] = [
        "family", "families", "kids", "children", "child-friendly",
        "safe", "park", "playground", "educational", "zoo",
        "aquarium", "theme-park", "stroller", "baby",
    ]

    # ── Labeling thresholds ────────────────────────────────────────────────────
    MIN_REVIEWS_FOR_LABELING: int = 30
    # Minimum keyword density (total occurrences / num_reviews) for a label
    KEYWORD_THRESHOLD: float = 0.15

    # ── Content sources ────────────────────────────────────────────────────────
    WIKIVOYAGE_API: str = "https://en.wikivoyage.org/w/api.php"
    WIKIPEDIA_API: str = "https://en.wikipedia.org/w/api.php"
    # Minimum paragraph character length to keep (filters boilerplate headers)
    MIN_PARAGRAPH_LENGTH: int = 80
    # Maximum paragraphs to keep per destination
    MAX_PARAGRAPHS: int = 40


def get_config() -> DataProcessingConfig:
    return DataProcessingConfig()
