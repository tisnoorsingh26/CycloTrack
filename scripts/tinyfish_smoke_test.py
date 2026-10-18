#!/usr/bin/env python
"""Live TinyFish Search -> Fetch -> parser smoke test (never calls IMD or LSTM)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.services.live_sources import (  # noqa: E402
    OFFICIAL_HOSTS,
    _validation,
    parse_observations,
    validate_fetch_url,
)

FIXTURES = ROOT / "tests" / "fixtures"
REPORT = ROOT / "TINYFISH_SMOKE_REPORT.md"
SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run"
DOMAINS = "imd.gov.in,noaa.gov,ncei.noaa.gov,metoffice.gov.uk,bom.gov.au,jma.go.jp,wmo.int,ibtracs.unca.edu"
CYCLONES = [
    ("Amphan", 2020),
    ("Fani", 2019),
    ("Michaung", 2023),
    ("Dana", 2024),
]
QUERY_TEMPLATES = (
    '"{name}" {year} cyclone historical track best track latitude longitude observation time wind speed',
    '"{name}" {year} cyclone track positions 3-hourly latitude longitude wind speed',
)
AGENT_GOAL_VERSION = "cyclone-track-json-v1"
MAX_AGENT_RUNS_PER_CYCLONE = 2
MAX_FETCH_URLS = 10
HTTP_TIMEOUT = httpx.Timeout(155.0, connect=20.0)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _save_raw(name: str, payload: object) -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _response_record(response: httpx.Response, request: dict) -> dict:
    # Never persist request headers: they contain the secret API key.
    return {
        "request": request,
        "http_status": response.status_code,
        "response_headers": {
            key: value for key, value in response.headers.items()
            if key.lower() in {"content-type", "date", "x-request-id"}
        },
        "raw_body": response.text,
    }


def _error_record(exc: Exception, request: dict, raw_body: str | None = None) -> dict:
    if isinstance(exc, httpx.TimeoutException):
        category = "timeout"
    elif isinstance(exc, httpx.ConnectError):
        category = "connection"
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        category = "authentication" if status in (401, 403) else f"HTTP {status}"
    elif isinstance(exc, (json.JSONDecodeError, ValueError)):
        category = "response parsing"
    elif isinstance(exc, httpx.HTTPError):
        category = "connection/TLS"
    else:
        category = type(exc).__name__
    response = getattr(exc, "response", None)
    return {
        "request": request,
        "error_category": category,
        "http_status": response.status_code if isinstance(response, httpx.Response) else None,
        "error": str(exc)[:1000],
        "raw_body": raw_body if raw_body is not None else response.text if isinstance(response, httpx.Response) else None,
    }


def _safe_candidates(results: list[dict], name: str, year: int) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for row in results:
        url = row.get("url")
        if not isinstance(url, str) or url in seen:
            continue
        seen.add(url)
        host = (urlparse(url).hostname or "").lower().rstrip(".")
        approved = any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_HOSTS)
        try:
            safe_url = validate_fetch_url(url)
        except ValueError:
            safe_url = None
        candidate = {
            "title": row.get("title") if isinstance(row.get("title"), str) else "",
            "url": url,
            "host": host,
            "approved_for_fetch": bool(safe_url),
            "official_or_meteorological_domain": approved,
            "snippet_unverified": row.get("snippet") if isinstance(row.get("snippet"), str) else "",
        }
        text = f"{candidate['title']} {candidate['snippet_unverified']}".lower()
        candidate["relevance_score"] = (
            4 * int(name.lower() in text)
            + 2 * int(str(year) in text)
            + 2 * int(bool(re.search(r"best[ -]?track|observed track|track positions|cyclone report|tropical cyclone report", text)))
            + int(bool(re.search(r"historical|track|position|bulletin|cyclone", text)))
        )
        candidates.append(candidate)
    # Prioritize the requested storm and track records, then trusted domains.
    candidates.sort(key=lambda item: (-item["relevance_score"], not item["official_or_meteorological_domain"], not item["approved_for_fetch"]))
    return candidates


def _spacing(rows: list[object]) -> tuple[str, list[float]]:
    ordered = sorted(rows, key=lambda row: row.time)
    gaps = [round((b.time - a.time).total_seconds() / 3600, 3) for a, b in zip(ordered, ordered[1:])]
    if not gaps:
        return "not enough rows", gaps
    kinds = {"3h" if abs(gap - 3) < 0.15 else "6h" if abs(gap - 6) < 0.15 else "other" for gap in gaps}
    if len(kinds) > 1:
        return "mixed", gaps
    return next(iter(kinds)), gaps


def _window_results(rows: list[object], name: str, source_text: str) -> dict:
    ordered = sorted(rows, key=lambda row: row.time)
    duplicate_times = len({row.time for row in ordered}) != len(ordered)
    windows: list[list[object]] = []
    for index in range(max(0, len(ordered) - 8)):
        candidate = ordered[index:index + 9]
        if len(candidate) != 9:
            continue
        gaps = [(b.time - a.time).total_seconds() / 3600 for a, b in zip(candidate, candidate[1:])]
        if all(abs(gap - 3) < 0.15 for gap in gaps):
            windows.append(candidate)
    latest = windows[-1] if windows else []
    validation: list[str] = []
    domain_issues: list[str] = []
    if latest:
        validation = _validation(latest, datetime.now(timezone.utc), name, {latest[0].source_url: source_text})
        for row in latest:
            if not (-40 <= row.lat <= 40 and 30 <= row.lon <= 130):
                domain_issues.append(
                    f"{row.time.isoformat()}: ({row.lat}, {row.lon}) outside training envelope lat -40..40, lon 30..130."
                )
    elif ordered:
        validation = _validation(ordered, datetime.now(timezone.utc), name,
                                 {ordered[0].source_url: source_text})
    # This is a spacing-only estimate, never a generated/interpolated track.
    interpolation_eligible = False
    if not latest and len(ordered) >= 5 and not duplicate_times:
        gaps = [(b.time - a.time).total_seconds() / 3600 for a, b in zip(ordered, ordered[1:])]
        interpolation_eligible = len(gaps) >= 4 and all(abs(gap - 6) < 0.15 for gap in gaps)
    return {
        "row_count": len(rows),
        "duplicate_timestamps": duplicate_times,
        "spacing": _spacing(rows)[0],
        "gaps_hours": _spacing(rows)[1],
        "has_nine_consecutive_3h_rows": bool(latest),
        "would_qualify_after_6h_to_3h_interpolation_spacing_only": interpolation_eligible,
        "validator_passes": bool(latest) and not validation,
        "domain_passes": bool(latest) and not domain_issues,
        "existing_validator_passes": bool(latest) and not validation and not domain_issues,
        "validator_issues": validation,
        "domain_check_passes": bool(latest) and not domain_issues,
        "domain_issues": domain_issues,
        "tested_window_times_utc": [row.time.isoformat() for row in latest],
    }


def _source_classification(text: str) -> str:
    if re.search(r"best[ _-]?track|historical|ibtracs|hurdat", text, re.I):
        return "historical_best_track"
    if re.search(r"analy[sz]|reanalysis", text, re.I):
        return "analyzed"
    return "observed"


def _agent_json_rows(raw_body: str) -> list[dict]:
    """Read only structured final result JSON; do not scrape agent prose/snippets."""
    try:
        response = json.loads(raw_body)
    except json.JSONDecodeError:
        return []
    result = response.get("result") if isinstance(response, dict) else None
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return []
    observations = result.get("observations") if isinstance(result, dict) else None
    return [row for row in observations if isinstance(row, dict)] if isinstance(observations, list) else []


def _agent_observations(rows: list[dict], source_url: str, name: str, source_text: str) -> tuple[list[object], list[str]]:
    normalized: list[object] = []
    issues: list[str] = []
    classification = _source_classification(source_text)
    for index, row in enumerate(rows):
        try:
            timestamp = datetime.fromisoformat(str(row.get("datetime_utc", "")).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("timestamp lacks UTC offset")
            timestamp = timestamp.astimezone(timezone.utc)
            lat, lon = float(row["lat"]), float(row["lon"])
            wind_value = row.get("wind_kt")
            if wind_value is None:
                raise ValueError("wind_kt missing; the existing inference contract requires numeric wind")
            wind = float(wind_value)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= wind <= 250):
                raise ValueError("latitude, longitude, or wind outside allowed value ranges")
            normalized.append(SimpleNamespace(
                time=timestamp, lat=lat, lon=lon, wind=wind,
                classification=classification, source_url=source_url,
                cyclone_name=name, cyclone_identifier=name,
                basin=("Arabian Sea" if 45 <= lon < 76.5 else "Bay of Bengal" if 77.5 < lon <= 100 and 0 <= lat <= 30 else None),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(f"Agent row {index + 1} excluded: {exc}.")
    return normalized, issues


def run_search(client: httpx.Client, key: str, query: str, cache_name: str) -> tuple[dict, list[dict]]:
    params = {"query": query, "purpose": "Find cyclone historical best-track observations with timestamp, latitude, longitude, and wind speed.",
              "location": "IN", "language": "en", "include_domains": DOMAINS}
    request = {"method": "GET", "url": SEARCH_URL, "params": params}
    try:
        response = client.get(SEARCH_URL, params=params, headers={"X-API-Key": key})
        _save_raw(cache_name, _response_record(response, request))
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError("Successful Search response did not contain results[]")
        return {"query": query, "status": "ok", "result_count": len(body["results"]),
                "raw_response": response.text if not body["results"] else None,
                "fixture": f"tests/fixtures/{cache_name}"}, body["results"]
    except Exception as exc:  # Keep a per-query record so the report shows the failure category.
        failure = _error_record(exc, request, response.text if "response" in locals() and isinstance(response, httpx.Response) else None)
        _save_raw(cache_name, failure)
        category = failure["error_category"]
        if category == "authentication":
            diagnosis = "authentication rejected (401/403)"
        elif category == "HTTP 400":
            diagnosis = "request schema/parameters rejected"
        elif category.startswith("HTTP"):
            diagnosis = f"endpoint/service response: {category}"
        elif category in {"timeout", "connection", "connection/TLS"}:
            diagnosis = category
        else:
            diagnosis = "response parsing/schema"
        return {"query": query, "status": "error", "error": failure["error"], "diagnosis": diagnosis,
                "fixture": f"tests/fixtures/{cache_name}"}, []


def run_fetch(client: httpx.Client, key: str, urls: list[str], query: str, cache_name: str) -> tuple[dict, dict]:
    request = {"method": "POST", "url": FETCH_URL,
               "json": {"urls": urls, "format": "markdown", "ttl": 0, "per_url_timeout_ms": 45000,
                        "purpose": f"Fetch historical best track observations for {query}; extract source content."}}
    try:
        response = client.post(FETCH_URL, json=request["json"], headers={"X-API-Key": key}, timeout=HTTP_TIMEOUT)
        _save_raw(cache_name, _response_record(response, request))
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError("Successful Fetch response did not contain results[]")
        errors = body.get("errors", []) if isinstance(body.get("errors"), list) else []
        return {"status": "ok", "fixture": f"tests/fixtures/{cache_name}", "errors": errors}, body
    except Exception as exc:
        failure = _error_record(exc, request, response.text if "response" in locals() and isinstance(response, httpx.Response) else None)
        _save_raw(cache_name, failure)
        return {"status": "error", "error": failure["error"], "error_category": failure["error_category"],
                "fixture": f"tests/fixtures/{cache_name}"}, {"results": [], "errors": []}


def run_agent(client: httpx.Client, key: str, url: str, cyclone: str, year: int, cache_name: str) -> tuple[dict, list[dict]]:
    goal = (
        f"Find the historical best-track table for Cyclone {cyclone} ({year}) on this page. "
        "Return ONLY JSON with shape {\"observations\":[{\"datetime_utc\":\"YYYY-MM-DDTHH:MM:SSZ\","
        "\"lat\":number,\"lon\":number,\"wind_kt\":number|null,\"category\":string|null}]}. "
        "Include only rows visibly present in the page, preserve the page's units (convert wind to knots only if the page labels units), "
        "keep chronological order, do not infer missing rows, and return an empty observations array if no such table exists."
    )
    schema = {"type": "object", "properties": {"observations": {"type": "array", "items": {
        "type": "object", "properties": {"datetime_utc": {"type": "string"}, "lat": {"type": "number"},
        "lon": {"type": "number"}, "wind_kt": {"type": "number", "nullable": True}, "category": {"type": "string", "nullable": True}},
        "required": ["datetime_utc", "lat", "lon", "wind_kt", "category"]}}}, "required": ["observations"]}
    request = {"method": "POST", "url": AGENT_URL, "json": {"url": url, "goal": goal, "output_schema": schema}}
    try:
        response = client.post(AGENT_URL, json=request["json"], headers={"X-API-Key": key}, timeout=HTTP_TIMEOUT)
        raw = _response_record(response, request)
        _save_raw(cache_name, raw)
        response.raise_for_status()
        rows = _agent_json_rows(response.text)
        metadata = json.loads(response.text)
        status = metadata.get("status", "ok") if isinstance(metadata, dict) else "ok"
        if status == "FAILED":
            return {"url": url, "status": "failed", "row_count": len(rows), "fixture": f"tests/fixtures/{cache_name}",
                    "run_id": _safe_run_id(response.text), "response_error_body": json.dumps(metadata.get("error"), ensure_ascii=False)}, rows
        return {"url": url, "status": "ok", "row_count": len(rows), "fixture": f"tests/fixtures/{cache_name}",
                "run_id": _safe_run_id(response.text)}, rows
    except Exception as exc:
        failure = _error_record(exc, request, response.text if "response" in locals() and isinstance(response, httpx.Response) else None)
        _save_raw(cache_name, failure)
        return {"url": url, "status": "error", "error": failure["error"], "error_category": failure["error_category"],
                "http_status": failure.get("http_status"), "response_error_body": failure.get("raw_body"),
                "fixture": f"tests/fixtures/{cache_name}"}, []


def _safe_run_id(raw: str) -> str | None:
    try:
        value = json.loads(raw)
        run_id = value.get("run_id") if isinstance(value, dict) else None
        return run_id if isinstance(run_id, str) else None
    except json.JSONDecodeError:
        return None


def _run_cyclone(client: httpx.Client, key: str, name: str, year: int) -> dict:
    slug = _slug(f"{name}_{year}")
    search_reports: list[dict] = []
    results: list[dict] = []
    for index, template in enumerate(QUERY_TEMPLATES, start=1):
        query = template.format(name=name, year=year)
        report, rows = run_search(client, key, query, f"{slug}_search_{index}.json")
        search_reports.append(report)
        results.extend(rows)

    candidates = _safe_candidates(results, name, year)
    to_fetch = [item for item in candidates if item["approved_for_fetch"]][:MAX_FETCH_URLS]
    fetched_report: dict = {"status": "not run", "errors": []}
    fetched_rows: list[dict] = []
    parsed_by_url: dict[str, list[object]] = {}
    text_by_url: dict[str, str] = {}
    if to_fetch:
        urls = [item["url"] for item in to_fetch]
        fetch_query = f"{name} {year}"
        fetch_report, fetch_body = run_fetch(client, key, urls, fetch_query, f"{slug}_fetch.json")
        fetched_report = {"status": fetch_report["status"], "fixture": fetch_report.get("fixture"),
                          "errors": fetch_report.get("errors", []), "error": fetch_report.get("error"),
                          "error_category": fetch_report.get("error_category"), "fetched_urls": urls}
        fetched_rows = fetch_body.get("results", [])
        fetched_at = datetime.now(timezone.utc)
        for item in fetched_rows:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            text = item.get("text") if isinstance(item.get("text"), str) else ""
            title = item.get("title") if isinstance(item.get("title"), str) else None
            url = item["url"]
            text_by_url[url] = text
            issues: list[str] = []
            rows = parse_observations(text, url, title, fetched_at, query=name, issues=issues)
            parsed_by_url[url] = rows
            item["smoke_extraction"] = {"rows": len(rows), "notes": issues}
        # Save a second cache artifact with exact extracted response text and parser counts.
        _save_raw(f"{slug}_fetch_parsed.json", {"fetch_raw_fixture": f"tests/fixtures/{slug}_fetch.json",
                                                   "results": fetched_rows, "errors": fetch_body.get("errors", [])})

    best_fetch_count = max((len(rows) for rows in parsed_by_url.values()), default=0)
    use_agent = best_fetch_count < 9 and fetched_report["status"] == "ok"
    agent_reports: list[dict] = []
    agent_counts: dict[str, int] = {}
    agent_validation: dict[str, dict] = {}
    if use_agent:
        # Run only for fetched URLs; at most two runs per cyclone, as requested.
        agent_targets = [item["url"] for item in to_fetch if item["url"] in parsed_by_url][:MAX_AGENT_RUNS_PER_CYCLONE]
        for index, url in enumerate(agent_targets, start=1):
            report, raw_rows = run_agent(client, key, url, name, year, f"{slug}_agent_{index}.json")
            safe_rows, row_issues = _agent_observations(raw_rows, url, name, text_by_url.get(url, ""))
            agent_counts[url] = len(safe_rows)
            agent_validation[url] = _window_results(safe_rows, name, text_by_url.get(url, "")) if safe_rows else {
                "row_count": 0, "spacing": "not enough rows", "has_nine_consecutive_3h_rows": False,
                "would_qualify_after_6h_to_3h_interpolation_spacing_only": False,
                "existing_validator_passes": False, "domain_check_passes": False,
                "validator_issues": row_issues or ["Agent returned no structured observation rows; none promoted to validated data."],
                "domain_issues": [],
            }
            report["accepted_rows_for_validator"] = len(safe_rows)
            report["row_validation_notes"] = row_issues
            agent_reports.append(report)

    source_reports: list[dict] = []
    for item in to_fetch:
        url = item["url"]
        rows = parsed_by_url.get(url, [])
        source_reports.append({"url": url, "title": item["title"], "fetch_status": "fetched" if any(row.get("url") == url for row in fetched_rows if isinstance(row, dict)) else "not returned",
                               "fetch_rows": _window_results(rows, name, text_by_url.get(url, ""))})
    total_parser_rows = sum(len(rows) for rows in parsed_by_url.values())
    max_agent_rows = max(agent_counts.values(), default=0)
    best_agent = max(agent_validation.values(), key=lambda value: value.get("row_count", 0), default=None)
    return {
        "cyclone": f"{name} {year}",
        "search": search_reports,
        "zero_result_diagnosis": ("Search succeeded with zero results for both queries; query coverage/result availability issue, not auth or endpoint." if all(item.get("status") == "ok" and item.get("result_count") == 0 for item in search_reports) else None),
        "candidates": candidates,
        "fetched_urls": fetched_report.get("fetched_urls", []),
        "fetch": fetched_report,
        "sources": source_reports,
        "fetch_total_rows_across_sources_not_combined_for_validation": total_parser_rows,
        "agent_fallback_ran": use_agent,
        "agent_runs": agent_reports,
        "agent_rows_per_source": agent_counts,
        "agent_best_source_check": best_agent,
        "agent_run_cap": MAX_AGENT_RUNS_PER_CYCLONE,
        "agent_note": "Agent JSON is model-generated evidence and only diagnostics are reported; smoke test never runs the LSTM.",
        "credit_note": "This script does not query usage endpoints or wallet balances. Search and Fetch are within their documented daily free allowances when quota remains; Agent execution may consume credits. Check the TinyFish dashboard for exact wallet debits.",
        "fixtures_dir": "tests/fixtures",
    }


def _render_report(results: list[dict], missing_key: bool, stopped_on_network: bool) -> str:
    lines = [
        "# TinyFish live-data smoke report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This diagnostic performs TinyFish Search, Fetch, the existing `parse_observations` parser, and a capped Agent fallback only when fetched tables have fewer than nine usable rows. It does not call IMD, interpolate observations, or run an LSTM. Search snippets and Agent output are not treated as verified observations.",
        "",
    ]
    if missing_key:
        lines.extend(["**Live checks not run:** `TINYFISH_API_KEY` is missing from backend settings/environment. No API requests were made.", ""])
    if stopped_on_network:
        lines.extend(["**Live checks blocked:** the backend could not reach TinyFish. See the per-query errors below; no results were invented.", ""])
    for result in results:
        lines.extend([f"## {result['cyclone']}", "", "### Search queries", ""])
        for item in result.get("search", []):
            lines.append(f"- `{item['query']}` — {item.get('result_count', 'not available')} results; status: {item['status']}; fixture: `{item.get('fixture', 'none')}`")
            if item.get("diagnosis"):
                lines.append(f"  - Failure category: {item['diagnosis']} — {item.get('error', '')}")
        if result.get("zero_result_diagnosis"):
            lines.append(f"- Diagnosis: {result['zero_result_diagnosis']}")
        for item in result.get("search", []):
            if item.get("raw_response"):
                lines.append(f"  - Raw zero-result response: `{item['raw_response'][:1600]}`")
        lines.extend(["", "### Candidates and Fetch", ""])
        if result.get("candidates"):
            for candidate in result["candidates"]:
                lines.append(f"- [{candidate['title'] or candidate['host']}]({candidate['url']}) — approved for Fetch: {candidate['approved_for_fetch']}; fetched: {candidate['url'] in result.get('fetched_urls', [])}; snippet unverified: `{candidate['snippet_unverified'][:180]}`")
        else:
            lines.append("- No candidate URLs returned.")
        fetch = result.get("fetch", {})
        lines.extend([f"- Fetch status: {fetch.get('status')}; cache: `{fetch.get('fixture', 'none')}`; per-URL errors: {json.dumps(fetch.get('errors', []), ensure_ascii=False)}"])
        if fetch.get("error"):
            lines.append(f"- Fetch failure category: {fetch.get('error_category')}: {fetch['error']}")
        lines.extend(["", "### Rows, spacing, validator, and training domain", ""])
        if result.get("sources"):
            for source in result["sources"]:
                check = source["fetch_rows"]
                lines.append(f"- **{source['url']}**: Fetch status {source['fetch_status']}; parser rows {check['row_count']}; spacing **{check['spacing']}**; 9 consecutive 3-hour rows: **{check['has_nine_consecutive_3h_rows']}**; validator pass: **{check['validator_passes']}**; training-domain pass: **{check['domain_passes']}**; spacing-only 6h interpolation possibility: **{check['would_qualify_after_6h_to_3h_interpolation_spacing_only']}**.")
                if check.get("gaps_hours"):
                    lines.append(f"  - Gaps (hours): `{check['gaps_hours']}`")
                for issue in check.get("validator_issues", []) + check.get("domain_issues", []):
                    lines.append(f"  - Check: {issue}")
        else:
            lines.append("- No fetched source rows to validate.")
        lines.extend(["", "### Agent fallback", ""])
        lines.append(f"- Ran: **{result.get('agent_fallback_ran')}**; max runs per cyclone: {result.get('agent_run_cap')}; exact credit amount: not exposed by the run response.")
        if result.get("agent_runs"):
            for agent in result["agent_runs"]:
                lines.append(f"- {agent['url']}: status {agent['status']}; structured rows {agent.get('row_count', 0)}; rows accepted for validation {agent.get('accepted_rows_for_validator', 0)}; fixture `{agent['fixture']}`; run ID `{agent.get('run_id')}`.")
                if agent.get("error"):
                    lines.append(f"  - Agent failure ({agent.get('error_category')}): {agent['error']}")
                if agent.get("response_error_body"):
                    lines.append(f"  - Agent response error: `{str(agent['response_error_body'])[:500]}`")
                for issue in agent.get("row_validation_notes", []):
                    lines.append(f"  - Row excluded: {issue}")
                check = result.get("agent_best_source_check") if result.get("agent_best_source_check") and result.get("agent_best_source_check", {}).get("row_count") == agent.get("accepted_rows_for_validator") else None
                if check:
                    lines.append(f"  - Spacing {check.get('spacing')}; 9 consecutive 3h: {check.get('has_nine_consecutive_3h_rows')}; validator pass: {check.get('existing_validator_passes')}; domain pass: {check.get('domain_check_passes')}; spacing-only interpolation possibility: {check.get('would_qualify_after_6h_to_3h_interpolation_spacing_only')}.")
        else:
            lines.append("- Not run (Fetch source produced at least nine parser rows, Fetch failed/no approved URLs were available, or no key/network).")
        lines.extend(["", "### Provenance and limits", "", result["agent_note"], result["credit_note"], ""])
    if not results:
        lines.extend(["## Run status", "", "No cyclone requests were attempted.", ""])
    lines.extend(["## Usage", "", "Run with `backend/.venv/Scripts/python.exe scripts/tinyfish_smoke_test.py`. Raw HTTP response bodies (with no API-key headers) and request metadata are cached under `tests/fixtures/`.", ""])
    return "\n".join(lines)


def main() -> int:
    settings = get_settings()
    key = settings.tinyfish_api_key
    if not key:
        results = [{"cyclone": f"{name} {year}", "search": [], "candidates": [], "fetched_urls": [],
                    "fetch": {"status": "not run", "errors": []}, "sources": [], "agent_fallback_ran": False,
                    "agent_runs": [], "agent_run_cap": MAX_AGENT_RUNS_PER_CYCLONE,
                    "agent_note": "No API requests made.", "credit_note": "No API requests or credit usage.",
                    "fixtures_dir": "tests/fixtures"} for name, year in CYCLONES]
        FIXTURES.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(_render_report(results, missing_key=True, stopped_on_network=False), encoding="utf-8")
        print("TINYFISH_API_KEY is not configured; live calls were skipped. Wrote TINYFISH_SMOKE_REPORT.md.")
        return 2

    all_results: list[dict] = []
    stopped_on_network = False
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        for name, year in CYCLONES:
            result = _run_cyclone(client, key, name, year)
            all_results.append(result)
            # Stop after a repeated transport failure; do not hammer an unreachable service.
            errors = [item for item in result.get("search", []) if item.get("status") == "error"]
            if len(errors) == len(QUERY_TEMPLATES) and errors and all(item.get("diagnosis") in {"connection", "connection/TLS", "timeout"} for item in errors):
                stopped_on_network = True
                for remaining_name, remaining_year in CYCLONES[len(all_results):]:
                    remaining_slug = _slug(f"{remaining_name}_{remaining_year}")
                    all_results.append({
                        "cyclone": f"{remaining_name} {remaining_year}",
                        "search": [{"query": template.format(name=remaining_name, year=remaining_year),
                                    "status": "not attempted (TinyFish unreachable)", "result_count": "not attempted",
                                    "diagnosis": "not sent after DNS/connection failure for first cyclone"}
                                   for template in QUERY_TEMPLATES],
                        "candidates": [], "fetched_urls": [],
                        "fetch": {"status": "not attempted (TinyFish unreachable)", "errors": []},
                        "sources": [], "agent_fallback_ran": False, "agent_runs": [],
                        "agent_run_cap": MAX_AGENT_RUNS_PER_CYCLONE,
                        "agent_note": "Not attempted because the TinyFish Search endpoint was unreachable.",
                        "credit_note": "No API request or credit usage for this cyclone.",
                        "fixtures_dir": "tests/fixtures",
                    })
                break
    REPORT.write_text(_render_report(all_results, missing_key=False, stopped_on_network=stopped_on_network), encoding="utf-8")
    total_search = sum(item.get("result_count", 0) for cyclone in all_results for item in cyclone.get("search", []))
    total_fetch_rows = sum(cyclone.get("fetch_total_rows_across_sources_not_combined_for_validation", 0) for cyclone in all_results)
    total_agent_runs = sum(len(cyclone.get("agent_runs", [])) for cyclone in all_results)
    print(f"Wrote TINYFISH_SMOKE_REPORT.md; cyclones attempted={len(all_results)}, Search results={total_search}, Fetch parser rows (not combined)={total_fetch_rows}, Agent runs={total_agent_runs}.")
    return 1 if stopped_on_network else 0


if __name__ == "__main__":
    raise SystemExit(main())
