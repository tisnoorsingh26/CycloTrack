/**
 * TinyFish Search is proxied through the Python API so the key never ships to the browser.
 * Results are web snippets, not model outputs.
 */

import { fetchSources, type SourceIntelligenceResponse } from '@/lib/api'

export type { SourceIntelligenceResponse }

export async function retrieveSourceEvidence(stormQuery: string): Promise<SourceIntelligenceResponse> {
  return fetchSources(stormQuery)
}
