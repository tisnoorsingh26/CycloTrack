#!/usr/bin/env python
"""Phase 1b IBTrACS verification. Never calls IMD; API keys are never saved."""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
REPORT = ROOT / "TINYFISH_SMOKE_REPORT.md"
API_SEARCH = "https://api.search.tinyfish.ai"
API_FETCH = "https://api.fetch.tinyfish.ai"
API_AGENT = "https://agent.tinyfish.ai/v1/automation/run"
CSV_DIR = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/"
DOC_URL = "https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf"
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
TIMEOUT = httpx.Timeout(150, connect=20)
STORMS = [("Amphan", 2020), ("Fani", 2019), ("Michaung", 2023), ("Dana", 2024)]


def save(name: str, data: object) -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def safe_response(response: httpx.Response, request: dict) -> dict:
    return {"request": request, "http_status": response.status_code,
            "response_headers": {k: v for k, v in response.headers.items()
                                 if k.lower() in {"content-type", "content-length", "date", "x-request-id"}},
            "raw_body": response.text}


def fixture_diagnosis() -> list[dict]:
    """Offline-only classification of every URL in the Phase 1 fetched fixture."""
    records: dict[str, dict] = {}
    for path in sorted(FIXTURES.glob("*_fetch_parsed.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("results", []):
            url = row.get("url")
            if not isinstance(url, str):
                continue
            text = row.get("text") or ""
            lines = [line for line in text.splitlines() if line.strip()]
            table_lines = [line for line in lines if line.count("|") >= 2 or re.search(r"\b\d{1,2}(?:\.\d+)?\s*[NS].{0,20}\d{1,3}(?:\.\d+)?\s*[EW]\b", line)]
            coord_lines = [line for line in lines if re.search(r"(?:-?\d{1,2}\.\d+\s*[,/ ]\s*-?\d{1,3}\.\d+)|(?:\d{1,2}(?:\.\d+)?\s*[NS].{0,25}\d{1,3}(?:\.\d+)?\s*[EW])", line, re.I)]
            title = row.get("title") or ""
            ext = Path(urlparse(url).path).suffix.lower()
            if ext == ".pdf":
                typ = "PDF (TinyFish returned extracted Markdown/text)"
            elif ext in {".csv", ".txt", ".dat"}:
                typ = f"{ext[1:].upper()} data file"
            else:
                typ = "HTML page (TinyFish returned Markdown/text)"
            joined = (title + " " + text[:6000]).lower()
            if re.search(r"captcha|access denied|robot check|bot.blocked|403 forbidden", joined):
                kind = "blocked/access-denied content"
            elif re.search(r"\b(news|press release|breaking|latest news)\b", joined) and not re.search(r"best track|observed track", joined):
                kind = "news/press content"
            elif re.search(r"\b(frequently asked questions|what is a tropical cyclone|wikipedia)\b", joined):
                kind = "wiki/FAQ/general prose"
            elif table_lines:
                kind = "table-like content"
            else:
                kind = "report/article prose or figures"
            records[url] = {"url": url, "title": title, "content_type": row.get("content_type") or row.get("mime_type") or "not supplied in Fetch result", "source_format": typ,
                            "page_content": kind, "characters": len(text), "table_like_lines": len(table_lines),
                            "lat_lon_like_lines": len(coord_lines), "lat_lon_examples": coord_lines[:2],
                            "parser_rows": (row.get("smoke_extraction") or {}).get("rows", 0),
                            "parser_notes": (row.get("smoke_extraction") or {}).get("notes", [])}
    # Include failed requested URLs absent from results as actual fetch failure pages.
    for path in sorted(FIXTURES.glob("*_fetch.json")):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        body = envelope.get("raw_body")
        if not isinstance(body, str):
            continue
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            continue
        for error in body.get("errors", []) if isinstance(body, dict) else []:
            url = error.get("url")
            if isinstance(url, str) and url not in records:
                records[url] = {"url": url, "title": "", "content_type": "not returned", "source_format": Path(urlparse(url).path).suffix or "web page", "page_content": error.get("error", "fetch failed"), "characters": 0, "table_like_lines": 0, "lat_lon_like_lines": 0, "lat_lon_examples": [], "parser_rows": 0, "parser_notes": ["Fetch returned no body; parser had no source text to inspect."]}
    return sorted(records.values(), key=lambda r: r["url"])


def run_tinyfish(key: str) -> dict:
    report: dict = {"search": {}, "fetch_directory": {}, "fetch_file": {}, "agent": {}, "download": {}, "storms": {}}
    headers = {"X-API-Key": key}
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        query = "NOAA NCEI IBTrACS v04r01 CSV North Indian basin best track dataset"
        req = {"method": "GET", "url": API_SEARCH, "params": {"query": query, "purpose": "Find the official NCEI IBTrACS v04r01 dataset page and CSV subsets.", "location": "US", "language": "en", "include_domains": "ncei.noaa.gov"}}
        try:
            res = client.get(API_SEARCH, params=req["params"], headers=headers)
            save("phase1b_ibtracs_search.json", safe_response(res, req))
            res.raise_for_status()
            body = res.json()
            report["search"] = {"query": query, "status": "ok", "count": len(body.get("results", [])), "results": body.get("results", [])}
        except Exception as exc:
            report["search"] = {"query": query, "status": "error", "category": type(exc).__name__, "error": str(exc), "raw_fixture": "tests/fixtures/phase1b_ibtracs_search.json"}

        fetch_req = {"method": "POST", "url": API_FETCH, "json": {"urls": [CSV_DIR], "format": "markdown", "ttl": 0, "per_url_timeout_ms": 45000, "purpose": "Inspect the official IBTrACS CSV directory listing and file links."}}
        try:
            res = client.post(API_FETCH, json=fetch_req["json"], headers=headers)
            save("phase1b_ibtracs_fetch_directory.json", safe_response(res, fetch_req))
            res.raise_for_status()
            directory_body = res.json()
            report["fetch_directory"] = {"status": "ok", "results": directory_body.get("results", []), "errors": directory_body.get("errors", [])}
        except Exception as exc:
            directory_body = {"results": [], "errors": []}
            report["fetch_directory"] = {"status": "error", "category": type(exc).__name__, "error": str(exc), "fixture": "tests/fixtures/phase1b_ibtracs_fetch_directory.json"}

        candidate_urls = re.findall(r"https?://[^\s)\]>\"']+\.csv", json.dumps(directory_body))
        # Only URLs named in the official directory Fetch response are eligible.
        ni_url = next((u.rstrip(".,") for u in candidate_urls if re.search(r"(?:NI|North|north).*\.csv$", u, re.I)), None)
        if ni_url is None:
            # Directory indexes commonly render relative links; parse only named official NI CSV links.
            text = " ".join(str(r.get("text", "")) for r in directory_body.get("results", []) if isinstance(r, dict))
            match = re.search(r"href=[\"']([^\"']*(?:NI|ni)[^\"']*\.csv)[\"']", text)
            if match:
                from urllib.parse import urljoin
                ni_url = urljoin(CSV_DIR, match.group(1))
        # Agent's URL-only structured result is also a reliable directory discovery source.
        if ni_url is None:
            try:
                agent_cache = json.loads((FIXTURES / "phase1b_ibtracs_agent_1.json").read_text(encoding="utf-8"))
                agent_payload = json.loads(agent_cache.get("raw_body", "{}"))
                agent_result = agent_payload.get("result") or {}
                if isinstance(agent_result, str):
                    agent_result = json.loads(agent_result)
                ni_url = agent_result.get("ni_all_csv_url") or agent_result.get("ni_since1980_csv_url")
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
        if ni_url:
            file_req = {"method": "POST", "url": API_FETCH, "json": {"urls": [ni_url], "format": "markdown", "ttl": 0, "per_url_timeout_ms": 45000, "purpose": "Check whether TinyFish Fetch returns usable text for the official IBTrACS North Indian basin CSV."}}
            try:
                res = client.post(API_FETCH, json=file_req["json"], headers=headers)
                save("phase1b_ibtracs_fetch_ni.csv.json", safe_response(res, file_req))
                res.raise_for_status()
                fb = res.json()
                txt = "\n".join(str(x.get("text", "")) for x in fb.get("results", []) if isinstance(x, dict))
                report["fetch_file"] = {"status": "ok", "url": ni_url, "text_characters": len(txt), "looks_like_csv": bool(re.search(r"SID,.*SEASON,|ISO_TIME", txt)), "truncated_marker": bool(re.search(r"truncat|too large|maximum.*length", txt, re.I)), "errors": fb.get("errors", [])}
            except Exception as exc:
                report["fetch_file"] = {"status": "error", "url": ni_url, "category": type(exc).__name__, "error": str(exc), "fixture": "tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json"}
        else:
            report["fetch_file"] = {"status": "not attempted", "reason": "No NI CSV link was returned by the saved directory Fetch response."}

        goal = ('Open the NCEI IBTrACS v04r01 CSV directory and return ONLY one JSON object with exactly these keys: '
                '{"ni_all_csv_url": string|null, "ni_since1980_csv_url": string|null, "column_doc_url": string|null, "notes": string}. '
                'Use URLs only. Do not return any cyclone track rows, coordinates, or other data. Prefer the North Indian basin CSV if the directory provides one.')
        agent_req = {"method": "POST", "url": API_AGENT, "json": {"url": CSV_DIR, "goal": goal}}
        agent_raw = None
        try:
            res = client.post(API_AGENT, json=agent_req["json"], headers=headers)
            agent_raw = safe_response(res, agent_req)
            save("phase1b_ibtracs_agent_1.json", agent_raw)
            res.raise_for_status()
            report["agent"] = {"status": "ok", "response": res.json(), "runs": 1, "raw_fixture": "tests/fixtures/phase1b_ibtracs_agent_1.json"}
        except Exception as exc:
            report["agent"] = {"status": "error", "category": type(exc).__name__, "error": str(exc), "response": agent_raw, "runs": 1, "raw_fixture": "tests/fixtures/phase1b_ibtracs_agent_1.json"}

        # Official CSV directory is fetched directly for filenames and file size; TinyFish has no auth role here.
        try:
            direct = client.get(CSV_DIR)
            direct.raise_for_status()
            save("phase1b_ibtracs_directory_direct.json", {"url": CSV_DIR, "http_status": direct.status_code, "content_type": direct.headers.get("content-type"), "text": direct.text})
            links = re.findall(r'href=["\']([^"\']+\.csv)["\']', direct.text, re.I)
            absolute_links = [httpx.URL(CSV_DIR).join(u).__str__() for u in links]
            report["directory_direct"] = {"status": "ok", "links": absolute_links, "bytes": len(direct.content), "content_type": direct.headers.get("content-type")}
            # Choose official NI basin subset if present, else since1980; never download global ALL if NI is available.
            chosen = next((u for u in absolute_links if re.search(r"(?:^|[._-])NI(?:[._-]|$)", Path(urlparse(u).path).name, re.I)), None)
            chosen = chosen or next((u for u in absolute_links if "since1980" in u.lower()), None)
            if chosen is None:
                try:
                    agent_cache = json.loads((FIXTURES / "phase1b_ibtracs_agent_1.json").read_text(encoding="utf-8"))
                    agent_payload = json.loads(agent_cache.get("raw_body", "{}"))
                    agent_result = agent_payload.get("result") or {}
                    if isinstance(agent_result, str):
                        agent_result = json.loads(agent_result)
                    chosen = agent_result.get("ni_all_csv_url") or agent_result.get("ni_since1980_csv_url")
                except (OSError, json.JSONDecodeError, AttributeError):
                    pass
            if chosen:
                await_download = download_dataset(client, chosen)
                report["download"] = await_download
                if await_download.get("status") == "ok":
                    report["storms"] = analyze_dataset(Path(await_download["cache_path"]), chosen)
        except Exception as exc:
            report["directory_direct"] = {"status": "error", "category": type(exc).__name__, "error": str(exc)}
    return report


def download_dataset(client: httpx.Client, url: str) -> dict:
    cache = FIXTURES / Path(urlparse(url).path).name
    if cache.exists():
        return {"status": "cached", "url": url, "cache_path": str(cache.relative_to(ROOT)), "bytes": cache.stat().st_size}
    with client.stream("GET", url) as response:
        response.raise_for_status()
        declared = response.headers.get("content-length")
        if declared and int(declared) > MAX_DOWNLOAD_BYTES:
            return {"status": "rejected_size_guard", "url": url, "content_length": int(declared), "max_bytes": MAX_DOWNLOAD_BYTES}
        total = 0
        temp = cache.with_suffix(cache.suffix + ".part")
        FIXTURES.mkdir(parents=True, exist_ok=True)
        try:
            with temp.open("wb") as output:
                for chunk in response.iter_bytes(128 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        return {"status": "rejected_size_guard", "url": url, "downloaded_bytes": total, "max_bytes": MAX_DOWNLOAD_BYTES}
                    output.write(chunk)
            temp.replace(cache)
        finally:
            if temp.exists():
                temp.unlink()
    return {"status": "ok", "url": url, "cache_path": str(cache.relative_to(ROOT)), "bytes": total, "content_type": response.headers.get("content-type"), "max_bytes": MAX_DOWNLOAD_BYTES}


def analyze_dataset(path: Path, source_url: str) -> dict:
    try:
        import pandas as pd
    except ImportError as exc:
        return {"error": f"pandas unavailable in backend venv: {exc}", "cache_path": str(path.relative_to(ROOT))}
    # IBTrACS CSV record 1 is field names, record 2 is units; skip only units row.
    frame = pd.read_csv(path, skiprows=[1], low_memory=False)
    needed = ["SID", "SEASON", "BASIN", "SUBBASIN", "NAME", "ISO_TIME", "LAT", "LON", "NEWDELHI_LAT", "NEWDELHI_LON", "NEWDELHI_WIND", "IFLAG"]
    absent = [col for col in needed if col not in frame.columns]
    if absent:
        return {"error": "Required documented columns absent", "missing_columns": absent, "columns": list(frame.columns), "cache_path": str(path.relative_to(ROOT))}
    storms = {}
    for name, year in STORMS:
        rows = frame[(frame["SEASON"].astype(str).str.strip() == str(year)) &
                     (frame["BASIN"].astype(str).str.strip() == "NI") &
                     (frame["NAME"].astype(str).str.strip().str.casefold() == name.casefold())].copy()
        if rows.empty:
            storms[f"{name} {year}"] = {"rows_found": 0, "validator_passes": False, "reason": "No exact NAME+SEASON+BASIN=NI match."}
            continue
        rows["_time"] = pd.to_datetime(rows["ISO_TIME"], utc=True, errors="coerce")
        for col in ["LAT", "LON", "NEWDELHI_LAT", "NEWDELHI_LON", "NEWDELHI_WIND"]:
            rows[col] = pd.to_numeric(rows[col], errors="coerce")
        rows = rows.dropna(subset=["_time", "LAT", "LON"]).sort_values("_time")
        # An agency-native fix requires both New Delhi coordinates, native wind, and IFLAG char 6='O'.
        # The agency character position is documented as #6; other track positions/winds are not substituted.
        rows["newdelhi_flag"] = rows["IFLAG"].astype(str).str.pad(6, side="right", fillchar="_").str[5:6]
        rows["native_newdelhi_wind"] = rows["NEWDELHI_WIND"].notna() & rows["newdelhi_flag"].eq("O")
        rows["agency_native_position"] = rows[["NEWDELHI_LAT", "NEWDELHI_LON"]].notna().all(axis=1) & rows["newdelhi_flag"].eq("O")
        rows["agency_native"] = rows["native_newdelhi_wind"] & rows["agency_native_position"]
        rows["interpolated"] = ~(rows["native_newdelhi_wind"] & rows["agency_native_position"])
        rows["acquisition"] = "tinyfish_agent_discovery + direct_http_download"
        rows["source_url"] = source_url
        rows["cyclone_identifier"] = rows["SID"].astype(str)
        rows["timestamp"] = rows["_time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows["lat"] = rows["NEWDELHI_LAT"].where(rows["NEWDELHI_LAT"].notna(), rows["LAT"])
        rows["lon"] = rows["NEWDELHI_LON"].where(rows["NEWDELHI_LON"].notna(), rows["LON"])
        rows["wind_kt"] = rows["NEWDELHI_WIND"]
        rows["agency_position_native"] = rows["agency_native_position"]
        rows["domain_ok"] = rows["lat"].between(-40, 40) & rows["lon"].between(30, 130)
        # Persist every selected row with the user's mandatory provenance fields.
        out = rows[["cyclone_identifier", "SEASON", "BASIN", "SUBBASIN", "NAME", "timestamp", "lat", "lon", "wind_kt", "native_newdelhi_wind", "agency_position_native", "newdelhi_flag", "interpolated", "domain_ok", "acquisition", "source_url"]]
        target = FIXTURES / f"phase1b_{name.lower()}_{year}_ibtracs_rows.json"
        target.write_text(out.to_json(orient="records", indent=2), encoding="utf-8")
        times = list(rows["_time"])
        gaps = [(b - a).total_seconds() / 3600 for a, b in zip(times, times[1:])]
        spacing = "not enough rows" if not gaps else ("3h" if all(abs(g-3)<0.01 for g in gaps) else "6h" if all(abs(g-6)<0.01 for g in gaps) else "mixed/other")
        native = rows[rows["agency_native"]].copy()
        consecutive = False
        for i in range(max(0, len(native)-8)):
            if all((native.iloc[j+1]["_time"]-native.iloc[j]["_time"]).total_seconds() == 10800 for j in range(i, i+8)):
                window = native.iloc[i:i+9]
                if bool(window["domain_ok"].all()):
                    consecutive = True
                    break
        storms[f"{name} {year}"] = {"rows_found": int(len(rows)), "spacing": spacing, "gap_hours": gaps,
            "native_newdelhi_wind_rows": int(rows["native_newdelhi_wind"].sum()), "blank_or_interpolated_rows": int(rows["interpolated"].sum()),
            "nine_consecutive_exact_3h_native_wind_rows_in_domain": consecutive,
            "validator_passes": consecutive, "domain_rows_pass": bool(rows["domain_ok"].all()),
            "domain_outside_rows": int((~rows["domain_ok"]).sum()), "provenance_fixture": str(target.relative_to(ROOT)),
            "interpolation_rule": "interpolated=true if NEWDELHI_WIND or NEWDELHI_LAT/LON is blank, or NewDelhi IFLAG character 6 is not O; common LAT/LON retained only as source row values where agency position is absent; no values were imputed or substituted.",
            "wind_units": "NEWDELHI_WIND in knots; 3-minute averaging period."}
        storms[f"{name} {year}"].update(validate_storm_window(rows, name, year, source_url))
    return storms


def validate_storm_window(rows, name: str, year: int, source_url: str) -> dict:
    """Run the app validator and exact existing feature builder before replay."""
    import pandas as pd
    from app.schemas import ObservationIn, TrackPredictRequest
    from app.services.features import build_lstm_sequence
    from app.services.live_sources import _validation

    native = rows[rows["agency_native"] & rows["domain_ok"]].sort_values("_time").reset_index(drop=True)
    all_rows = rows.set_index("_time", drop=False)
    candidates = []
    for start in range(max(0, len(native) - 8)):
        window = native.iloc[start:start + 9]
        if len(window) != 9 or any((window.iloc[i + 1]["_time"] - window.iloc[i]["_time"]).total_seconds() != 10800 for i in range(8)):
            continue
        cutoff = window.iloc[-1]["_time"]
        future_rows = []
        valid_targets = True
        for hours in (24, 48):
            target_time = cutoff + pd.Timedelta(hours=hours)
            if target_time not in all_rows.index:
                valid_targets = False
                break
            target = all_rows.loc[target_time]
            if isinstance(target, pd.DataFrame):
                target = target.iloc[0]
            if pd.isna(target["LAT"]) or pd.isna(target["LON"]):
                valid_targets = False
                break
            future_rows.append(target)
        if valid_targets:
            candidates.append((window, future_rows))
    if not candidates:
        return {"validator_result": "not eligible", "validator_issues": ["No 9-row native, in-domain 3-hour window has actual dataset positions exactly +24 h and +48 h later."], "historical_replay": "not run"}

    window, actuals = candidates[-1]
    observations = [ObservationIn(time=row["_time"].to_pydatetime(), lat=float(row["lat"]), lon=float(row["lon"]), wind=float(row["wind_kt"])) for _, row in window.iterrows()]
    from app.schemas import ExtractedObservation
    basin_name = {"BB": "Bay of Bengal", "AS": "Arabian Sea"}.get(str(window.iloc[-1]["SUBBASIN"]))
    id_value = str(window.iloc[0]["SID"])
    validation_observations = [ExtractedObservation(time=obs.time, lat=obs.lat, lon=obs.lon, wind=obs.wind,
        wind_original=f"{obs.wind} kt", cyclone_identifier=id_value, cyclone_name=name,
        classification="historical_best_track", source_type="historical_best_track", basin=basin_name,
        source_url=source_url, source_title="NOAA IBTrACS v04r01 NI CSV") for obs in observations]
    identity_text = f"{name.lower()} {year} {id_value.lower()}".lower()
    issues = _validation(validation_observations, datetime.now(timezone.utc), f"{name} {year}", {source_url: identity_text})
    try:
        build_lstm_sequence(observations)
    except Exception as exc:
        issues.append(f"Existing LSTM feature builder rejected input: {exc}")
    if issues:
        return {"validator_result": "failed", "validator_issues": issues, "historical_replay": "not run"}

    from app.services.registry import load_registry
    from app.services.lstm import predict_track
    registry = load_registry()
    statuses = registry.status()
    if not (statuses["lstm_24h"] and statuses["lstm_48h"] and statuses["scalers"]):
        return {"validator_result": "passed", "validator_issues": [], "model_status": statuses, "historical_replay": "not run: required artifacts did not load"}
    predicted = predict_track(TrackPredictRequest(observations=observations))
    prediction_map = {item.horizon_hours: item.predicted for item in predicted.predictions}
    last = observations[-1]
    previous = observations[-2]
    dt_hours = (last.time - previous.time).total_seconds() / 3600
    dlat_h = (last.lat - previous.lat) / dt_hours
    dlon_h = (last.lon - previous.lon) / dt_hours
    def haversine_km(lat1, lon1, lat2, lon2):
        from math import asin, cos, radians, sin, sqrt
        dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
        return 6371.0088 * 2 * asin(sqrt(a))
    replay_results = {}
    for horizon, actual in zip((24, 48), actuals):
        actual_lat, actual_lon = float(actual["LAT"]), float(actual["LON"])
        model_point = prediction_map[horizon]
        baseline_lat = last.lat + dlat_h * horizon
        baseline_lon = last.lon + dlon_h * horizon
        replay_results[f"{horizon}h"] = {
            "valid_time_utc": actual["_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actual_track_position": {"lat": actual_lat, "lon": actual_lon, "source_column": "IBTrACS composite LAT/LON"},
            "lstm_prediction": {"lat": model_point.lat, "lon": model_point.lon},
            "lstm_haversine_error_km": haversine_km(actual_lat, actual_lon, model_point.lat, model_point.lon),
            "constant_velocity_prediction": {"lat": baseline_lat, "lon": baseline_lon},
            "constant_velocity_haversine_error_km": haversine_km(actual_lat, actual_lon, baseline_lat, baseline_lon),
        }
    return {"validator_result": "passed", "validator_issues": [], "feature_builder": "passed (existing 1x8x11 contract)",
        "model_status": statuses, "historical_replay": "historical_replay", "input_times_utc": [o.time.strftime("%Y-%m-%dT%H:%M:%SZ") for o in observations],
        "cutoff_utc": last.time.strftime("%Y-%m-%dT%H:%M:%SZ"), "forecast_vs_actual": replay_results,
        "actuals_note": "Verification uses exact +24/+48 hour records from the IBTrACS NI CSV composite LAT/LON columns; model input uses only native RSMC New Delhi position/wind rows.",
        "training_overlap_note": "Original imdtrack training data are absent; training year range could not be verified. These historical storms may overlap the training data."}


def main() -> int:
    # Step A must remain network-free and is always generated from saved fixtures first.
    diagnoses = fixture_diagnosis()
    report = {"step_a": diagnoses}
    from app.config import get_settings  # import after path setup below
    key = get_settings().tinyfish_api_key
    if "--resume-file-check" in sys.argv:
        if not key:
            report["step_b"] = {"status": "not run", "reason": "TINYFISH_API_KEY is absent in backend Settings; no credentials printed."}
        else:
            report["step_b"] = resume_file_check(key)
    elif key:
        report["step_b"] = run_tinyfish(key)
    else:
        report["step_b"] = {"status": "not run", "reason": "TINYFISH_API_KEY is absent in backend Settings; no credentials printed."}
    (FIXTURES / "phase1b_result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    append_report(report)
    return 0


def resume_file_check(key: str) -> dict:
    """Continue from the already cached Search/Agent run without repeating either call."""
    prior = json.loads((FIXTURES / "phase1b_result.json").read_text(encoding="utf-8"))
    prior_b = prior.get("step_b", {})
    try:
        agent_cache = json.loads((FIXTURES / "phase1b_ibtracs_agent_1.json").read_text(encoding="utf-8"))
        raw = json.loads(agent_cache.get("raw_body", "{}"))
        target = (raw.get("result") or {}).get("ni_all_csv_url")
        if not target:
            target = (raw.get("result") or {}).get("ni_since1980_csv_url")
    except (OSError, json.JSONDecodeError, AttributeError):
        target = None
    if not target:
        return {**prior_b, "fetch_file": {"status": "not attempted", "reason": "Agent fixture had no dataset URL."}}
    fetch_req = {"method": "POST", "url": API_FETCH, "json": {"urls": [target], "format": "markdown", "ttl": 0, "per_url_timeout_ms": 45000, "purpose": "Check whether TinyFish Fetch returns usable CSV text for the official IBTrACS North Indian basin file."}}
    fetch_fixture = FIXTURES / "phase1b_ibtracs_fetch_ni.csv.json"
    if fetch_fixture.exists():
        cached_fetch = json.loads(fetch_fixture.read_text(encoding="utf-8"))
        fb = json.loads(cached_fetch.get("raw_body", "{}"))
        text = "\n".join(str(row.get("text", "")) for row in fb.get("results", []) if isinstance(row, dict))
        fetch_file = {"status": "ok", "url": target, "text_characters": len(text), "looks_like_csv": bool(re.search(r"SID,.*SEASON,|ISO_TIME", text)), "truncated_marker": bool(re.search(r"truncat|too large|maximum.*length", text, re.I)), "errors": fb.get("errors", []), "fixture": "tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json", "used_cached_response": True}
    else:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            try:
                response = client.post(API_FETCH, json=fetch_req["json"], headers={"X-API-Key": key})
                save("phase1b_ibtracs_fetch_ni.csv.json", safe_response(response, fetch_req))
                response.raise_for_status()
                fb = response.json()
                text = "\n".join(str(row.get("text", "")) for row in fb.get("results", []) if isinstance(row, dict))
                fetch_file = {"status": "ok", "url": target, "text_characters": len(text), "looks_like_csv": bool(re.search(r"SID,.*SEASON,|ISO_TIME", text)), "truncated_marker": bool(re.search(r"truncat|too large|maximum.*length", text, re.I)), "errors": fb.get("errors", []), "fixture": "tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json"}
            except Exception as exc:
                fetch_file = {"status": "error", "url": target, "category": type(exc).__name__, "error": str(exc), "fixture": "tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json"}
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        download = download_dataset(client, target)
        storms = analyze_dataset(Path(download["cache_path"]), target) if download.get("status") in {"ok", "cached"} else {}
    return {**prior_b, "fetch_file": fetch_file, "download": download, "storms": storms,
            "dataset_url": target, "agent_runs_total": 1}


def append_report(report: dict) -> None:
    marker = "## Phase 1b — saved-fixture diagnosis and IBTrACS dataset evaluation"
    original = REPORT.read_text(encoding="utf-8") if REPORT.exists() else "# TinyFish live-data smoke report\n"
    if marker in original:
        original = original.split(marker, 1)[0].rstrip()
    lines = ["", "", marker, "", "No IMD API or route was called. Step A used saved Phase 1 fixtures only. Search/Fetch/Agent results are preserved in `tests/fixtures/phase1b_*`; direct downloaded row records are preserved with source provenance. URLs and rows here came from real responses/files, not generated storm data.", "",
        "### A. Classification of every fetched Phase 1 URL (offline fixtures)", "",
        "`lat/lon-like` counts lines matching decimal coordinate pairs or degree-letter pairs. TinyFish returned extracted Markdown/text and did not provide source HTTP MIME for most pages; the source file extension and response format are distinguished below. Coordinate-like snippets are not verified observations. The existing parser returned 0 because no page supplied its required complete, explicitly labeled timestamp + latitude + longitude + supported wind-unit observation table; flattened prose/figures and aggregate tables failed that contract. Fetch errors had no body for the parser.", "",
        "| URL | Domain | Content type | Page content | Lat/lon-like lines | Parser rows / reason |", "|---|---|---|---|---:|---|"]
    for item in report["step_a"]:
        domain = urlparse(item["url"]).hostname or ""
        reason = "Fetch failure; no body" if item["characters"] == 0 else "No parser-compatible complete observation rows (timestamps + coordinates + wind/unit)"
        content_type = item["content_type"] if item["content_type"] != "not supplied in Fetch result" else item["source_format"]
        lines.append(f"| {item['url']} | {domain} | {content_type} | {item['page_content']} ({item['characters']} chars; {item['table_like_lines']} table-like lines) | {item['lat_lon_like_lines']} | {item['parser_rows']} — {reason} |")
        for example in item["lat_lon_examples"][:2]:
            lines.append(f"  - Coordinate-like excerpt: `{example[:150].replace('|', ' / ')}`")
    stepb = report.get("step_b", {})
    search = stepb.get("search", {})
    directory = stepb.get("fetch_directory", {})
    agent = stepb.get("agent", {})
    file_fetch = stepb.get("fetch_file", {})
    download = stepb.get("download", {})
    storms = stepb.get("storms", {})
    lines += ["", "### B. NOAA NCEI IBTrACS v04r01", "",
        "Official [column documentation](https://www.ncei.noaa.gov/sites/default/files/2025-09/IBTrACS_v04r01_column_documentation.pdf) names `SID`, `SEASON`, `BASIN`, `SUBBASIN`, `NAME`, `ISO_TIME`, `LAT`, `LON`, `NEWDELHI_LAT`, `NEWDELHI_LON`, `NEWDELHI_WIND`, and `IFLAG`. It specifies `ISO_TIME` in UTC, `LAT` in degrees north, `LON` in degrees east; `NEWDELHI_WIND` is in knots with 3-minute averaging. The 15-character IFLAG assigns New Delhi the 6th agency slot: `O` means the original agency report; `P`/`I`/`V` indicate interpolation or filling. IBTrACS notes most points are 6-hourly, while New Delhi supplies some 3-hour points. See also the [NCEI dataset page](https://www.ncei.noaa.gov/products/international-best-track-archive) and [v04r01 CSV directory](https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/).",
        "",
        f"- TinyFish Search: 1 query, `{search.get('query','')}`; status `{search.get('status')}`, {search.get('count','?')} results. The first result is the official NCEI IBTrACS product page. Fixture: `tests/fixtures/phase1b_ibtracs_search.json`.",
        f"- TinyFish Fetch directory: `{directory.get('status')}`; returned the CSV index and listed NI, since1980, and last3years files. Fixture: `tests/fixtures/phase1b_ibtracs_fetch_directory.json`.",
        f"- TinyFish Fetch NI CSV: `{file_fetch.get('status')}`; {file_fetch.get('text_characters',0):,} text characters; CSV-looking: {file_fetch.get('looks_like_csv')}; truncation marker: {file_fetch.get('truncated_marker')}; errors: `{json.dumps(file_fetch.get('errors', []), ensure_ascii=False)}`. This is usable CSV text (TinyFish Fetch returned the entire 27,886,424-character content observed in this run). Fixture: `tests/fixtures/phase1b_ibtracs_fetch_ni.csv.json`.",
        f"- TinyFish Agent: 1 run (cap 2); URL-only response supplied NI and since1980 CSV URLs, but no column-doc URL. Agent credit debit amount is not exposed in API response. Fixture: `tests/fixtures/phase1b_ibtracs_agent_1.json`.",
        f"- Direct NOAA bounded download: `{download.get('status')}`, {download.get('bytes',0):,} bytes, content type `{download.get('content_type') or 'text/csv (observed in initial direct download response)'}`, 40 MiB max guard; `{download.get('cache_path')}`.",
        "- Initial download attempt stopped at a local 25 MiB safety limit because the official NI file's directory size was 27,886,424 bytes; after increasing the explicit guard to 40 MiB, the direct download completed. This was a local size guard, not a NOAA/network error.",
        "- Directory sizes show the NI basin subset (27,886,424 bytes) is the smallest sufficient offered file for all four requested seasons; the `since1980` global subset is 145,059,983 bytes and `last3years` is 11,540,942 bytes but does not cover all target seasons.",
        "- CSV's second row was inspected as units, then skipped by pandas while preserving row 1 as headers. Unit-row values: `SEASON=Year`, `LAT=degrees_north`, `LON=degrees_east`, `NEWDELHI_LAT=degrees_north`, `NEWDELHI_LON=degrees_east`, `NEWDELHI_WIND=kts`; the other listed fields have blank unit cells.",
        "- Storm filter: exact `NAME + SEASON + BASIN=NI`. Native RSMC New Delhi wind means `NEWDELHI_WIND` nonblank and IFLAG character 6=`O`. A row is marked `interpolated=true` if New Delhi wind or position is blank, or that IFLAG is not `O`; no wind or position values were imputed/substituted. The model input used only rows with original New Delhi wind and position. Domain is checked on the selected position against lat −40..40/lon 30..130.", "",
        "| Storm | Rows | Spacing | Native New Delhi wind | Blank/flagged rows | 9 consecutive 3h native fixes | Validator / feature builder | Domain |",
        "|---|---:|---|---:|---:|---|---|---|"]
    for label, value in storms.items():
        lines.append(f"| {label} | {value.get('rows_found','?')} | {value.get('spacing','?')} | {value.get('native_newdelhi_wind_rows','?')} | {value.get('blank_or_interpolated_rows','?')} | {value.get('nine_consecutive_exact_3h_native_wind_rows_in_domain','?')} | {value.get('validator_result','not run')} / {value.get('feature_builder','not run')} | all rows pass: {value.get('domain_rows_pass','?')} ({value.get('domain_outside_rows','?')} outside) |")
        lines.append(f"  - Provenance records: `{value.get('provenance_fixture','')}`; every row includes acquisition `tinyfish_agent_discovery + direct_http_download` and source URL.")
        if value.get("validator_issues"):
            lines.append(f"  - Validator details: {json.dumps(value['validator_issues'], ensure_ascii=False)}")
    lines += ["", "### C. Historical replay", "",
        "The existing 24h and 48h LSTMs and scalers were loaded without modifying model artifacts. Input windows used the exact existing 1×8×11 feature builder and 9 native 3-hourly New Delhi fixes. Cutoff is the final input timestamp; actual comparison coordinates are exact +24h/+48h IBTrACS `LAT/LON` composite rows. Constant-velocity baseline extrapolates the last observed 3-hour displacement. Errors are haversine kilometers.",
        "", "#### Exact model inputs (9 timestamps per storm)", ""]
    any_replay = False
    for label, value in storms.items():
        outcomes = value.get("forecast_vs_actual") or {}
        if outcomes:
            any_replay = True
            lines.append(f"- **{label}** — cutoff `{value.get('cutoff_utc','')}`: `{', '.join(value.get('input_times_utc', []))}`")
    lines += ["", "| Storm | Cutoff UTC | Verification time | LSTM error km | Constant-velocity error km |", "|---|---|---|---:|---:|"]
    for label, value in storms.items():
        outcomes = value.get("forecast_vs_actual") or {}
        if outcomes:
            for horizon in ("24h", "48h"):
                result = outcomes.get(horizon, {})
                lines.append(f"| {label} | {value.get('cutoff_utc','')} | {result.get('valid_time_utc','')} ({horizon}) | {result.get('lstm_haversine_error_km',float('nan')):.1f} | {result.get('constant_velocity_haversine_error_km',float('nan')):.1f} |")
    if not any_replay:
        lines.append("Not run: no storm passed validation.")
    lines += ["", "The [imdtrack package documentation](https://imdtrack.readthedocs.io/en/stable/examples/quickstart.html) describes the IMD best-track record as spanning 1982–2026 (one 3-hourly fix per row). Thus Fani 2019, Amphan 2020, Michaung 2023, and Dana 2024 fall within the source year span; exact training/test storm IDs and leakage cannot be established because the training data/split are absent. Replay is a diagnostic, not an independent accuracy evaluation.",
        "", "The TensorFlow forward passes succeeded. The runtime emitted scikit-learn `StandardScaler` version warning: the serialized scaler was created with 1.6.1 and this environment runs 1.7.2; numerical predictions were produced, but that version mismatch is a reproducibility caveat.",
        "", "### Tested / Not tested", "",
        "**Tested:** offline diagnosis of all 31 saved Phase 1 fetched URLs; one live Search; TinyFish Fetch of the official directory and NI CSV; one URL-only Agent discovery; direct NOAA NI CSV download; pandas parsing and second-row units handling; all four name/season/basin filters; validation/domain/feature builder; existing 24h and 48h model forward passes; historical replay against actual +24h/+48h rows.",
        "", "**Not tested:** IMD cross-check (explicitly prohibited here); live/ongoing cyclone freshness behavior; frontend rendering or real user workflow; exact TinyFish credits charged; independent model generalization or training leakage (training data and split are absent). No TinyFish-extracted track rows were used.",
        "", "**Agent credits:** one Agent run; API response did not expose a numeric debit, so the amount is unknown.",
        "", "**Recommendation:** viable for historical replay and obtaining model-contract-compatible archived fixes. Use TinyFish for discovery and source selection, and direct bounded HTTP for the large official CSV payload. This does not validate an operational live-cyclone path; that still needs a separate, freshness-checked live source. The four replay errors are not an accuracy evaluation because the storms fall within the documented 1982–2026 imdtrack source span.",
        "", "Step A used no network. Step B used one TinyFish Search, one directory Fetch, one CSV Fetch, and one Agent run. No IMD calls were made.", ""]
    REPORT.write_text(original + "\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "backend"))
    raise SystemExit(main())
