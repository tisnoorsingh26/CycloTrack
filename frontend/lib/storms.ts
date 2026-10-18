/**
 * Illustrative sample storms. These are NOT real cyclones and NOT live observations.
 * Observation rows are synthetic demo values on a 3-hour cadence matching the LSTM window.
 */

import type { HorizonPrediction } from '@/lib/api'

export type StormId = 'anvaya' | 'tamayo' | 'sharav'

export type Observation = {
  time: string
  lat: number
  lon: number
  windKt: number
  pressureHpa: number | null
}

export type ForecastPoint = {
  leadHours: number
  time: string
  lat: number
  lon: number
  source: 'ml_prediction' | 'unavailable'
}

export type Storm = {
  id: StormId
  code: string
  name: string
  basin: string
  dataKind: 'sample' | 'live'
  observations: Observation[]
  forecast: ForecastPoint[]
  provenance?: {
    classification: 'historical_best_track' | 'observed' | 'analyzed'
    sourceType: string
    sourceUrl: string
    sourceTitle: string
    inputTimes: string[]
    validation: string[]
    disagreementCount: number
  }
  historicalReplay?: {
    actualFuture: Observation[]
    baseline: ForecastPoint[]
  }
}

const HOUR = 3_600_000

function buildObservations(start: string, rows: [number, number, number][]): Observation[] {
  const t0 = Date.parse(start)
  return rows.map(([lat, lon, windKt], i) => ({
    time: new Date(t0 + i * 3 * HOUR).toISOString(),
    lat,
    lon,
    windKt,
    pressureHpa: Math.round(1008 - (windKt - 25) * 0.62),
  }))
}

function makeStorm(
  base: Omit<Storm, 'observations' | 'forecast' | 'dataKind'>,
  start: string,
  obs: [number, number, number][],
): Storm {
  const observations = buildObservations(start, obs)
  return { ...base, dataKind: 'sample', observations, forecast: [] }
}

export const STORMS: Storm[] = [
  makeStorm(
    { id: 'anvaya', code: 'SMP-BOB-01', name: 'Anvaya', basin: 'Bay of Bengal' },
    '2026-11-02T00:00:00Z',
    [
      [10.2, 88.6, 30],
      [10.45, 88.5, 32],
      [10.7, 88.4, 35],
      [10.95, 88.25, 38],
      [11.2, 88.1, 40],
      [11.5, 88.0, 43],
      [11.8, 87.9, 45],
      [12.1, 87.8, 48],
      [12.4, 87.7, 50],
      [12.7, 87.65, 52],
      [13.0, 87.6, 55],
      [13.3, 87.5, 58],
    ],
  ),
  makeStorm(
    { id: 'tamayo', code: 'SMP-WPAC-02', name: 'Tamayo', basin: 'West Pacific' },
    '2026-09-14T00:00:00Z',
    [
      [11.5, 142.0, 35],
      [11.75, 141.5, 38],
      [12.0, 141.0, 40],
      [12.2, 140.5, 42],
      [12.4, 140.0, 45],
      [12.65, 139.5, 50],
      [12.9, 139.0, 55],
      [13.1, 138.5, 60],
      [13.3, 138.0, 65],
      [13.55, 137.5, 70],
      [13.8, 137.0, 75],
      [14.05, 136.55, 80],
    ],
  ),
  makeStorm(
    { id: 'sharav', code: 'SMP-ARB-03', name: 'Sharav', basin: 'Arabian Sea' },
    '2026-05-20T00:00:00Z',
    [
      [12.8, 69.5, 30],
      [13.05, 69.4, 32],
      [13.3, 69.3, 35],
      [13.55, 69.15, 38],
      [13.8, 69.0, 40],
      [14.05, 68.85, 42],
      [14.3, 68.7, 45],
      [14.55, 68.5, 48],
      [14.8, 68.3, 50],
      [15.05, 68.1, 52],
      [15.3, 67.9, 55],
      [15.55, 67.7, 58],
    ],
  ),
]

export const DEFAULT_STORM_ID: StormId = 'anvaya'

export function getStorm(id: StormId): Storm {
  return STORMS.find((s) => s.id === id) ?? STORMS[0]
}

export function latestObservation(storm: Storm): Observation {
  return storm.observations[storm.observations.length - 1]
}

export function forecastAt(storm: Storm, leadHours: number): ForecastPoint | undefined {
  return storm.forecast.find((f) => f.leadHours === leadHours)
}

export function observationsToApi(storm: Storm) {
  return storm.observations.map((o) => ({
    time: o.time,
    lat: o.lat,
    lon: o.lon,
    wind: o.windKt,
  }))
}

export function predictionsToForecast(preds: HorizonPrediction[]): ForecastPoint[] {
  return preds.map((p) => ({
    leadHours: p.horizon_hours,
    time: p.valid_time,
    lat: p.predicted.lat,
    lon: p.predicted.lon,
    source: 'ml_prediction' as const,
  }))
}

export type TrackStep = {
  kind: 'observed' | 'forecast'
  time: string
  lat: number
  lon: number
  leadHours?: number
  windKt?: number
}

export function buildSteps(storm: Storm): TrackStep[] {
  return [
    ...storm.observations.map((o) => ({
      kind: 'observed' as const,
      time: o.time,
      lat: o.lat,
      lon: o.lon,
      windKt: o.windKt,
    })),
    ...storm.forecast.map((f) => ({
      kind: 'forecast' as const,
      time: f.time,
      lat: f.lat,
      lon: f.lon,
      leadHours: f.leadHours,
    })),
  ]
}

const toRad = (d: number) => (d * Math.PI) / 180

export function distanceKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const R = 6371
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function bearingDeg(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const y = Math.sin(toRad(b.lon - a.lon)) * Math.cos(toRad(b.lat))
  const x =
    Math.cos(toRad(a.lat)) * Math.sin(toRad(b.lat)) -
    Math.sin(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.cos(toRad(b.lon - a.lon))
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
}

const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
export function compass(deg: number) {
  return COMPASS[Math.round(deg / 22.5) % 16]
}

export function formatLat(lat: number) {
  return `${Math.abs(lat).toFixed(1)}°${lat >= 0 ? 'N' : 'S'}`
}
export function formatLon(lon: number) {
  return `${Math.abs(lon).toFixed(1)}°${lon >= 0 ? 'E' : 'W'}`
}
export function formatTime(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:00Z`
}
