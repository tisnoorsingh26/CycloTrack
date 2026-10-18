from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib

from app.config import Settings, get_settings
from app.schemas import FEATURE_COUNT

logger = logging.getLogger("cyclotrack")

CNN_FILE = "best_cyclone_cnn_huber.keras"
LSTM_24_FILE = "cyclone_24h.keras"
LSTM_48_FILE = "cyclone_48h.keras"
SCALERS = {
    "x24": "x_scaler_24h.pkl",
    "y24": "y_scaler_24h.pkl",
    "x48": "x_scaler_48h.pkl",
    "y48": "y_scaler_48h.pkl",
}


@dataclass
class ModelRegistry:
    loaded: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)
    cnn: Any = None
    lstm_24: Any = None
    lstm_48: Any = None
    x_scaler_24: Any = None
    y_scaler_24: Any = None
    x_scaler_48: Any = None
    y_scaler_48: Any = None

    def status(self) -> dict[str, bool]:
        return {
            "cnn": self.cnn is not None,
            "lstm_24h": self.lstm_24 is not None,
            "lstm_48h": self.lstm_48 is not None,
            "scalers": all(
                item is not None
                for item in (
                    self.x_scaler_24,
                    self.y_scaler_24,
                    self.x_scaler_48,
                    self.y_scaler_48,
                )
            ),
        }


registry = ModelRegistry()


def _load_keras(path: Path):
    import tensorflow as tf

    return tf.keras.models.load_model(path)


def _load_trusted_scaler(path: Path, expected_features: int):
    if path.suffix != ".pkl":
        raise ValueError(f"Refusing to load non-pickle scaler: {path}")
    scaler = joblib.load(path)
    n_in = int(getattr(scaler, "n_features_in_", -1))
    if n_in != expected_features:
        raise ValueError(f"{path.name} n_features_in_={n_in}, expected {expected_features}")
    return scaler


def load_registry(settings: Settings | None = None) -> ModelRegistry:
    settings = settings or get_settings()
    artifacts = settings.artifact_dir()
    logger.info("Loading models from %s", artifacts)

    def mark(name: str, ok: bool, detail: str) -> None:
        registry.loaded[name] = ok
        registry.details[name] = detail
        logger.info("%s: %s", name, detail)

    try:
        registry.cnn = _load_keras(artifacts / CNN_FILE)
        shape = tuple(registry.cnn.input_shape)
        mark("cnn", True, f"loaded input_shape={shape}")
    except Exception as exc:  # noqa: BLE001 — startup must survive missing TF
        registry.cnn = None
        mark("cnn", False, str(exc))

    try:
        registry.lstm_24 = _load_keras(artifacts / LSTM_24_FILE)
        mark("lstm_24h", True, f"loaded input_shape={registry.lstm_24.input_shape}")
    except Exception as exc:  # noqa: BLE001
        registry.lstm_24 = None
        mark("lstm_24h", False, str(exc))

    try:
        registry.lstm_48 = _load_keras(artifacts / LSTM_48_FILE)
        mark("lstm_48h", True, f"loaded input_shape={registry.lstm_48.input_shape}")
    except Exception as exc:  # noqa: BLE001
        registry.lstm_48 = None
        mark("lstm_48h", False, str(exc))

    try:
        registry.x_scaler_24 = _load_trusted_scaler(artifacts / SCALERS["x24"], FEATURE_COUNT)
        registry.y_scaler_24 = _load_trusted_scaler(artifacts / SCALERS["y24"], 2)
        registry.x_scaler_48 = _load_trusted_scaler(artifacts / SCALERS["x48"], FEATURE_COUNT)
        registry.y_scaler_48 = _load_trusted_scaler(artifacts / SCALERS["y48"], 2)
        mark("scalers", True, "24h/48h StandardScalers loaded")
    except Exception as exc:  # noqa: BLE001
        registry.x_scaler_24 = registry.y_scaler_24 = None
        registry.x_scaler_48 = registry.y_scaler_48 = None
        mark("scalers", False, str(exc))

    return registry
