export function Disclosure({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="group border-t border-border last:border-b" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-3.5 text-sm font-medium">
        {title}
        <span aria-hidden="true" className="font-mono text-muted-foreground transition-transform group-open:rotate-45">
          +
        </span>
      </summary>
      <div className="max-w-prose pb-4 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </details>
  )
}
