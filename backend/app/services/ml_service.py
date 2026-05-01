import structlog
import pandas as pd
import joblib

log = structlog.get_logger()


class MLService:
    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model = None
        try:
            self._model = joblib.load(model_path)
            log.info("ml_model_loaded", path=model_path)
        except FileNotFoundError:
            log.warning("ml_model_not_found", path=model_path)
        except Exception as exc:
            log.error("ml_model_load_failed", path=model_path, error=str(exc))

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, features: dict) -> str:
        """Run the trained pipeline on a feature dict and return the travel-style label."""
        if self._model is None:
            raise RuntimeError(
                f"ML model is not loaded (path={self._model_path}). "
                "Train the model first or check the path."
            )
        X = pd.DataFrame([features])
        label: str = self._model.predict(X)[0]
        log.debug("ml_prediction", label=label, features=features)
        return label
