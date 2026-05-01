"""
Sklearn Pipeline definition for the travel-style classifier.

Feature design
--------------
We use four independent features that are set before the labeling step,
ensuring no information from the labels leaks into the features:

  climate      Categorical — 6 climates (tropical, subtropical, temperate,
                continental, highland, arid). Objective geographic property.
  budget_tier  Categorical — 3 tiers (budget, mid, luxury). Hand-assigned
                from Numbeo cost-of-living data and Lonely Planet price tiers.
  best_season  Text — month ranges such as "Nov-Feb" or "Apr-Oct,Dec-Mar".
                Encoded with TF-IDF so the model learns seasonal patterns.
  tags         Text — comma-separated destination keywords (temple, beach, etc.).
                These are seed metadata, not derived from the labels, so using
                them as features is legitimate.

Preprocessing lives inside the Pipeline to prevent leakage: the TF-IDF
vocabulary and OHE categories are fit only on the training split.

Imported by train.py (fitting) and backend/app/services/ml_service.py
(inference).
"""
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


def build_preprocessor() -> ColumnTransformer:
    """Return a ColumnTransformer that handles all four feature types."""
    # sparse_threshold=0.0 forces dense output so every classifier works
    # (HistGradientBoostingClassifier rejects sparse matrices)
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["climate", "budget_tier"],
            ),
            (
                "season",
                # token_pattern keeps month abbreviations ("Nov", "Feb") and
                # "Year" from "Year-round"
                TfidfVectorizer(token_pattern=r"[A-Za-z]{3,}", max_features=30),
                "best_season",
            ),
            (
                "tags",
                # Accepts comma-separated keywords; token_pattern keeps
                # hyphenated terms intact (e.g. "street-food")
                TfidfVectorizer(token_pattern=r"[a-z][a-z\-]+", max_features=60),
                "tags",
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def build_pipeline(classifier) -> Pipeline:
    """Return a full sklearn Pipeline: preprocessing + classifier.

    The preprocessor is created fresh each call so pipelines are independent.
    """
    return Pipeline(
        steps=[
            ("preproc", build_preprocessor()),
            ("clf", classifier),
        ]
    )
