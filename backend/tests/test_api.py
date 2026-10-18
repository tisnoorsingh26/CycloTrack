from datetime import datetime, timedelta, timezone
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.registry import registry


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _valid_observations():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(9):
        rows.append(
            {
                "time": (start + timedelta(hours=3 * i)).isoformat(),
                "lat": 14.0 + 0.2 * i,
                "lon": 82.5 + 0.1 * i,
                "wind": 35 + i,
            }
        )
    return rows


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "up"
    assert "cnn" in body["models"]
    assert "lstm_24h" in body["models"]
    assert "lstm_48h" in body["models"]
    assert "scalers" in body["models"]


def test_scalers_loaded(client: TestClient):
    assert registry.x_scaler_24 is not None
    assert registry.y_scaler_24 is not None
    assert registry.x_scaler_48 is not None
    assert registry.y_scaler_48 is not None
    assert registry.x_scaler_24.n_features_in_ == 11
    assert registry.y_scaler_24.n_features_in_ == 2
    assert registry.x_scaler_48.n_features_in_ == 11
    assert registry.y_scaler_48.n_features_in_ == 2


def test_lstm_models_input_shape(client: TestClient):
    if registry.lstm_24 is None or registry.lstm_48 is None:
        pytest.skip(f"LSTM not loaded: {registry.details}")
    assert tuple(registry.lstm_24.input_shape)[1:] == (8, 11)
    assert tuple(registry.lstm_48.input_shape)[1:] == (8, 11)
    assert tuple(registry.lstm_24.output_shape)[1:] == (2,)
    assert tuple(registry.lstm_48.output_shape)[1:] == (2,)


def test_cnn_model_input_shape(client: TestClient):
    if registry.cnn is None:
        pytest.skip(f"CNN not loaded: {registry.details}")
    assert tuple(registry.cnn.input_shape)[1:] == (128, 128, 4)


def test_track_validation_missing_rows(client: TestClient):
    response = client.post("/predict/track", json={"observations": _valid_observations()[:4]})
    assert response.status_code == 422


def test_track_validation_bad_lat(client: TestClient):
    rows = _valid_observations()
    rows[0]["lat"] = 120
    response = client.post("/predict/track", json={"observations": rows})
    assert response.status_code == 422


def test_track_prediction_structure(client: TestClient):
    if not all(registry.status().values()):
        pytest.skip(f"models not loaded: {registry.details}")
    response = client.post("/predict/track", json={"observations": _valid_observations()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_kind"] == "ml_prediction"
    assert len(body["predictions"]) == 2
    horizons = {item["horizon_hours"] for item in body["predictions"]}
    assert horizons == {24, 48}
    last = body["last_observed"]
    for item in body["predictions"]:
        pred = item["predicted"]
        disp = item["displacement"]
        assert pred["lat"] == pytest.approx(last["lat"] + disp["delta_lat_deg"])
        assert pred["lon"] == pytest.approx(last["lon"] + disp["delta_lon_deg"])
        assert abs(pred["lat"]) <= 90
        assert abs(pred["lon"]) <= 180


def test_wind_rejects_rgb(client: TestClient):
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (128, 128), color=(1, 2, 3)).save(buf, format="PNG")
    buf.seek(0)
    response = client.post("/predict/wind", files={"file": ("photo.png", buf, "image/png")})
    assert response.status_code == 422
    assert "RGB" in response.json()["detail"]


def test_wind_npy_inference(client: TestClient):
    if registry.cnn is None:
        pytest.skip(f"CNN not loaded: {registry.details}")
    array = np.zeros((128, 128, 4), dtype=np.uint8)
    array[..., 0] = 40
    array[..., 1] = 80
    buf = BytesIO()
    np.save(buf, array)
    buf.seek(0)
    response = client.post(
        "/predict/wind",
        files={"file": ("chip.npy", buf.getvalue(), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_kind"] == "ml_prediction"
    assert np.isfinite(body["predicted_wind_knots"])
    assert body["input_shape"] == [128, 128, 4]


def test_sources_without_key(client: TestClient, monkeypatch):
    from app.services import tinyfish as tinyfish_mod

    monkeypatch.setattr(tinyfish_mod.get_settings(), "tinyfish_api_key", "")
    response = client.get("/sources", params={"q": "Bay of Bengal cyclone"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["kind"] == "web_search"
    assert "not ML" in " ".join(body["notes"]) or "not ML" in body["notes"][0]


def test_sources_uses_tinyfish_search_rest_contract(client: TestClient, monkeypatch):
    from app.services import tinyfish as tinyfish_mod

    monkeypatch.setattr(tinyfish_mod.get_settings(), "tinyfish_api_key", "test-key")
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {
                        "site_name": "IMD",
                        "title": "Cyclone bulletin",
                        "snippet": "Official advisory excerpt",
                        "url": "https://mausam.imd.gov.in/bulletin",
                    },
                    {"title": "Invalid URL", "url": "javascript:alert(1)"},
                ]
            }

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(tinyfish_mod.httpx, "get", fake_get)
    response = client.get("/sources", params={"q": "Cyclone Example"})
    assert response.status_code == 200
    body = response.json()
    assert captured["url"] == "https://api.search.tinyfish.ai"
    assert captured["headers"] == {"X-API-Key": "test-key"}
    assert captured["params"]["location"] == "IN"
    assert captured["params"]["language"] == "en"
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["publisher"] == "IMD"
    assert "test-key" not in response.text


def test_sources_rate_limit_is_clear(client: TestClient, monkeypatch):
    import httpx

    from app.services import tinyfish as tinyfish_mod

    monkeypatch.setattr(tinyfish_mod.get_settings(), "tinyfish_api_key", "test-key")

    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", "https://api.search.tinyfish.ai")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(tinyfish_mod.httpx, "get", fake_get)
    response = client.get("/sources", params={"q": "Cyclone Example"})
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "rate limit" in response.json()["message"]
    assert "test-key" not in response.text


def test_synthetic_chip_file_inference(client: TestClient):
    """Test CNN input validation and forward pass with the saved synthetic 128x128x4 chip.

    Note: This synthetic chip verifies input shape, channel depth, and pipeline mechanics.
    It does not claim real-world meteorological accuracy.
    """
    from pathlib import Path

    chip_path = Path(__file__).resolve().parents[2] / "ml" / "sample_chips" / "synthetic_chip_128x128x4.npy"
    if not chip_path.exists():
        pytest.skip(f"Synthetic chip not found at {chip_path}")
    if registry.cnn is None:
        pytest.skip(f"CNN model not loaded: {registry.details}")

    with open(chip_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/predict/wind",
        files={"file": ("synthetic_chip_128x128x4.npy", file_bytes, "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_kind"] == "ml_prediction"
    assert np.isfinite(body["predicted_wind_knots"])
    assert body["input_shape"] == [128, 128, 4]
    assert any("255" in n for n in body["notes"])


def test_sources_empty_query(client: TestClient):
    response = client.get("/sources", params={"q": ""})
    assert response.status_code == 422

