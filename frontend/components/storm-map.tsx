'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { geoGraticule, geoMercator, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import land50m from 'world-atlas/land-50m.json'
import { buildSteps, formatLat, formatLon, latestObservation, type Storm } from '@/lib/storms'
import { meanErrorAtLead } from '@/lib/evaluation'
import { cn } from '@/lib/utils'

type LandTopology = Parameters<typeof feature>[0]
const topology = land50m as unknown as LandTopology
const LAND = feature(topology, topology.objects.land as Parameters<typeof feature>[1])

export type MapLayers = { points: boolean; cone: boolean; graticule: boolean }
export const DEFAULT_LAYERS: MapLayers = { points: true, cone: false, graticule: true }

function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

type Props = {
  storm: Storm
  step?: number
  layers?: MapLayers
  compact?: boolean
  className?: string
}

function roundCoord(val: number, precision = 2): number {
  return Number(val.toFixed(precision))
}

export function StormMap({ storm, step, layers = DEFAULT_LAYERS, compact = false, className }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(compact ? 520 : 960)
  const height = compact
    ? Math.round(width * 0.68)
    : width < 640
      ? Math.round(width * 1.05)
      : Math.round(Math.min(Math.max(width * 0.6, 380), 620))
  const pad = compact ? 28 : width < 640 ? 36 : 56

  const steps = useMemo(() => buildSteps(storm), [storm])
  const mapPoints = [...steps, ...(storm.historicalReplay?.actualFuture ?? []), ...(storm.historicalReplay?.baseline ?? [])]
  const latest = latestObservation(storm)

  const geo = useMemo(() => {
    const lats = mapPoints.map((s) => s.lat)
    const lons = mapPoints.map((s) => s.lon)
    const margin = compact ? 2.5 : 3.5
    const bounds = {
      type: 'MultiPoint' as const,
      coordinates: [
        [Math.min(...lons) - margin, Math.min(...lats) - margin],
        [Math.max(...lons) + margin, Math.max(...lats) + margin],
      ],
    }
    const projection = geoMercator()
      .fitExtent(
        [
          [pad, pad],
          [width - pad, height - pad],
        ],
        bounds,
      )
    const path = geoPath(projection)
    const p = (lon: number, lat: number): [number, number] => {
      const pt = projection([lon, lat]) as [number, number] | null
      return pt ? [roundCoord(pt[0]), roundCoord(pt[1])] : [0, 0]
    }

    const [lonW, latN] = projection.invert!([0, 0])!
    const [lonE, latS] = projection.invert!([width, height])!
    const latTicks: number[] = []
    for (let v = Math.ceil(latS / 5) * 5; v <= latN; v += 5) latTicks.push(v)
    const lonTicks: number[] = []
    for (let v = Math.ceil(lonW / 5) * 5; v <= lonE; v += 5) lonTicks.push(v)

    const kmToPx = (lat: number, lon: number, km: number) =>
      roundCoord(Math.abs(p(lon, lat)[1] - p(lon, lat + km / 111.2)[1]))
    const midLat = (latN + latS) / 2
    const midLon = (lonW + lonE) / 2
    const scaleKm = 500
    const scalePx = kmToPx(midLat, midLon, scaleKm)

    return {
      land: path(LAND) ?? '',
      graticule: path(geoGraticule().step([5, 5])()) ?? '',
      p,
      kmToPx,
      latTicks,
      lonTicks,
      midLat,
      midLon,
      scaleKm,
      scalePx,
    }
  }, [steps, mapPoints, width, height, pad, compact])

  const { p } = geo
  const toPath = (pts: { lat: number; lon: number }[]) =>
    pts.map((pt, i) => `${i ? 'L' : 'M'}${p(pt.lon, pt.lat).map((n) => n.toFixed(2)).join(',')}`).join('')

  const f24 = storm.forecast.filter((f) => f.leadHours === 24)
  const f48 = storm.forecast.filter((f) => f.leadHours === 48)
  const end24 = f24[0]
  const end48 = f48[0]
  const replay = storm.historicalReplay
  const [lx, ly] = p(latest.lon, latest.lat)
  const e24 = end24 ? p(end24.lon, end24.lat) : null
  const e48 = end48 ? p(end48.lon, end48.lat) : null
  const selected = step !== undefined ? steps[step] : undefined
  const sel = selected ? p(selected.lon, selected.lat) : undefined
  const labelSize = compact ? 10 : 11

  const trackDescription = storm.dataKind === 'sample'
    ? 'sample'
    : storm.provenance?.classification === 'historical_best_track'
      ? 'historical best-track observations'
      : 'retrieved source observations'
  const ariaLabel = `Map of ${trackDescription} for storm ${storm.name} in the ${storm.basin}. Track ends at ${formatLat(latest.lat)} ${formatLon(latest.lon)}.${
    end48 ? ` Predicted 48-hour endpoint ${formatLat(end48.lat)} ${formatLon(end48.lon)}.` : ' No model forecast loaded yet.'
  }`

  return (
    <div ref={ref} className={cn('relative w-full overflow-hidden bg-ocean', className)}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel} className="block">
        {layers.graticule && <path d={geo.graticule} fill="none" stroke="var(--foreground)" strokeOpacity={0.09} strokeWidth={1} />}
        <path d={geo.land} fill="var(--land)" stroke="var(--foreground)" strokeOpacity={0.35} strokeWidth={0.75} />

        {layers.graticule && !compact && (
          <g className="font-mono" fill="var(--muted-foreground)" fontSize={10}>
            {geo.latTicks.map((lat) => (
              <text key={`lat${lat}`} x={8} y={roundCoord(p(geo.midLon, lat)[1] - 4)}>
                {formatLat(lat).replace('.0', '')}
              </text>
            ))}
            {geo.lonTicks.map((lon) => (
              <text key={`lon${lon}`} x={roundCoord(p(lon, geo.midLat)[0] + 4)} y={height - 8}>
                {formatLon(lon).replace('.0', '')}
              </text>
            ))}
          </g>
        )}

        {layers.cone && (
          <g opacity={0.16} fill="var(--teal)">
            {storm.forecast.map((f) => {
              const [x, y] = p(f.lon, f.lat)
              return <circle key={f.leadHours} cx={x} cy={y} r={geo.kmToPx(f.lat, f.lon, meanErrorAtLead(f.leadHours))} />
            })}
          </g>
        )}

        <path d={toPath(storm.observations)} fill="none" stroke="var(--foreground)" strokeWidth={2} strokeLinejoin="round" />
        {replay ? (
          <>
            <path d={toPath(replay.actualFuture)} fill="none" stroke="#fbbf24" strokeWidth={2.5} strokeDasharray="5 3" strokeLinejoin="round" />
            <path d={toPath(storm.forecast)} fill="none" stroke="#2dd4bf" strokeWidth={2.75} strokeDasharray="8 4" strokeLinejoin="round" />
            <path d={toPath(replay.baseline)} fill="none" stroke="#f472b6" strokeWidth={2.5} strokeDasharray="2 4" strokeLinejoin="round" />
            {replay.actualFuture.map((point) => { const [x, y] = p(point.lon, point.lat); return <circle key={`actual-${point.time}`} cx={x} cy={y} r={3} fill="#fbbf24" /> })}
            {storm.forecast.map((point) => { const [x, y] = p(point.lon, point.lat); return <circle key={`lstm-${point.time}`} cx={x} cy={y} r={3.25} fill="#2dd4bf" /> })}
            {replay.baseline.map((point) => { const [x, y] = p(point.lon, point.lat); return <circle key={`baseline-${point.time}`} cx={x} cy={y} r={3} fill="#f472b6" /> })}
          </>
        ) : end24 && (
          <path
            d={toPath([latest, end24])}
            fill="none"
            stroke="var(--teal)"
            strokeWidth={2.25}
            strokeDasharray="7 5"
            strokeLinecap="round"
          />
        )}
        {!replay && end24 && end48 && (
          <path
            d={toPath([end24, end48])}
            fill="none"
            stroke="var(--signal)"
            strokeWidth={2.25}
            strokeDasharray="1.5 5"
            strokeLinecap="round"
          />
        )}

        {layers.points &&
          storm.observations.slice(0, -1).map((o) => {
            const [x, y] = p(o.lon, o.lat)
            return <circle key={o.time} cx={x} cy={y} r={2.5} fill="var(--foreground)" />
          })}

        <circle cx={lx} cy={ly} r={5.5} fill="var(--foreground)" stroke="var(--background)" strokeWidth={2} />
        {e24 && <circle cx={e24[0]} cy={e24[1]} r={5} fill="var(--background)" stroke="var(--teal)" strokeWidth={2} />}
        {e48 && (
          <rect
            x={roundCoord(e48[0] - 5)}
            y={roundCoord(e48[1] - 5)}
            width={10}
            height={10}
            fill="var(--background)"
            stroke="var(--signal)"
            strokeWidth={2}
            transform={`rotate(45 ${e48[0]} ${e48[1]})`}
          />
        )}

        {!compact || width > 360 ? (
          <g className="font-mono" fontSize={labelSize} fill="var(--foreground)" paintOrder="stroke" stroke="var(--ocean)" strokeWidth={3} strokeLinejoin="round">
            <text x={roundCoord(lx + 20)} y={roundCoord(ly + 4)}>
              Latest obs
            </text>
            {e24 && (
              <text x={roundCoord(e24[0] + 10)} y={roundCoord(e24[1] + 4)} fill="var(--teal)">
                +24 h
              </text>
            )}
            {e48 && (
              <text x={roundCoord(e48[0] + 10)} y={roundCoord(e48[1] + 4)} fill="var(--signal)">
                +48 h
              </text>
            )}
          </g>
        ) : null}

        {sel && selected && (
          <g style={{ transform: `translate(${sel[0]}px, ${sel[1]}px)`, transition: 'transform 280ms ease-out' }} aria-hidden="true">
            <circle r={11} fill="none" stroke={selected.kind === 'observed' ? 'var(--foreground)' : 'var(--teal)'} strokeWidth={1.5} />
            <line x1={-17} x2={-12} y1={0} y2={0} stroke="var(--foreground)" strokeWidth={1.25} />
            <line x1={12} x2={17} y1={0} y2={0} stroke="var(--foreground)" strokeWidth={1.25} />
            <line y1={-17} y2={-12} x1={0} x2={0} stroke="var(--foreground)" strokeWidth={1.25} />
            <line y1={12} y2={17} x1={0} x2={0} stroke="var(--foreground)" strokeWidth={1.25} />
          </g>
        )}

        {!compact && (
          <g transform={`translate(${roundCoord(width - geo.scalePx - 20)}, ${height - 22})`} className="font-mono" fontSize={10} fill="var(--muted-foreground)">
            <line x1={0} x2={geo.scalePx} y1={0} y2={0} stroke="var(--foreground)" strokeWidth={1.5} />
            <line x1={0} x2={0} y1={-4} y2={4} stroke="var(--foreground)" strokeWidth={1.5} />
            <line x1={geo.scalePx} x2={geo.scalePx} y1={-4} y2={4} stroke="var(--foreground)" strokeWidth={1.5} />
            <text x={0} y={-8}>
              {geo.scaleKm} km
            </text>
          </g>
        )}
      </svg>
    </div>
  )
}

export function MapLegend({ showCone = false, observedLabel = 'Observed track', historicalReplay = false, className }: { showCone?: boolean; observedLabel?: string; historicalReplay?: boolean; className?: string }) {
  if (historicalReplay) return (
    <ul className={cn('flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground', className)}>
      <li><span className="mr-2 inline-block h-0.5 w-7 align-middle bg-foreground" />Input observations</li>
      <li><span className="mr-2 inline-block h-0.5 w-7 align-middle bg-[#fbbf24]" />Actual future (IBTrACS)</li>
      <li><span className="mr-2 inline-block h-0.5 w-7 align-middle bg-[#2dd4bf]" />LSTM forecast</li>
      <li><span className="mr-2 inline-block h-0.5 w-7 align-middle bg-[#f472b6]" />Constant-velocity baseline</li>
    </ul>
  )
  return (
    <ul className={cn('flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground', className)}>
      <li className="flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="0" x2="28" y1="4" y2="4" stroke="var(--foreground)" strokeWidth="2" />
        </svg>
        {observedLabel}
      </li>
      <li className="flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="0" x2="28" y1="4" y2="4" stroke="var(--teal)" strokeWidth="2.25" strokeDasharray="7 5" />
        </svg>
        0–24 h prediction
      </li>
      <li className="flex items-center gap-2">
        <svg width="28" height="8" aria-hidden="true">
          <line x1="1" x2="28" y1="4" y2="4" stroke="var(--signal)" strokeWidth="2.25" strokeDasharray="1.5 5" strokeLinecap="round" />
        </svg>
        24–48 h prediction
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="size-2.5 rounded-full bg-foreground" />
        Latest observed position
      </li>
      {showCone && (
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2.5 w-4 bg-teal/25" />
          Illustrative spread (mean held-out error, not calibrated)
        </li>
      )}
    </ul>
  )
}
