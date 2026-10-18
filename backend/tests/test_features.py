from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.schemas import ObservationIn
from app.services.cnn import CnnError, load_cnn_input
from app.services.features import build_lstm_sequence, time_encodings


def _obs(start: datetime, n: int, step_hours: float = 3.0) -> list[ObservationIn]:
    rows = []
    for i in range(n):
        rows.append(
            ObservationIn(
                time=start + timedelta(hours=step_hours * i),
                lat=12.0 + 0.1 * i,
                lon=88.0 - 0.05 * i,
                wind=30 + i,
            )
        )
    return rows


def test_time_encodings_match_notebook():
    dt = datetime(2024, 11, 2, 18, 0, tzinfo=timezone.utc)
    hour_sin, hour_cos, month_sin, month_cos = time_encodings(dt)
    assert hour_sin == pytest.approx(np.sin(2 * np.pi * 18 / 24))
    assert hour_cos == pytest.approx(np.cos(2 * np.pi * 18 / 24))
    assert month_sin == pytest.approx(np.sin(2 * np.pi * 11 / 12))
    assert month_cos == pytest.approx(np.cos(2 * np.pi * 11 / 12))


def test_sequence_shape_and_feature_order():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    seq, last = build_lstm_sequence(_obs(start, 9))
    assert seq.shape == (1, 8, 11)
    assert last.lat == pytest.approx(12.0 + 0.1 * 8)
    # first window step uses predecessor for deltas
    first = seq[0, 0]
    assert first[0] == pytest.approx(12.1)
    assert first[9] == pytest.approx(0.1)  # delta_lat
    assert first[10] == pytest.approx(-0.05)


def test_rejects_wrong_spacing():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    rows = _obs(start, 9, step_hours=6.0)
    with pytest.raises(ValueError, match="3 hours"):
        build_lstm_sequence(rows)


def test_rejects_bad_predecessor_to_first_step_spacing():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    rows = _obs(start, 9)
    rows[0] = rows[0].model_copy(update={"time": rows[0].time + timedelta(hours=1)})
    with pytest.raises(ValueError, match="3 hours"):
        build_lstm_sequence(rows)


def test_rejects_duplicate_observation_timestamps():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    rows = _obs(start, 9)
    rows[3] = rows[3].model_copy(update={"time": rows[2].time})
    with pytest.raises(ValueError, match="unique timestamps"):
        build_lstm_sequence(rows)


def test_rejects_too_few_rows():
    start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="at least 9"):
        build_lstm_sequence(_obs(start, 8))


def test_cnn_rejects_rgb_png():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (128, 128), (10, 20, 30)).save(buf, format="PNG")
    with pytest.raises(CnnError, match="3-channel RGB"):
        load_cnn_input("storm.png", buf.getvalue())


def test_cnn_accepts_uint8_four_channel_npy():
    from io import BytesIO

    payload = np.zeros((128, 128, 4), dtype=np.uint8)
    payload[..., 0] = 128
    buf = BytesIO()
    np.save(buf, payload)
    array, notes = load_cnn_input("sample.npy", buf.getvalue())
    assert array.shape == (1, 128, 128, 4)
    assert array.max() == pytest.approx(128 / 255.0)
    assert any("255" in note for note in notes)


def test_cnn_rejects_wrong_spatial_size():
    from io import BytesIO

    buf = BytesIO()
    np.save(buf, np.zeros((64, 64, 4), dtype=np.float32))
    with pytest.raises(CnnError, match="128"):
        load_cnn_input("small.npy", buf.getvalue())


def test_exact_11_features_and_motion_math():
    from math import cos, radians
    from app.schemas import FEATURE_ORDER
    from app.services.features import motion_features

    # 1. Predecessor observation
    t0 = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
    obs_prev = ObservationIn(time=t0, lat=10.0, lon=80.0, wind=35.0)

    # 2. Step 1 observation (3 hours later)
    t1 = t0 + timedelta(hours=3)
    obs_curr = ObservationIn(time=t1, lat=10.6, lon=80.9, wind=40.0)

    # Motion features
    north_kmh, east_kmh, dlat, dlon = motion_features(obs_prev, obs_curr)
    expected_dlat = 10.6 - 10.0  # 0.6
    expected_dlon = 80.9 - 80.0  # 0.9
    expected_north = expected_dlat * 111.0 / 3.0
    expected_east = expected_dlon * 111.0 * cos(radians(10.6)) / 3.0

    assert dlat == pytest.approx(expected_dlat)
    assert dlon == pytest.approx(expected_dlon)
    assert north_kmh == pytest.approx(expected_north)
    assert east_kmh == pytest.approx(expected_east)

    # 3. Build a full 9-observation window and check all 11 columns in sequence step 0
    obs_list = [obs_prev]
    for i in range(1, 9):
        obs_list.append(
            ObservationIn(
                time=t0 + timedelta(hours=3 * i),
                lat=10.0 + 0.6 * i,
                lon=80.0 + 0.9 * i,
                wind=35.0 + 5.0 * i,
            )
        )

    seq, last = build_lstm_sequence(obs_list)
    assert seq.shape == (1, 8, 11)
    assert len(FEATURE_ORDER) == 11

    # Check step 0 (which corresponds to obs_list[1] using obs_list[0] as predecessor)
    s0 = seq[0, 0]
    assert s0[0] == pytest.approx(10.6)  # lat
    assert s0[1] == pytest.approx(80.9)  # lon
    assert s0[2] == pytest.approx(40.0)  # wind
    assert s0[3] == pytest.approx(np.sin(2 * np.pi * t1.hour / 24))  # hour_sin
    assert s0[4] == pytest.approx(np.cos(2 * np.pi * t1.hour / 24))  # hour_cos
    assert s0[5] == pytest.approx(np.sin(2 * np.pi * t1.month / 12)) # month_sin
    assert s0[6] == pytest.approx(np.cos(2 * np.pi * t1.month / 12)) # month_cos
    assert s0[7] == pytest.approx(expected_north)                    # north_kmh
    assert s0[8] == pytest.approx(expected_east)                     # east_kmh
    assert s0[9] == pytest.approx(expected_dlat)                     # delta_lat
    assert s0[10] == pytest.approx(expected_dlon)                    # delta_lon

    # Check last observed point
    assert last.lat == pytest.approx(obs_list[-1].lat)
    assert last.lon == pytest.approx(obs_list[-1].lon)
    assert last.time == obs_list[-1].time

