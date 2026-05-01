"""Pydantic validation schemas for the data processing pipeline."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TravelStyle = Literal["adventure", "relaxation", "culture", "budget", "luxury", "family"]
BudgetTier = Literal["budget", "mid", "luxury"]
Climate = Literal["tropical", "subtropical", "temperate", "continental", "highland", "arid"]


class RawDestinationRow(BaseModel):
    """Schema for a row coming out of 1_fetch_raw_data.py (destinations_raw.csv)."""

    destination_name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    travel_style: TravelStyle
    budget_tier: BudgetTier = "mid"
    climate: Climate = "tropical"
    avg_temp: float = Field(ge=-30, le=50, default=25.0)
    best_season: str = Field(default="")
    tags: str = Field(default="")
    num_reviews: int = Field(ge=0, default=0)
    price_level: str = Field(default="$$")
    reviews: str = Field(default="")   # pipe-separated paragraphs from Wikivoyage

    @field_validator("price_level")
    @classmethod
    def validate_price_level(cls, v: str) -> str:
        if v not in ("$", "$$", "$$$", "$$$$"):
            return "$$"
        return v


class LabeledDestinationRow(BaseModel):
    """Schema for a fully processed row (destinations_labeled.csv)."""

    model_config = {"extra": "ignore"}

    destination_name: str
    country: str
    climate: Climate
    avg_temp: float = Field(ge=-30, le=50)
    cost_index: int = Field(ge=1, le=10)
    safety_score: int = Field(ge=0, le=10)
    tourism_density: int = Field(ge=1, le=10)
    activities: str
    num_reviews: int = Field(ge=0)
    travel_style: TravelStyle
    keyword_label: TravelStyle = "budget"   # keyword-density derived label (audit only)
    secondary_styles: str = Field(default="")
    labeling_confidence: Literal["high", "medium", "low"] = "low"
    best_season: str = Field(default="")
    tags: str = Field(default="")
    budget_tier: BudgetTier = "mid"


class MLTrainingRow(BaseModel):
    """Schema for the ML training CSV consumed by ml/train.py."""

    name: str
    country: str
    climate: Climate
    travel_style: TravelStyle
    budget_tier: BudgetTier
    best_season: str
    tags: str
