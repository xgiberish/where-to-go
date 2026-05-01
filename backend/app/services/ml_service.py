from pathlib import Path

import joblib
import pandas as pd
import structlog

log = structlog.get_logger()

# backend/app/services/ -> backend/app/ -> backend/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class MLService:
    def __init__(self, model_path: str) -> None:
        resolved = Path(model_path)
        if not resolved.is_absolute():
            resolved = _PROJECT_ROOT / resolved
        self._model_path = str(resolved)
        self._model = None
        try:
            self._model = joblib.load(self._model_path)
            log.info("ml_model_loaded", path=self._model_path)
        except FileNotFoundError:
            log.warning("ml_model_not_found", path=self._model_path)
        except Exception as exc:
            log.error("ml_model_load_failed", path=self._model_path, error=str(exc))

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, features: dict) -> str:
        """Run the trained pipeline on a feature dict and return the travel-style label."""
        if self._model is None:
            raise RuntimeError(
                f"ML model is not loaded (path={self._model_path}). "
                "Train the model first: python ml/train.py"
            )
        X = pd.DataFrame([features])
        label: str = self._model.predict(X)[0]
        log.debug("ml_prediction", label=label, features=features)
        return label
