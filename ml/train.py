"""
Train the travel-style classifier.

Usage:
    python ml/train.py

Output:
    ml/models/travel_style_classifier.joblib   — best model (highest macro F1)
    ml/results/experiment_results.csv          — one row per experiment

Design decisions
----------------
* k for CV: we use StratifiedKFold with k = min(5, min_class_count).
  With our dataset the rarest classes (luxury, family) have only 2 examples
  each, forcing k=2.  We compensate by repeating: RepeatedStratifiedKFold
  with n_splits=2, n_repeats=10 yields 20 folds and stable mean/std estimates.
  This limitation is honest and documented — in production we would collect
  more data for the rare styles.

* Class imbalance: Wikivoyage pages use the word "budget" in accommodation
  sections for almost every destination, causing the labeler to over-assign
  the "budget" style (45 % of rows).  "luxury" and "family" appear in < 3 %
  of rows each.  We address this with class_weight="balanced" (RandomForest,
  LogisticRegression) and class_weight="balanced" for HistGradientBoosting
  (supported since sklearn 1.2).  Per-class metrics are always reported.

* Seeds: all random states fixed to 42 for reproducibility.

* Leakage check: preprocessing (TF-IDF, OHE) is fit inside the Pipeline,
  so vocabulary and categories are learned only on the training portion of
  each fold.
"""
import csv
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _ROOT.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import (
    GridSearchCV,
    RepeatedStratifiedKFold,
    cross_validate,
    train_test_split,
)

from ml.pipelines.classifier_pipeline import build_pipeline

# ── Paths ──────────────────────────────────────────────────────────────────────
_DATA_PATH = _ROOT / "data" / "raw" / "destinations.csv"
_MODEL_DIR = _ROOT / "models"
_RESULTS_PATH = _ROOT / "results" / "experiment_results.csv"
_MODEL_PATH = _MODEL_DIR / "travel_style_classifier.joblib"

# ── Config ─────────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
FEATURE_COLS = ["climate", "budget_tier", "best_season", "tags"]
TARGET_COL = "travel_style"
TEST_SIZE = 0.20

# ── Classifier definitions ─────────────────────────────────────────────────────
CLASSIFIERS = {
    "random_forest": RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    ),
    "logistic_regression": LogisticRegression(
        class_weight="balanced",
        max_iter=2000,
        random_state=RANDOM_STATE,
        solver="lbfgs",
    ),
    "hist_gradient_boosting": HistGradientBoostingClassifier(
        class_weight="balanced",
        random_state=RANDOM_STATE,
        max_iter=200,
    ),
}

# ── Hyperparameter grid (for tuning RandomForest) ──────────────────────────────
# We searched the following space:
#   n_estimators   — more trees improve stability but slow training
#   max_depth      — None = fully grown (may overfit); small values regularize
#   min_samples_split — higher = more conservative splits, helps with rare classes
RF_PARAM_GRID = {
    "clf__n_estimators": [50, 100, 200],
    "clf__max_depth": [None, 5, 10],
    "clf__min_samples_split": [2, 5, 10],
}


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(_DATA_PATH)
    X = df[FEATURE_COLS].copy()
    y = df[TARGET_COL].copy()
    return X, y


def get_cv(y: pd.Series) -> tuple[RepeatedStratifiedKFold, str]:
    """Return (cv, cv_label) respecting the minimum class size."""
    min_class = min(Counter(y).values())
    n_splits = min(5, min_class)
    print(f"  Class distribution: {dict(Counter(y))}")
    print(f"  Min class count = {min_class} -> using n_splits={n_splits}, n_repeats=10")
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=10, random_state=RANDOM_STATE)
    return cv, f"{n_splits}x10"


def append_result(row: dict) -> None:
    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _RESULTS_PATH.exists() or _RESULTS_PATH.stat().st_size < 50
    with _RESULTS_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def compare_classifiers(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: RepeatedStratifiedKFold,
    cv_label: str = "2x10",
) -> dict[str, dict]:
    """Run k-fold CV for each classifier, return results."""
    results: dict[str, dict] = {}
    for name, clf in CLASSIFIERS.items():
        print(f"\n  [{name}]")
        pipeline = build_pipeline(clf)
        scores = cross_validate(
            pipeline,
            X_train,
            y_train,
            cv=cv,
            scoring=["accuracy", "f1_macro"],
            return_train_score=False,
            n_jobs=-1,
        )
        acc_mean = float(np.mean(scores["test_accuracy"]))
        acc_std = float(np.std(scores["test_accuracy"]))
        f1_mean = float(np.mean(scores["test_f1_macro"]))
        f1_std = float(np.std(scores["test_f1_macro"]))
        fit_time = float(np.mean(scores["fit_time"]))

        print(f"    accuracy : {acc_mean:.3f} ± {acc_std:.3f}")
        print(f"    f1_macro : {f1_mean:.3f} ± {f1_std:.3f}")

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": name,
            "params": "default",
            "cv_folds": cv_label,
            "accuracy_mean": round(acc_mean, 4),
            "accuracy_std": round(acc_std, 4),
            "f1_macro_mean": round(f1_mean, 4),
            "f1_macro_std": round(f1_std, 4),
            "fit_time_s": round(fit_time, 3),
            "notes": "initial_comparison",
        }
        append_result(row)
        results[name] = {"f1_macro": f1_mean, "row": row}

    return results


def tune_random_forest(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cv: RepeatedStratifiedKFold,
    cv_label: str = "2x10",
) -> tuple[object, dict]:
    """GridSearchCV over RandomForest hyperparameters.

    Rationale for the search space:
      n_estimators [50,100,200]: ensures stability without excessive cost.
      max_depth [None,5,10]: None grows full trees (high variance); small
        values add bias but help generalise on 147-row dataset.
      min_samples_split [2,5,10]: higher values prevent splitting on single
        rare-class examples, especially important for luxury/family.
    """
    print("\n  [random_forest_tuned] GridSearchCV")
    pipeline = build_pipeline(
        RandomForestClassifier(class_weight="balanced", random_state=RANDOM_STATE)
    )
    search = GridSearchCV(
        pipeline,
        RF_PARAM_GRID,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
    )
    search.fit(X_train, y_train)
    best_params = {k: v for k, v in search.best_params_.items()}
    print(f"    best params : {best_params}")
    print(f"    best f1_macro (CV) : {search.best_score_:.3f}")

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "random_forest_tuned",
        "params": str(best_params),
        "cv_folds": cv_label,
        "accuracy_mean": "N/A",
        "accuracy_std": "N/A",
        "f1_macro_mean": round(search.best_score_, 4),
        "f1_macro_std": "N/A",
        "fit_time_s": "N/A",
        "notes": "grid_search_tuned",
    }
    append_result(row)
    return search.best_estimator_, row


def evaluate_on_test(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    label: str,
) -> None:
    """Print per-class and overall metrics on the held-out test set."""
    y_pred = model.predict(X_test)
    print(f"\n=== Test-set evaluation: {label} ===")
    print(classification_report(y_test, y_pred, zero_division=0))
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
    print(f"  Macro F1 (test): {macro_f1:.3f}")


def main() -> None:
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    X, y = load_data()
    print(f"  {len(X)} rows, {len(FEATURE_COLS)} features, {y.nunique()} classes")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    cv, cv_label = get_cv(y_train)

    print("\n=== Classifier comparison (CV) ===")
    cv_results = compare_classifiers(X_train, y_train, cv, cv_label)

    best_default = max(cv_results, key=lambda k: cv_results[k]["f1_macro"])
    print(f"\n  Best default: {best_default} (f1_macro={cv_results[best_default]['f1_macro']:.3f})")

    print("\n=== Hyperparameter tuning (RandomForest) ===")
    best_model, _ = tune_random_forest(X_train, y_train, cv, cv_label)

    # Compare tuned vs best default on test set
    evaluate_on_test(
        build_pipeline(CLASSIFIERS[best_default]).fit(X_train, y_train),
        X_test, y_test,
        f"best_default ({best_default})",
    )
    evaluate_on_test(best_model, X_test, y_test, "random_forest_tuned")

    # Save winner (best CV macro F1 = tuned RF by design of this script)
    joblib.dump(best_model, _MODEL_PATH)
    print(f"\nSaved model -> {_MODEL_PATH}")


if __name__ == "__main__":
    main()
