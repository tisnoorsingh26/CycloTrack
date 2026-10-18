/** Held-out historical evaluation copied from cyclone-project-hackathon-path-predictor.ipynb. */

export type EvaluationRow = {
  leadHours: 24 | 48
  lstmKm: number
  baselineKm: number
}

export const EVALUATION: EvaluationRow[] = [
  { leadHours: 24, lstmKm: 140.7, baselineKm: 206.5 },
  { leadHours: 48, lstmKm: 323.5, baselineKm: 448.2 },
]

export function improvementPct(row: EvaluationRow) {
  return ((row.baselineKm - row.lstmKm) / row.baselineKm) * 100
}

export function meanErrorAtLead(leadHours: number) {
  const [e24, e48] = EVALUATION
  if (leadHours <= 24) return (leadHours / 24) * e24.lstmKm
  return e24.lstmKm + ((leadHours - 24) / 24) * (e48.lstmKm - e24.lstmKm)
}

export const MODEL_SPEC = {
  architecture: 'LSTM (displacement)',
  sequenceLength: 8,
  featureCount: 11,
  stepHours: 3,
  outputs: ['24-hour Δlat/Δlon', '48-hour Δlat/Δlon'],
  baseline: 'Persist latest observed velocity',
  cnn: {
    input: '128×128×4',
    output: 'wind speed (knots)',
    testMae: 11.75,
    testRmse: 16.32,
  },
}
