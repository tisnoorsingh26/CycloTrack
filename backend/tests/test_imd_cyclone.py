from datetime import datetime, timedelta, timezone

from app.schemas import (
    Coordinate,
    CycloneForecastRequest,
    Displacement,
    HorizonPrediction,
    TrackPredictResponse,
)
from app.services import imd_cyclone


def _provider_rows(*, step_hours=3, age_hours=3, name="BIPARJOY", storm_id=None):
    latest = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=age_hours)
    rows = []
    for index in range(9):
        time = latest - timedelta(hours=step_hours * (8 - index))
        row = {
            "CYCLONE_NAME": name,
            "Date/Time": time.strftime("%d.%m.%y/%H%M"),
            "lat": f"{14 + index * 0.1:.1f}",
            "lon": f"{65 + index * 0.1:.1f}",
            "MSW (kt)": "45.0",
        }
        if storm_id:
            row["STORM_ID"] = storm_id
        rows.append(row)
    return rows


class _Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def _forecast(last):
    points = [
        HorizonPrediction(
            horizon_hours=hours,
            displacement=Displacement(delta_lat_deg=0.5, delta_lon_deg=0.5),
            predicted=Coordinate(lat=last["lat"] + 0.5, lon=last["lon"] + 0.5,
                                time=last["time"] + timedelta(hours=hours)),
            valid_time=last["time"] + timedelta(hours=hours),
        )
        for hours in (24, 48)
    ]
    return TrackPredictResponse(last_observed=Coordinate(**last), predictions=points, notes=[])


def _run(monkeypatch, rows, query="Cyclone Biparjoy", predictor=None):
    monkeypatch.setattr(imd_cyclone.get_settings(), "imd_api_token", "unit-test-token")
    captured = {}

    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response({"status": True, "data": {"observed": rows, "forecast": [{"lat": 0}]}})

    monkeypatch.setattr(imd_cyclone.httpx, "get", get)
    if predictor:
        monkeypatch.setattr(imd_cyclone, "predict_track", predictor)
    result = imd_cyclone.get_cyclone_forecast(CycloneForecastRequest(cyclone_query=query))
    return result, captured


def test_imd_track_response_parses_observed_rows_and_runs_both_horizons(monkeypatch):
    rows = _provider_rows(storm_id="BOB-2024-03")
    calls = []

    def predictor(payload):
        calls.append(payload)
        last = payload.observations[-1].model_dump()
        last["time"] = payload.observations[-1].time
        return _forecast(last)

    result, captured = _run(monkeypatch, rows, predictor=predictor)

    assert captured["url"] == imd_cyclone.IMD_TRACK_URL
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert result.status == "ok"
    assert result.cyclone_name == "Biparjoy"
    assert result.storm_id == "BOB-2024-03"
    assert result.basin == "Arabian Sea"
    assert len(result.observations) == 9
    assert all(row.classification == "observed" for row in result.observations)
    assert len(calls) == 1 and len(calls[0].observations) == 9
    assert [point.horizon_hours for point in result.forecast.predictions] == [24, 48]
    assert result.forecast.predictions[0].valid_time != result.forecast.predictions[1].valid_time


def test_parser_converts_mean_wind_from_kmph_when_knots_missing():
    rows = _provider_rows()
    for row in rows:
        row.pop("MSW (kt)")
        row["Mean MSW (kmph)"] = "55"
    parsed = imd_cyclone._parse_observations(rows)
    assert parsed[-1].wind == 55 * 0.5399568
    assert "km/h" in parsed[-1].wind_original


def test_resolver_accepts_an_unambiguous_provider_storm_id(monkeypatch):
    rows = _provider_rows(storm_id="BOB-2024-03")
    result, _ = _run(monkeypatch, rows, query="BOB-2024-03", predictor=lambda payload: _forecast(payload.observations[-1].model_dump()))
    assert result.status == "ok"
    assert result.storm_id == "BOB-2024-03"


def test_ambiguous_storm_name_is_rejected(monkeypatch):
    rows = _provider_rows(storm_id="BOB-2024-03") + _provider_rows(storm_id="BOB-2018-01")
    result, _ = _run(monkeypatch, rows)
    assert result.status == "error"
    assert "more than one active IMD storm" in result.message


def test_missing_provider_track_returns_insufficient_data(monkeypatch):
    result, _ = _run(monkeypatch, [])
    assert result.status == "insufficient_data"
    assert "no active observed track" in result.message


def test_wrong_timestamp_spacing_is_not_sent_to_lstm(monkeypatch):
    called = []
    result, _ = _run(monkeypatch, _provider_rows(step_hours=6), predictor=lambda payload: called.append(payload))
    assert result.status == "insufficient_data"
    assert any("requires observations every 3 hours" in issue for issue in result.validation)
    assert called == []


def test_stale_track_is_not_sent_to_lstm(monkeypatch):
    called = []
    result, _ = _run(monkeypatch, _provider_rows(age_hours=18), predictor=lambda payload: called.append(payload))
    assert result.status == "insufficient_data"
    assert any("latest actual fix" in issue for issue in result.validation)
    assert called == []


def test_missing_imd_token_does_not_make_network_request(monkeypatch):
    monkeypatch.setattr(imd_cyclone.get_settings(), "imd_api_token", "")
    monkeypatch.setattr(imd_cyclone.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network must not run")))
    result = imd_cyclone.get_cyclone_forecast(CycloneForecastRequest(cyclone_query="Biparjoy"))
    assert result.status == "unavailable"
    assert "IMD_API_TOKEN" in result.message


def test_automatic_forecast_route_dispatches_name_query(monkeypatch):
    from types import SimpleNamespace

    from app import main

    expected = object()
    monkeypatch.setattr(main, "_limit_source_requests", lambda request: None)
    monkeypatch.setattr(main, "get_cyclone_forecast", lambda payload: expected)
    result = main.cyclone_forecast(
        CycloneForecastRequest(cyclone_query="Biparjoy"),
        SimpleNamespace(client=SimpleNamespace(host="test-client")),
    )
    assert result is expected


def test_resolver_marks_duplicate_names_with_distinct_ids_ambiguous():
    rows = _provider_rows(storm_id="ID-1") + _provider_rows(storm_id="ID-2")
    name, _, matched = imd_cyclone._resolve("Biparjoy", rows)
    assert name == "AMBIGUOUS"
    assert len(matched) == 18


def test_existing_predict_track_executes_both_model_specific_inference_paths(monkeypatch):
    import numpy as np

    from app.schemas import ObservationIn, TrackPredictRequest
    from app.services.lstm import predict_track
    from app.services.registry import registry

    called = []

    class Scaler:
        n_features_in_ = 11

        def transform(self, values):
            return values

        def inverse_transform(self, values):
            return values

    class Model:
        def __init__(self, horizon):
            self.horizon = horizon

        def predict(self, values, verbose=0):
            called.append((self.horizon, tuple(values.shape)))
            return np.asarray([[0.25, 0.5]], dtype=np.float32)

    monkeypatch.setattr(registry, "lstm_24", Model(24))
    monkeypatch.setattr(registry, "lstm_48", Model(48))
    monkeypatch.setattr(registry, "x_scaler_24", Scaler())
    monkeypatch.setattr(registry, "y_scaler_24", Scaler())
    monkeypatch.setattr(registry, "x_scaler_48", Scaler())
    monkeypatch.setattr(registry, "y_scaler_48", Scaler())

    observed = _parse_input_observations(_provider_rows())
    result = predict_track(TrackPredictRequest(observations=observed))
    assert called == [(24, (1, 8, 11)), (48, (1, 8, 11))]
    assert [point.horizon_hours for point in result.predictions] == [24, 48]


def _parse_input_observations(rows):
    from app.schemas import ObservationIn

    return [ObservationIn(time=row.time, lat=row.lat, lon=row.lon, wind=row.wind) for row in imd_cyclone._parse_observations(rows)]
