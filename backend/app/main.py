import logging
import json
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import CycloneForecastRequest, HealthResponse, ModelStatus, TrackPredictRequest, IBTracsReplayRequest, IBTracsReplayResponse
from app.services.cnn import CnnError, predict_wind
from app.services.lstm import LstmError, predict_track
from app.services.registry import load_registry, registry
from app.services.tinyfish import retrieve_source_evidence
from app.services.live_sources import fetch_and_forecast
from app.schemas import SourceFetchRequest
from app.services.imd_cyclone import get_cyclone_forecast
from app.services.ibtracs_replay import replay_ibtracs, search_storms

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("cyclotrack")
_source_rate_lock = threading.Lock()
_source_request_times: dict[str, deque[float]] = {}


def _limit_source_requests(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _source_rate_lock:
        history = _source_request_times.setdefault(client, deque())
        while history and now - history[0] >= 60:
            history.popleft()
        if len(history) >= 20:
            raise HTTPException(status_code=429, detail="Source requests are limited to 20 per minute. Please wait and try again.")
        history.append(now)


def _redact_replay_body(raw_body: str) -> str:
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return f"<non-json body; {len(raw_body.encode('utf-8'))} bytes>"

    def redact(value):
        if isinstance(value, dict):
            return {
                key: ("[REDACTED]" if any(word in str(key).casefold() for word in
                                          ("key", "token", "secret", "authorization", "credential"))
                      else redact(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return json.dumps(redact(payload), ensure_ascii=False, separators=(",", ":"))


def _redact_replay_query(query: str) -> str:
    sensitive_words = ("key", "token", "secret", "authorization", "credential")
    pairs = parse_qsl(query, keep_blank_values=True)
    return urlencode([(key, "[REDACTED]" if any(word in key.casefold() for word in sensitive_words) else value)
                      for key, value in pairs])


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_registry(settings)
    yield


app = FastAPI(
    title="CycloTrack API",
    description=(
        "Inference for the trained Huber CNN (wind in knots from 128×128×4 arrays) "
        "and the 24 h / 48 h LSTM track-displacement models. "
        "TinyFish Search is optional source intelligence, not a model output."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error method=%s path=%s", request.method, request.url.path)
    origin = request.headers.get("origin")
    allowed_origins = set(settings.cors_origin_list()) | {
        "http://127.0.0.1:3000", "http://localhost:3000",
    }
    headers = {}
    if origin in allowed_origins:
        headers = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true",
                   "Vary": "Origin"}
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "error": type(exc).__name__},
                        headers=headers)


@app.middleware("http")
async def log_replay_requests(request: Request, call_next):
    if not request.url.path.startswith("/replay/"):
        return await call_next(request)
    started = time.perf_counter()
    body = _redact_replay_body((await request.body()).decode("utf-8", errors="replace"))
    method, path = request.method, str(request.url.path)
    if request.url.query:
        path += f"?{_redact_replay_query(request.url.query)}"
    origin = request.headers.get("origin", "<none>")
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception("Replay request exception method=%s path=%s origin=%s body=%s status=500 duration_ms=%.1f",
                         method, path, origin, body, duration_ms)
        raise
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info("Replay request method=%s path=%s origin=%s body=%s status=%s duration_ms=%.1f",
                method, path, origin, body, response.status_code, duration_ms)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(settings.cors_origin_list() + [
        "http://127.0.0.1:3000", "http://localhost:3000",
    ])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CnnError)
async def cnn_error(_, exc: CnnError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(LstmError)
async def lstm_error(_, exc: LstmError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", response_model=HealthResponse)
def health():
    status = registry.status()
    models = ModelStatus(
        cnn=status["cnn"],
        lstm_24h=status["lstm_24h"],
        lstm_48h=status["lstm_48h"],
        scalers=status["scalers"],
        details=registry.details,
    )
    overall = "ok" if all(status.values()) else "degraded"
    return HealthResponse(status=overall, models=models)


@app.post("/predict/wind")
def predict_wind_endpoint(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="A filename is required.")
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Empty upload.")
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 8 MB.")
    return predict_wind(file.filename, content)


@app.post("/predict/track")
def predict_track_endpoint(payload: TrackPredictRequest):
    return predict_track(payload)


@app.get("/sources")
def sources(request: Request, q: str = Query(..., min_length=1, max_length=200)):
    _limit_source_requests(request)
    return retrieve_source_evidence(q)


@app.post("/sources/fetch")
def fetch_sources(payload: SourceFetchRequest, request: Request):
    _limit_source_requests(request)
    return fetch_and_forecast(payload)


@app.post("/cyclone/forecast")
def cyclone_forecast(payload: CycloneForecastRequest, request: Request):
    _limit_source_requests(request)
    return get_cyclone_forecast(payload)


@app.get("/replay/ibtracs/storms")
def replay_ibtracs_storms(q: str = Query(..., min_length=1, max_length=100)):
    try:
        return search_storms(q, settings)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/replay/ibtracs", response_model=IBTracsReplayResponse)
def replay_ibtracs_endpoint(payload: IBTracsReplayRequest):
    """Replay archived IBTrACS positions through the existing 24h/48h LSTMs.

    TinyFish Agent discovery is a daily maintenance/prewarm action, never invoked
    inside this request path. This endpoint does not call the IMD integration.
    """
    return replay_ibtracs(payload, settings)
