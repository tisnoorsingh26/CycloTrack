import type { Metadata } from 'next'
import { ForecastAnalysis } from '@/components/forecast-analysis'

export const metadata: Metadata = { title: 'Forecast Analysis' }

export default function Page() {
  return <ForecastAnalysis />
}
