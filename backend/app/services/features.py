from datetime import datetime, timezone
from math import cos, radians

import numpy as np

from app.schemas import (
    FEATURE_COUNT,
    FEATURE_ORDER,
    SEQUENCE_LENGTH,
    STEP_HOURS,
    ObservationIn,
)

HOUR_TOLERANCE = 0.15


class FeatureError(ValueError):
    pass


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hours_between(a: datetime, b: datetime) -> float:
    return (_aware(b) - _aware(a)).total_seconds() / 3600.0


def time_encodings(dt: datetime) -> tuple[float, float, float, float]:
    hour = dt.hour
    month = dt.month
    hour_sin = float(np.sin(2 * np.pi * hour / 24))
    hour_cos = float(np.cos(2 * np.pi * hour / 24))
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))
    return hour_sin, hour_cos, month_sin, month_cos


def motion_features(prev: ObservationIn, curr: ObservationIn) -> tuple[float, float, float, float]:
    delta_hours = hours_between(prev.time, curr.time)
    if not np.isfinite(delta_hours) or delta_hours <= 0:
        raise FeatureError("Observations must be strictly increasing in time.")
    delta_lat = curr.lat - prev.lat
    delta_lon = curr.lon - prev.lon
    north_kmh = delta_lat * 111.0 / delta_hours
    east_kmh = delta_lon * 111.0 * cos(radians(curr.lat)) / delta_hours
    if not all(np.isfinite(v) for v in (delta_lat, delta_lon, north_kmh, east_kmh)):
        raise FeatureError("Motion features contain non-finite values.")
    return north_kmh, east_kmh, delta_lat, delta_lon


def build_lstm_sequence(observations: list[ObservationIn]) -> tuple[np.ndarray, ObservationIn]:
    """Return (1, 8, 11) unscaled features and the last observed point.

    Training required eight 3-hourly steps plus a predecessor so every step
    had defined groupby-diff motion features.
    """
    ordered = sorted(observations, key=lambda row: _aware(row.time))
    if len(ordered) < SEQUENCE_LENGTH + 1:
        raise FeatureError(
            f"Need at least {SEQUENCE_LENGTH + 1} observations (8 steps + predecessor)."
        )

    window = ordered[-(SEQUENCE_LENGTH + 1) :]
    predecessor, steps = window[0], window[1:]

    if len({_aware(row.time) for row in window}) != len(window):
        raise FeatureError("Observations must have unique timestamps.")

    for i in range(1, len(window)):
        gap = hours_between(window[i - 1].time, window[i].time)
        if abs(gap - STEP_HOURS) > HOUR_TOLERANCE:
            raise FeatureError(
                f"LSTM inputs must be {STEP_HOURS:.0f} hours apart. "
                f"Found {gap:.2f} h between observation {i} and {i + 1} of the 9-observation window."
            )

    rows: list[list[float]] = []
    prev = predecessor
    for obs in steps:
        hour_sin, hour_cos, month_sin, month_cos = time_encodings(obs.time)
        north_kmh, east_kmh, delta_lat, delta_lon = motion_features(prev, obs)
        rows.append(
            [
                obs.lat,
                obs.lon,
                obs.wind,
                hour_sin,
                hour_cos,
                month_sin,
                month_cos,
                north_kmh,
                east_kmh,
                delta_lat,
                delta_lon,
            ]
        )
        prev = obs

    array = np.asarray(rows, dtype=np.float32)
    if array.shape != (SEQUENCE_LENGTH, FEATURE_COUNT):
        raise FeatureError(f"Internal shape error: {array.shape}")
    if not np.isfinite(array).all():
        raise FeatureError("Feature matrix contains non-finite values.")
    return array[np.newaxis, ...], steps[-1]


def scale_sequence(sequence: np.ndarray, scaler) -> np.ndarray:
    shaped = sequence.reshape(-1, sequence.shape[-1])
    if getattr(scaler, "n_features_in_", FEATURE_COUNT) != sequence.shape[-1]:
        raise FeatureError(
            f"X scaler expects {scaler.n_features_in_} features, got {sequence.shape[-1]}."
        )
    scaled = scaler.transform(shaped).reshape(sequence.shape).astype(np.float32)
    return scaled
