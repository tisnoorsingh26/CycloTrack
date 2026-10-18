export function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
}

export type ApiObservation = {
  time: string
  lat: number
  lon: number
  wind: number
}

export type HorizonPrediction = {
  horizon_hours: 24 | 48
  displacement: { delta_lat_deg: number; delta_lon_deg: number }
  predicted: { lat: number; lon: number; time: string }
  valid_time: string
}

export type TrackPredictResponse = {
  data_kind: 'ml_prediction'
  last_observed: { lat: number; lon: number; time: string }
  predictions: HorizonPrediction[]
  notes: string[]
}

export type WindPredictResponse = {
  data_kind: 'ml_prediction'
  predicted_wind_knots: number
  input_shape: number[]
  preprocessing: string
  notes: string[]
}

export type HealthResponse = {
  status: 'ok' | 'degraded'
  api: 'up'
  models: {
    cnn: boolean
    lstm_24h: boolean
    lstm_48h: boolean
    scalers: boolean
    details: Record<string, string>
  }
}

export type SourceEvidence = {
  url: string
  publisher: string
  retrieved_at: string
  excerpt: string
  title: string
  published_date?: string | null
  verification: 'unverified'
}

export type SourceIntelligenceResponse = {
  status: 'ok' | 'unavailable' | 'error'
  kind: 'web_search'
  storm_query: string
  retrieved_at: string | null
  evidence: SourceEvidence[]
  message: string | null
  notes: string[]
}

export type SourceFetchResponse = {
  status: 'ok' | 'unavailable' | 'error' | 'insufficient_data'
  storm_query: string
  retrieved_at: string | null
  sources: { url: string; final_url?: string; title?: string | null; retrieved_at: string; status: string; source_type?: string; message?: string; preview?: string; evidence?: string; extraction_notes?: string[] }[]
  observations: ExtractedObservation[]
  model_observations: ExtractedObservation[]
  disagreements: { time: string; source_a: string; source_b: string; position_difference_km: number; wind_difference_kt: number; comparison_rule: string }[]
  imd_reference_status: string | null
  validation: string[]
  forecast: TrackPredictResponse | null
  message: string | null
}

export type ExtractedObservation = ApiObservation & {
  wind_original: string
  units: string
  cyclone_identifier?: string | null
  cyclone_name?: string | null
  source_group?: string | null
  classification: 'observed' | 'analyzed' | 'historical_best_track'
  source_type: 'imd_operational' | 'historical_best_track' | 'meteorological_bulletin' | 'public_web'
  basin: 'Bay of Bengal' | 'Arabian Sea' | null
  source_url: string
  source_title?: string | null
  original_evidence?: string | null
  extraction: 'direct'
  flags: string[]
}

export type CycloneForecastResponse = {
  status: 'ok' | 'unavailable' | 'error' | 'insufficient_data'
  cyclone_name: string | null
  storm_id: string | null
  basin: 'Bay of Bengal' | 'Arabian Sea' | null
  source: string
  source_url: string
  retrieved_at: string | null
  observations: (ApiObservation & {
    wind_original: string
    classification: string
    basin: 'Bay of Bengal' | 'Arabian Sea' | null
    source_url: string
    source_title?: string | null
    extraction: 'direct'
    flags: string[]
  })[]
  forecast: TrackPredictResponse | null
  validation: string[]
  message: string | null
}

export type IBTracsReplayResponse = {
  status: 'ok' | 'insufficient_data' | 'unavailable' | 'error' | 'needs_selection' | 'not_found'
  name: string
  season: number | null
  mode: 'live' | 'historical_replay'
  source_url: string | null
  retrieval_path: 'tinyfish_fetch' | 'direct_http_fallback' | null
  retrieved_at: string | null
  cache_status: 'cached' | 'fresh' | 'unavailable'
  cached_result_from: string | null
  cutoff_count: number
  training_overlap_label: 'held_out_test' | 'possible_training_overlap'
  training_overlap_warning: string
  cutoffs: {
    cutoff: string
    input_observations: (ApiObservation & { source_url: string; retrieval_path: string; retrieved_at: string; interpolated: boolean; interpolation_rule: string })[]
    interpolated_count: number
    quality: 'validated_input' | 'approximate_input'
    warnings: string[]
    results: { horizon_hours: 24 | 48; actual: { lat: number; lon: number; time: string }; lstm: { lat: number; lon: number; time: string }; constant_velocity: { lat: number; lon: number; time: string }; lstm_error_km: number; constant_velocity_error_km: number }[]
  }[]
  summary: Record<string, { mean_km: number; median_km: number }>
  validation: string[]
  rejection_reasons: Record<string, number>
  season_options: { name: string; season: number; basin?: string; rows?: number }[]
  suggestions: { name: string; season: number; basin?: string; rows?: number }[]
  message: string | null
}

export type IBTracsStormSuggestion = { name: string; season: number; basin: string; rows: number }

async function readError(response: Response): Promise<string> {
  const raw = await response.text()
  if (!raw) return response.statusText || `HTTP ${response.status}`
  try {
    const body = JSON.parse(raw)
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg?: string }) => item.msg || JSON.stringify(item)).join('; ')
    }
    return JSON.stringify(body)
  } catch {
    return raw
  }
}

async function apiFetch(path: string, init?: RequestInit, timeoutMs?: number): Promise<Response> {
  const url = `${apiBase()}${path}`
  let response: Response
  const controller = timeoutMs ? new AbortController() : null
  let timedOut = false
  const timeout = controller && timeoutMs
    ? window.setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
    : undefined
  try {
    response = await fetch(url, controller ? { ...init, signal: controller.signal } : init)
  } catch (cause) {
    const reason = cause instanceof Error ? cause.message : String(cause)
    if (timedOut) throw new Error(`Request timed out after ${Math.round((timeoutMs || 0) / 1000)} seconds at ${url}.`)
    if (cause instanceof DOMException && cause.name === 'AbortError') throw new Error(`Request was aborted at ${url}.`)
    throw new Error(`Network error calling ${url}: ${reason}. Check that the backend is running and that its CORS origins include this page.`)
  } finally {
    if (timeout !== undefined) window.clearTimeout(timeout)
  }
  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(`HTTP error ${response.status} ${response.statusText} at ${url}: ${detail}`)
  }
  return response
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiFetch('/health')
  return response.json()
}

export async function predictTrack(observations: ApiObservation[]): Promise<TrackPredictResponse> {
  const response = await apiFetch('/predict/track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ observations }),
  })
  return response.json()
}

export async function predictWind(file: File): Promise<WindPredictResponse> {
  const form = new FormData()
  form.append('file', file)
  const response = await apiFetch('/predict/wind', { method: 'POST', body: form })
  return response.json()
}

export async function fetchSources(query: string): Promise<SourceIntelligenceResponse> {
  const response = await apiFetch(`/sources?${new URLSearchParams({ q: query })}`)
  return response.json()
}

export async function fetchSourceObservations(query: string, urls: string[]): Promise<SourceFetchResponse> {
  const response = await apiFetch('/sources/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ storm_query: query, urls }),
  })
  return response.json()
}

export async function fetchCycloneForecast(query: string): Promise<CycloneForecastResponse> {
  const response = await apiFetch('/cyclone/forecast', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cyclone_query: query }),
  })
  return response.json()
}

export async function replayIBTracs(
  name: string,
  season?: number,
  mode: 'live' | 'historical_replay' = 'historical_replay',
): Promise<IBTracsReplayResponse> {
  const response = await apiFetch('/replay/ibtracs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ...(season == null ? {} : { season }), mode }),
  }, 330_000)
  return response.json()
}

export async function suggestIBTracsStorms(query: string): Promise<IBTracsStormSuggestion[]> {
  const response = await apiFetch(`/replay/ibtracs/storms?${new URLSearchParams({ q: query })}`)
  return response.json()
}
