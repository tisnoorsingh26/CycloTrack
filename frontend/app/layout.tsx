import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono, Instrument_Serif } from 'next/font/google'
import { StormProvider } from '@/components/storm-context'
import { SiteFooter, SiteHeader } from '@/components/site-header'
import './globals.css'

const geist = Geist({ subsets: ['latin'], variable: '--font-geist' })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono' })
const instrumentSerif = Instrument_Serif({ subsets: ['latin'], weight: '400', style: ['normal', 'italic'], variable: '--font-instrument-serif' })

export const metadata: Metadata = {
  title: {
    default: 'CycloTrack — Reading the path of a storm',
    template: '%s · CycloTrack',
  },
  description:
    'An experimental ML research tool for exploring tropical cyclone tracks and 24-hour / 48-hour LSTM track predictions. Not an official warning service.',
  generator: 'v0.app',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#f2f0eb',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable} ${instrumentSerif.variable}`}>
      <body className="min-h-dvh antialiased">
        <StormProvider>
          <SiteHeader />
          <main>{children}</main>
          <SiteFooter />
        </StormProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
