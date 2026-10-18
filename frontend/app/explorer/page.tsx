import type { Metadata } from 'next'
import { StormExplorerPage } from '@/components/storm-explorer'

export const metadata: Metadata = { title: 'Storm Explorer' }

export default function Page() {
  return <StormExplorerPage />
}
