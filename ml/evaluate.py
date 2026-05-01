"""
Evaluate a saved model against a data file and print full metrics.

Usage:
    python ml/evaluate.py
    python ml/evaluate.py --model ml/models/travel_style_classifier.joblib \
                          --data  ml/data/raw/destinations.csv
"""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT.parent))

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

FEATURE_COLS = ["climate", "budget_tier", "best_season", "tags"]
TARGET_COL = "travel_style"


def evaluate(model_path: Path, data_path: Path) -> None:
    model = joblib.load(model_path)
    df = pd.read_csv(data_path)

    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    y_pred = model.predict(X)

    print(f"Model  : {model_path.name}")
    print(f"Data   : {data_path.name}  ({len(df)} rows)")
    print(f"Classes: {sorted(y.unique())}\n")

    print("=== Classification Report ===")
    print(classification_report(y, y_pred, zero_division=0))

    macro_f1 = f1_score(y, y_pred, average="macro", zero_division=0)
    weighted_f1 = f1_score(y, y_pred, average="weighted", zero_division=0)
    print(f"Macro F1   : {macro_f1:.4f}")
    print(f"Weighted F1: {weighted_f1:.4f}")

    print("\n=== Confusion Matrix ===")
    labels = sorted(y.unique())
    cm = confusion_matrix(y, y_pred, labels=labels)
    header = "            " + "  ".join(f"{l[:6]:>6}" for l in labels)
    print(header)
    for i, label in enumerate(labels):
        row = "  ".join(f"{v:>6}" for v in cm[i])
        print(f"  {label[:10]:<10}  {row}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default=str(_ROOT / "models" / "travel_style_classifier.joblib"),
    )
    parser.add_argument(
        "--data",
        default=str(_ROOT / "data" / "raw" / "destinations.csv"),
    )
    args = parser.parse_args()
    evaluate(Path(args.model), Path(args.data))


if __name__ == "__main__":
    main()
