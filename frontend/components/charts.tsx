'use client'

import { useState } from 'react'
import { EVALUATION, improvementPct } from '@/lib/evaluation'
import { formatTime, type Observation } from '@/lib/storms'
import { cn } from '@/lib/utils'

export function TrackErrorChart() {
  const max = 500
  return (
    <figure>
      <div className="flex flex-col gap-8">
        {EVALUATION.map((row) => (
          <div key={row.leadHours}>
            <div className="flex items-baseline justify-between">
              <p className="font-serif text-2xl">{row.leadHours}-hour lead</p>
              <p className="font-mono text-xs text-muted-foreground">
                {improvementPct(row).toFixed(1)}% lower error than baseline
              </p>
            </div>
            <dl className="mt-3 flex flex-col gap-2">
              <Bar label="LSTM" value={row.lstmKm} max={max} className="bg-teal" />
              <Bar label="Linear baseline" value={row.baselineKm} max={max} className="bg-muted-foreground/45" />
            </dl>
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="mt-3 ml-[7.5rem] flex justify-between border-t border-border pt-1 font-mono text-[10px] text-muted-foreground">
        {[0, 100, 200, 300, 400, 500].map((v) => (
          <span key={v}>{v}</span>
        ))}
      </div>
      <figcaption className="mt-2 text-right font-mono text-[11px] text-muted-foreground">Mean track error, km (lower is better)</figcaption>
    </figure>
  )
}

function Bar({ label, value, max, className }: { label: string; value: number; max: number; className: string }) {
  return (
    <div className="flex items-center gap-3">
      <dt className="w-[6.75rem] shrink-0 text-sm text-muted-foreground">{label}</dt>
      <dd className="flex flex-1 items-center gap-3">
        <span className={cn('block h-5', className)} style={{ width: `${(value / max) * 100}%` }} />
        <span className="font-mono text-sm">{value.toFixed(1)}</span>
      </dd>
    </div>
  )
}

type Metric = 'wind' | 'pressure'

export function ObservationSeriesChart({ observations, title }: { observations: Observation[]; title?: string }) {
  const [metric, setMetric] = useState<Metric>('wind')
  const W = 640
  const H = 220
  const padL = 44
  const padR = 12
  const padT = 14
  const padB = 28
  const usable = observations.filter((o) => metric === 'wind' || o.pressureHpa !== null)
  const values = usable.map((o) => (metric === 'wind' ? o.windKt : o.pressureHpa as number))
  const lo = Math.floor((Math.min(...values) - 5) / 10) * 10
  const hi = Math.ceil((Math.max(...values) + 5) / 10) * 10
  const x = (i: number) => padL + (i / (usable.length - 1)) * (W - padL - padR)
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB)
  const ticks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) / 4) * i)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const unit = metric === 'wind' ? 'kt' : 'hPa'

  if (values.length < 2) return <p className="text-sm text-muted-foreground">No source-reported pressure values are available to chart.</p>

  return (
    <figure>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {title && <figcaption className="text-sm font-medium">{title}</figcaption>}
        <div role="group" aria-label="Chart variable" className="flex border border-border text-xs">
          {(['wind', 'pressure'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={metric === m}
              onClick={() => setMetric(m)}
              className={cn('px-3 py-2 capitalize transition-colors', metric === m ? 'bg-foreground text-background' : 'hover:bg-muted')}
            >
              {m === 'wind' ? 'Max wind (kt)' : 'Pressure (hPa)'}
            </button>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 h-auto w-full" role="img" aria-label={`Sample ${metric} over time, ${values[0]} to ${values[values.length - 1]} ${unit}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--border)" />
            <text x={padL - 8} y={y(t) + 3} textAnchor="end" fontSize={10} className="font-mono" fill="var(--muted-foreground)">
              {Math.round(t)}
            </text>
          </g>
        ))}
        <path d={d} fill="none" stroke="var(--foreground)" strokeWidth={2} />
        {values.map((v, i) => (
          <circle key={i} cx={x(i)} cy={y(v)} r={2.5} fill="var(--foreground)" />
        ))}
        <text x={padL} y={H - 8} fontSize={10} className="font-mono" fill="var(--muted-foreground)">
          {formatTime(usable[0].time)}
        </text>
        <text x={W - padR} y={H - 8} fontSize={10} textAnchor="end" className="font-mono" fill="var(--muted-foreground)">
          {formatTime(usable[usable.length - 1].time)}
        </text>
      </svg>
    </figure>
  )
}
