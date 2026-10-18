'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { LoaderCircle, MapPinned, Search } from 'lucide-react'
import {
  fetchSources,
  fetchSourceObservations,
  replayIBTracs,
  suggestIBTracsStorms,
  type SourceFetchResponse,
  type SourceIntelligenceResponse,
  type IBTracsStormSuggestion,
} from '@/lib/api'
import { useStorm } from '@/components/storm-context'

export function SourceIntelligencePanel() {
  const router = useRouter()
  const { setLiveForecast } = useStorm()
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchResult, setSearchResult] = useState<SourceIntelligenceResponse | null>(null)
  const [selectedUrls, setSelectedUrls] = useState<string[]>([])
  const [fetchResult, setFetchResult] = useState<SourceFetchResponse | null>(null)
  const [replayName, setReplayName] = useState('')
  const [replaySuggestions, setReplaySuggestions] = useState<IBTracsStormSuggestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionError, setSuggestionError] = useState<string | null>(null)
  const [replayLoading, setReplayLoading] = useState(false)
  const [replayError, setReplayError] = useState<string | null>(null)
  const [replayResult, setReplayResult] = useState<Awaited<ReturnType<typeof replayIBTracs>> | null>(null)
  const replayRequestId = useRef(0)
  const suggestionRequestId = useRef(0)
  const skipSuggestionTerm = useRef<string | null>(null)

  useEffect(() => {
    const term = replayName.trim()
    const requestId = ++suggestionRequestId.current
    if (skipSuggestionTerm.current === term.toLocaleLowerCase()) {
      skipSuggestionTerm.current = null
      setReplaySuggestions([])
      setSuggestionError(null)
      setSuggestionsLoading(false)
      return
    }
    if (term.length < 2) {
      setReplaySuggestions([])
      setSuggestionError(null)
      return
    }
    let current = true
    const timer = window.setTimeout(() => {
      setSuggestionsLoading(true)
      suggestIBTracsStorms(term).then((items) => {
        if (current && requestId === suggestionRequestId.current) { setReplaySuggestions(items); setSuggestionError(null) }
      }).catch((cause: unknown) => {
        if (current && requestId === suggestionRequestId.current) setSuggestionError(cause instanceof Error ? cause.message : 'Storm suggestions are unavailable.')
      }).finally(() => { if (current && requestId === suggestionRequestId.current) setSuggestionsLoading(false) })
    }, 250)
    return () => { current = false; window.clearTimeout(timer) }
  }, [replayName])

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const term = query.trim()
    if (!term) {
      setError('Enter a cyclone name or identifier to search public sources.')
      setSearchResult(null)
      return
    }
    setSearching(true)
    setError(null)
    setFetchResult(null)
    setSelectedUrls([])
    try {
      const result = await fetchSources(term)
      setSearchResult(result)
      if (result.status !== 'ok') setError(result.message || 'No source results were returned.')
    } catch (cause) {
      setSearchResult(null)
      setError(cause instanceof Error ? cause.message : 'Source search failed. Try again later.')
    } finally {
      setSearching(false)
    }
  }

  async function fetchSelected() {
    if (!selectedUrls.length) {
      setError('Select at least one source URL to fetch.')
      return
    }
    setFetching(true)
    setError(null)
    setFetchResult(null)
    try {
      const result = await fetchSourceObservations(query.trim(), selectedUrls)
      setFetchResult(result)
      if (result.status === 'error' || result.status === 'unavailable') {
        setError(result.message || 'Selected sources could not be fetched.')
        return
      }
      if (result.status === 'ok' && result.forecast) {
        const modelRows = result.model_observations
        const mapSource = modelRows[0]
        const latestBasin = modelRows.find((row) => row.basin)?.basin
        setLiveForecast({
          name: mapSource?.cyclone_name || query.trim(),
          code: mapSource?.cyclone_identifier || `WEB-${query.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '-').slice(0, 32)}`,
          basin: latestBasin || 'North Indian Ocean',
          observations: modelRows.map((row) => ({
            time: row.time,
            lat: row.lat,
            lon: row.lon,
            windKt: row.wind,
            pressureHpa: null,
          })),
          forecast: result.forecast.predictions.map((point) => ({
            leadHours: point.horizon_hours,
            time: point.valid_time,
            lat: point.predicted.lat,
            lon: point.predicted.lon,
            source: 'ml_prediction' as const,
          })),
          provenance: {
            classification: modelRows[0]?.classification || 'observed',
            sourceType: mapSource?.source_type || 'public_web',
            sourceUrl: mapSource?.source_url || '',
            sourceTitle: mapSource?.source_title || mapSource?.source_url || 'Retrieved source',
            inputTimes: modelRows.map((row) => row.time),
            validation: result.validation,
            disagreementCount: result.disagreements.length,
          },
        })
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Selected sources could not be fetched.')
    } finally {
      setFetching(false)
    }
  }

  async function runHistoricalReplay(name: string, season?: number, event?: React.FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    const term = name.trim()
    if (!term) {
      setReplayError('Enter a cyclone name.')
      return
    }
    const requestId = ++replayRequestId.current
    suggestionRequestId.current += 1
    setReplayLoading(true)
    setReplayError(null)
    setReplayResult(null)
    setReplaySuggestions([])
    setSuggestionError(null)
    setSuggestionsLoading(false)
    setLiveForecast(null)
    try {
      const result = await replayIBTracs(term, season, 'historical_replay')
      if (requestId !== replayRequestId.current) return
      setReplayResult(result)
      if (result.status === 'needs_selection') setReplaySuggestions([])
      if (result.status === 'ok' && result.cutoffs.length) {
        const selected = result.cutoffs[result.cutoffs.length - 1]
        const used = selected.input_observations
        const actualFuture = selected.results.map((row) => ({ time: row.actual.time, lat: row.actual.lat, lon: row.actual.lon, windKt: 0, pressureHpa: null }))
        const baseline = selected.results.map((row) => ({ leadHours: row.horizon_hours, time: row.constant_velocity.time, lat: row.constant_velocity.lat, lon: row.constant_velocity.lon, source: 'ml_prediction' as const }))
        setLiveForecast({
          name: result.name,
          code: `${result.name.toUpperCase()}-${result.season}`,
          basin: 'North Indian Ocean',
          observations: used.map((row) => ({ time: row.time, lat: row.lat, lon: row.lon, windKt: row.wind, pressureHpa: null })),
          forecast: selected.results.filter((row) => row.horizon_hours === 24 || row.horizon_hours === 48).map((row) => ({
            leadHours: row.horizon_hours, time: row.lstm.time, lat: row.lstm.lat, lon: row.lstm.lon, source: 'ml_prediction' as const,
          })),
          historicalReplay: { actualFuture, baseline },
          provenance: {
            classification: 'historical_best_track', sourceType: 'IBTrACS NOAA/NCEI',
            sourceUrl: result.source_url || '', sourceTitle: `IBTrACS ${result.name} ${result.season}`,
            inputTimes: used.map((row) => row.time), validation: result.validation, disagreementCount: 0,
          },
        })
      }
    } catch (cause) {
      if (requestId === replayRequestId.current && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setReplayError(cause instanceof Error ? cause.message : 'Historical replay request failed.')
      }
    } finally {
      if (requestId === replayRequestId.current) setReplayLoading(false)
    }
  }

  function submitHistoricalReplay(event: React.FormEvent<HTMLFormElement>) {
    void runHistoricalReplay(replayName, undefined, event)
  }

  function chooseReplayStorm(storm: IBTracsStormSuggestion) {
    skipSuggestionTerm.current = storm.name.trim().toLocaleLowerCase()
    setReplayName(storm.name)
    setReplaySuggestions([])
    setReplayError(null)
    setReplayResult(null)
    void runHistoricalReplay(storm.name, storm.season)
  }

  function changeReplayName(value: string) {
    replayRequestId.current += 1
    suggestionRequestId.current += 1
    setReplayLoading(false)
    setReplayError(null)
    setReplayResult(null)
    setSuggestionError(null)
    setReplaySuggestions([])
    setLiveForecast(null)
    setReplayName(value)
  }

  const latest = fetchResult?.observations.at(-1)
  const forecast24 = fetchResult?.forecast?.predictions.find((point) => point.horizon_hours === 24)
  const forecast48 = fetchResult?.forecast?.predictions.find((point) => point.horizon_hours === 48)

  return (
    <div className="mt-6 border border-border p-5">
      <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">TinyFish public source search · cyclone observations</p>
      <form onSubmit={search} className="mt-4 flex flex-col gap-3 sm:flex-row">
        <label htmlFor="cyclone-source-query" className="sr-only">Cyclone name or identifier</label>
        <input
          id="cyclone-source-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          maxLength={100}
          placeholder="Cyclone name or identifier"
          className="min-w-0 flex-1 border border-input bg-background px-3 py-2 text-sm outline-none focus:border-teal"
        />
        <button type="submit" disabled={searching || fetching} className="inline-flex items-center justify-center gap-2 bg-foreground px-4 py-2 text-xs font-medium uppercase tracking-wider text-background transition-colors hover:bg-teal disabled:cursor-not-allowed disabled:opacity-60">
          {searching ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : <Search className="size-4" aria-hidden="true" />}
          {searching ? 'Searching sources' : 'Search Sources'}
        </button>
      </form>

      {searching && <p role="status" className="mt-4 text-sm text-muted-foreground">Searching official and credible meteorological sources for observed or best-track fixes…</p>}
      {error && <p role="alert" className="mt-4 border-l-2 border-destructive pl-3 text-sm text-destructive">{error}</p>}

      {searchResult?.status === 'ok' && (
        <section className="mt-5 border-t border-border pt-4" aria-live="polite">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{searchResult.evidence.length} search result{searchResult.evidence.length === 1 ? '' : 's'} · snippets are unverified until fetched</p>
          {searchResult.evidence.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">No matching source URLs were found. Try the official cyclone name or a different identifier.</p> : (
            <div className="mt-3 space-y-3">
              {searchResult.evidence.map((source) => (
                <label key={source.url} className="flex cursor-pointer gap-3 border border-border p-3">
                  <input type="checkbox" checked={selectedUrls.includes(source.url)} onChange={(event) => setSelectedUrls((current) => event.target.checked ? [...current, source.url] : current.filter((url) => url !== source.url))} className="mt-1 size-4 accent-[var(--teal)]" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{source.title || source.publisher}</span>
                    <span className="mt-1 block break-all text-xs text-teal underline">{source.url}</span>
                    {source.excerpt && <span className="mt-2 block text-xs leading-relaxed text-muted-foreground">{source.excerpt}</span>}
                    <span className="mt-2 block font-mono text-[10px] uppercase text-muted-foreground">{source.publisher}{source.published_date ? ` · published ${source.published_date}` : ''} · search result not verified</span>
                  </span>
                </label>
              ))}
            </div>
          )}
          {searchResult.evidence.length > 0 && (
            <button type="button" onClick={fetchSelected} disabled={fetching || selectedUrls.length === 0} className="mt-4 inline-flex items-center justify-center gap-2 bg-foreground px-4 py-2 text-xs font-medium uppercase tracking-wider text-background hover:bg-teal disabled:cursor-not-allowed disabled:opacity-50">
              {fetching && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
              {fetching ? 'Fetching and validating' : `Fetch Selected Sources (${selectedUrls.length})`}
            </button>
          )}
        </section>
      )}

      {fetching && <p role="status" className="mt-4 text-sm text-muted-foreground">Fetching selected pages, extracting explicitly labeled observations, and checking timestamps, units, identity, and 3-hour spacing…</p>}
      {fetchResult && (
        <section className="mt-5 border-t border-border pt-4" aria-live="polite">
          <p className={`font-mono text-[11px] uppercase tracking-wider ${fetchResult.status === 'ok' ? 'text-teal' : 'text-signal'}`}>
            {fetchResult.status === 'ok' ? 'Observations validated · LSTM forecast complete' : fetchResult.status === 'insufficient_data' ? 'Insufficient or incompatible observations' : 'Source fetch unavailable'}
          </p>
          {fetchResult.message && <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{fetchResult.message}</p>}
          {fetchResult.validation.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">{fetchResult.validation.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
          {fetchResult.imd_reference_status && <p className="mt-2 text-xs text-muted-foreground">IMD reference: {fetchResult.imd_reference_status}. IMD credentials are optional for this web-source workflow.</p>}
          {fetchResult.sources.map((source, index) => (
            <details key={`${source.url}-${index}`} className="mt-3 border border-border p-3">
              <summary className="cursor-pointer text-xs font-medium">{source.title || source.url} · {source.source_type || 'public source'} · {source.status}</summary>
              {source.message && <p className="mt-2 text-xs text-destructive">{source.message}</p>}
              {(source.extraction_notes || []).map((note) => <p key={note} className="mt-2 text-xs text-signal">{note}</p>)}
              {(source.evidence || source.preview) && <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-muted-foreground">{source.evidence || source.preview}</pre>}
              <a href={source.final_url || source.url} target="_blank" rel="noopener noreferrer" className="mt-3 block break-all text-xs text-teal underline">{source.final_url || source.url}</a>
            </details>
          ))}
          {fetchResult.observations.length > 0 && (
            <>
              <div className="mt-4 grid gap-3 border-y border-border py-3 text-sm sm:grid-cols-3">
                <div><p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Latest observation (UTC)</p><p className="mt-1">{latest && new Date(latest.time).toISOString().replace('T', ' ').replace('.000Z', ' UTC')}</p></div>
                <div><p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Position and wind</p><p className="mt-1">{latest?.lat.toFixed(2)}°, {latest?.lon.toFixed(2)}° · {latest?.wind.toFixed(1)} kt</p></div>
                <div><p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Extracted fixes</p><p className="mt-1">{fetchResult.observations.length}</p></div>
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[900px] text-left text-xs">
                  <thead><tr className="border-b border-border font-mono uppercase text-muted-foreground"><th className="py-2">Cyclone ID</th><th>Time (UTC)</th><th>Latitude</th><th>Longitude</th><th>Wind</th><th>Record type</th><th>Source type</th><th>Source</th></tr></thead>
                  <tbody>{fetchResult.observations.map((row, index) => <tr key={`${row.time}-${index}`} className="border-b border-border/60"><td className="py-2">{row.cyclone_identifier || row.cyclone_name || fetchResult.storm_query}</td><td>{new Date(row.time).toISOString()}</td><td>{row.lat.toFixed(2)}</td><td>{row.lon.toFixed(2)}</td><td>{row.wind_original} ({row.wind.toFixed(1)} kt)</td><td>{row.classification}</td><td>{row.source_type}</td><td><a href={row.source_url} target="_blank" rel="noopener noreferrer" className="text-teal underline">{row.source_title || new URL(row.source_url).hostname}</a></td></tr>)}</tbody>
                </table>
              </div>
            </>
          )}
          {fetchResult.disagreements.length > 0 && (
            <section className="mt-5 border-l-2 border-signal pl-4" aria-label="Cross-source disagreements">
              <h3 className="font-mono text-[11px] uppercase tracking-wider text-signal">Source disagreements · exact matching timestamps</h3>
              <ul className="mt-2 space-y-2 text-xs text-muted-foreground">
                {fetchResult.disagreements.map((item, index) => <li key={`${item.time}-${index}`}>{new Date(item.time).toISOString()} · positions differ by {item.position_difference_km} km; wind differs by {item.wind_difference_kt} kt. <a className="text-teal underline" href={item.source_a} target="_blank" rel="noopener noreferrer">Source A</a> · <a className="text-teal underline" href={item.source_b} target="_blank" rel="noopener noreferrer">Source B</a></li>)}
              </ul>
            </section>
          )}
          {fetchResult.status === 'ok' && fetchResult.forecast && (
            <>
              <details className="mt-4 border border-border p-3">
                <summary className="cursor-pointer text-xs font-medium">Exact 9 observations used for both LSTM forecasts</summary>
                <ol className="mt-3 space-y-1 font-mono text-[11px] text-muted-foreground">
                  {fetchResult.model_observations.map((row, index) => <li key={`${row.time}-${index}`}>{index + 1}. {new Date(row.time).toISOString()} · {row.lat.toFixed(3)}, {row.lon.toFixed(3)} · {row.wind.toFixed(1)} kt · {row.cyclone_identifier}</li>)}
                </ol>
                <p className="mt-2 text-xs text-muted-foreground">Single source: {fetchResult.model_observations[0]?.source_title || fetchResult.model_observations[0]?.source_url}. Historical records are model replay inputs, not current observations.</p>
              </details>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {[{ label: '24-hour forecast', point: forecast24 }, { label: '48-hour forecast', point: forecast48 }].map(({ label, point }) => <div key={label} className="border border-border p-4"><p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label} · existing LSTM</p><p className="mt-2 font-serif text-2xl">{point ? `${point.predicted.lat.toFixed(2)}°, ${point.predicted.lon.toFixed(2)}°` : 'Unavailable'}</p>{point && <p className="mt-1 text-xs text-muted-foreground">{new Date(point.valid_time).toISOString().replace('T', ' ').replace('.000Z', ' UTC')}</p>}</div>)}
              </div>
              <button type="button" onClick={() => router.push('/explorer')} className="mt-4 inline-flex items-center gap-2 border border-foreground px-4 py-2 text-xs font-medium uppercase tracking-wider hover:border-teal"><MapPinned className="size-4" />View on storm map</button>
            </>
          )}
        </section>
      )}

      <section className="mt-8 border-t border-border pt-5" aria-labelledby="historical-replay-title">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="historical-replay-title" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Historical replay</h2>
          <span className="border border-signal px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-signal">Historical replay, not live</span>
        </div>
        <form onSubmit={submitHistoricalReplay} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="replay-name">Cyclone name</label>
          <input id="replay-name" value={replayName} onChange={(event) => changeReplayName(event.target.value)} maxLength={100} autoComplete="off" placeholder="Type any cyclone name" aria-autocomplete="list" aria-controls="replay-storm-suggestions" className="min-w-0 flex-1 border border-input bg-background px-3 py-2 text-sm outline-none focus:border-teal" />
          <button type="submit" disabled={replayLoading} className="inline-flex items-center justify-center gap-2 bg-foreground px-4 py-2 text-xs font-medium uppercase tracking-wider text-background hover:bg-teal disabled:opacity-60">
            {replayLoading && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}{replayLoading ? 'Running replay' : 'Run Historical Replay'}
          </button>
        </form>
        {suggestionsLoading && <p role="status" className="mt-2 text-xs text-muted-foreground">Finding matching IBTrACS cyclone names…</p>}
        {suggestionError && <p role="status" className="mt-2 text-xs text-signal">Autocomplete unavailable: {suggestionError}</p>}
        {replaySuggestions.length > 0 && <ul id="replay-storm-suggestions" role="listbox" aria-label="Cyclone name suggestions" className="mt-2 max-h-56 overflow-auto border border-border">{replaySuggestions.slice(0, 20).map((storm) => <li key={`${storm.name}-${storm.season}`}><button type="button" role="option" aria-selected="false" onClick={() => chooseReplayStorm(storm)} className="flex w-full justify-between px-3 py-2 text-left text-sm hover:bg-muted"><span>{storm.name} ({storm.season})</span><span className="text-xs text-muted-foreground">{storm.basin} · {storm.rows} rows</span></button></li>)}</ul>}
        {replayLoading && <p role="status" className="mt-3 text-sm text-muted-foreground">Running… Loading the archived IBTrACS track and evaluating every qualifying cutoff.</p>}
        {replayError && <p role="alert" className="mt-3 border-l-2 border-destructive pl-3 text-sm text-destructive">{replayError}</p>}
        {replayResult && <div className="mt-4 space-y-4" aria-live="polite">
          {replayResult.message && <p className="text-sm text-muted-foreground">{replayResult.message}</p>}
          {replayResult.status === 'needs_selection' && <div role="status" className="space-y-2"><p className="text-sm">Choose which season to replay:</p>{replayResult.season_options.map((storm) => <button key={`${storm.name}-${storm.season}`} type="button" onClick={() => chooseReplayStorm(storm as IBTracsStormSuggestion)} className="mr-2 border border-border px-3 py-2 text-sm hover:border-teal">{storm.name} ({storm.season})</button>)}</div>}
          {replayResult.status === 'not_found' && <div role="status" className="space-y-2"><p className="text-sm">No exact match. Try one of these names:</p>{replayResult.suggestions.map((storm) => <button key={`${storm.name}-${storm.season}`} type="button" onClick={() => chooseReplayStorm(storm as IBTracsStormSuggestion)} className="mr-2 border border-border px-3 py-2 text-sm hover:border-teal">{storm.name} ({storm.season})</button>)}</div>}
          {replayResult.status === 'insufficient_data' && <section role="alert" className="border-l-2 border-signal pl-3 text-sm"><h3 className="font-medium">This storm has IBTrACS rows, but no forecast cutoff passed validation.</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">{Object.entries(replayResult.rejection_reasons).map(([reason, count]) => <li key={reason}>{reason}: {count} window(s)</li>)}</ul></section>}
          {replayResult.status === 'ok' && <>
          <div className="grid gap-3 border border-border p-3 text-xs sm:grid-cols-2">
            <p><span className="font-mono uppercase text-muted-foreground">Result status</span><br />{replayResult.cache_status === 'cached' ? 'Cached · served from cache after live retrieval failed' : 'Live · retrieved for this request'}</p>
            {replayResult.cache_status === 'cached' && replayResult.message && <p className="sm:col-span-2 text-signal">{replayResult.message}</p>}
            <p><span className="font-mono uppercase text-muted-foreground">Retrieval path</span><br />{replayResult.retrieval_path || 'Unavailable'}</p>
            <p><span className="font-mono uppercase text-muted-foreground">Source</span><br />{replayResult.source_url ? <a href={replayResult.source_url} target="_blank" rel="noopener noreferrer" className="break-all text-teal underline">{replayResult.source_url}</a> : 'Unavailable'}</p>
            <p><span className="font-mono uppercase text-muted-foreground">Cutoffs / input flags</span><br />{replayResult.cutoff_count} cutoffs; {replayResult.cutoffs.map((cutoff) => `${cutoff.interpolated_count}/9`).join(', ') || 'no valid input windows'}</p>
            <p><span className="font-mono uppercase text-muted-foreground">Training overlap</span><br />{replayResult.training_overlap_label}</p>
            {replayResult.cached_result_from && <p className="sm:col-span-2"><strong>Cached result from {new Date(replayResult.cached_result_from).toISOString()}</strong></p>}
          </div>
          {replayResult.training_overlap_warning && <p role="note" className="border-l-2 border-signal pl-3 text-xs text-signal">{replayResult.training_overlap_warning}</p>}
          {replayResult.cutoffs.some((cutoff) => cutoff.quality === 'approximate_input') && <p role="alert" className="border-l-2 border-signal pl-3 text-xs text-signal">{replayResult.cutoffs.filter((cutoff) => cutoff.quality === 'approximate_input').length} of {replayResult.cutoff_count} cutoffs use more than 2 flagged/interpolated inputs (approximate); {replayResult.cutoffs.filter((cutoff) => cutoff.quality === 'validated_input').length} are validated.</p>}
          {replayResult.validation.length > 0 && <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{replayResult.validation.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] text-left text-xs">
              <thead><tr className="border-b border-border font-mono uppercase text-muted-foreground"><th className="py-2">Horizon</th><th>LSTM mean / median km</th><th>Constant velocity mean / median km</th><th>Cutoffs</th></tr></thead>
              <tbody>{([24, 48] as const).map((horizon) => {
                const lstm = replayResult.summary[`lstm_${horizon}h`]
                const baseline = replayResult.summary[`constant_velocity_${horizon}h`]
                return <tr key={horizon} className="border-b border-border/60"><td className="py-2">{horizon} h</td><td>{lstm ? `${lstm.mean_km.toFixed(1)} / ${lstm.median_km.toFixed(1)}` : '—'}</td><td>{baseline ? `${baseline.mean_km.toFixed(1)} / ${baseline.median_km.toFixed(1)}` : '—'}</td><td>{replayResult.cutoff_count}</td></tr>
              })}</tbody>
            </table>
          </div>
          {replayResult.cutoffs.flatMap((cutoff) => cutoff.warnings.filter((warning) => !/approximate_input|more than 2 flagged|interpolated input/i.test(warning))).map((warning, index) => <p key={`${warning}-${index}`} className="text-xs text-signal">{warning}</p>)}
          {replayResult.status === 'ok' && <><p className="text-xs text-muted-foreground">The existing map now shows the latest qualifying cutoff: input observations, actual +24 h/+48 h IBTrACS fixes, LSTM forecast, and constant-velocity baseline.</p><button type="button" onClick={() => router.push('/explorer')} className="inline-flex items-center gap-2 border border-foreground px-4 py-2 text-xs font-medium uppercase tracking-wider hover:border-teal"><MapPinned className="size-4" />View historical replay on map</button></>}
          </>}
        </div>}
      </section>
      <p className="mt-4 text-xs text-muted-foreground">Search results are web leads, not verified observations. Only fetched, explicitly labeled observed, analyzed, or best-track rows are considered. Forecast-only content, missing wind units, stale or irregularly spaced fixes, and unconfirmed cyclone identity are rejected; no observations are fabricated or silently interpolated.</p>
    </div>
  )
}
