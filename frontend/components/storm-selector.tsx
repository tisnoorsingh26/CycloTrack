'use client'

import { useStorm } from '@/components/storm-context'
import { STORMS, formatLat, formatLon, latestObservation } from '@/lib/storms'
import { cn } from '@/lib/utils'

export function StormSelector({ dense = false, className }: { dense?: boolean; className?: string }) {
  const { stormId, setStormId } = useStorm()

  return (
    <fieldset className={cn('min-w-0', className)}>
      <legend className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
        Select storm · sample data
      </legend>
      <div role="radiogroup" className="border-t border-border">
        {STORMS.map((s) => {
          const active = s.id === stormId
          const last = latestObservation(s)
          return (
            <button
              key={s.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setStormId(s.id)}
              className={cn(
                'group flex w-full items-baseline justify-between gap-4 border-b border-border text-left transition-colors',
                dense ? 'py-2.5' : 'py-4',
                active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <span className="flex items-baseline gap-3">
                <span
                  aria-hidden="true"
                  className={cn('size-2 shrink-0 translate-y-[-1px] border border-foreground', active && 'bg-signal border-signal')}
                />
                <span className={cn('font-serif', dense ? 'text-xl' : 'text-2xl md:text-3xl')}>{s.name}</span>
                <span className="text-sm">{s.basin}</span>
              </span>
              {!dense && (
                <span className="hidden font-mono text-xs sm:inline">
                  {formatLat(last.lat)} {formatLon(last.lon)}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
