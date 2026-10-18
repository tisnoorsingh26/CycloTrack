'use client'

import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { useStorm } from '@/components/storm-context'
import { StormSelector } from '@/components/storm-selector'
import { DataLabel, SectionEyebrow } from '@/components/data-label'
import { ObservationSeriesChart, TrackErrorChart } from '@/components/charts'
import { Disclosure } from '@/components/disclosure'
import { bearingDeg, compass, distanceKm, forecastAt, formatLat, formatLon, formatTime, latestObservation } from '@/lib/storms'
import { MODEL_SPEC } from '@/lib/evaluation'

export function ForecastAnalysis() {
  const { storm, forecastStatus, forecastError } = useStorm()
  const last = latestObservation(storm)

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8">
      <header className="grid gap-6 pt-8 md:grid-cols-12 md:pt-12">
        <div className="md:col-span-7">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Forecast Analysis</p>
          <h1 className="mt-2 font-serif text-4xl text-balance md:text-5xl">Where the model thinks {storm.name} goes next.</h1>
        </div>
        <StormSelector dense className="md:col-span-4 md:col-start-9" />
      </header>

      <section aria-labelledby="pred-heading" className="mt-12">
        <SectionEyebrow index="01">Predicted positions · {storm.name}</SectionEyebrow>
        <h2 id="pred-heading" className="sr-only">
          Predicted positions
        </h2>
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          From latest observed {formatLat(last.lat)} {formatLon(last.lon)} at {formatTime(last.time)}
        </p>
        <div className="mt-6 grid border-t border-border md:grid-cols-2">
          {[24, 48].map((lead) => {
            const f = forecastAt(storm, lead)
            const km = f ? distanceKm(last, f) : null
            const brg = f ? bearingDeg(last, f) : null
            return (
              <article key={lead} className="border-b border-border py-6 md:px-8 md:first:border-r md:first:pl-0">
                <div className="flex items-baseline justify-between gap-4">
                  <h3 className={lead === 24 ? 'font-serif text-3xl text-teal' : 'font-serif text-3xl text-signal'}>+{lead} hours</h3>
                  <DataLabel kind="prediction" />
                </div>
                <p className="mt-4 font-mono text-3xl md:text-4xl">
                  {f ? `${formatLat(f.lat)} ${formatLon(f.lon)}` : forecastStatus === 'loading' ? 'Loading…' : 'Unavailable'}
                </p>
                <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-xs text-muted-foreground">Valid time</dt>
                    <dd className="mt-0.5 font-mono">{f ? formatTime(f.time) : forecastStatus === 'loading' ? 'Requesting prediction' : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Displacement</dt>
                    <dd className="mt-0.5 font-mono">
                      {km != null && brg != null ? `${Math.round(km)} km ${compass(brg)} (${Math.round(brg)}°)` : '—'}
                    </dd>
                  </div>
                </dl>
              </article>
            )
          })}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          {forecastStatus === 'error'
            ? `Track predictions could not be retrieved: ${forecastError || 'unknown backend error'}. Check that the backend is running and retry.`
            : forecastStatus === 'loading'
              ? 'Waiting for the backend track models to return both horizon predictions.'
              : forecastStatus === 'ready'
                ? `The model outputs latitude and longitude only. Displacement is derived from those coordinates. ${storm.name} is a synthetic sample track; this is model output for illustrative input, not a validated historical prediction or real forecast.`
                : 'No track prediction is available yet.'}
        </p>
      </section>

      <section aria-labelledby="eval-heading" className="mt-20 grid gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <SectionEyebrow index="02">Model evaluation</SectionEyebrow>
          <h2 id="eval-heading" className="mt-3 font-serif text-3xl text-balance">LSTM versus linear extrapolation</h2>
          <DataLabel kind="evaluation" className="mt-4">Preliminary · held-out historical</DataLabel>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Mean great-circle distance between predicted and observed positions on a held-out set of historical storms. These
            are preliminary results, not guaranteed real-world accuracy, and are independent of the three sample storms.
          </p>
        </div>
        <div className="md:col-span-7 md:col-start-6">
          <TrackErrorChart />
          <div className="mt-8">
            <Disclosure title="What is the baseline?">
              The baseline extends each storm&apos;s most recent motion in a straight line at constant speed. Beating it shows the
              LSTM captures some curvature and acceleration in tracks, but it is a simple reference, not an operational model.
            </Disclosure>
            <Disclosure title="Model inputs and outputs">
              {MODEL_SPEC.architecture} over {MODEL_SPEC.sequenceLength} chronological observations at 3-hour intervals with{' '}
              {MODEL_SPEC.featureCount} numerical features (position, wind, time encodings, and motion features). Outputs:{' '}
              {MODEL_SPEC.outputs.join(' and ')}. It does not use satellite imagery and does not predict intensity, rainfall, or
              landfall probability.{' '}
              <Link href="/methodology" className="underline underline-offset-4">
                Full methodology
              </Link>
            </Disclosure>
            <Disclosure title="Limitations">
              The evaluation sample is limited and has not been compared against official agency forecasts. Error grows sharply
              with lead time, so the +48 h position should be read as a broad direction rather than a precise location.
            </Disclosure>
          </div>
        </div>
      </section>

      <section aria-labelledby="series-heading" className="mt-20 grid gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <SectionEyebrow index="03">Observed history · {storm.name}</SectionEyebrow>
          <h2 id="series-heading" className="mt-3 font-serif text-3xl">Wind and pressure</h2>
          <DataLabel kind="sample" className="mt-4" />
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Sample intensity values supplied with the demo storm. They are model inputs, not model outputs.
          </p>
        </div>
        <div className="md:col-span-7 md:col-start-6">
          <ObservationSeriesChart observations={storm.observations} />
        </div>
      </section>

      <div className="mt-14 flex justify-end">
        <Link href="/history" className="inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">
          Inspect the observations in Historical Data
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}
