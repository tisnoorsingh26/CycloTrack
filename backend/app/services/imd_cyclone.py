"""Retrieve the active North Indian Ocean track from IMD and forecast only observed fixes."""
from __future__ import annotations

import re
import json
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.schemas import (
    CycloneForecastRequest,
    CycloneForecastResponse,
    ExtractedObservation,
    TrackPredictRequest,
)
from app.services.lstm import LstmError, predict_track

IMD_TRACK_URL = "https://api.imd.gov.in/api/v1/cyclone_track"
SOURCE_TITLE = "India Meteorological Department (IMD) operational Cyclone Track API"
TIMEOUT_SECONDS = 20.0
HOUR_TOLERANCE = 0.15


def _key(value: str) -> str:
    value = re.sub(r"\b(tropical\s+)?cyclone\b|\bstorm\b", " ", value, flags=re.I)
    return "".join(re.findall(r"[a-z0-9]+", value.lower()))


def _records(body: object) -> list[dict]:
    if not isinstance(body, dict) or body.get("status") is False:
        return []
    data = body.get("data")
    if not isinstance(data, dict):
        return []
    observed = data.get("observed")
    return [row for row in observed if isinstance(row, dict)] if isinstance(observed, list) else []


def _resolve(query: str, records: list[dict]) -> tuple[str, str | None, list[dict]]:
    requested = _key(query)
    if not requested:
        return "", None, []
    matches: dict[tuple[str, str], list[dict]] = {}
    for row in records:
        name = str(row.get("CYCLONE_NAME") or row.get("cyclone_name") or "").strip()
        storm_id = str(row.get("STORM_ID") or row.get("storm_id") or row.get("CYCLONE_ID") or row.get("Cyclone ID") or "").strip() or None
        if requested in {_key(name), _key(storm_id or "")}:
            matches.setdefault((name.upper(), (storm_id or "").upper()), []).append(row)
    if len(matches) > 1:
        return "AMBIGUOUS", None, [row for grouped in matches.values() for row in grouped]
    if not matches:
        return "", None, []
    (name, storm_id), matched_rows = next(iter(matches.items()))
    return name, storm_id or None, matched_rows


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing observation time")
    raw = value.strip()
    for pattern in ("%d.%m.%y/%H%M", "%d.%m.%Y/%H%M"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("unrecognized observation time") from exc
    if parsed.tzinfo is None:
        raise ValueError("observation time has no UTC offset")
    return parsed.astimezone(timezone.utc)


def _number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("not numeric")
    number = float(str(value).strip())
    if not (number == number and abs(number) != float("inf")):
        raise ValueError("not finite")
    return number


def _basin(row: dict, lat: float, lon: float) -> str | None:
    supplied = str(row.get("BASIN") or row.get("basin") or "").strip().lower()
    if not 0 <= lat <= 30:
        return None
    # IMD's track schema omits basin. The NIO longitude divide is used only
    # away from the transition; ambiguous fixes are rejected below.
    if 45 <= lon < 76.5:
        inferred = "Arabian Sea"
    elif 77.5 < lon <= 100:
        inferred = "Bay of Bengal"
    else:
        return None
    if supplied and (("arabian" in supplied and inferred != "Arabian Sea") or
                     (("bay" in supplied or "bengal" in supplied) and inferred != "Bay of Bengal")):
        return None
    return "Arabian Sea" if "arabian" in supplied else "Bay of Bengal" if ("bay" in supplied or "bengal" in supplied) else inferred


def _parse_observations(rows: list[dict]) -> list[ExtractedObservation]:
    result: list[ExtractedObservation] = []
    for row in rows:
        time_value = row.get("Date/Time") or row.get("DATE_TIME") or row.get("datetime")
        try:
            timestamp = _parse_time(time_value)
            lat = _number(row.get("lat", row.get("LAT")))
            lon = _number(row.get("lon", row.get("LON")))
            wind_value = row.get("MSW (kt)")
            if wind_value not in (None, ""):
                wind = _number(wind_value)
                original = f"{wind_value} kt"
            else:
                wind_value = row.get("Mean MSW (kmph)")
                wind = _number(wind_value) * 0.5399568
                original = f"{wind_value} km/h"
            name = str(row.get("CYCLONE_NAME") or row.get("cyclone_name") or "").strip()
            if not name:
                continue
            basin = _basin(row, lat, lon)
            flags = ["Basin inferred from IMD North Indian Ocean track coordinates"] if not row.get("BASIN") and not row.get("basin") else []
            result.append(ExtractedObservation(
                time=timestamp,
                lat=lat,
                lon=lon,
                wind=wind,
                wind_original=original,
                units="kt",
                cyclone_identifier=name,
                classification="observed",
                source_type="imd_operational",
                basin=basin,
                source_url=IMD_TRACK_URL,
                source_title=SOURCE_TITLE,
                original_evidence=json.dumps(row, ensure_ascii=False, sort_keys=True),
                extraction="direct",
                flags=flags,
            ))
        except (TypeError, ValueError, OverflowError):
            continue
    return sorted(result, key=lambda item: item.time)


def fetch_reference_observations(query: str) -> tuple[str, list[ExtractedObservation]]:
    """Optional IMD evidence for cross-checking; does not run inference or alter the IMD route."""
    token = get_settings().imd_api_token
    if not token:
        return "not_configured", []
    try:
        response = httpx.get(
            IMD_TRACK_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.TimeoutException:
        return "timeout", []
    except httpx.HTTPStatusError as exc:
        return f"http_{exc.response.status_code}", []
    except (httpx.HTTPError, ValueError):
        return "unavailable", []
    records = _records(body)
    name, _, matched = _resolve(query, records)
    if not matched or name == "AMBIGUOUS":
        return "no_matching_active_observations", []
    return "available", _parse_observations(matched)


def _validation(observations: list[ExtractedObservation], now: datetime) -> list[str]:
    issues: list[str] = []
    if len(observations) < 9:
        issues.append(f"Insufficient recent observations: need 9 actual fixes (predecessor plus 8 model steps), received {len(observations)}.")
    if len({item.time for item in observations}) != len(observations):
        issues.append("The operational track contains duplicate observation timestamps.")
    if any(item.classification != "observed" for item in observations):
        issues.append("Only observed records can be used; forecast positions are excluded.")
    if any(item.basin is None for item in observations):
        issues.append("The track basin is ambiguous at the Arabian Sea / Bay of Bengal boundary.")
    basins = {item.basin for item in observations}
    if len(basins) != 1:
        issues.append("The observations do not remain in one consistent basin.")
    for previous, current in zip(observations, observations[1:]):
        hours = (current.time - previous.time).total_seconds() / 3600
        if abs(hours - 3) > HOUR_TOLERANCE:
            issues.append(f"The LSTM requires observations every 3 hours; the operational track has a {hours:g}-hour interval.")
            break
    if observations:
        latest = observations[-1]
        age_hours = (now - latest.time).total_seconds() / 3600
        if age_hours > 12:
            issues.append(f"Insufficient recent observations: latest actual fix is {age_hours:.1f} hours old; maximum is 12 hours.")
        if age_hours < -0.5:
            issues.append("The latest observation timestamp is more than 30 minutes in the future.")
        if any(not (-40 <= item.lat <= 40 and 30 <= item.lon <= 130) for item in observations):
            issues.append("The track is outside the existing LSTM training envelope (latitude −40…40, longitude 30…130).")
        if any(not (0 <= item.wind <= 250) for item in observations):
            issues.append("Wind values are outside the existing model input range in knots.")
    return issues


def get_cyclone_forecast(payload: CycloneForecastRequest) -> CycloneForecastResponse:
    query = payload.cyclone_query.strip()
    settings = get_settings()
    if not settings.imd_api_token:
        return CycloneForecastResponse(
            status="unavailable",
            message="IMD_API_TOKEN is not configured on the backend. Add an authorized token from the IMD API portal; credentials stay server-side.",
        )
    try:
        response = httpx.get(
            IMD_TRACK_URL,
            headers={"Authorization": f"Bearer {settings.imd_api_token}", "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
    except httpx.TimeoutException:
        return CycloneForecastResponse(status="error", message="IMD Cyclone Track request timed out.")
    except httpx.ConnectError:
        return CycloneForecastResponse(status="error", message="Could not connect to the official IMD Cyclone Track API.")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            message = "IMD denied Cyclone Track API access. Check the backend IMD API portal token and permissions."
        elif exc.response.status_code == 429:
            message = "IMD API rate limit reached. Please retry later."
        else:
            message = f"IMD Cyclone Track API returned HTTP {exc.response.status_code}."
        return CycloneForecastResponse(status="error", message=message)
    except (httpx.HTTPError, ValueError):
        return CycloneForecastResponse(status="error", message="IMD returned an unreadable or malformed Cyclone Track response.")

    records = _records(body)
    if not records:
        return CycloneForecastResponse(status="insufficient_data", message="IMD's operational Cyclone Track feed has no active observed track records. Historical best-track replay is not available from this live endpoint.")
    name, storm_id, matched = _resolve(query, records)
    if not matched:
        return CycloneForecastResponse(status="insufficient_data", message="No unambiguous active IMD track matches this cyclone name or ID. This operational feed does not provide historical replay lookup.")
    if name == "AMBIGUOUS":
        return CycloneForecastResponse(status="error", message="The identifier matches more than one active IMD storm. Enter its full cyclone name or provider storm ID.")

    observed = _parse_observations(matched)
    model_window = observed[-9:] if len(observed) >= 9 else observed
    now = datetime.now(timezone.utc)
    issues = _validation(model_window, now)
    if issues:
        return CycloneForecastResponse(
            status="insufficient_data", cyclone_name=name.title(), storm_id=storm_id,
            basin=model_window[-1].basin if model_window else None, retrieved_at=now,
            observations=model_window, validation=issues,
            message="IMD identified the cyclone, but its observed track does not satisfy the existing LSTM input contract. No prediction was run.",
        )
    selected = model_window
    try:
        forecast = predict_track(TrackPredictRequest(observations=[
            {"time": row.time, "lat": row.lat, "lon": row.lon, "wind": row.wind} for row in selected
        ]))
    except (LstmError, ValueError) as exc:
        return CycloneForecastResponse(
            status="insufficient_data", cyclone_name=name.title(), storm_id=storm_id,
            basin=selected[-1].basin, retrieved_at=now, observations=selected,
            validation=[str(exc)], message="The verified track could not pass through the existing LSTM preprocessing pipeline.",
        )
    return CycloneForecastResponse(
        status="ok", cyclone_name=name.title(), storm_id=storm_id, basin=selected[-1].basin,
        retrieved_at=now, observations=selected, forecast=forecast,
        validation=["Nine actual observed fixes, including the predecessor, are 3 hours apart.",
                    "Wind values are normalized to knots; no forecast positions or interpolation were used.",
                    "Track is recent, within the trained basin and training coordinate envelope."],
        message="Both existing LSTM horizons completed from the IMD observed track.",
    )
