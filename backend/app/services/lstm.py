from datetime import timedelta

import numpy as np

from app.schemas import (
    Coordinate,
    Displacement,
    HorizonPrediction,
    TrackPredictRequest,
    TrackPredictResponse,
)
from app.services.features import FeatureError, build_lstm_sequence, scale_sequence
from app.services.registry import registry


class LstmError(ValueError):
    pass


def _predict_horizon(sequence: np.ndarray, last, hours: int) -> HorizonPrediction:
    if hours == 24:
        model, x_scaler, y_scaler = registry.lstm_24, registry.x_scaler_24, registry.y_scaler_24
    else:
        model, x_scaler, y_scaler = registry.lstm_48, registry.x_scaler_48, registry.y_scaler_48
    if model is None or x_scaler is None or y_scaler is None:
        raise LstmError(f"{hours}h LSTM artifacts are not loaded. Check /health.")

    scaled = scale_sequence(sequence, x_scaler)
    raw = model.predict(scaled, verbose=0)
    displacement = y_scaler.inverse_transform(np.asarray(raw).reshape(1, 2))[0]
    if displacement.shape != (2,) or not np.isfinite(displacement).all():
        raise LstmError("Model returned an invalid displacement vector.")
    dlat, dlon = float(displacement[0]), float(displacement[1])
    pred_lat = last.lat + dlat
    pred_lon = last.lon + dlon
    valid = last.time + timedelta(hours=hours)
    return HorizonPrediction(
        horizon_hours=hours,  # type: ignore[arg-type]
        displacement=Displacement(delta_lat_deg=dlat, delta_lon_deg=dlon),
        predicted=Coordinate(lat=pred_lat, lon=pred_lon, time=valid),
        valid_time=valid,
    )


def predict_track(payload: TrackPredictRequest) -> TrackPredictResponse:
    try:
        sequence, last = build_lstm_sequence(payload.observations)
    except FeatureError as exc:
        raise LstmError(str(exc)) from exc

    pred24 = _predict_horizon(sequence, last, 24)
    pred48 = _predict_horizon(sequence, last, 48)
    return TrackPredictResponse(
        last_observed=Coordinate(lat=last.lat, lon=last.lon, time=last.time),
        predictions=[pred24, pred48],
        notes=[
            "Outputs are (delta_lat, delta_lon) in degrees added to the last observed centre.",
            "Held-out notebook mean error: 140.7 km at 24 h, 323.5 km at 48 h — not a confidence score.",
            "Wind is treated as knots, matching the IMD training column.",
        ],
    )
