"""Historical IBTrACS replay using the existing parser, validator and LSTMs.

Discovery refresh is deliberately an explicit maintenance operation (used by
prewarm scripts); the per-storm replay request never invokes the TinyFish Agent.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import logging
import re
import statistics
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pandas as pd

from app.config import BACKEND_DIR, PROJECT_ROOT, Settings, get_settings
from app.schemas import (
    IBTracsCoordinate,
    IBTracsHorizonReplay,
    IBTracsMetricSummary,
    IBTracsObservation,
    IBTracsReplayRequest,
    IBTracsReplayResponse,
    IBTracsCutoffReplay,
    ObservationIn,
    TrackPredictRequest,
)
from app.services.features import build_lstm_sequence
from app.services.live_sources import _validation, parse_observations
from app.services.lstm import LstmError, predict_track

logger = logging.getLogger("cyclotrack.ibtracs")

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run"
CSV_DIRECTORY_URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/"
NI_CSV_URL = CSV_DIRECTORY_URL + "ibtracs.NI.list.v04r01.csv"
COLUMN_DOC_URL = "https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf"
MAX_CSV_BYTES = 40 * 1024 * 1024
HOUR_TOLERANCE = 0.15
_dataset_refresh_lock = threading.Lock()
INTERPOLATION_RULE = (
    "True when NEWDELHI_WIND is absent, the New Delhi position is absent at this timestamp, "
    "or New Delhi IFLAG character 6 is not O. The supplied IBTrACS LAT/LON or flagged "
    "NEWDELHI values are retained as published; this service does not interpolate or fill values."
)
AGENCY_COLUMNS = [
    "SID", "SEASON", "BASIN", "SUBBASIN", "NAME", "ISO_TIME", "LAT", "LON",
    "NEWDELHI_LAT", "NEWDELHI_LON", "NEWDELHI_WIND", "IFLAG",
]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return _utc(value or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")


def _cache_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = settings.ibtracs_cache_dir
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _fixture_paths() -> tuple[Path, Path, Path, Path]:
    fixtures = PROJECT_ROOT / "tests" / "fixtures"
    return (
        fixtures / "phase1b_ibtracs_search.json",
        fixtures / "phase1b_ibtracs_agent_1.json",
        fixtures / "phase1b_ibtracs_fetch_ni.csv.json",
        fixtures / "ibtracs.NI.list.v04r01.csv",
    )


def seed_phase1_discovery_cache(settings: Settings | None = None) -> dict | None:
    """Promote the prior approved Search/Agent result into the application cache."""
    cache_file = _cache_dir(settings) / "discovery.json"
    if cache_file.exists():
        return _read_json(cache_file)
    search_file, agent_file, _, _ = _fixture_paths()
    search_envelope, agent_envelope = _read_json(search_file), _read_json(agent_file)
    if not search_envelope or not agent_envelope:
        return None
    try:
        search_body = json.loads(search_envelope.get("raw_body", "{}"))
        agent_body = json.loads(agent_envelope.get("raw_body", "{}"))
    except json.JSONDecodeError:
        return None
    result = agent_body.get("result") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return None
    if not isinstance(result, dict) or not result.get("ni_all_csv_url"):
        return None
    retrieved_at = agent_body.get("started_at") or search_envelope.get("response_headers", {}).get("date") or _stamp()
    discovery = {
        "retrieved_at": retrieved_at,
        "search_query": "NOAA NCEI IBTrACS v04r01 CSV North Indian basin best track dataset",
        "search_results": search_body.get("results", []),
        "ni_all_csv_url": result.get("ni_all_csv_url"),
        "ni_since1980_csv_url": result.get("ni_since1980_csv_url"),
        "column_doc_url": result.get("column_doc_url") or COLUMN_DOC_URL,
        "notes": result.get("notes", "Seeded from the approved Phase 1b URL-only discovery run."),
        "source": "phase1b_cached_tinyfish_search_and_agent",
        "agent_run_id": agent_body.get("run_id"),
    }
    _write_json(cache_file, discovery)
    return discovery


def refresh_discovery(settings: Settings | None = None, now: datetime | None = None) -> dict:
    """Explicit daily Search->Agent maintenance refresh. Never called by replay API."""
    settings = settings or get_settings()
    cache_file = _cache_dir(settings) / "discovery.json"
    now = _utc(now or datetime.now(timezone.utc))
    existing = _read_json(cache_file) or seed_phase1_discovery_cache(settings)
    previous = _parse_datetime((existing or {}).get("last_agent_attempt_at") or (existing or {}).get("retrieved_at"))
    if previous and now - previous < timedelta(hours=24):
        return {"status": "cached", "retrieved_at": (existing or {}).get("retrieved_at"), "discovery": existing}
    if not settings.tinyfish_api_key:
        return {"status": "unavailable", "detail": "TINYFISH_API_KEY is not configured; existing cached URLs were retained.", "discovery": existing}

    # Persist attempt time before network calls: failures must not trigger Agent spend on each request/run.
    cached = dict(existing or {})
    cached["last_agent_attempt_at"] = _stamp(now)
    cached["refresh_status"] = "in_progress"
    _write_json(cache_file, cached)
    query = "NOAA NCEI IBTrACS v04r01 CSV North Indian basin best track dataset"
    search_params = {"query": query, "purpose": "Find the official NOAA NCEI IBTrACS v04r01 dataset, CSV index, and column documentation.",
                     "location": "US", "language": "en", "include_domains": "ncei.noaa.gov"}
    try:
        search_response = httpx.get(SEARCH_URL, params=search_params,
                                    headers={"X-API-Key": settings.tinyfish_api_key}, timeout=30)
        search_response.raise_for_status()
        search_body = search_response.json()
        if not isinstance(search_body, dict) or not isinstance(search_body.get("results"), list):
            raise ValueError("TinyFish Search response missing results[].")
        agent_request = {
            "url": CSV_DIRECTORY_URL,
            "goal": ('Open the NOAA NCEI IBTrACS v04r01 CSV directory and return ONLY JSON with exactly '
                     '{"ni_all_csv_url": string|null, "ni_since1980_csv_url": string|null, '
                     '"column_doc_url": string|null, "notes": string}. Return URLs only; never return cyclone rows or track observations.'),
        }
        agent_response = httpx.post(AGENT_URL, json=agent_request,
                                    headers={"X-API-Key": settings.tinyfish_api_key}, timeout=150)
        agent_response.raise_for_status()
        agent_body = agent_response.json()
        agent_result = agent_body.get("result") if isinstance(agent_body, dict) else None
        if isinstance(agent_result, str):
            agent_result = json.loads(agent_result)
        if not isinstance(agent_result, dict) or not agent_result.get("ni_all_csv_url"):
            raise ValueError("TinyFish Agent did not return a North Indian CSV URL.")
        ni_url = _validate_ncei_csv_url(agent_result["ni_all_csv_url"])
        fresh = {
            "retrieved_at": _stamp(now), "last_agent_attempt_at": _stamp(now),
            "search_query": query, "search_results": search_body["results"],
            "ni_all_csv_url": ni_url,
            "ni_since1980_csv_url": _safe_ncei_url(agent_result.get("ni_since1980_csv_url")),
            "column_doc_url": _safe_doc_url(agent_result.get("column_doc_url")) or COLUMN_DOC_URL,
            "notes": str(agent_result.get("notes") or "")[:1000],
            "source": "tinyfish_search_plus_agent", "agent_run_id": agent_body.get("run_id"),
            "refresh_status": "ok",
        }
        _write_json(cache_file, fresh)
        return {"status": "ok", "retrieved_at": fresh["retrieved_at"], "discovery": fresh}
    except Exception as exc:  # keep stale URLs for offline/local cache operation
        cached["refresh_status"] = "error"
        cached["refresh_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        _write_json(cache_file, cached)
        return {"status": "error", "detail": cached["refresh_error"], "discovery": cached}


def _safe_ncei_url(value: object) -> str | None:
    try:
        return _validate_ncei_csv_url(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _validate_ncei_csv_url(value: object) -> str:
    parsed = urlparse(value if isinstance(value, str) else "")
    if parsed.scheme != "https" or parsed.hostname != "www.ncei.noaa.gov" or not parsed.path.endswith(".csv"):
        raise ValueError("Discovered IBTrACS CSV URL is outside the approved HTTPS NCEI host.")
    return value


def _safe_doc_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname == "www.ncei.noaa.gov" and parsed.path.lower().endswith(".pdf") else None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if not isinstance(value, str):
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _fetch_text_response(url: str, settings: Settings) -> tuple[str | None, dict]:
    if not settings.tinyfish_api_key:
        return None, {"status": "skipped", "reason": "TINYFISH_API_KEY is not configured."}
    request_body = {"urls": [url], "format": "markdown", "ttl": 0,
                    "per_url_timeout_ms": 45000,
                    "purpose": "Retrieve the official IBTrACS NI CSV as the primary data source; preserve the complete CSV text."}
    try:
        response = httpx.post(FETCH_URL, json=request_body,
                              headers={"X-API-Key": settings.tinyfish_api_key}, timeout=150)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError("TinyFish Fetch did not return results[].")
        result = next((row for row in body["results"] if isinstance(row, dict) and row.get("url") == url), None)
        text = result.get("text") if isinstance(result, dict) else None
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_CSV_BYTES:
            raise ValueError("TinyFish Fetch CSV text was missing or exceeded the bounded 40 MiB limit.")
        return text, {"status": "ok", "response_headers": _safe_headers(response), "result_url": url,
                      "text_bytes": len(text.encode("utf-8")), "title": result.get("title")}
    except httpx.TimeoutException:
        return None, {"status": "error", "error": "TinyFish Fetch timed out."}
    except httpx.HTTPStatusError as exc:
        return None, {"status": "error", "http_status": exc.response.status_code,
                      "error": f"TinyFish Fetch returned HTTP {exc.response.status_code}."}
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        return None, {"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def _safe_headers(response: httpx.Response) -> dict:
    return {key: value for key, value in response.headers.items()
            if key.lower() in {"content-type", "date", "x-request-id", "content-length"}}


def _direct_download(url: str, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    total = 0
    try:
        with httpx.Client(timeout=httpx.Timeout(150, connect=20), follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                declared = response.headers.get("content-length")
                if declared and int(declared) > MAX_CSV_BYTES:
                    raise ValueError(f"IBTrACS CSV exceeds size limit ({declared} > {MAX_CSV_BYTES} bytes).")
                with temp.open("wb") as out:
                    for chunk in response.iter_bytes(128 * 1024):
                        total += len(chunk)
                        if total > MAX_CSV_BYTES:
                            raise ValueError(f"IBTrACS CSV exceeded {MAX_CSV_BYTES} byte streaming guard.")
                        out.write(chunk)
                content_type = response.headers.get("content-type")
        temp.replace(path)
        return {"status": "ok", "bytes": total, "content_type": content_type}
    except Exception as exc:
        temp.unlink(missing_ok=True)
        return {"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}


def _csv_row_count(text_or_path: str | Path) -> int:
    if isinstance(text_or_path, Path):
        with text_or_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            next(reader, None)  # IBTrACS units row
            return sum(1 for row in reader if row)
    reader = csv.reader(io.StringIO(text_or_path, newline=""))
    next(reader, None)
    next(reader, None)
    return sum(1 for row in reader if row)


def _integrity_check(fetch_text: str | None, direct_path: Path, settings: Settings) -> dict:
    integrity_path = _cache_dir(settings) / "integrity-v04r01-ni.json"
    cached = _read_json(integrity_path)
    if cached:
        return cached
    if fetch_text is None or not direct_path.exists():
        result = {"status": "not_comparable", "reason": "Both a successful Fetch text and direct CSV were not available for the one-time comparison."}
    else:
        fetch_bytes = fetch_text.encode("utf-8")
        direct_hash = hashlib.sha256()
        with direct_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                direct_hash.update(chunk)
        fetch_hash = hashlib.sha256(fetch_bytes).hexdigest()
        fetch_rows, direct_rows = _csv_row_count(fetch_text), _csv_row_count(direct_path)
        result = {
            "status": "passed" if fetch_rows == direct_rows and fetch_hash == direct_hash.hexdigest() else "mismatch",
            "fetch_row_count": fetch_rows, "direct_download_row_count": direct_rows,
            "row_counts_match": fetch_rows == direct_rows,
            "fetch_sha256": fetch_hash, "direct_download_sha256": direct_hash.hexdigest(),
            "checksums_match": fetch_hash == direct_hash.hexdigest(),
            "checked_at": _stamp(),
        }
    _write_json(integrity_path, result)
    return result


def _phase1_fixture_csv() -> tuple[str | None, Path | None, datetime | None]:
    _, _, fetch_path, direct_path = _fixture_paths()
    fetch_text = None
    retrieved_at = None
    envelope = _read_json(fetch_path)
    if envelope:
        try:
            body = json.loads(envelope.get("raw_body", "{}"))
            result = next((item for item in body.get("results", []) if isinstance(item, dict) and item.get("url", "").endswith("ibtracs.NI.list.v04r01.csv")), None)
            fetch_text = result.get("text") if isinstance(result, dict) and isinstance(result.get("text"), str) else None
            date_header = envelope.get("response_headers", {}).get("date")
            retrieved_at = _parse_datetime(date_header)
        except (json.JSONDecodeError, AttributeError):
            pass
    return fetch_text, direct_path if direct_path.exists() else None, retrieved_at


def _load_csv(settings: Settings, force_refresh: bool = False) -> tuple[pd.DataFrame | None, dict, str | None]:
    # Concurrent replay requests share the dataset cache and the direct-download
    # temporary path. Serialize refreshes to prevent partial files/cache races.
    if force_refresh:
        with _dataset_refresh_lock:
            return _load_csv_impl(settings, force_refresh=True)
    return _load_csv_impl(settings, force_refresh=False)


def _load_csv_impl(settings: Settings, force_refresh: bool = False) -> tuple[pd.DataFrame | None, dict, str | None]:
    cache = _cache_dir(settings)
    cache.mkdir(parents=True, exist_ok=True)
    csv_path = cache / "ibtracs.NI.list.v04r01.csv"
    meta_path = cache / "dataset_meta.json"
    metadata = _read_json(meta_path) or {}
    integrity = _read_json(cache / "integrity-v04r01-ni.json")

    if csv_path.exists() and not force_refresh:
        try:
            return _read_dataset(csv_path), {**metadata, "cache_status": "cached", "integrity_check": integrity}, None
        except Exception as exc:
            logger.warning("Cached IBTrACS CSV rejected: %s", exc)

    fetch_text = None
    fetch_info = {"status": "not_attempted"}
    retrieval_path = None
    retrieved_at = None
    source_url = NI_CSV_URL
    discovery = _read_json(cache / "discovery.json") or seed_phase1_discovery_cache(settings)
    if not discovery:
        return None, {"cache_status": "unavailable"}, "No cached Search/Agent discovery URLs. Run the explicit daily discovery prewarm."
    source_url = _safe_ncei_url(discovery.get("ni_all_csv_url") or NI_CSV_URL)

    # The approved Phase 1b Fetch response is an offline primary-source cache.
    fixture_fetch, fixture_direct, fixture_retrieved = (None, None, None) if force_refresh else _phase1_fixture_csv()
    if fixture_fetch:
        fetch_text = fixture_fetch
        fetch_info = {"status": "cached_fixture", "text_bytes": len(fetch_text.encode("utf-8"))}
        retrieval_path = "tinyfish_fetch"
        retrieved_at = fixture_retrieved or _parse_datetime(discovery.get("retrieved_at")) or datetime.now(timezone.utc)
        direct_source = fixture_direct
    else:
        fetch_text, fetch_info = _fetch_text_response(source_url, settings)
        if fetch_text:
            retrieval_path = "tinyfish_fetch"
            retrieved_at = _parse_datetime(fetch_info.get("response_headers", {}).get("date")) or datetime.now(timezone.utc)
            raw_fetch_path = cache / "tinyfish_fetch_ni.csv"
            raw_fetch_path.write_text(fetch_text, encoding="utf-8")
            fetch_text = raw_fetch_path.read_text(encoding="utf-8")
        direct_source = None

    if not fetch_text:
        # A bounded direct download is the fallback when Fetch is unavailable or truncated.
        download = _direct_download(source_url, csv_path)
        if download.get("status") != "ok":
            fetch_reason = fetch_info.get("error") or fetch_info.get("reason") or fetch_info.get("status", "unknown failure")
            download_reason = download.get("error") or download.get("status", "unknown failure")
            detail = f"TinyFish Fetch failed ({fetch_reason}); direct HTTP fallback failed ({download_reason})."
            return None, {"cache_status": "unavailable", "fetch_error": fetch_info, "download_error": download}, detail
        retrieval_path = "direct_http_fallback"
        retrieved_at = datetime.now(timezone.utc)
        metadata = {"source_url": source_url, "retrieval_path": retrieval_path, "retrieved_at": _stamp(retrieved_at), "download": download}
        _write_json(meta_path, metadata)
        integrity = _integrity_check(None, csv_path, settings)
        try:
            return _read_dataset(csv_path), {**metadata, "cache_status": "fresh", "integrity_check": integrity}, None
        except Exception as exc:
            csv_path.unlink(missing_ok=True)
            return None, {**metadata, "cache_status": "unavailable", "integrity_check": integrity}, f"Downloaded CSV parse failed: {exc}"

    # Save and validate Fetch data, then perform the required one-time comparison.
    fetch_temp = cache / "fetched-ni.tmp.csv"
    fetch_temp.write_text(fetch_text, encoding="utf-8")
    try:
        _read_dataset(fetch_temp)
    except Exception as exc:
        fetch_temp.unlink(missing_ok=True)
        download = _direct_download(source_url, csv_path)
        if download.get("status") != "ok":
            return None, {"cache_status": "unavailable", "fetch_error": f"Invalid Fetch CSV: {exc}", "download_error": download}, "Fetch response was not valid CSV and direct fallback failed."
        retrieval_path = "direct_http_fallback"
        retrieved_at = datetime.now(timezone.utc)
        metadata = {"source_url": source_url, "retrieval_path": retrieval_path, "retrieved_at": _stamp(retrieved_at), "download": download}
        _write_json(meta_path, metadata)
        return _read_dataset(csv_path), {**metadata, "cache_status": "fresh", "integrity_check": _integrity_check(None, csv_path, settings)}, None

    if direct_source is None:
        direct_status = _direct_download(source_url, csv_path)
        if direct_status.get("status") != "ok":
            fetch_temp.unlink(missing_ok=True)
            # Fetch succeeded; still accept its valid CSV, but report integrity was not comparable.
            fetch_temp.replace(csv_path)
            integrity = _integrity_check(None, csv_path, settings)
            integrity["status"] = "not_comparable"
            integrity["reason"] = "One-time direct download used for checksum comparison failed."
            _write_json(cache / "integrity-v04r01-ni.json", integrity)
        else:
            integrity = _integrity_check(fetch_text, csv_path, settings)
            fetch_temp.unlink(missing_ok=True)
    else:
        # Existing approved Phase 1b direct download supplies the comparison without another transfer.
        integrity = _integrity_check(fetch_text, direct_source, settings)
        fetch_temp.replace(csv_path)
    if not csv_path.exists():
        fetch_temp.replace(csv_path)
    metadata = {"source_url": source_url, "retrieval_path": retrieval_path or "tinyfish_fetch",
                "retrieved_at": _stamp(retrieved_at or datetime.now(timezone.utc)),
                "fetch_info": fetch_info, "integrity_check": integrity}
    _write_json(meta_path, metadata)
    try:
        return _read_dataset(csv_path), {**metadata, "cache_status": "fresh"}, None
    except Exception as exc:
        csv_path.unlink(missing_ok=True)
        return None, {**metadata, "cache_status": "unavailable"}, f"Fetched CSV parse failed: {exc}"


def _read_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, skiprows=[1], low_memory=False)
    missing = sorted(set(AGENCY_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"IBTrACS CSV is missing documented columns: {', '.join(missing)}")
    return frame


def _normalize_storm_name(name: str) -> str:
    return str(name or "").strip().casefold()


def _storm_cache_name(name: str, season: int, sid: str | None = None) -> str:
    identity = (sid or _normalize_storm_name(name)).casefold()
    return f"storm_{re.sub(r'[^a-z0-9]+', '_', identity).strip('_')}_{season}.json"


def _replay_cache_path(cache_dir: Path, name: str, season: int, mode: str, sid: str | None = None) -> Path:
    storm_key = _storm_cache_name(name, season, sid).removesuffix(".json")
    return cache_dir / f"replay_{storm_key}_{mode}.json"


def _storm_sid(frame: pd.DataFrame, name: str, season: int) -> str | None:
    selected = frame[(pd.to_numeric(frame["SEASON"], errors="coerce") == int(season)) &
                     (frame["BASIN"].astype(str).str.strip() == "NI") &
                     (frame["NAME"].fillna("").astype(str).map(_normalize_storm_name) == _normalize_storm_name(name))]
    sids = sorted({str(value).strip() for value in selected["SID"].dropna() if str(value).strip()})
    return sids[0] if len(sids) == 1 else None


def _storm_dataframe(frame: pd.DataFrame, name: str, season: int, sid: str | None = None) -> pd.DataFrame:
    selected = frame[(pd.to_numeric(frame["SEASON"], errors="coerce") == int(season)) &
                     (frame["BASIN"].astype(str).str.strip() == "NI")]
    if sid:
        selected = selected[selected["SID"].fillna("").astype(str).str.strip().str.casefold() == sid.strip().casefold()]
    else:
        selected = selected[selected["NAME"].fillna("").astype(str).map(_normalize_storm_name) == _normalize_storm_name(name)]
    selected = selected.copy()
    selected["_time"] = pd.to_datetime(selected["ISO_TIME"], utc=True, errors="coerce")
    for column in ["LAT", "LON", "NEWDELHI_LAT", "NEWDELHI_LON", "NEWDELHI_WIND"]:
        selected[column] = pd.to_numeric(selected[column], errors="coerce")
    selected = selected.dropna(subset=["_time", "LAT", "LON"])
    return selected


def _storm_choices(frame: pd.DataFrame, query: str, limit: int = 20) -> list[dict]:
    data = frame[["NAME", "SEASON", "BASIN"]].copy()
    data["NAME"] = data["NAME"].fillna("").astype(str).str.strip()
    data["season"] = pd.to_numeric(data["SEASON"], errors="coerce")
    data["_folded"] = data["NAME"].str.casefold()
    data = data[data["BASIN"].astype(str).str.strip() == "NI"]
    term = _normalize_storm_name(query)
    valid = data["NAME"].ne("") & ~data["_folded"].isin({"not_named", "not named", "unnamed", "un named", "unknown", "-"})
    if term:
        valid &= data["_folded"].str.startswith(term) | data["_folded"].str.contains(re.escape(term), regex=True)
    subset = data.loc[valid].dropna(subset=["season"])
    grouped = subset.groupby(["NAME", "season"], sort=False).agg(basin=("BASIN", "first"), rows=("NAME", "size")).reset_index()
    result = [{"name": str(row.NAME), "season": int(row.season), "basin": str(row.basin).strip(), "rows": int(row.rows)}
              for row in grouped.itertuples(index=False)]
    return sorted(result, key=lambda item: (item["name"].casefold(), item["season"]))[:limit]


def search_storms(query: str, settings: Settings | None = None) -> list[dict]:
    frame, _, error = _load_csv(settings or get_settings())
    if frame is None:
        raise RuntimeError(error or "IBTrACS dataset is unavailable.")
    return _storm_choices(frame, query, limit=20)


def _close_storm_suggestions(frame: pd.DataFrame, query: str, limit: int = 5) -> list[dict]:
    all_names = _storm_choices(frame, "", limit=len(frame))
    unique_names = sorted({item["name"] for item in all_names}, key=str.casefold)
    folded_names = {name.casefold(): name for name in unique_names}
    matches = difflib.get_close_matches(query.strip().casefold(), list(folded_names), n=limit, cutoff=0.45)
    selected_names = [folded_names[name] for name in matches]
    return [item for name in selected_names for item in all_names if item["name"] == name][:limit]


def _parse_storm_rows(frame: pd.DataFrame, name: str, season: int, source_url: str,
                      retrieval_path: str, retrieved_at: datetime, sid: str | None = None) -> list[dict]:
    selected = _storm_dataframe(frame, name, season, sid)
    # Let the existing strict parser establish row identity, UTC time, coordinates, units, and wind.
    source_text = selected[AGENCY_COLUMNS].to_csv(index=False)
    parse_issues: list[str] = []
    parsed = parse_observations(source_text, source_url, "IBTrACS historical best track; New Delhi wind is knots", retrieved_at,
                                query=_normalize_storm_name(name), issues=parse_issues, preserve_duplicates=True)
    by_time: dict[datetime, list] = {}
    for observation in parsed:
        by_time.setdefault(_utc(observation.time), []).append(observation)
    result: list[dict] = []
    for _, raw in selected.iterrows():
        time = _utc(raw["_time"].to_pydatetime())
        # Agency position is preferred; composite LAT/LON is retained where it is absent and flagged.
        use_agency_position = pd.notna(raw["NEWDELHI_LAT"]) and pd.notna(raw["NEWDELHI_LON"])
        lat = float(raw["NEWDELHI_LAT"] if use_agency_position else raw["LAT"])
        lon = float(raw["NEWDELHI_LON"] if use_agency_position else raw["LON"])
        flag = str(raw["IFLAG"] or "").ljust(6, "_")[5:6]
        subbasin = str(raw["SUBBASIN"]).strip().upper()
        basin = "Bay of Bengal" if subbasin == "BB" else "Arabian Sea" if subbasin == "AS" else None
        wind_value = None if pd.isna(raw["NEWDELHI_WIND"]) else float(raw["NEWDELHI_WIND"])
        if wind_value is None:
            # Keep the timestamp/position for audit and duplicate detection, but it cannot enter an LSTM window.
            result.append({
                "time": time, "lat": lat, "lon": lon, "wind": None,
                "cyclone_identifier": str(raw["SID"]).strip(), "cyclone_name": str(raw["NAME"]).strip(),
                "season": int(raw["SEASON"]), "basin": basin,
                "source_url": source_url, "retrieval_path": retrieval_path, "retrieved_at": retrieved_at,
                "interpolated": True, "interpolation_rule": INTERPOLATION_RULE,
                "iflag_newdelhi": flag, "data_type": "historical",
                "domain_ok": -40 <= lat <= 40 and 30 <= lon <= 130,
                "original_lat": float(raw["LAT"]), "original_lon": float(raw["LON"]),
                "newdelhi_lat": None if pd.isna(raw["NEWDELHI_LAT"]) else float(raw["NEWDELHI_LAT"]),
                "newdelhi_lon": None if pd.isna(raw["NEWDELHI_LON"]) else float(raw["NEWDELHI_LON"]),
            })
            continue
        choices = by_time.get(time, [])
        if not choices:
            continue
        observation = choices.pop(0)
        basin = basin or observation.basin
        result.append({
            "time": time, "lat": lat, "lon": lon, "wind": wind_value,
            "cyclone_identifier": str(raw["SID"]).strip(), "cyclone_name": str(raw["NAME"]).strip(),
            "season": int(raw["SEASON"]), "basin": basin,
            "source_url": source_url, "retrieval_path": retrieval_path, "retrieved_at": retrieved_at,
            "interpolated": (not use_agency_position) or flag != "O",
            "interpolation_rule": INTERPOLATION_RULE, "iflag_newdelhi": flag,
            "data_type": "historical", "domain_ok": -40 <= lat <= 40 and 30 <= lon <= 130,
            "original_lat": float(raw["LAT"]), "original_lon": float(raw["LON"]),
            "newdelhi_lat": None if pd.isna(raw["NEWDELHI_LAT"]) else float(raw["NEWDELHI_LAT"]),
            "newdelhi_lon": None if pd.isna(raw["NEWDELHI_LON"]) else float(raw["NEWDELHI_LON"]),
        })
    return result


def _load_storm_rows(name: str, season: int, settings: Settings, force_refresh: bool = False) -> tuple[list[dict], dict, str | None]:
    cache = _cache_dir(settings)
    frame, metadata, error = _load_csv(settings, force_refresh=force_refresh)
    if frame is None:
        return [], metadata, error
    sid = _storm_sid(frame, name, season)
    if sid is None:
        return [], metadata, None
    table_path = cache / _storm_cache_name(name, season, sid)
    dataset_path = cache / "ibtracs.NI.list.v04r01.csv"
    try:
        stat = dataset_path.stat()
        dataset_version = f"{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        dataset_version = None
    if table_path.exists() and not force_refresh:
        try:
            cached = _read_json(table_path)
            if (cached and isinstance(cached.get("rows"), list)
                    and cached.get("metadata", {}).get("sid", "").casefold() == sid.casefold()
                    and cached.get("metadata", {}).get("dataset_version") == dataset_version):
                meta = dict(cached["metadata"])
                meta["cache_status"] = "cached"
                return cached["rows"], meta, None
        except (KeyError, TypeError, AttributeError):
            pass
    source_url = str(metadata.get("source_url") or NI_CSV_URL)
    retrieval_path = metadata.get("retrieval_path", "direct_http_fallback")
    retrieved_at = _parse_datetime(metadata.get("retrieved_at")) or datetime.now(timezone.utc)
    rows = _parse_storm_rows(frame, name, season, source_url, retrieval_path, retrieved_at, sid=sid)
    if not rows:
        return [], metadata, None
    serializable = [{key: (_stamp(value) if isinstance(value, datetime) else value) for key, value in row.items()} for row in rows]
    try:
        stat = dataset_path.stat()
        dataset_version = f"{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        dataset_version = None
    storm_metadata = {"source_url": source_url, "retrieval_path": retrieval_path, "retrieved_at": _stamp(retrieved_at),
                      "sid": sid, "dataset_version": dataset_version,
                      "cache_status": metadata.get("cache_status", "fresh"), "integrity_check": metadata.get("integrity_check")}
    _write_json(table_path, {"rows": serializable, "metadata": storm_metadata})
    return serializable, storm_metadata, None


def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        item = dict(row)
        item["time"] = _parse_datetime(item.get("time")) or datetime.fromisoformat(str(item["time"]))
        item["retrieved_at"] = _parse_datetime(item.get("retrieved_at")) or datetime.now(timezone.utc)
        normalized.append(item)
    return normalized


def _source_order(rows: list[dict]) -> str:
    times = [_parse_datetime(row.get("time")) for row in rows]
    deltas = [(b - a).total_seconds() for a, b in zip(times, times[1:]) if a and b and a != b]
    if not deltas or all(delta > 0 for delta in deltas):
        return "ascending"
    if all(delta < 0 for delta in deltas):
        return "descending"
    return "mixed"


def _duplicate_diagnostics(rows: list[dict]) -> tuple[bool, list[dict]]:
    grouped: dict[datetime, list[dict]] = {}
    for row in rows:
        stamp = _parse_datetime(row.get("time"))
        if stamp:
            grouped.setdefault(stamp, []).append(row)
    conflicts = []
    for stamp, values in grouped.items():
        if len(values) < 2:
            continue
        signatures = {(v.get("lat"), v.get("lon"), v.get("wind")) for v in values}
        if len(signatures) > 1:
            conflicts.append({"time": _stamp(stamp), "values": [{"lat": v.get("lat"), "lon": v.get("lon"), "wind": v.get("wind")} for v in values],
                              "reason": "Duplicate UTC timestamp has conflicting position or wind values; rows remain separate."})
    return any(len(values) > 1 for values in grouped.values()), conflicts


def _training_overlap(name: str, season: int) -> tuple[str, str]:
    path = PROJECT_ROOT / "ml" / "test_storms.json"
    if not path.exists():
        return "possible_training_overlap", "ml/test_storms.json is missing; this historical storm may overlap training data."
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "possible_training_overlap", "ml/test_storms.json could not be read; this historical storm may overlap training data."
    strings: list[str] = []
    def collect(item: Any):
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, list):
            for value in item:
                collect(value)
        elif isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, (str, list, dict)):
                    collect(value)
    collect(document)
    normal_name = re.sub(r"[^a-z0-9]", "", name.lower())
    season_text = str(season)
    for item in strings:
        normalized = re.sub(r"[^a-z0-9]", "", item.lower())
        if normal_name in normalized and season_text in normalized:
            return "held_out_test", f"Matched {name} {season} in ml/test_storms.json."
    return "possible_training_overlap", f"{name} {season} was not identified in ml/test_storms.json; possible training overlap."


def _basin_row(value: str | None) -> str | None:
    if value in {"Bay of Bengal", "Arabian Sea"}:
        return value
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    h = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371.0088 * 2 * asin(sqrt(min(1, h)))


def _coordinate(value: dict) -> IBTracsCoordinate:
    return IBTracsCoordinate(time=_utc(value["time"]), lat=float(value["lat"]), lon=float(value["lon"]))


def _rejection_summary(rows: list[dict], requested_cutoff: datetime | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    ordered = sorted(rows, key=lambda row: _utc(row["time"]))
    def add(reason: str) -> None:
        counts[reason] = counts.get(reason, 0) + 1
    if len(ordered) < 9:
        add("fewer than 9 consecutive 3-hourly rows")
    for index in range(max(0, len(ordered) - 8)):
        window = ordered[index:index + 9]
        times = [_utc(row["time"]) for row in window]
        if requested_cutoff and times[-1] != requested_cutoff:
            continue
        failed = False
        if any(row.get("wind") is None or not 0 <= float(row.get("wind") or 0) <= 250 for row in window):
            add("missing or invalid wind in input window")
            failed = True
        if any(abs((times[n] - times[n - 1]).total_seconds() / 3600 - 3) > HOUR_TOLERANCE for n in range(1, 9)):
            add("fewer than 9 consecutive 3-hourly rows")
            failed = True
        cutoff = times[-1]
        available = {_utc(row["time"]) for row in ordered}
        missing_targets = [h for h in (24, 48) if cutoff + timedelta(hours=h) not in available]
        if missing_targets:
            add("missing exact +24h/+48h target rows" if len(missing_targets) == 2 else f"missing exact +{missing_targets[0]}h target row")
            failed = True
        if any(not bool(row.get("domain_ok", -40 <= float(row["lat"]) <= 40 and 30 <= float(row["lon"]) <= 130)) for row in window):
            add("one or more input positions outside training domain")
            failed = True
        if not failed:
            add("existing validator or LSTM feature contract rejected input")
    if not counts:
        add("requested cutoff does not match a qualifying input window")
    return counts


def _evaluate(
    rows: list[dict], request: IBTracsReplayRequest, settings: Settings,
    prediction_function=predict_track,
) -> IBTracsReplayResponse:
    name = request.name.strip()
    season = request.season
    ordered = sorted(rows, key=lambda row: _utc(row["time"]))
    original_order = rows
    source_order = _source_order(original_order)
    duplicates, conflicts = _duplicate_diagnostics(original_order)
    overlap, overlap_warning = _training_overlap(name, season)
    retrieved_at = max((_utc(row["retrieved_at"]) for row in ordered), default=None)
    input_rows = [row for row in ordered if row.get("wind") is not None and row.get("lat") is not None and row.get("lon") is not None
                  and 0 <= float(row["wind"]) <= 250 and -90 <= float(row["lat"]) <= 90 and -180 <= float(row["lon"]) <= 180]
    by_time: dict[datetime, list[dict]] = {}
    for row in ordered:
        by_time.setdefault(_utc(row["time"]), []).append(row)
    requested_cutoff = _utc(request.cutoff) if request.cutoff else None
    cutoff_runs: list[IBTracsCutoffReplay] = []
    validation_messages: list[str] = []
    domain_ok = True

    for index in range(max(0, len(input_rows) - 8)):
        window = input_rows[index:index + 9]
        if len(window) != 9:
            continue
        times = [_utc(item["time"]) for item in window]
        if any(abs((times[n] - times[n-1]).total_seconds()/3600 - 3) > HOUR_TOLERANCE for n in range(1, 9)):
            continue
        cutoff = times[-1]
        if requested_cutoff and cutoff != requested_cutoff:
            continue
        actuals = []
        for horizon in (24, 48):
            candidates = by_time.get(cutoff + timedelta(hours=horizon), [])
            actual = next((row for row in candidates if row.get("lat") is not None and row.get("lon") is not None), None)
            if actual is None:
                break
            actuals.append(actual)
        if len(actuals) != 2:
            continue
        if not all(bool(item.get("domain_ok", -40 <= float(item["lat"]) <= 40 and 30 <= float(item["lon"]) <= 130)) for item in window):
            domain_ok = False
            continue

        observations = [ObservationIn(time=_utc(item["time"]), lat=float(item["lat"]), lon=float(item["lon"]), wind=float(item["wind"])) for item in window]
        validation_rows = []
        for observation, raw in zip(observations, window):
            classification = "historical_best_track" if request.mode == "historical_replay" else "observed"
            basin = _basin_row(raw.get("basin"))
            # Minimal object shape used by the existing evidence validator.
            validation_rows.append(type("IBTracsValidationRow", (), {
                "time": observation.time, "lat": observation.lat, "lon": observation.lon,
                "wind": observation.wind, "classification": classification,
                "basin": basin, "cyclone_identifier": raw.get("cyclone_identifier"),
                "source_url": raw.get("source_url"),
            })())
        source_url = str(window[0].get("source_url", NI_CSV_URL))
        source_text = f"{name.lower()} {season} ibtracs north indian best track"
        issues = _validation(validation_rows, datetime.now(timezone.utc), f"{name} {season}", {source_url: source_text})
        try:
            build_lstm_sequence(observations)
        except Exception as exc:
            issues.append(f"Existing LSTM feature builder rejected this input: {exc}")
        if issues:
            validation_messages.extend(issue for issue in issues if issue not in validation_messages)
            continue
        try:
            forecast = prediction_function(TrackPredictRequest(observations=observations))
        except (LstmError, ValueError) as exc:
            validation_messages.append(f"Existing LSTM could not forecast this window: {exc}")
            continue

        last, previous = observations[-1], observations[-2]
        delta_hours = (last.time - previous.time).total_seconds() / 3600
        dlat_per_hour = (last.lat - previous.lat) / delta_hours
        dlon_per_hour = (last.lon - previous.lon) / delta_hours
        by_horizon = {item.horizon_hours: item.predicted for item in forecast.predictions}
        results = []
        for horizon, actual in zip((24, 48), actuals):
            model_coordinate = by_horizon[horizon]
            baseline_coordinate = IBTracsCoordinate(
                time=cutoff + timedelta(hours=horizon),
                lat=last.lat + dlat_per_hour * horizon,
                lon=last.lon + dlon_per_hour * horizon,
            )
            actual_coordinate = _coordinate(actual)
            results.append(IBTracsHorizonReplay(
                horizon_hours=horizon, actual=actual_coordinate,
                lstm=IBTracsCoordinate(time=_utc(model_coordinate.time), lat=model_coordinate.lat, lon=model_coordinate.lon),
                constant_velocity=baseline_coordinate,
                lstm_error_km=_haversine_km(actual_coordinate.lat, actual_coordinate.lon, model_coordinate.lat, model_coordinate.lon),
                constant_velocity_error_km=_haversine_km(actual_coordinate.lat, actual_coordinate.lon, baseline_coordinate.lat, baseline_coordinate.lon),
            ))
        model_rows = []
        interpolated_count = sum(bool(item.get("interpolated")) for item in window)
        warnings = []
        quality = "approximate_input" if interpolated_count > 2 else "validated_input"
        if quality == "approximate_input":
            warnings.append(f"{interpolated_count} of 9 input observations are flagged/interpolated; this exceeds the allowed threshold of 2. Forecast is approximate.")
        for item in window:
            model_rows.append(IBTracsObservation(
                time=_utc(item["time"]), lat=float(item["lat"]), lon=float(item["lon"]), wind=float(item["wind"]),
                cyclone_identifier=str(item.get("cyclone_identifier") or ""), cyclone_name=str(item.get("cyclone_name") or name),
                basin=_basin_row(item.get("basin")) or "Bay of Bengal", data_type="historical",
                source_url=str(item.get("source_url") or source_url), retrieval_path=item.get("retrieval_path", "direct_http_fallback"),
                retrieved_at=_utc(item.get("retrieved_at") or retrieved_at or datetime.now(timezone.utc)),
                interpolated=bool(item.get("interpolated")), interpolation_rule=str(item.get("interpolation_rule") or INTERPOLATION_RULE),
            ))
        cutoff_runs.append(IBTracsCutoffReplay(cutoff=cutoff, input_observations=model_rows,
            results=results, interpolated_count=interpolated_count, quality=quality,
            warnings=warnings, validation=[]))

    summaries: dict[str, IBTracsMetricSummary] = {}
    for horizon in (24, 48):
        for metric, key in (("lstm", "lstm_error_km"), ("constant_velocity", "constant_velocity_error_km")):
            values = [getattr(result, key) for run in cutoff_runs for result in run.results if result.horizon_hours == horizon]
            if values:
                summaries[f"{metric}_{horizon}h"] = IBTracsMetricSummary(mean_km=statistics.fmean(values), median_km=statistics.median(values))

    rejection_reasons = _rejection_summary(ordered, requested_cutoff) if not cutoff_runs else {}
    if rejection_reasons:
        validation_messages.extend(f"{count} window(s): {reason}." for reason, count in rejection_reasons.items())
    cache_status = "cached" if rows and all(item.get("cache_status") == "cached" for item in rows) else "fresh"
    return IBTracsReplayResponse(
        status="ok" if cutoff_runs else "insufficient_data", name=name, season=season, mode=request.mode,
        source_url=str(ordered[0].get("source_url")) if ordered else None,
        retrieval_path=ordered[0].get("retrieval_path") if ordered else None,
        retrieved_at=retrieved_at, cache_status=cache_status,
        cutoff_count=len(cutoff_runs), source_order=source_order,
        duplicate_timestamps=duplicates, conflicting_duplicate_timestamps=conflicts,
        domain_check_passed=domain_ok and bool(cutoff_runs),
        training_overlap_label=overlap, training_overlap_warning=overlap_warning,
        cutoffs=cutoff_runs, summary=summaries, rejection_reasons=rejection_reasons,
        validation=validation_messages,
        imd_cross_check={"requested": request.imd_cross_check, "executed": False,
                         "status": "separate_opt_in_not_run_by_ibtracs_replay"},
        message=(f"Evaluated {len(cutoff_runs)} valid cutoff(s) using historical IBTrACS rows; results are historical replay, not live forecasts."
                 if cutoff_runs else "No forecasts were run because no cutoff passed validation; rejection counts are listed above."),
    )


def replay_ibtracs(request: IBTracsReplayRequest, settings: Settings | None = None) -> IBTracsReplayResponse:
    settings = settings or get_settings()
    name = request.name.strip()
    frame_for_choices = None
    if request.season is None:
        frame_for_choices, _, choice_error = _load_csv(settings)
        if frame_for_choices is None:
            overlap, warning = _training_overlap(name, 0)
            return IBTracsReplayResponse(status="unavailable", name=name, season=None, mode=request.mode,
                cache_status="unavailable", training_overlap_label=overlap, training_overlap_warning=warning,
                message=choice_error)
        exact = [item for item in _storm_choices(frame_for_choices, "", limit=len(frame_for_choices))
                 if _normalize_storm_name(item["name"]) == _normalize_storm_name(name)]
        if len(exact) > 1:
            return IBTracsReplayResponse(status="needs_selection", name=name, season=None, mode=request.mode,
                cache_status="unavailable", training_overlap_label="possible_training_overlap",
                training_overlap_warning="Choose a season before replaying this storm.", season_options=exact,
                message=f"{name} appears in multiple IBTrACS seasons. Select one season to continue.")
        if not exact:
            return IBTracsReplayResponse(status="not_found", name=name, season=None, mode=request.mode,
                cache_status="unavailable", training_overlap_label="possible_training_overlap",
                training_overlap_warning="No matching cyclone name was found in the cached North Indian Ocean IBTrACS table.",
                suggestions=_close_storm_suggestions(frame_for_choices, name),
                message=f"No North Indian Ocean storm named {name} was found.")
        season = exact[0]["season"]
    else:
        season = request.season

    resolved_request = request.model_copy(update={"season": season})
    rows, metadata, error = _load_storm_rows(name, season, settings, force_refresh=True)
    sid = metadata.get("sid")
    if error:
        cache_frame, _, _ = _load_csv(settings)
        sid = _storm_sid(cache_frame, name, season) if cache_frame is not None else sid
        response_caches = [_replay_cache_path(_cache_dir(settings), name, season, request.mode, sid),
                           _replay_cache_path(_cache_dir(settings), name, season, request.mode)]
        cached = next((_read_json(path) for path in response_caches if path.exists()), None)
        if cached and cached.get("status") == "ok":
            try:
                result = IBTracsReplayResponse.model_validate(cached)
                if _normalize_storm_name(result.name) != _normalize_storm_name(name) or result.season != season or result.mode != request.mode:
                    raise ValueError("Cached result identity or mode did not match the request.")
                original_retrieved_at = result.retrieved_at
                result.cache_status = "cached"
                result.cached_result_from = original_retrieved_at
                result.message = (f"Cached result from {_stamp(original_retrieved_at)}; live retrieval failed: {error} "
                                 "Historical cache data is not a live observation.")
                return result
            except Exception as exc:
                logger.warning("Cached IBTrACS replay response was rejected: %s", exc)
        return IBTracsReplayResponse(status="unavailable", name=name, season=season,
            mode=request.mode, cache_status="unavailable", training_overlap_label=_training_overlap(name, season)[0],
            training_overlap_warning=_training_overlap(name, season)[1],
            imd_cross_check={"requested": request.imd_cross_check, "executed": False, "status": "separate_opt_in_not_run_by_ibtracs_replay"}, message=error)
    if not rows:
        frame, _, _ = _load_csv(settings)
        suggestions = _close_storm_suggestions(frame, name) if frame is not None else []
        return IBTracsReplayResponse(status="not_found", name=name, season=season,
            mode=request.mode, cache_status="unavailable", training_overlap_label="possible_training_overlap",
            training_overlap_warning=f"No North Indian Ocean IBTrACS rows match {name} {season}.",
            source_url=metadata.get("source_url"), retrieval_path=metadata.get("retrieval_path"),
            retrieved_at=_parse_datetime(metadata.get("retrieved_at")), suggestions=suggestions,
            integrity_check=metadata.get("integrity_check"),
            message=f"No IBTrACS NI rows match {name} {season}.")
    normalized = _normalize_rows(rows)
    result = _evaluate(normalized, resolved_request, settings)
    result.integrity_check = metadata.get("integrity_check")
    result.cache_status = metadata.get("cache_status", "cached")
    result.cached_result_from = _parse_datetime(metadata.get("retrieved_at")) if result.cache_status == "cached" else None
    if result.status == "ok":
        response_cache = _replay_cache_path(_cache_dir(settings), name, season, request.mode, sid)
        _write_json(response_cache, result.model_dump(mode="json"))
    return result
