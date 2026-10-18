"""TinyFish fetch and conservative parsing of explicitly tabular observations."""
from __future__ import annotations

import ipaddress
import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.schemas import ExtractedObservation, SourceFetchRequest, SourceFetchResponse, TrackPredictRequest
from app.services.lstm import LstmError, predict_track
from app.services.imd_cyclone import fetch_reference_observations

OFFICIAL_HOSTS = (
    "imd.gov.in", "noaa.gov", "nhc.noaa.gov", "metoffice.gov.uk", "bom.gov.au",
    "jma.go.jp", "weather.gov", "wmo.int", "ibtracs.unca.edu", "ncei.noaa.gov",
)
TIMEOUTS = (4.0, 5.0, 20.0, 5.0)


def validate_fetch_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only HTTPS URLs on approved public meteorological or scientific domains can be fetched.")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError("Private or non-public IP addresses cannot be fetched.")
        raise ValueError("Fetch requires an approved public domain name, not an IP address.")
    except ValueError as exc:
        if "cannot be fetched" in str(exc) or "approved public" in str(exc):
            raise
    if host in ("localhost",) or host.endswith((".localhost", ".local")):
        raise ValueError("Local network URLs cannot be fetched.")
    if not any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_HOSTS):
        raise ValueError("Choose a source hosted on an approved meteorological or scientific domain.")
    return value


def _cell_number(text: str) -> tuple[float, str]:
    value = text.strip().replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?\s*[NSEW]?", value, re.I)
    if not match:
        raise ValueError("not numeric")
    token = match.group().strip()
    number = float(re.match(r"[-+]?\d+(?:\.\d+)?", token).group())  # type: ignore[union-attr]
    suffix = token[-1:].upper()
    if suffix in ("S", "W"):
        number = -abs(number)
    elif suffix in ("N", "E"):
        number = abs(number)
    return number, token


def _observation_time(date_text: str, time_text: str | None, assume_utc: bool = False) -> datetime:
    raw = date_text.strip()
    if time_text:
        raw += " " + time_text.strip()
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ("%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%Y%m%d %H%M", "%Y-%m-%d %H%M", "%Y-%m-%d %H:%M", "%d %b %Y %H:%M"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            raise ValueError("unrecognized timestamp")
    if dt.tzinfo is None:
        # Bulletins commonly report UTC but must say so explicitly to avoid guessing.
        if not assume_utc and not re.search(r"\bUTC\b|\bGMT\b|Z$", raw, re.I):
            raise ValueError("timestamp has no UTC offset")
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _split_table(line: str) -> list[str]:
    return [part.strip().strip("`") for part in line.strip().strip("|").split("|")]


class _HtmlTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if len(self._table) > 1:
                self.tables.append(self._table)
            self._table = None


def _basin_from_text(text: str) -> str | None:
    normalized = text.lower()
    found = []
    if re.search(r"\bbay of bengal\b|\b(?:basin\s*[:=]?\s*)bob\b", normalized):
        found.append("Bay of Bengal")
    if re.search(r"\barabian sea\b|\b(?:basin\s*[:=]?\s*)arb\b", normalized):
        found.append("Arabian Sea")
    return found[0] if len(found) == 1 else None


def _basin_from_coordinates(lat: float, lon: float) -> str | None:
    if not 0 <= lat <= 30:
        return None
    if 45 <= lon < 76.5:
        return "Arabian Sea"
    if 77.5 < lon <= 100:
        return "Bay of Bengal"
    return None


def _identity_terms(query: str) -> list[str]:
    ignored = {"cyclone", "tropical", "storm", "typhoon", "hurricane", "basin", "advisory", "observed", "track", "data", "best", "history", "historical"}
    return [t.lower() for t in re.findall(r"[a-z0-9]+", query) if len(t) > 2 and t.lower() not in ignored]


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _record_observation(headers: list[str], values: list[str], context: str, source_url: str,
                        title: str | None, query: str, retrieved_at: datetime,
                        issues: list[str], source_group: str | None = None) -> ExtractedObservation | None:
    normalized = [_header_key(value) for value in headers]
    def col(*aliases: str) -> int | None:
        keys = set(aliases)
        return next((i for i, value in enumerate(normalized) if value in keys or any((key == "wind" and "wind" in value) or (len(key) > 4 and key in value) for key in keys)), None)
    date_col = col("date", "observationdate", "validdate", "dateutc")
    clock_col = col("utctime", "timeutc", "observationtimeutc", "time")
    time_col = col("datetime", "validtime", "timestamp", "datetimeutc", "dateandtime", "observationtime", "isotime")
    if date_col is not None and clock_col is not None:
        time_col = date_col
    elif time_col is None:
        time_col = date_col if date_col is not None else clock_col
    lat_col, lon_col = col("latitude", "lat", "centerlatitude", "centrelatitude"), col("longitude", "lon", "long", "centerlongitude", "centrelongitude")
    wind_col = col("newdelhiwind", "wind", "vmax", "msw", "maximumsustainedwind", "wmowind", "usawind", "cmawind", "jmawind", "hkowind")
    if lat_col is None or lon_col is None:
        return None
    if time_col is None:
        issues.append("Track data has latitude and longitude but no supported observation timestamp column.")
        return None
    if wind_col is None:
        issues.append("Track data has time and coordinates but no supported wind-speed column.")
        return None
    context_l = context.lower()
    if re.search(r"\bforecast\b|\bforecast positions?\b", context_l):
        return None
    if re.search(r"best[ _-]?track|historical|ibtracs|hurdat|best track archive", context_l):
        classification = "historical_best_track"
        source_type = "historical_best_track"
    elif re.search(r"analys|analyz|reanalysis", context_l):
        classification = "analyzed"
        source_type = "meteorological_bulletin"
    elif re.search(r"observed|observation|best estimate|track fixes|storm positions", context_l):
        classification = "observed"
        source_type = "meteorological_bulletin" if "bulletin" in context_l or "advisory" in context_l else "public_web"
    else:
        issues.append("Found a track-shaped table without context identifying it as observed, analyzed, or historical best track.")
        return None
    if max(time_col, lat_col, lon_col, wind_col) >= len(values):
        issues.append("A source track row is missing one or more required timestamp, coordinate, or wind fields.")
        return None
    unit_header = headers[wind_col].lower()
    unit_context = context_l
    if any(x in unit_header for x in ("kt", "knot")):
        unit = "kt"
    elif any(x in unit_header for x in ("km/h", "kmph", "km h", "km per hour")) or re.search(r"\bkmph\b|\bkm/?h\b", unit_context):
        unit = "km/h"
    elif any(x in unit_header for x in ("m/s", "m s")) or re.search(r"\bm/s\b|\bmps\b", unit_context):
        unit = "m/s"
    elif re.search(r"\bkt\b|\bknots?\b", unit_context) or ((urlparse(source_url).hostname or "").lower().endswith("ncei.noaa.gov") and normalized[wind_col] in {"wmowind", "usawind", "cmawind", "jmawind", "hkowind"}):
        unit = "kt"
    else:
        issues.append("Wind speed was found without an explicit supported unit (kt, km/h, or m/s).")
        return None
    row_name_col = col("cyclonename", "stormname", "name")
    row_id_col = col("stormid", "cycloneid", "sid", "stormidentifier", "cycloneidentifier")
    row_name = values[row_name_col].strip() if row_name_col is not None and row_name_col < len(values) else ""
    row_id = values[row_id_col].strip() if row_id_col is not None and row_id_col < len(values) else ""
    row_identity = row_id or row_name or query
    query_terms = _identity_terms(query)
    if row_name and (not query_terms or not all(term in row_name.lower() for term in query_terms)):
        issues.append("A fetched track row identifies a different cyclone and was excluded.")
        return None
    try:
        date_value = values[time_col]
        time_value = values[clock_col] if clock_col is not None and clock_col != time_col and clock_col < len(values) else None
        assume_utc = "utc" in headers[time_col].lower() or (normalized[time_col] == "isotime" and "ibtracs" in context_l) or (clock_col is not None and "utc" in headers[clock_col].lower()) or bool(re.search(r"\bUTC\b|\bGMT\b", context_l))
        timestamp = _observation_time(date_value, time_value, assume_utc=assume_utc)
        lat, _ = _cell_number(values[lat_col])
        lon, _ = _cell_number(values[lon_col])
        wind, original = _cell_number(values[wind_col])
        factor = {"kt": 1.0, "km/h": 0.5399568, "m/s": 1.9438445}[unit]
        wind *= factor
        evidence = json.dumps(dict(zip(headers, values)), ensure_ascii=False)
        source_host = (urlparse(source_url).hostname or "").lower()
        if source_host.endswith("imd.gov.in") and urlparse(source_url).path.rstrip("/").endswith("/api/v1/cyclone_track"):
            source_type = "imd_operational"
        elif classification == "historical_best_track":
            source_type = "historical_best_track"
        elif source_host.endswith("imd.gov.in"):
            source_type = "meteorological_bulletin"
        return ExtractedObservation(
            time=timestamp, lat=lat, lon=lon, wind=wind, wind_original=f"{original} {unit}", units="kt",
            cyclone_identifier=row_identity or query, cyclone_name=row_name or query,
            source_group=source_group,
            classification=classification, source_type=source_type,
            basin=_basin_from_text(context) or _basin_from_coordinates(lat, lon), source_url=source_url, source_title=title,
            original_evidence=evidence[:2000],
            flags=[f"Wind converted from {unit} to knots"] if factor != 1 else [],
        )
    except (ValueError, IndexError, TypeError) as exc:
        issues.append(f"A track row could not be normalized ({str(exc)[:100]})."); return None


def parse_observations(text: str, source_url: str, title: str | None, retrieved_at: datetime,
                       query: str = "", issues: list[str] | None = None,
                       preserve_duplicates: bool = False) -> list[ExtractedObservation]:
    """Extract direct rows from Markdown/HTML tables, CSV, and accessible JSON."""
    issues = issues if issues is not None else []
    tables: list[tuple[list[str], list[list[str]], str]] = []
    lines = text.splitlines()
    context = title or ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#"):
            context = " ".join(lines[i:i + 3])
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"\s*\|?[\s:|\-]+\|?\s*$", lines[i + 1]):
            headers = _split_table(line)
            body: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(_split_table(lines[i])); i += 1
            tables.append((headers, body, context + " " + " ".join(lines[max(0, i-len(body)-4):i-len(body)])))
            continue
        i += 1
    html = _HtmlTables()
    try:
        html.feed(text)
        tables.extend((table[0], table[1:], f"{title or ''} {text}") for table in html.tables if table)
    except Exception:
        pass
    # CSV/TSV attachments are returned as text by Fetch. Use a delimited table only when its header is track-shaped.
    try:
        sample_lines = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
        if len(sample_lines) >= 2:
            dialect = csv.Sniffer().sniff("\n".join(sample_lines[:8]), delimiters=",;\t")
            parsed = list(csv.reader(io.StringIO("\n".join(sample_lines)), dialect))
            if parsed and any(_header_key(h) in {"latitude", "lat"} for h in parsed[0]):
                tables.append((parsed[0], parsed[1:], f"{title or ''} {text}"))
    except csv.Error:
        pass
    # TinyFish returns JSON documents as raw JSON text. Walk only lists of row objects.
    try:
        payload = json.loads(text)
        def walk(value, path=""):
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                keys = list(value[0].keys())
                if any(_header_key(k) in {"latitude", "lat"} for k in keys):
                    tables.append((keys, [[str(row.get(k, "")) for k in keys] for row in value], f"{title or ''} {path}"))
                else:
                    for item in value: walk(item, path)
            elif isinstance(value, dict):
                for key, item in value.items(): walk(item, f"{path} {key}")
        walk(payload)
    except (ValueError, TypeError):
        pass

    # PDF text extraction may flatten a table. Accept only rows with an explicit
    # timezone-bearing ISO timestamp, two coordinate columns, and a unit declared nearby.
    plain_row = re.compile(
        r"^\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2}))\s+"
        r"([-+]?\d+(?:\.\d+)?[NS]?)\s+([-+]?\d+(?:\.\d+)?[EW]?)\s+([-+]?\d+(?:\.\d+)?)\s*$", re.I
    )
    for line_number, line in enumerate(lines):
        match = plain_row.match(line)
        if not match:
            continue
        context_lines = lines[:1] + lines[max(1, line_number - 8):line_number]
        local_context = f"{title or ''} " + " ".join(context_lines)
        lower_context = local_context.lower()
        if not re.search(r"observed|observation|best[ _-]?track|historical|analy[sz]", lower_context) or "forecast" in lower_context:
            continue
        if re.search(r"\bkm/?h\b|\bkmph\b", lower_context):
            unit_name = "km/h"
        elif re.search(r"\bm/s\b|\bmps\b", lower_context):
            unit_name = "m/s"
        elif re.search(r"\bkt\b|\bknots?\b", lower_context):
            unit_name = "kt"
        else:
            issues.append("Flattened track rows found, but no explicit wind-speed unit was declared nearby.")
            continue
        tables.append((["timestamp UTC", "latitude", "longitude", f"wind ({unit_name})"], [list(match.groups())], local_context))

    parsed_rows: list[ExtractedObservation] = []
    seen: set[tuple[datetime, float, float, str, str | None]] = set()
    for table_index, (headers, table_rows, table_context) in enumerate(tables):
        for row in table_rows:
            group_id = f"{source_url}#table-{table_index + 1}"
            observation = _record_observation(headers, row, table_context, source_url, title, query, retrieved_at, issues, group_id)
            if observation:
                key = (observation.time, observation.lat, observation.lon, observation.source_url, observation.source_group)
                if preserve_duplicates or key not in seen:
                    seen.add(key)
                    parsed_rows.append(observation)
    return sorted(parsed_rows, key=lambda row: row.time)


def _validation(observations: list[ExtractedObservation], now: datetime, query: str | None = None,
                source_text_by_url: dict[str, str] | None = None) -> list[str]:
    issues: list[str] = []
    if len(observations) < 9:
        issues.append(f"Need 9 actual fixes (one predecessor plus eight 3-hour model steps); found {len(observations)}.")
    ordered = sorted(observations, key=lambda x: x.time)
    if len({x.time for x in ordered}) != len(ordered):
        issues.append("Duplicate observation timestamps were found.")
    if any(x.classification not in ("observed", "analyzed", "historical_best_track") for x in ordered):
        issues.append("Forecast or unclassified positions cannot be model inputs.")
    basins = {x.basin for x in ordered}
    if None in basins or len(basins) != 1:
        issues.append("Source content must identify one consistent trained basin: Bay of Bengal or Arabian Sea.")
    if query:
        identity_terms = _identity_terms(query)
        source_text_by_url = source_text_by_url or {}
        if not identity_terms:
            issues.append("Enter a specific cyclone name or identifier before using observations for inference.")
        elif not any(all(term in source_text_by_url.get(url, "") for term in identity_terms)
                     for url in {x.source_url for x in ordered}):
            issues.append("Fetched source content does not confirm the requested cyclone name or identifier.")
        identifiers = {"".join(re.findall(r"[a-z0-9]+", (row.cyclone_identifier or "").lower())) for row in ordered}
        identifiers.discard("")
        if len(identifiers) > 1:
            issues.append("The candidate sequence contains more than one cyclone identifier; records were not combined for inference.")
    for previous, current in zip(ordered, ordered[1:]):
        hours = (current.time - previous.time).total_seconds() / 3600
        if abs(hours - 3) > 0.15:
            issues.append(f"Observations must be exactly 3 hours apart; found a {hours:g}-hour gap.")
            break
    if ordered:
        latest = ordered[-1]
        historical = all(x.classification == "historical_best_track" for x in ordered)
        if not historical and (now - latest.time).total_seconds() > 12 * 3600:
            issues.append("Latest fix is more than 12 hours old; this live forecast workflow requires recent observations.")
        if (latest.time - now).total_seconds() > 30 * 60:
            issues.append("Latest observation timestamp is in the future.")
        if any(not (-40 <= x.lat <= 40 and 30 <= x.lon <= 130) for x in ordered):
            issues.append("Track is outside the LSTM training envelope (latitude −40…40, longitude 30…130).")
    return issues


def _compare_observations(groups: list[list[ExtractedObservation]]) -> list[dict]:
    """Compare exact-time reports; never average or merge conflicting source rows."""
    by_time: dict[datetime, list[ExtractedObservation]] = {}
    for group in groups:
        for row in group:
            by_time.setdefault(row.time, []).append(row)
    conflicts: list[dict] = []
    for timestamp, rows in by_time.items():
        for i, first in enumerate(rows):
            for second in rows[i + 1:]:
                if first.source_url == second.source_url and first.source_group == second.source_group:
                    continue
                first_name = "".join(re.findall(r"[a-z0-9]+", (first.cyclone_name or "").lower()))
                second_name = "".join(re.findall(r"[a-z0-9]+", (second.cyclone_name or "").lower()))
                if not first_name or not second_name or first_name != second_name:
                    continue
                lat1, lat2 = math.radians(first.lat), math.radians(second.lat)
                dlat = lat2 - lat1
                dlon = math.radians(second.lon - first.lon)
                hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                distance = 6371.0 * 2 * math.asin(min(1.0, math.sqrt(hav)))
                wind_delta = abs(first.wind - second.wind)
                if distance > 30 or wind_delta > 10:
                    conflicts.append({
                        "time": timestamp.isoformat(),
                        "source_a": first.source_url,
                        "source_b": second.source_url,
                        "position_difference_km": round(distance, 1),
                        "wind_difference_kt": round(wind_delta, 1),
                        "comparison_rule": "Flag when positions differ by over 30 km or wind differs by over 10 kt; records remain separate.",
                    })
    return conflicts


def fetch_and_forecast(payload: SourceFetchRequest) -> SourceFetchResponse:
    settings = get_settings()
    query = payload.storm_query.strip()
    if not settings.tinyfish_api_key:
        return SourceFetchResponse(status="unavailable", storm_query=query, message="TINYFISH_API_KEY is not configured on the backend.")
    try:
        urls = list(dict.fromkeys(validate_fetch_url(url) for url in payload.urls))
    except ValueError as exc:
        return SourceFetchResponse(status="error", storm_query=query, message=str(exc))
    if not urls:
        return SourceFetchResponse(status="error", storm_query=query, message="Select at least one source URL.")
    try:
        response = httpx.post(
            "https://api.fetch.tinyfish.ai",
            headers={"X-API-Key": settings.tinyfish_api_key},
            json={"urls": urls, "format": "markdown", "ttl": 0, "per_url_timeout_ms": 25000,
                  "purpose": f"Retrieve observed or historical best-track cyclone positions for {query}; exclude forecasts."},
            timeout=max(settings.tinyfish_timeout_seconds, 150.0),
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError("TinyFish Fetch returned an invalid response.")
    except httpx.TimeoutException:
        return SourceFetchResponse(status="error", storm_query=query, message="TinyFish Fetch timed out.")
    except httpx.ConnectError:
        return SourceFetchResponse(status="error", storm_query=query, message="TinyFish Fetch connection failed from the backend. Check outbound network or proxy access to api.fetch.tinyfish.ai.")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            msg = "TinyFish Fetch rejected the configured backend API key (HTTP 401)."
        elif status == 402:
            msg = "TinyFish Fetch credits or daily allowance are unavailable (HTTP 402)."
        elif status == 429:
            msg = "TinyFish Fetch rate limit reached (HTTP 429)."
        elif status == 400:
            msg = "TinyFish Fetch rejected the request schema or URLs (HTTP 400)."
        else:
            msg = f"TinyFish Fetch returned HTTP {status}."
        return SourceFetchResponse(status="error", storm_query=query, message=msg)
    except ValueError:
        return SourceFetchResponse(status="error", storm_query=query, message="TinyFish Fetch returned invalid JSON or a response without the documented results array.")
    except httpx.HTTPError:
        return SourceFetchResponse(status="error", storm_query=query, message="TinyFish Fetch failed during the HTTPS request. Check backend network and TLS configuration.")

    retrieved = datetime.now(timezone.utc)
    fetched: list[dict] = []
    source_text_by_url: dict[str, str] = {}
    candidate_groups: list[list[ExtractedObservation]] = []
    identity_terms = _identity_terms(query)
    errors = body.get("errors", []) if isinstance(body.get("errors"), list) else []
    for item in body["results"]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        url = item["url"]
        title = item.get("title") if isinstance(item.get("title"), str) else None
        text = item.get("text")
        meta = f"{title or ''} {url}".lower()
        if "ibtracs" in meta or "best track" in meta or "best-track" in meta or "historical" in meta:
            source_type = "historical_best_track"
        elif "bulletin" in meta or "advisory" in meta:
            source_type = "meteorological_bulletin"
        elif urlparse(url).path.rstrip("/").endswith("/api/v1/cyclone_track"):
            source_type = "imd_operational"
        else:
            source_type = "public_web"
        fetch_row = {"url": url, "final_url": item.get("final_url"), "title": title,
                     "retrieved_at": retrieved.isoformat(), "status": "fetched", "source_type": source_type,
                     "preview": text[:2400] if isinstance(text, str) else "",
                     "evidence": text[:50000] if isinstance(text, str) else ""}
        fetched.append(fetch_row)
        if not isinstance(text, str):
            fetch_row["status"] = "fetched · no extractable text"
            continue
        source_text_by_url[url] = text.lower()
        if not identity_terms or not all(term in text.lower() for term in identity_terms):
            fetch_row["status"] = "fetched · cyclone identity not confirmed"
            fetch_row["extraction_notes"] = ["Fetched content does not confirm the requested cyclone name or identifier."]
            continue
        parse_issues: list[str] = []
        group = parse_observations(text, url, title, retrieved, query=query, issues=parse_issues)
        fetch_row["extraction_notes"] = parse_issues[:20]
        fetch_row["status"] = f"fetched · {len(group)} direct observation rows parsed"
        if group:
            # A page may contain multiple storms (or reused names). Keep each provider identifier isolated.
            identities: dict[tuple[str, str], list[ExtractedObservation]] = {}
            for row in group:
                identities.setdefault((row.cyclone_identifier or query, row.source_group or row.source_url), []).append(row)
            candidate_groups.extend(identities.values())
    for item in errors:
        if isinstance(item, dict):
            fetched.append({"url": item.get("url", ""), "retrieved_at": retrieved.isoformat(), "status": "error",
                            "message": str(item.get("message") or item.get("error") or "Fetch failed")[:300]})

    # IMD remains the optional trusted reference for matching current observed fixes.
    imd_status, imd_rows = fetch_reference_observations(query)
    if imd_rows:
        fetched.append({"url": "https://api.imd.gov.in/api/v1/cyclone_track", "title": "IMD operational observed track", "source_type": "imd_operational",
                        "retrieved_at": retrieved.isoformat(), "status": "reference checked · observed rows only",
                        "preview": "IMD `data.observed` rows are used for comparison; `data.forecast` is excluded.",
                        "evidence": "\n".join(row.original_evidence or "" for row in imd_rows)[:50000]})
        candidate_groups.append(imd_rows)
    disagreements = _compare_observations(candidate_groups)
    all_observations = sorted([row for group in candidate_groups for row in group], key=lambda row: (row.time, row.source_url))

    valid_groups: list[tuple[list[ExtractedObservation], list[str]]] = []
    diagnostics: list[tuple[int, list[ExtractedObservation], list[str]]] = []
    for group in candidate_groups:
        source_urls = {row.source_url for row in group}
        source_text = {url: source_text_by_url.get(url, "") for url in source_urls}
        ordered = sorted(group, key=lambda row: row.time)
        model_window = ordered[-9:]
        has_source_identity_text = any(source_text.values())
        group_issues = _validation(model_window, retrieved, query if has_source_identity_text else None, source_text)
        diagnostics.append((len(model_window), model_window, group_issues))
        if not group_issues:
            valid_groups.append((model_window, group_issues))

    imd_valid = next((item for item in valid_groups if item[0] and item[0][0].source_type == "imd_operational"), None)
    # Prefer IMD only when its sequence overlaps fetched evidence at exact UTC times.
    web_times = {row.time for group in candidate_groups for row in group if row.source_type != "imd_operational"}
    if imd_valid and any(row.time in web_times for row in imd_valid[0]):
        selected_group = imd_valid[0]
        reference_note = "IMD supplied a complete compatible sequence and was selected as the trusted reference."
    else:
        web_valid = [item for item in valid_groups if item[0] and item[0][0].source_type != "imd_operational"]
        selected_group = max(web_valid, key=lambda item: len(item[0]))[0] if web_valid else []
        reference_note = "IMD was not available as a matching compatible reference; fetched source sequences were evaluated independently."

    if not selected_group:
        best = max(diagnostics, key=lambda item: item[0], default=(0, [], []))
        issues = best[2] or ["No single source contained enough compatible observations to form an LSTM input sequence."]
        if not candidate_groups:
            issues.append("No explicitly labeled, parseable observation rows were found in fetched content.")
        if imd_status != "available":
            issues.append(f"IMD reference status: {imd_status}.")
        if disagreements:
            issues.append(f"Found {len(disagreements)} timestamped cross-source disagreement(s); source rows were kept separate.")
        return SourceFetchResponse(status="insufficient_data", storm_query=query, retrieved_at=retrieved.isoformat(),
                                   sources=fetched, observations=all_observations, disagreements=disagreements,
                                   imd_reference_status=imd_status, validation=issues,
                                   message="No single source passed the existing LSTM input checks. No observations were combined and no forecast was run.")

    model_observations = sorted(selected_group, key=lambda row: row.time)[-9:]
    try:
        forecast = predict_track(TrackPredictRequest(observations=[
            {"time": row.time, "lat": row.lat, "lon": row.lon, "wind": row.wind}
            for row in model_observations
        ]))
    except LstmError as exc:
        return SourceFetchResponse(status="insufficient_data", storm_query=query, retrieved_at=retrieved.isoformat(),
                                   sources=fetched, observations=all_observations,
                                   model_observations=model_observations, disagreements=disagreements,
                                   imd_reference_status=imd_status,
                                   validation=[f"The selected sequence passed track validation, but the existing LSTM could not run: {exc}"],
                                   message="No forecast was returned because the existing model artifacts or preprocessing were unavailable.")
    historical = all(row.classification == "historical_best_track" for row in model_observations)
    validation = [
        "Nine actual UTC fixes from one source and one cyclone, spaced at 3-hour intervals.",
        "Wind values are normalized to knots; no missing rows were interpolated.",
        "Both LSTM horizons received the exact observations listed in model_observations.",
        reference_note,
    ]
    if historical:
        validation.append("Historical best-track replay; these observations are not live/current fixes.")
    if disagreements:
        validation.append(f"Warning: {len(disagreements)} cross-source discrepancy(ies) were found. The model input remains the single selected source sequence; no values were averaged.")
    return SourceFetchResponse(status="ok", storm_query=query, retrieved_at=retrieved.isoformat(), sources=fetched,
                               observations=all_observations, model_observations=model_observations,
                               disagreements=disagreements, imd_reference_status=imd_status, forecast=forecast,
                               validation=validation,
                               message="One source sequence passed evidence and model-contract checks and was sent to the existing 24 h / 48 h LSTMs.")
