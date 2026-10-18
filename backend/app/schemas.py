from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


FEATURE_ORDER = [
    "lat",
    "lon",
    "wind",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
    "north_kmh",
    "east_kmh",
    "delta_lat",
    "delta_lon",
]

SEQUENCE_LENGTH = 8
FEATURE_COUNT = 11
STEP_HOURS = 3.0
CNN_SHAPE = (128, 128, 4)


class ObservationIn(BaseModel):
    time: datetime
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    wind: float = Field(..., ge=0, le=250, description="Wind speed in knots, matching IMD training labels.")


class TrackPredictRequest(BaseModel):
    observations: list[ObservationIn]

    @field_validator("observations")
    @classmethod
    def enough_rows(cls, value: list[ObservationIn]) -> list[ObservationIn]:
        if len(value) < SEQUENCE_LENGTH + 1:
            raise ValueError(
                f"Need at least {SEQUENCE_LENGTH + 1} chronological observations: "
                f"{SEQUENCE_LENGTH} model steps plus one predecessor for motion features."
            )
        return value


class Coordinate(BaseModel):
    lat: float
    lon: float
    time: datetime | None = None


class Displacement(BaseModel):
    delta_lat_deg: float
    delta_lon_deg: float


class HorizonPrediction(BaseModel):
    horizon_hours: Literal[24, 48]
    displacement: Displacement
    predicted: Coordinate
    valid_time: datetime


class TrackPredictResponse(BaseModel):
    data_kind: Literal["ml_prediction"] = "ml_prediction"
    last_observed: Coordinate
    predictions: list[HorizonPrediction]
    feature_order: list[str] = FEATURE_ORDER
    sequence_length: int = SEQUENCE_LENGTH
    step_hours: float = STEP_HOURS
    notes: list[str]


class CycloneForecastRequest(BaseModel):
    cyclone_query: str = Field(..., min_length=2, max_length=100)


class WindPredictResponse(BaseModel):
    data_kind: Literal["ml_prediction"] = "ml_prediction"
    predicted_wind_knots: float
    input_shape: list[int]
    preprocessing: str
    notes: list[str]


class ModelStatus(BaseModel):
    cnn: bool
    lstm_24h: bool
    lstm_48h: bool
    scalers: bool
    details: dict[str, str]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    api: Literal["up"] = "up"
    models: ModelStatus


class SourceEvidence(BaseModel):
    url: str
    publisher: str
    retrieved_at: str
    excerpt: str
    title: str
    published_date: str | None = None
    verification: Literal["unverified"] = "unverified"


class SourceIntelligenceResponse(BaseModel):
    status: Literal["ok", "unavailable", "error"]
    kind: Literal["web_search"] = "web_search"
    storm_query: str
    retrieved_at: str | None = None
    evidence: list[SourceEvidence] = []
    message: str | None = None
    notes: list[str] = Field(
        default_factory=lambda: [
            "TinyFish Search results are public web snippets, not ML predictions.",
        ]
    )


class SourceFetchRequest(BaseModel):
    storm_query: str = Field(..., min_length=1, max_length=200)
    urls: list[str] = Field(..., min_length=1, max_length=5)


class ExtractedObservation(BaseModel):
    time: datetime
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    wind: float = Field(..., ge=0, le=250)
    wind_original: str
    units: str = "kt"
    cyclone_identifier: str | None = None
    cyclone_name: str | None = None
    source_group: str | None = None
    classification: Literal["observed", "analyzed", "historical_best_track"]
    source_type: Literal["imd_operational", "historical_best_track", "meteorological_bulletin", "public_web"] = "public_web"
    basin: Literal["Bay of Bengal", "Arabian Sea"] | None = None
    source_url: str
    source_title: str | None = None
    original_evidence: str | None = None
    extraction: Literal["direct"] = "direct"
    flags: list[str] = Field(default_factory=list)


class CycloneForecastResponse(BaseModel):
    status: Literal["ok", "unavailable", "error", "insufficient_data"]
    cyclone_name: str | None = None
    storm_id: str | None = None
    basin: Literal["Bay of Bengal", "Arabian Sea"] | None = None
    source: str = "India Meteorological Department (IMD) operational Cyclone Track API"
    source_url: str = "https://api.imd.gov.in/api/v1/cyclone_track"
    retrieved_at: datetime | None = None
    observations: list[ExtractedObservation] = Field(default_factory=list)
    forecast: TrackPredictResponse | None = None
    validation: list[str] = Field(default_factory=list)
    message: str | None = None


class SourceFetchResponse(BaseModel):
    status: Literal["ok", "unavailable", "error", "insufficient_data"]
    storm_query: str
    retrieved_at: str | None = None
    sources: list[dict] = Field(default_factory=list)
    observations: list[ExtractedObservation] = Field(default_factory=list)
    model_observations: list[ExtractedObservation] = Field(default_factory=list)
    disagreements: list[dict] = Field(default_factory=list)
    imd_reference_status: str | None = None
    validation: list[str] = Field(default_factory=list)
    forecast: TrackPredictResponse | None = None
    message: str | None = None


class IBTracsReplayRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    season: int | None = Field(default=None, ge=1840, le=2200)
    cutoff: datetime | None = None
    mode: Literal["live", "historical_replay"] = "historical_replay"
    imd_cross_check: bool = False


class IBTracsObservation(BaseModel):
    time: datetime
    lat: float
    lon: float
    wind: float
    wind_units: Literal["kt"] = "kt"
    cyclone_identifier: str
    cyclone_name: str
    basin: Literal["Bay of Bengal", "Arabian Sea"]
    data_type: Literal["historical"] = "historical"
    source_url: str
    retrieval_path: Literal["tinyfish_fetch", "direct_http_fallback"]
    retrieved_at: datetime
    interpolated: bool = False
    interpolation_rule: str


class IBTracsCoordinate(BaseModel):
    time: datetime
    lat: float
    lon: float


class IBTracsHorizonReplay(BaseModel):
    horizon_hours: Literal[24, 48]
    actual: IBTracsCoordinate
    lstm: IBTracsCoordinate
    constant_velocity: IBTracsCoordinate
    lstm_error_km: float
    constant_velocity_error_km: float


class IBTracsCutoffReplay(BaseModel):
    cutoff: datetime
    input_observations: list[IBTracsObservation]
    results: list[IBTracsHorizonReplay]
    interpolated_count: int
    quality: Literal["validated_input", "approximate_input"]
    warnings: list[str] = Field(default_factory=list)
    validation: list[str] = Field(default_factory=list)


class IBTracsMetricSummary(BaseModel):
    mean_km: float
    median_km: float


class IBTracsReplayResponse(BaseModel):
    status: Literal["ok", "insufficient_data", "unavailable", "error", "needs_selection", "not_found"]
    name: str
    season: int | None = None
    mode: Literal["live", "historical_replay"]
    source_url: str | None = None
    retrieval_path: Literal["tinyfish_fetch", "direct_http_fallback"] | None = None
    retrieved_at: datetime | None = None
    cache_status: Literal["cached", "fresh", "unavailable"]
    cached_result_from: datetime | None = None
    cutoff_count: int = 0
    source_order: Literal["ascending", "descending", "mixed"] = "ascending"
    duplicate_timestamps: bool = False
    conflicting_duplicate_timestamps: list[dict] = Field(default_factory=list)
    domain_check_passed: bool = False
    training_overlap_label: Literal["held_out_test", "possible_training_overlap"] = "possible_training_overlap"
    training_overlap_warning: str
    input_interpolation_threshold: int = 2
    cutoffs: list[IBTracsCutoffReplay] = Field(default_factory=list)
    summary: dict[str, IBTracsMetricSummary] = Field(default_factory=dict)
    integrity_check: dict | None = None
    imd_cross_check: dict = Field(default_factory=lambda: {"requested": False, "executed": False, "status": "not_run_by_ibtracs_replay"})
    validation: list[str] = Field(default_factory=list)
    rejection_reasons: dict[str, int] = Field(default_factory=dict)
    season_options: list[dict] = Field(default_factory=list)
    suggestions: list[dict] = Field(default_factory=list)
    message: str | None = None
