import { cn } from '@/lib/utils'

export type DataKind = 'sample' | 'observed' | 'prediction' | 'evaluation' | 'evidence' | 'pending'

const STYLES: Record<DataKind, { label: string; swatch: string }> = {
  sample: { label: 'Sample data', swatch: 'border border-foreground bg-transparent' },
  observed: { label: 'Observed', swatch: 'bg-foreground' },
  prediction: { label: 'ML prediction', swatch: 'bg-teal' },
  evaluation: { label: 'Model evaluation', swatch: 'bg-muted-foreground' },
  evidence: { label: 'Web-retrieved evidence', swatch: 'bg-signal' },
  pending: { label: 'Integration pending', swatch: 'border border-dashed border-signal bg-transparent' },
}

export function DataLabel({ kind, children, className }: { kind: DataKind; children?: React.ReactNode; className?: string }) {
  const s = STYLES[kind]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground',
        className,
      )}
    >
      <span aria-hidden="true" className={cn('size-2 shrink-0', s.swatch)} />
      {children ?? s.label}
    </span>
  )
}

export function SectionEyebrow({ index, children }: { index: string; children: React.ReactNode }) {
  return (
    <p className="flex items-baseline gap-3 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
      <span className="text-signal">{index}</span>
      <span>{children}</span>
    </p>
  )
}
