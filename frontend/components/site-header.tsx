'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useStorm } from '@/components/storm-context'
import { cn } from '@/lib/utils'

export const NAV = [
  { href: '/', label: 'Overview' },
  { href: '/explorer', label: 'Storm Explorer' },
  { href: '/forecast', label: 'Forecast Analysis' },
  { href: '/intensity', label: 'Wind Estimator' },
  { href: '/history', label: 'Historical Data' },
  { href: '/methodology', label: 'Methodology & Sources' },
]

export function SiteHeader() {
  const pathname = usePathname()
  const { storm } = useStorm()

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 pt-4 md:flex-row md:items-end md:justify-between md:gap-8 md:px-8 md:pt-5">
        <div className="flex items-baseline justify-between gap-4 md:pb-3.5">
          <Link
            href="/"
            className="text-3xl font-semibold tracking-[0.18em] text-foreground"
            style={{ fontFamily: 'Footlight MT Light, Footlight MT, serif' }}
          >
            CycloTrack
          </Link>
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground md:hidden">
            {storm.name} · sample
          </p>
        </div>
        <nav aria-label="Primary" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
          <ul className="flex min-w-max gap-5 text-sm md:gap-7">
            {NAV.map((item) => {
              const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'block border-b-2 pb-3 pt-1 transition-colors',
                      active
                        ? 'border-signal font-medium text-foreground'
                        : 'border-transparent text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-muted-foreground md:flex-row md:justify-between md:px-8">
        <p>CycloTrack is an experimental research tool. It is not an official warning service.</p>
        <p className="font-mono">Storms shown are illustrative samples, not live systems.</p>
      </div>
    </footer>
  )
}
