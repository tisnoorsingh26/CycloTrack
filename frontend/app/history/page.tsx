import type { Metadata } from 'next'
import { HistoricalData } from '@/components/historical-data'

export const metadata: Metadata = { title: 'Historical Data' }

export default function Page() {
  return <HistoricalData />
}
