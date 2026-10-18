import type { Metadata } from 'next'
import { WindEstimator } from '@/components/wind-estimator'

export const metadata: Metadata = {
  title: 'Satellite Wind Estimator · CycloTrack',
  description: 'AI-assisted tropical cyclone intensity and sustained wind speed estimation from multi-spectral satellite imagery.',
}

export default function Page() {
  return <WindEstimator />
}
