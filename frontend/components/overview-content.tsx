'use client'

import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { useStorm } from '@/components/storm-context'
import { StormSelector } from '@/components/storm-selector'
import { StormMap } from '@/components/storm-map'
import { DataLabel } from '@/components/data-label'
import { compass, bearingDeg, distanceKm, forecastAt, formatLat, formatLon, formatTime, latestObservation } from '@/lib/storms'

export function OverviewContent() {
  const { storm, forecastStatus, forecastError } = useStorm()
  const last = latestObservation(storm)
  const f48 = forecastAt(storm, 48)
  const moveKm = f48 ? distanceKm(last, f48) : null
  const heading = f48 ? compass(bearingDeg(last, f48)) : null

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8">
      <section className="grid gap-10 pt-12 md:grid-cols-12 md:gap-12 md:pt-20">
        <div className="md:col-span-5">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Tropical cyclone track research
          </p>
          <h1 className="mt-4 font-serif text-5xl leading-[1.02] text-balance md:text-7xl">
            Reading the path of a <em className="text-teal">storm.</em>
          </h1>
          <p className="mt-6 max-w-md text-pretty leading-relaxed text-muted-foreground">
            CycloTrack pairs observed storm tracks with experimental LSTM predictions of where a cyclone will be in
            24 and 48 hours, and shows how those predictions have performed historically.
          </p>

          <StormSelector className="mt-10" />

          <Link
            href="/explorer"
            className="mt-8 inline-flex items-center gap-3 bg-foreground px-6 py-3.5 text-sm font-medium text-background transition-colors hover:bg-teal focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Explore {storm.name}
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>

        <div className="md:col-span-7 md:pt-2">
          <figure>
            <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2">
              <figcaption className="font-mono text-xs text-muted-foreground">
                {storm.code} · {storm.basin}
              </figcaption>
              <DataLabel kind="sample" />
            </div>
            <StormMap storm={storm} compact className="mt-3" />
          </figure>

          <dl className="mt-6 grid grid-cols-1 border-t border-border sm:grid-cols-3">
            <Metric term="Latest observed" detail={formatTime(last.time)}>
              {formatLat(last.lat)} {formatLon(last.lon)}
            </Metric>
            <Metric term="Predicted +48 h" detail={forecastStatus === 'ready' ? 'ML prediction' : forecastStatus === 'loading' ? 'Loading model' : 'Unavailable'}>
              {f48 ? `${formatLat(f48.lat)} ${formatLon(f48.lon)}` : forecastStatus === 'loading' ? '…' : '—'}
            </Metric>
            <Metric term="Predicted motion" detail="over 48 h">
              {moveKm != null && heading ? `${Math.round(moveKm)} km ${heading}` : '—'}
            </Metric>
          </dl>
        </div>
      </section>

      {forecastError && (
        <p className="mt-8 border-l-2 border-destructive pl-4 text-sm text-destructive">
          Track model unavailable: {forecastError}. Start the backend (see README) and refresh.
        </p>
      )}
      <p className="mt-16 border-l-2 border-signal pl-4 text-sm text-muted-foreground">
        Observations are labelled sample data. 24 h / 48 h positions come from the trained LSTM when the API is running.
        They are not official warnings — consult your national meteorological service.
      </p>
    </div>
  )
}

function Metric({ term, detail, children }: { term: string; detail: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border py-4 sm:border-b-0 sm:border-r sm:px-4 sm:first:pl-0 sm:last:border-r-0">
      <dt className="text-xs text-muted-foreground">{term}</dt>
      <dd className="mt-1 font-mono text-base text-foreground">{children}</dd>
      <dd className="mt-0.5 font-mono text-[11px] text-muted-foreground">{detail}</dd>
    </div>
  )
}
