'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, Search } from 'lucide-react'
import { useStorm } from '@/components/storm-context'
import { StormMap } from '@/components/storm-map'
import { ObservationSeriesChart } from '@/components/charts'
import { DataLabel } from '@/components/data-label'
import { STORMS, formatLat, formatLon, formatTime, type StormId } from '@/lib/storms'
import { cn } from '@/lib/utils'

type Filter = StormId | 'all'

const ROWS = STORMS.flatMap((s) => s.observations.map((o) => ({ ...o, stormId: s.id, stormName: s.name, code: s.code, basin: s.basin })))

export function HistoricalData() {
  const { storm, setStormId } = useStorm()
  const [filter, setFilter] = useState<Filter>(storm.id)
  const [query, setQuery] = useState('')

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return ROWS.filter(
      (r) =>
        (filter === 'all' || r.stormId === filter) &&
        (!q || [r.stormName, r.code, r.basin, formatTime(r.time)].some((v) => v.toLowerCase().includes(q))),
    )
  }, [filter, query])

  const choose = (f: Filter) => {
    setFilter(f)
    if (f !== 'all') setStormId(f)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8">
      <header className="flex flex-col gap-3 pt-8 md:flex-row md:items-end md:justify-between md:pt-12">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Historical Data</p>
          <h1 className="mt-2 font-serif text-4xl md:text-5xl">Observation records</h1>
        </div>
        <DataLabel kind="sample">Sample observations · {ROWS.length} records · not real historical data</DataLabel>
      </header>

      <div className="mt-8 grid gap-10 lg:grid-cols-12">
        <section aria-labelledby="table-heading" className="min-w-0 lg:col-span-7">
          <h2 id="table-heading" className="sr-only">
            Observation table
          </h2>
          <div className="flex flex-col gap-3 border-y border-border py-3 sm:flex-row sm:items-center sm:justify-between">
            <div role="group" aria-label="Filter by storm" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
              {(['all', ...STORMS.map((s) => s.id)] as Filter[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={filter === f}
                  onClick={() => choose(f)}
                  className={cn(
                    'border-b-2 py-1 capitalize transition-colors',
                    filter === f ? 'border-signal text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}
                >
                  {f === 'all' ? 'All storms' : f}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 border-b border-input pb-1 sm:w-56">
              <Search className="size-4 text-muted-foreground" aria-hidden="true" />
              <span className="sr-only">Search records</span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name, ID, date"
                className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
            </label>
          </div>

          <div className="max-h-[560px] overflow-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <caption className="sr-only">Synthetic sample storm observations, recorded at 3-hour intervals</caption>
              <thead className="sticky top-0 bg-background font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 font-normal">Storm</th>
                  <th scope="col" className="py-2 font-normal">Time (UTC)</th>
                  <th scope="col" className="py-2 font-normal">Lat</th>
                  <th scope="col" className="py-2 font-normal">Lon</th>
                  <th scope="col" className="py-2 text-right font-normal">Wind kt</th>
                  <th scope="col" className="py-2 text-right font-normal">hPa</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r) => (
                  <tr
                    key={`${r.stormId}-${r.time}`}
                    onClick={() => setStormId(r.stormId)}
                    className={cn('cursor-pointer border-b border-border/70 hover:bg-muted', r.stormId === storm.id && filter === 'all' && 'bg-muted/60')}
                  >
                    <td className="py-2 font-sans">
                      {r.stormName} <span className="font-mono text-[11px] text-muted-foreground">{r.code}</span>
                    </td>
                    <td className="py-2">{formatTime(r.time)}</td>
                    <td className="py-2">{formatLat(r.lat)}</td>
                    <td className="py-2">{formatLon(r.lon)}</td>
                    <td className="py-2 text-right">{r.windKt}</td>
                    <td className="py-2 text-right">{r.pressureHpa}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">No records match your search.</p>}
          </div>
        </section>

        <aside className="flex flex-col gap-8 lg:col-span-5">
          <figure>
            <figcaption className="flex items-baseline justify-between border-b border-border pb-2">
              <span className="font-serif text-2xl">{storm.name}</span>
              <span className="font-mono text-xs text-muted-foreground">{storm.observations.length} observations</span>
            </figcaption>
            <StormMap storm={storm} compact className="mt-3" />
          </figure>
          <ObservationSeriesChart observations={storm.observations} />
          <Link href="/explorer" className="inline-flex items-center gap-2 self-start text-sm font-medium underline-offset-4 hover:underline">
            Open {storm.name} in Storm Explorer
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </aside>
      </div>
    </div>
  )
}
