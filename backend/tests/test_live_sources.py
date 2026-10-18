from datetime import datetime, timedelta, timezone

import httpx

from app.schemas import Coordinate, Displacement, HorizonPrediction, SourceFetchRequest, TrackPredictResponse
from app.services import live_sources


def _table(now: datetime, heading: str = "## Observed positions") -> str:
    if heading == "## Observed positions":
        heading = "## Cyclone Test (Bay of Bengal) — Observed positions"
    lines = [heading, "| Date UTC | Latitude | Longitude | Max wind (kt) |", "|---|---:|---:|---:|"]
    for i in range(9):
        dt = now - timedelta(hours=3 * (8 - i))
        lines.append(f"| {dt.isoformat()} | {12 + i * .1:.1f} | {80 + i * .1:.1f} | {35 + i} |")
    return "\n".join(lines)


def test_parse_only_explicit_observation_table():
    now = datetime.now(timezone.utc)
    rows = live_sources.parse_observations(_table(now), "https://mausam.imd.gov.in/test", "Observed fixes", now)
    assert len(rows) == 9
    assert rows[0].classification == "observed"
    assert rows[-1].wind == 43
    forecast = live_sources.parse_observations(_table(now, "## Forecast positions"), "https://mausam.imd.gov.in/test", None, now)
    assert forecast == []


def test_parse_html_table_and_normalize_kmh():
    now = datetime.now(timezone.utc)
    html = '<h2>Observed positions UTC Bay of Bengal</h2><table><tr><th>Valid time UTC</th><th>Latitude</th><th>Longitude</th><th>Wind speed km/h</th></tr>' + "".join(
        f"<tr><td>{(now - timedelta(hours=3 * (8-i))).isoformat()}</td><td>{12+i*.1:.1f}</td><td>{80+i*.1:.1f}</td><td>55</td></tr>" for i in range(9)
    ) + "</table>"
    rows = live_sources.parse_observations(html, "https://mausam.imd.gov.in/track", "Observed positions", now, "Cyclone Test")
    assert len(rows) == 9
    assert rows[0].wind_original.endswith("km/h")
    assert rows[0].wind == 55 * 0.5399568
    assert rows[0].units == "kt"


def test_parse_accessible_json_and_historical_csv_formats():
    now = datetime.now(timezone.utc)
    json_text = '{"observed":[' + ",".join(
        f'{{"time":"{(now - timedelta(hours=3 * (8-i))).isoformat()}","cyclone_name":"Test","lat":{12+i*.1:.1f},"lon":{80+i*.1:.1f},"wind_kt":40}}' for i in range(9)
    ) + ']} '
    json_rows = live_sources.parse_observations(json_text, "https://mausam.imd.gov.in/api.json", "Observed track", now, "Test")
    assert len(json_rows) == 9
    assert all(row.cyclone_name == "Test" for row in json_rows)

    csv_lines = ["ISO_TIME,NAME,SID,LAT,LON,WMO_WIND"]
    for i in range(9):
        stamp = (datetime(2019, 11, 5, tzinfo=timezone.utc) + timedelta(hours=3*i)).strftime("%Y-%m-%d %H:%M:%S")
        csv_lines.append(f"{stamp},TEST,2019310N09090,{12+i*.1:.1f},{80+i*.1:.1f},40")
    historical = live_sources.parse_observations("\n".join(csv_lines), "https://www.ncei.noaa.gov/ibtracs.csv", "IBTrACS historical best track", now, "Test")
    assert len(historical) == 9
    assert historical[0].classification == "historical_best_track"
    assert historical[0].cyclone_identifier == "2019310N09090"
    assert live_sources._validation(historical, now) == []


def test_missing_timestamp_is_reported():
    now = datetime.now(timezone.utc)
    issues: list[str] = []
    text = "## Observed positions\n| Latitude | Longitude | Max wind (kt) |\n|---|---|---|\n| 12.0 | 80.0 | 30 |"
    assert live_sources.parse_observations(text, "https://mausam.imd.gov.in/track", None, now, "Test", issues) == []
    assert any("timestamp" in issue.lower() for issue in issues)


def test_parse_flattened_downloaded_track_text_with_explicit_units():
    now = datetime.now(timezone.utc)
    lines = ["Historical best track observations · timestamps UTC · wind kt"]
    for i in range(9):
        stamp = (now - timedelta(days=800) - timedelta(hours=3 * (8-i))).isoformat()
        lines.append(f"{stamp} {12+i*.1:.1f}N {80+i*.1:.1f}E {40+i}")
    rows = live_sources.parse_observations("\n".join(lines), "https://www.ncei.noaa.gov/archive.pdf", "Historical best track PDF", now, "Test")
    assert len(rows) == 9
    assert all(row.classification == "historical_best_track" for row in rows)
    assert live_sources._validation(rows, now) == []


def test_search_discovery_targets_observations_bulletins_and_official_archives(monkeypatch):
    from app.services import tinyfish

    monkeypatch.setattr(tinyfish.get_settings(), "tinyfish_api_key", "unit-key")
    captured = {}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"results": []}
    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()
    monkeypatch.setattr(tinyfish.httpx, "get", fake_get)
    result = tinyfish.retrieve_source_evidence("Biparjoy")
    assert result.status == "ok"
    assert "historical track" in captured["params"]["query"]
    assert "latitude" in captured["params"]["query"]
    assert "wind speed" in captured["params"]["query"]
    assert "imd.gov.in" in captured["params"]["include_domains"]
    assert "ncei.noaa.gov" in captured["params"]["include_domains"]
    assert captured["headers"]["X-API-Key"] == "unit-key"
    assert "unit-key" not in str(captured["params"])


def test_fetch_http_auth_failure_is_returned_without_secret(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "unit-key")
    request = httpx.Request("POST", "https://api.fetch.tinyfish.ai")
    response = httpx.Response(401, request=request)
    def fail(*args, **kwargs):
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)
    monkeypatch.setattr(live_sources.httpx, "post", fail)
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Biparjoy", urls=["https://mausam.imd.gov.in/track"]))
    assert result.status == "error"
    assert "401" in result.message
    assert "unit-key" not in result.model_dump_json()


def test_validation_rejects_duplicates_spacing_staleness_and_out_of_domain():
    now = datetime.now(timezone.utc)
    rows = live_sources.parse_observations(_table(now), "https://mausam.imd.gov.in/test", None, now)
    assert live_sources._validation(rows, now) == []
    assert any("Duplicate" in x for x in live_sources._validation(rows + [rows[-1]], now))
    irregular = rows.copy()
    irregular[4] = irregular[4].model_copy(update={"time": irregular[4].time + timedelta(hours=1)})
    assert any("3 hours" in x for x in live_sources._validation(irregular, now))
    stale = [r.model_copy(update={"time": r.time - timedelta(days=2)}) for r in rows]
    assert any("12 hours old" in x for x in live_sources._validation(stale, now))
    outside = [rows[0].model_copy(update={"lon": 145})] + rows[1:]
    assert any("training envelope" in x for x in live_sources._validation(outside, now))


def test_same_time_cross_source_disagreement_is_reported_without_merging():
    now = datetime.now(timezone.utc)
    a = live_sources.parse_observations(_table(now), "https://mausam.imd.gov.in/a", "Observed", now, "Cyclone Test")
    b = [row.model_copy(update={"source_url": "https://ncei.noaa.gov/b", "lat": row.lat + 1.0, "source_type": "historical_best_track", "classification": "historical_best_track"}) for row in a]
    conflicts = live_sources._compare_observations([a, b])
    assert len(conflicts) == 9
    assert conflicts[0]["position_difference_km"] > 30
    assert {row.source_url for row in a} == {"https://mausam.imd.gov.in/a"}
    other_cyclone = [row.model_copy(update={"cyclone_name": "Different storm"}) for row in b]
    assert live_sources._compare_observations([a, other_cyclone]) == []


def test_suitable_imd_reference_is_preferred_and_disagreement_is_reported(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    now = datetime.now(timezone.utc)
    web_rows = live_sources.parse_observations(_table(now), "https://mausam.imd.gov.in/bulletin", "Observed", now, "Cyclone Test")
    imd_url = "https://api.imd.gov.in/api/v1/cyclone_track"
    reference = [row.model_copy(update={"source_url": imd_url, "source_type": "imd_operational", "lat": row.lat + 0.6}) for row in web_rows]
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"url": "https://mausam.imd.gov.in/bulletin", "title": "Observed", "text": _table(now)}], "errors": []}
    monkeypatch.setattr(live_sources.httpx, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(live_sources, "fetch_reference_observations", lambda query: ("available", reference))
    def predictor(payload):
        last = payload.observations[-1]
        points = [HorizonPrediction(horizon_hours=h, displacement=Displacement(delta_lat_deg=0, delta_lon_deg=0),
                   predicted=Coordinate(lat=last.lat, lon=last.lon, time=last.time + timedelta(hours=h)),
                   valid_time=last.time + timedelta(hours=h)) for h in (24, 48)]
        return TrackPredictResponse(last_observed=Coordinate(lat=last.lat, lon=last.lon, time=last.time), predictions=points, notes=[])
    monkeypatch.setattr(live_sources, "predict_track", predictor)
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Cyclone Test", urls=["https://mausam.imd.gov.in/bulletin"]))
    assert result.status == "ok"
    assert result.disagreements
    assert {row.source_url for row in result.model_observations} == {imd_url}
    assert any("IMD supplied" in item for item in result.validation)


def test_fetch_request_contract_and_partial_success(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    now = datetime.now(timezone.utc)
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "https://mausam.imd.gov.in/test", "title": "Observed", "text": _table(now)}],
                    "errors": [{"url": "https://ncei.noaa.gov/missing", "error": "timeout"}]}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(live_sources.httpx, "post", fake_post)
    monkeypatch.setattr(live_sources, "fetch_reference_observations", lambda query: ("not_configured", []))
    monkeypatch.setattr(live_sources, "predict_track", lambda payload: (_ for _ in ()).throw(live_sources.LstmError("test model unavailable")))
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Cyclone test", urls=["https://mausam.imd.gov.in/test"]))
    assert captured["url"] == "https://api.fetch.tinyfish.ai"
    assert captured["headers"] == {"X-API-Key": "test-key"}
    assert captured["json"]["urls"] == ["https://mausam.imd.gov.in/test"]
    assert captured["json"]["format"] == "markdown"
    assert captured["json"]["ttl"] == 0
    assert captured["timeout"] >= 150
    assert result.status == "insufficient_data"
    assert len(result.observations) == 9
    assert len(result.sources) == 2
    assert result.sources[0].get("preview")
    assert result.forecast is None
    assert "test-key" not in result.model_dump_json()


def test_fetch_rejects_untrusted_urls_before_network(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    monkeypatch.setattr(live_sources.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network must not run")))
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="x", urls=["https://127.0.0.1/admin"]))
    assert result.status == "error"
    assert result.message


def test_validated_fetch_runs_existing_two_horizon_lstm(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    now = datetime.now(timezone.utc)
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "https://mausam.imd.gov.in/test", "title": "Observed", "text": _table(now)}], "errors": []}

    def fake_post(*args, **kwargs):
        return Response()

    def fake_predict(payload):
        captured["observations"] = payload.observations
        last = payload.observations[-1]
        points = [
            HorizonPrediction(horizon_hours=h, displacement=Displacement(delta_lat_deg=0.1, delta_lon_deg=0.2),
                              predicted=Coordinate(lat=last.lat + 0.1, lon=last.lon + 0.2, time=last.time + timedelta(hours=h)),
                              valid_time=last.time + timedelta(hours=h))
            for h in (24, 48)
        ]
        return TrackPredictResponse(last_observed=Coordinate(lat=last.lat, lon=last.lon, time=last.time), predictions=points, notes=[])

    monkeypatch.setattr(live_sources.httpx, "post", fake_post)
    monkeypatch.setattr(live_sources, "fetch_reference_observations", lambda query: ("not_configured", []))
    monkeypatch.setattr(live_sources, "predict_track", fake_predict, raising=False)
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Cyclone test", urls=["https://mausam.imd.gov.in/test"]))
    assert result.status == "ok"
    assert len(result.model_observations) == 9
    assert result.forecast is not None
    assert [point.horizon_hours for point in result.forecast.predictions] == [24, 48]
    assert len(captured["observations"]) == 9
    assert {row.source_url for row in result.model_observations} == {"https://mausam.imd.gov.in/test"}


def test_historical_csv_replay_uses_one_source_and_does_not_apply_live_freshness(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    now = datetime.now(timezone.utc)
    lines = ["ISO_TIME,NAME,SID,LAT,LON,WMO_WIND"]
    for i in range(9):
        stamp = (datetime(2019, 11, 5, tzinfo=timezone.utc) + timedelta(hours=3 * i)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{stamp},TEST,2019310N09090,{12+i*.1:.1f},{80+i*.1:.1f},40")

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"url": "https://www.ncei.noaa.gov/ibtracs.csv", "title": "IBTrACS historical best track", "text": "\n".join(lines)}], "errors": []}

    monkeypatch.setattr(live_sources.httpx, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(live_sources, "fetch_reference_observations", lambda query: ("no_matching_active_observations", []))
    called = []
    def fake_predict(payload):
        called.append(payload)
        last = payload.observations[-1]
        predictions = [HorizonPrediction(horizon_hours=h, displacement=Displacement(delta_lat_deg=0, delta_lon_deg=0),
                       predicted=Coordinate(lat=last.lat, lon=last.lon, time=last.time+timedelta(hours=h)), valid_time=last.time+timedelta(hours=h)) for h in (24, 48)]
        return TrackPredictResponse(last_observed=Coordinate(lat=last.lat, lon=last.lon, time=last.time), predictions=predictions, notes=[])
    monkeypatch.setattr(live_sources, "predict_track", fake_predict)

    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Test", urls=["https://www.ncei.noaa.gov/ibtracs.csv"]))
    assert result.status == "ok"
    assert len(called) == 1
    assert all(row.classification == "historical_best_track" for row in result.model_observations)
    assert any("not live/current" in item for item in result.validation)
    assert {row.source_url for row in result.model_observations} == {"https://www.ncei.noaa.gov/ibtracs.csv"}


def test_observations_from_two_sources_are_never_stitched_into_one_input(monkeypatch):
    monkeypatch.setattr(live_sources.get_settings(), "tinyfish_api_key", "test-key")
    now = datetime.now(timezone.utc)
    def partial(start, count):
        rows = ["## Cyclone Test Bay of Bengal observed track", "| Date UTC | Latitude | Longitude | Max wind (kt) |", "|---|---|---|---|"]
        for i in range(count):
            dt = now - timedelta(hours=3 * (8 - (start + i)))
            rows.append(f"| {dt.isoformat()} | {12+i*.1:.1f} | {80+i*.1:.1f} | 40 |")
        return "\n".join(rows)
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [
                {"url": "https://mausam.imd.gov.in/part-a", "title": "Observed", "text": partial(0, 4)},
                {"url": "https://ncei.noaa.gov/part-b", "title": "Observed", "text": partial(4, 5)},
            ], "errors": []}
    monkeypatch.setattr(live_sources.httpx, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(live_sources, "fetch_reference_observations", lambda query: ("not_configured", []))
    monkeypatch.setattr(live_sources, "predict_track", lambda payload: (_ for _ in ()).throw(AssertionError("must not run")))
    result = live_sources.fetch_and_forecast(SourceFetchRequest(storm_query="Cyclone Test", urls=["https://mausam.imd.gov.in/part-a", "https://ncei.noaa.gov/part-b"]))
    assert result.status == "insufficient_data"
    assert result.forecast is None
    assert result.model_observations == []
    assert any("Need 9 actual fixes" in issue for issue in result.validation)


def test_fetch_route_dispatches_to_backend_service(monkeypatch):
    from app import main
    from types import SimpleNamespace

    expected = object()
    monkeypatch.setattr(main, "fetch_and_forecast", lambda payload: expected)
    request = SimpleNamespace(client=SimpleNamespace(host="test-client"))
    result = main.fetch_sources(SourceFetchRequest(storm_query="Cyclone Test", urls=["https://mausam.imd.gov.in/test"]), request)
    assert result is expected


def test_search_reports_connection_failure_category(monkeypatch):
    from app.services import tinyfish

    monkeypatch.setattr(tinyfish.get_settings(), "tinyfish_api_key", "test-key")
    monkeypatch.setattr(tinyfish.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("connection failed")))
    response = tinyfish.retrieve_source_evidence("Cyclone test")
    assert response.status == "error"
    assert "connection failed" in response.message.lower()
    assert "test-key" not in response.model_dump_json()


def test_source_routes_apply_per_client_rate_limit():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app import main

    main._source_request_times.clear()
    request = SimpleNamespace(client=SimpleNamespace(host="limited-test-client"))
    for _ in range(20):
        main._limit_source_requests(request)
    try:
        main._limit_source_requests(request)
    except HTTPException as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("21st request should be rate limited")
    finally:
        main._source_request_times.clear()

