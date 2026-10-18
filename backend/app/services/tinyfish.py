from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.schemas import SourceEvidence, SourceIntelligenceResponse


def retrieve_source_evidence(storm_query: str) -> SourceIntelligenceResponse:
    """Public-web search via TinyFish Search API. Not an ML prediction."""
    settings = get_settings()
    query = storm_query.strip()
    if not query:
        return SourceIntelligenceResponse(
            status="error",
            storm_query=query,
            message="Provide a storm name, basin, or advisory query.",
        )

    if not settings.tinyfish_api_key:
        return SourceIntelligenceResponse(
            status="unavailable",
            storm_query=query,
            message="TINYFISH_API_KEY is not set. ML endpoints still work without it.",
        )

    try:
        response = httpx.get(
            "https://api.search.tinyfish.ai",
            params={
                "query": f'"{query}" cyclone historical track best track latitude longitude observation time wind speed',
                "purpose": "Find credible meteorological sources with cyclone observed, analyzed, or historical best-track tables containing timestamp, latitude, longitude, and wind speed. Prioritize official IMD and meteorological agency sources. Exclude forecast-only pages when possible.",
                "location": "IN",
                "language": "en",
                "include_domains": "imd.gov.in,noaa.gov,ncei.noaa.gov,metoffice.gov.uk,bom.gov.au,jma.go.jp,wmo.int,ibtracs.unca.edu",
            },
            headers={"X-API-Key": settings.tinyfish_api_key},
            timeout=settings.tinyfish_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("TinyFish Search returned an invalid response.")
    except httpx.TimeoutException:
        return SourceIntelligenceResponse(
            status="error",
            storm_query=query,
            message="TinyFish Search timed out. Please try again.",
        )
    except httpx.ConnectError:
        return SourceIntelligenceResponse(
            status="error",
            storm_query=query,
            message="TinyFish Search connection failed from the backend. Check outbound network or proxy access to api.search.tinyfish.ai.",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            message = "TinyFish Search rate limit reached. Please wait before trying again."
        elif exc.response.status_code == 401:
            message = "TinyFish rejected the configured API key (HTTP 401). Check the backend TINYFISH_API_KEY configuration."
        elif exc.response.status_code == 402:
            message = "TinyFish Search credits or daily allowance are unavailable (HTTP 402)."
        elif exc.response.status_code == 403:
            message = "TinyFish Search denied this request (HTTP 403)."
        elif exc.response.status_code == 400:
            message = "TinyFish Search rejected the request parameters (HTTP 400)."
        else:
            message = f"TinyFish Search returned HTTP {exc.response.status_code}."
        return SourceIntelligenceResponse(status="error", storm_query=query, message=message)
    except ValueError:
        return SourceIntelligenceResponse(
            status="error",
            storm_query=query,
            message="TinyFish Search returned invalid JSON or a response without the documented results array.",
        )
    except httpx.HTTPError:
        return SourceIntelligenceResponse(
            status="error",
            storm_query=query,
            message="TinyFish Search failed during the HTTPS request. Check backend network and TLS configuration.",
        )

    retrieved_at = datetime.now(timezone.utc).isoformat()
    evidence: list[SourceEvidence] = []
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            continue
        title = item.get("title") if isinstance(item.get("title"), str) else ""
        excerpt = item.get("snippet") if isinstance(item.get("snippet"), str) else ""
        publisher = item.get("site_name") if isinstance(item.get("site_name"), str) else urlparse(url).netloc
        evidence.append(
            SourceEvidence(
                url=url,
                publisher=publisher[:200],
                retrieved_at=retrieved_at,
                excerpt=excerpt[:500],
                title=title[:300],
                published_date=item.get("date") if isinstance(item.get("date"), str) else None,
            )
        )

    return SourceIntelligenceResponse(
        status="ok",
        storm_query=query,
        retrieved_at=retrieved_at,
        evidence=evidence,
        message=None if evidence else "TinyFish Search returned no results.",
    )
