'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, Pause, Play, RotateCcw } from 'lucide-react'
import { useStorm } from '@/components/storm-context'
import { StormSelector } from '@/components/storm-selector'
import { DEFAULT_LAYERS, MapLegend, StormMap, type MapLayers } from '@/components/storm-map'
import { DataLabel } from '@/components/data-label'
import { buildSteps, formatLat, formatLon, formatTime, type Storm } from '@/lib/storms'
import { cn } from '@/lib/utils'

export function StormExplorerPage() {
  const { storm, liveStorm, forecastStatus, forecastError } = useStorm()
  if (liveStorm) return <StormExplorer key={liveStorm.code} storm={liveStorm} forecastStatus="ready" forecastError={null} />
  return <StormExplorer key={storm.id} storm={storm} forecastStatus={forecastStatus} forecastError={forecastError} />
}

function StormExplorer({
  storm,
  forecastStatus,
  forecastError,
}: {
  storm: Storm
  forecastStatus: 'idle' | 'loading' | 'ready' | 'error'
  forecastError: string | null
}) {
  const steps = useMemo(() => buildSteps(storm), [storm])
  const obsCount = storm.observations.length
  const [step, setStep] = useState(obsCount - 1)
  const [playing, setPlaying] = useState(false)
  const [layers, setLayers] = useState<MapLayers>(DEFAULT_LAYERS)

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      setStep((s) => {
        if (s >= steps.length - 1) {
          setPlaying(false)
          return s
        }
        return s + 1
      })
    }, 650)
    return () => clearInterval(id)
  }, [playing, steps.length])

  const current = steps[step]
  const isForecast = current.kind === 'forecast'

  const togglePlay = () => {
    if (!playing && step >= steps.length - 1) setStep(0)
    setPlaying((p) => !p)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8">
      <div className="flex flex-col gap-2 pt-8 md:flex-row md:items-end md:justify-between md:pt-10">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Storm Explorer · {storm.code}
          </p>
          <h1 className="mt-2 font-serif text-4xl md:text-5xl">
            {storm.name} <span className="text-muted-foreground">— {storm.basin}</span>
          </h1>
        </div>
        <DataLabel kind={storm.dataKind === 'live' ? 'evidence' : 'sample'}>{storm.dataKind === 'live' ? `${storm.provenance?.classification === 'historical_best_track' ? 'Historical best track' : 'Retrieved observations'} · model prediction` : 'Sample storm · not a live system'}</DataLabel>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-12">
        <div className="min-w-0 lg:col-span-9">
          <StormMap storm={storm} step={step} layers={layers} className="border border-border" />
          {storm.historicalReplay && <p className="mt-3 border-l-2 border-signal pl-3 font-mono text-[10px] uppercase tracking-wider text-signal">Historical replay, not live</p>}
          <MapLegend showCone={layers.cone} historicalReplay={Boolean(storm.historicalReplay)} observedLabel={storm.dataKind === 'live' && storm.provenance?.classification === 'historical_best_track' ? 'Historical best-track observations' : storm.dataKind === 'live' ? 'Retrieved observations' : 'Observed track'} className="mt-3" />
          {storm.dataKind === 'live' && storm.provenance && (
            <section className="mt-4 border border-border p-4" aria-label="Track provenance">
              <h2 className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Track provenance</h2>
              <p className="mt-2 text-sm">Solid track: {storm.provenance.classification === 'historical_best_track' ? 'historical best-track observations (replay; not live)' : 'retrieved source observations'}. Dashed and dotted track: existing LSTM predictions at +24 h and +48 h.</p>
              <p className="mt-2 text-xs text-muted-foreground">Model input: {storm.provenance.inputTimes.length} observations from one source, {storm.provenance.sourceType}. Source: <a href={storm.provenance.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-teal underline">{storm.provenance.sourceTitle}</a></p>
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium underline underline-offset-4">Review exact model input timestamps and validation</summary>
                <ol className="mt-2 space-y-1 font-mono text-[11px] text-muted-foreground">{storm.provenance.inputTimes.map((time, index) => <li key={`${time}-${index}`}>{index + 1}. {formatTime(time)}</li>)}</ol>
                <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">{storm.provenance.validation.map((item) => <li key={item}>{item}</li>)}</ul>
                {storm.provenance.disagreementCount > 0 && <p className="mt-2 text-xs text-signal">{storm.provenance.disagreementCount} cross-source disagreement(s) were reported in Methodology & Sources. Model input uses the single source listed above.</p>}
              </details>
            </section>
          )}
          {forecastStatus === 'loading' && <p role="status" className="mt-3 text-sm text-muted-foreground">Requesting 24 h and 48 h track predictions…</p>}
          {forecastStatus === 'error' && <p role="alert" className="mt-3 border-l-2 border-destructive pl-3 text-sm text-destructive">Track predictions unavailable: {forecastError || 'The backend request failed.'}</p>}
          {forecastStatus === 'ready' && storm.forecast.length === 0 && <p className="mt-3 text-sm text-muted-foreground">The backend returned no forecast positions.</p>}

          <div className="mt-6 border-y border-border py-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={togglePlay}
                aria-label={playing ? 'Pause timeline' : 'Play timeline'}
                className="inline-flex size-11 items-center justify-center bg-foreground text-background transition-colors hover:bg-teal"
              >
                {playing ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setPlaying(false)
                  setStep(0)
                }}
                aria-label="Reset timeline to first observation"
                className="inline-flex size-11 items-center justify-center border border-border transition-colors hover:border-foreground"
              >
                <RotateCcw className="size-4" aria-hidden="true" />
              </button>
              <div className="ml-2 min-w-0 flex-1">
                <label htmlFor="timeline" className="sr-only">
                  Timeline position
                </label>
                <input
                  id="timeline"
                  type="range"
                  min={0}
                  max={steps.length - 1}
                  value={step}
                  onChange={(e) => {
                    setPlaying(false)
                    setStep(Number(e.target.value))
                  }}
                  aria-valuetext={`${formatTime(current.time)}, ${isForecast ? `forecast +${current.leadHours} hours` : 'observed'}`}
                  className="h-11 w-full cursor-pointer accent-[var(--teal)]"
                />
              </div>
            </div>
            <div className="mt-1 flex justify-between pl-[6.5rem] font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              <span>Observed</span>
              <span className="text-foreground">Now</span>
              <span>+48 h</span>
            </div>
          </div>
        </div>

        <aside className="flex flex-col gap-8 lg:col-span-3">
          <section aria-labelledby="position-heading" aria-live="polite">
            <h2 id="position-heading" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Selected position
            </h2>
            <DataLabel kind={isForecast ? 'prediction' : 'observed'} className="mt-3">
              {isForecast ? `ML prediction · +${current.leadHours} h` : storm.dataKind === 'live' ? 'Source observation' : 'Observed (sample)'}
            </DataLabel>
            <p className="mt-2 font-mono text-2xl leading-tight">
              {formatLat(current.lat)}
              <br />
              {formatLon(current.lon)}
            </p>
            <p className="mt-2 font-mono text-xs text-muted-foreground">{formatTime(current.time)}</p>
            {current.windKt !== undefined ? (
              <p className="mt-1 font-mono text-xs text-muted-foreground">{storm.dataKind === 'live' ? 'Source wind' : 'Sample wind'} {current.windKt} kt</p>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">The model predicts position only — no intensity.</p>
            )}
          </section>

          {storm.dataKind === 'sample' && <StormSelector dense />}

          <details className="group border-t border-border pt-3">
            <summary className="flex cursor-pointer list-none items-center justify-between py-1 text-sm font-medium">
              Map layers
              <span aria-hidden="true" className="font-mono text-muted-foreground group-open:rotate-45 transition-transform">
                +
              </span>
            </summary>
            <div className="mt-3 flex flex-col gap-3 text-sm">
              <LayerToggle label="Observation points" checked={layers.points} onChange={(v) => setLayers((l) => ({ ...l, points: v }))} />
              <LayerToggle label="Graticule & coordinates" checked={layers.graticule} onChange={(v) => setLayers((l) => ({ ...l, graticule: v }))} />
              <LayerToggle label="Illustrative uncertainty" checked={layers.cone} onChange={(v) => setLayers((l) => ({ ...l, cone: v }))} />
              <p className="text-xs leading-relaxed text-muted-foreground">
                Uncertainty circles use the preliminary mean held-out track error (140.7 km at 24 h, 323.5 km at 48 h). They
                are illustrative, not a calibrated confidence interval.
              </p>
            </div>
          </details>
        </aside>
      </div>

      <details className="group mt-8 border-b border-border">
        <summary className="flex cursor-pointer list-none items-center justify-between border-t border-border py-4">
          <span className="text-sm font-medium">Model forecast positions</span>
          <span className="font-mono text-xs text-muted-foreground">
            <span className="group-open:hidden">Show</span>
            <span className="hidden group-open:inline">Hide</span>
          </span>
        </summary>
        <div className="overflow-x-auto pb-4">
          <table className="w-full min-w-[480px] text-left text-sm">
            <caption className="sr-only">Predicted positions for {storm.name}. Select a row to move the map marker.</caption>
            <thead className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border">
                <th scope="col" className="py-2 font-normal">Lead</th>
                <th scope="col" className="py-2 font-normal">Valid time</th>
                <th scope="col" className="py-2 font-normal">Latitude</th>
                <th scope="col" className="py-2 font-normal">Longitude</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {storm.forecast.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-sm text-muted-foreground">
                    {forecastStatus === 'loading' ? 'Waiting for the 24 h and 48 h model responses…' : forecastStatus === 'error' ? 'No prediction was returned. See the error above.' : 'No forecast positions available.'}
                  </td>
                </tr>
              )}
              {storm.forecast.map((f, i) => {
                const idx = obsCount + i
                const active = idx === step
                return (
                  <tr
                    key={f.leadHours}
                    onClick={() => {
                      setPlaying(false)
                      setStep(idx)
                    }}
                    aria-selected={active}
                    className={cn('cursor-pointer border-b border-border/70 transition-colors hover:bg-muted', active && 'bg-muted')}
                  >
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setPlaying(false)
                          setStep(idx)
                        }}
                        className={cn('text-left', f.leadHours <= 24 ? 'text-teal' : 'text-signal', active && 'font-semibold')}
                      >
                        +{f.leadHours} h
                      </button>
                    </td>
                    <td className="py-2">{formatTime(f.time)}</td>
                    <td className="py-2">{formatLat(f.lat)}</td>
                    <td className="py-2">{formatLon(f.lon)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>

      <div className="mt-10 flex justify-end">
        <Link href="/forecast" className="inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">
          How reliable are these predictions? See Forecast Analysis
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}

function LayerToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="size-4 accent-[var(--teal)]" />
    </label>
  )
}
