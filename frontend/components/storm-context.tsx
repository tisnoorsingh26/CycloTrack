'use client'

import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { predictTrack } from '@/lib/api'
import {
  DEFAULT_STORM_ID,
  getStorm,
  observationsToApi,
  predictionsToForecast,
  type ForecastPoint,
  type Storm,
  type StormId,
} from '@/lib/storms'

type StormContextValue = {
  storm: Storm
  liveStorm: Storm | null
  setLiveForecast: (storm: Omit<Storm, 'id' | 'dataKind'> | null) => void
  stormId: StormId
  setStormId: (id: StormId) => void
  forecastStatus: 'idle' | 'loading' | 'ready' | 'error'
  forecastError: string | null
}

type ForecastState = {
  status: StormContextValue['forecastStatus']
  error: string | null
  forecast: ForecastPoint[]
}

const trackRequestsInFlight = new Map<StormId, ReturnType<typeof predictTrack>>()

function getTrackRequest(stormId: StormId) {
  const existing = trackRequestsInFlight.get(stormId)
  if (existing) return existing
  const request = predictTrack(observationsToApi(getStorm(stormId)))
  trackRequestsInFlight.set(stormId, request)
  const clear = () => {
    if (trackRequestsInFlight.get(stormId) === request) trackRequestsInFlight.delete(stormId)
  }
  void request.then(clear, clear)
  return request
}

const StormContext = createContext<StormContextValue | null>(null)

export function StormProvider({ children }: { children: React.ReactNode }) {
  const [stormId, setStormId] = useState<StormId>(DEFAULT_STORM_ID)
  const [forecastByStorm, setForecastByStorm] = useState<Partial<Record<StormId, ForecastState>>>({})
  const [liveStorm, setLiveStorm] = useState<Storm | null>(null)

  function setLiveForecast(storm: Omit<Storm, 'id' | 'dataKind'> | null) {
    setLiveStorm(storm ? { ...storm, id: 'anvaya', dataKind: 'live' } : null)
  }

  useEffect(() => {
    let cancelled = false
    setForecastByStorm((prev) => ({
      ...prev,
      [stormId]: { status: 'loading', error: null, forecast: prev[stormId]?.forecast ?? [] },
    }))
    getTrackRequest(stormId)
      .then((result) => {
        if (cancelled) return
        setForecastByStorm((prev) => ({
          ...prev,
          [stormId]: { status: 'ready', error: null, forecast: predictionsToForecast(result.predictions) },
        }))
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setForecastByStorm((prev) => ({
          ...prev,
          [stormId]: {
            status: 'error',
            error: cause instanceof Error ? cause.message : 'Track prediction request failed.',
            forecast: [],
          },
        }))
      })
    return () => {
      cancelled = true
    }
  }, [stormId])

  const value = useMemo(() => {
    const base = getStorm(stormId)
    const forecastState = forecastByStorm[stormId]
    return {
      liveStorm,
      setLiveForecast,
      stormId,
      setStormId,
      forecastStatus: forecastState?.status ?? 'idle',
      forecastError: forecastState?.error ?? null,
      storm: { ...base, forecast: forecastState?.status === 'ready' ? forecastState.forecast : [] },
    }
  }, [stormId, forecastByStorm, liveStorm])

  return <StormContext.Provider value={value}>{children}</StormContext.Provider>
}

export function useStorm() {
  const ctx = useContext(StormContext)
  if (!ctx) throw new Error('useStorm must be used within StormProvider')
  return ctx
}
