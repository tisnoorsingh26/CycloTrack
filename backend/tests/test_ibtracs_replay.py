from datetime import datetime, timedelta, timezone

import pytest

from app.schemas import (
    Coordinate,
    Displacement,
    HorizonPrediction,
    IBTracsReplayRequest,
    TrackPredictResponse,
)
from app.services import ibtracs_replay as replay
from app.services.live_sources import parse_observations


def _rows(*, interval_hours=3, interpolated_indices=(), outside_index=None):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(9):
        lat = 12.0 + i * 0.1
        if i == outside_index:
            lat = 41.0
        result.append({
            "time": start + timedelta(hours=interval_hours * i),
            "lat": lat,
            "lon": 80.0 + i * 0.1,
            "wind": 40.0 + i,
            "cyclone_identifier": "2020001N09090",
            "cyclone_name": "Amphan",
            "basin": "Bay of Bengal",
            "source_url": replay.NI_CSV_URL,
            "retrieval_path": "tinyfish_fetch",
            "retrieved_at": start,
            "interpolated": i in interpolated_indices,
            "interpolation_rule": replay.INTERPOLATION_RULE,
            "data_type": "historical",
            "domain_ok": -40 <= lat <= 40 and 30 <= 80.0 + i * 0.1 <= 130,
        })
    # Actual verification positions must be present at exact +24h and +48h from cutoff.
    cutoff = result[-1]["time"]
    for j, hour in enumerate((24, 48), start=1):
        result.append({
            "time": cutoff + timedelta(hours=hour), "lat": 14.0 + j, "lon": 84.0 + j,
            "wind": 50.0 + j, "cyclone_identifier": "2020001N09090", "cyclone_name": "Amphan",
            "basin": "Bay of Bengal", "source_url": replay.NI_CSV_URL,
            "retrieval_path": "tinyfish_fetch", "retrieved_at": start,
            "interpolated": False, "interpolation_rule": replay.INTERPOLATION_RULE,
            "data_type": "historical", "domain_ok": True,
        })
    return result


def _predictor(request):
    last = request.observations[-1]
    predictions = []
    for horizon in (24, 48):
        valid = last.time + timedelta(hours=horizon)
        predictions.append(HorizonPrediction(
            horizon_hours=horizon,
            displacement=Displacement(delta_lat_deg=0.2, delta_lon_deg=0.3),
            predicted=Coordinate(lat=last.lat + 0.2, lon=last.lon + 0.3, time=valid),
            valid_time=valid,
        ))
    return TrackPredictResponse(
        last_observed=Coordinate(lat=last.lat, lon=last.lon, time=last.time),
        predictions=predictions,
        notes=[],
    )


def _ibtracs_frame(name="MICHAUNG", season=2023, sid="2023334N08088", count=43):
    import pandas as pd
    start = datetime(2023, 11, 30, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        stamp = start + timedelta(hours=3 * index)
        rows.append({
            "SID": sid, "SEASON": season, "BASIN": "NI", "SUBBASIN": "BB", "NAME": name,
            "ISO_TIME": stamp.isoformat().replace("+00:00", "Z"), "LAT": 12 + index * 0.05,
            "LON": 82 + index * 0.05, "NEWDELHI_LAT": 12 + index * 0.05,
            "NEWDELHI_LON": 82 + index * 0.05, "NEWDELHI_WIND": 40 + index,
            "IFLAG": "OOOOOO",
        })
    return pd.DataFrame(rows)


def _name_replay(frame, name, season, tmp_path):
    rows = replay._parse_storm_rows(frame, name, season, replay.NI_CSV_URL, "tinyfish_fetch",
                                    datetime(2026, 1, 1, tzinfo=timezone.utc),
                                    sid=replay._storm_sid(frame, name, season))
    request = IBTracsReplayRequest(name=name, season=season, mode="historical_replay")
    return replay._evaluate(rows, request, replay.Settings(ibtracs_cache_dir=tmp_path / "cache"), _predictor)


def test_case_variants_of_michaung_resolve_same_sid_and_cutoffs(tmp_path):
    frame = _ibtracs_frame()
    results = [_name_replay(frame, name, 2023, tmp_path) for name in ("MICHAUNG", "Michaung", "michaung")]
    assert [result.status for result in results] == ["ok", "ok", "ok"]
    assert {result.cutoff_count for result in results} == {19}
    assert all(result.summary == results[0].summary for result in results[1:])
    assert replay._storm_cache_name("MICHAUNG", 2023) == replay._storm_cache_name("Michaung", 2023)
    assert replay._replay_cache_path(tmp_path, "MICHAUNG", 2023, "historical_replay") == replay._replay_cache_path(tmp_path, "michaung", 2023, "historical_replay")


@pytest.mark.parametrize(("name", "season", "sid"), [
    ("AMPHAN", 2020, "2020138N09090"),
    ("FANI", 2019, "2019117N09086"),
])
def test_uppercase_names_for_amphan_and_fani_keep_all_rows(tmp_path, name, season, sid):
    frame = _ibtracs_frame(name=name, season=season, sid=sid)
    result = _name_replay(frame, name, season, tmp_path)
    assert result.status == "ok"
    assert result.cutoff_count == 19


def test_old_partial_name_only_storm_cache_is_not_reused(tmp_path, monkeypatch):
    frame = _ibtracs_frame()
    settings = replay.Settings(ibtracs_cache_dir=tmp_path / "cache")
    settings.ibtracs_cache_dir.mkdir(parents=True)
    cache_path = settings.ibtracs_cache_dir / replay._storm_cache_name("Michaung", 2023)
    replay._write_json(cache_path, {"rows": [{"wind": None}] * 8, "metadata": {"cache_status": "cached"}})
    monkeypatch.setattr(replay, "_load_csv", lambda _settings, force_refresh=False: (frame, {"retrieval_path": "tinyfish_fetch"}, None))
    rows, metadata, error = replay._load_storm_rows("MICHAUNG", 2023, settings)
    assert error is None
    assert len(rows) == 43
    assert metadata["sid"] == "2023334N08088"




def _evaluate(rows, tmp_path, *, mode="historical_replay", cutoff=None):
    (tmp_path / "ml").mkdir(exist_ok=True)
    monkeypatch_root = replay.PROJECT_ROOT
    replay.PROJECT_ROOT = tmp_path
    try:
        request = IBTracsReplayRequest(name="Amphan", season=2020, mode=mode, cutoff=cutoff)
        return replay._evaluate(rows, request, replay.Settings(ibtracs_cache_dir=tmp_path / "cache"), _predictor)
    finally:
        replay.PROJECT_ROOT = monkeypatch_root


def test_valid_historical_window_runs_both_horizons_and_summarizes_all_cutoffs(tmp_path):
    result = _evaluate(_rows(), tmp_path)
    assert result.status == "ok"
    assert result.cutoff_count == 1
    assert {item.horizon_hours for item in result.cutoffs[0].results} == {24, 48}
    assert set(result.summary) == {"lstm_24h", "lstm_48h", "constant_velocity_24h", "constant_velocity_48h"}
    assert result.training_overlap_label == "possible_training_overlap"
    assert result.imd_cross_check["executed"] is False


def test_six_hourly_rows_are_rejected(tmp_path):
    result = _evaluate(_rows(interval_hours=6), tmp_path)
    assert result.status == "insufficient_data"
    assert result.cutoff_count == 0


def test_interpolated_rows_are_reported_and_quality_threshold_is_strictly_over_two(tmp_path):
    two = _evaluate(_rows(interpolated_indices=(0, 1)), tmp_path)
    assert two.cutoffs[0].interpolated_count == 2
    assert two.cutoffs[0].quality == "validated_input"
    three = _evaluate(_rows(interpolated_indices=(0, 1, 2)), tmp_path)
    assert three.cutoffs[0].interpolated_count == 3
    assert three.cutoffs[0].quality == "approximate_input"
    assert "exceeds" in three.cutoffs[0].warnings[0]


def test_gap_in_input_sequence_is_rejected(tmp_path):
    rows = _rows()
    rows[4]["time"] += timedelta(hours=1)
    result = _evaluate(rows, tmp_path)
    assert result.status == "insufficient_data"


def test_missing_wind_breaks_usable_three_hour_sequence(tmp_path):
    rows = [row for row in _rows() if row["time"] != datetime(2020, 1, 1, 6, tzinfo=timezone.utc)]
    result = _evaluate(rows, tmp_path)
    assert result.status == "insufficient_data"


def test_out_of_domain_input_is_rejected(tmp_path):
    result = _evaluate(_rows(outside_index=4), tmp_path)
    assert result.status == "insufficient_data"
    assert result.domain_check_passed is False


def test_duplicate_conflicting_timestamp_is_flagged_without_merging(tmp_path):
    rows = _rows()
    duplicate = dict(rows[3])
    duplicate["lon"] += 1
    rows.insert(4, duplicate)
    result = _evaluate(rows, tmp_path)
    assert result.duplicate_timestamps is True
    assert result.conflicting_duplicate_timestamps
    assert result.source_order == "ascending"


def test_source_order_mixed_is_reported(tmp_path):
    rows = _rows()
    rows[4], rows[5] = rows[5], rows[4]
    result = _evaluate(rows, tmp_path)
    assert result.source_order == "mixed"


def test_test_storm_overlap_labels_only_confirmed_held_out_entries(tmp_path, monkeypatch):
    (tmp_path / "ml").mkdir()
    (tmp_path / "ml" / "test_storms.json").write_text('["Amphan 2020", "Fani 2019"]', encoding="utf-8")
    monkeypatch.setattr(replay, "PROJECT_ROOT", tmp_path)
    assert replay._training_overlap("Amphan", 2020)[0] == "held_out_test"
    assert replay._training_overlap("Michaung", 2023)[0] == "possible_training_overlap"


def test_missing_test_storm_file_is_possible_training_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr(replay, "PROJECT_ROOT", tmp_path)
    label, warning = replay._training_overlap("Dana", 2024)
    assert label == "possible_training_overlap"
    assert "missing" in warning


def test_name_without_season_returns_needs_selection_for_multiple_seasons(monkeypatch):
    import pandas as pd
    frame = pd.DataFrame({"NAME": ["DANA", "DANA", "NOT_NAMED", ""],
                          "SEASON": [2024, 1965, 2000, 2001], "BASIN": ["NI"] * 4})
    monkeypatch.setattr(replay, "_load_csv", lambda settings: (frame, {}, None))
    result = replay.replay_ibtracs(IBTracsReplayRequest(name="Dana"))
    assert result.status == "needs_selection"
    assert [(item["name"], item["season"]) for item in result.season_options] == [("DANA", 1965), ("DANA", 2024)]


def test_unknown_name_returns_not_found_with_close_suggestions(monkeypatch):
    import pandas as pd
    frame = pd.DataFrame({"NAME": ["MICHAUNG", "AMPHAN"], "SEASON": [2023, 2020], "BASIN": ["NI", "NI"]})
    monkeypatch.setattr(replay, "_load_csv", lambda settings: (frame, {}, None))
    result = replay.replay_ibtracs(IBTracsReplayRequest(name="Michaunq"))
    assert result.status == "not_found"
    assert result.suggestions[0]["name"] == "MICHAUNG"


def test_insufficient_input_explains_missing_wind_and_target_reasons(tmp_path):
    rows = _rows()
    rows[4]["wind"] = None
    result = _evaluate(rows, tmp_path)
    assert result.status == "insufficient_data"
    assert result.rejection_reasons["missing or invalid wind in input window"] > 0
    assert any("target row" in reason for reason in result.rejection_reasons)


def test_existing_parser_reads_ibtracs_newdelhi_wind_and_can_preserve_duplicates():
    start = datetime(2020, 5, 1, tzinfo=timezone.utc)
    lines = ["ISO_TIME,NAME,SID,LAT,LON,NEWDELHI_WIND"]
    for index in range(9):
        stamp = (start + timedelta(hours=3 * index)).isoformat().replace("+00:00", "Z")
        lines.append(f"{stamp},AMPHAN,2020138N09090,12.0,85.0,{45 + index}")
    lines.append(lines[1])
    issues = []
    parsed = parse_observations(
        "\n".join(lines), replay.NI_CSV_URL,
        "IBTrACS historical best track; New Delhi wind is knots", start,
        query="Amphan", issues=issues, preserve_duplicates=True,
    )
    assert len(parsed) == 10
    assert parsed[0].wind == 45
    assert parsed[0].classification == "historical_best_track"
