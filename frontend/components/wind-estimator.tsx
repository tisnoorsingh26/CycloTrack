
'use client'

import { useState, useRef } from 'react'
import {
  Upload,
  FileUp,
  FileText,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Info,
  Layers,
  Sparkles,
} from 'lucide-react'
import { predictWind, type WindPredictResponse } from '@/lib/api'
import { DataLabel, SectionEyebrow } from '@/components/data-label'
import { Disclosure } from '@/components/disclosure'
import { MODEL_SPEC } from '@/lib/evaluation'
import { cn } from '@/lib/utils'

function imdCategory(knots: number): { label: string; tone: string } {
  if (knots < 28) return { label: 'Low Pressure Area / Depression', tone: 'text-muted-foreground' }
  if (knots < 34) return { label: 'Deep Depression', tone: 'text-foreground' }
  if (knots < 48) return { label: 'Cyclonic Storm (CS)', tone: 'text-teal' }
  if (knots < 64) return { label: 'Severe Cyclonic Storm (SCS)', tone: 'text-teal' }
  if (knots < 90) return { label: 'Very Severe Cyclonic Storm (VSCS)', tone: 'text-signal' }
  if (knots < 120) return { label: 'Extremely Severe Cyclonic Storm (ESCS)', tone: 'text-signal' }
  return { label: 'Super Cyclonic Storm (SuCS)', tone: 'text-signal' }
}

export function WindEstimator() {
  const [file, setFile] = useState<File | null>(null)
  const [isSyntheticSample, setIsSyntheticSample] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<WindPredictResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (selected: File, isSample = false) => {
    setFile(selected)
    setIsSyntheticSample(isSample)
    setError(null)
    setResult(null)
    setLoading(true)

    try {
      const response = await predictWind(selected)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Wind estimation request failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0], false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0], false)
    }
  }

  const loadSyntheticSample = async () => {
    setError(null)
    setResult(null)
    setFile(null)
    setIsSyntheticSample(false)
    setLoading(true)

    try {
      const res = await fetch('/sample_chips/synthetic_chip_128x128x4.npy')

      if (!res.ok) {
        throw new Error('Could not fetch sample chip file from server.')
      }

      const blob = await res.blob()
      const sampleFile = new File(
        [blob],
        'synthetic_chip_128x128x4.npy',
        { type: 'application/octet-stream' },
      )

      setFile(sampleFile)
      setIsSyntheticSample(true)

      const response = await predictWind(sampleFile)
      setResult(response)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load synthetic test chip.',
      )
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setResult(null)
    setError(null)
    setIsSyntheticSample(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="mx-auto max-w-7xl px-4 md:px-8">
      <header className="pt-8 md:pt-12">
        <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          CNN Intensity Estimator
        </p>
        <h1 className="mt-2 font-serif text-4xl text-balance md:text-5xl">
          Estimate cyclone wind speed from <em className="text-teal">satellite chips.</em>
        </h1>
        <p className="mt-4 max-w-3xl leading-relaxed text-muted-foreground">
          Upload a 4-channel 128×128 satellite image chip to predict maximum sustained wind speed
          in knots. The prediction is computed by the Huber-loss trained CNN checkpoint (held-out test
          MAE 11.75 kt).
        </p>
      </header>

      {/* Constraints Notice Banner */}
      <aside
        aria-label="CNN Input Constraints"
        className="mt-8 border-l-2 border-signal bg-ocean/40 p-5 text-sm"
      >
        <div className="flex items-start gap-3">
          <Info className="mt-0.5 size-5 shrink-0 text-signal" aria-hidden="true" />
          <div className="space-y-1 text-muted-foreground">
            <p className="font-medium text-foreground">
              Required Input Tensor: Exactly (128, 128, 4) Float32 or UInt8
            </p>
            <p>
              This model was trained on 4-channel satellite arrays from Kaggle&apos;s Cyclone Image
              Dataset. <strong>Standard 3-channel RGB photographs are strictly rejected</strong>{' '}
              because the network requires the 4th auxiliary sensor band (infrared / water vapor / microwave).
              The API will not synthesize a fourth channel, silently resize arbitrary images, or claim an ordinary image has been scientifically analyzed.
            </p>
          </div>
        </div>
      </aside>

      <div className="mt-10 grid gap-10 lg:grid-cols-12">
        {/* Main Upload / Results Area */}
        <section aria-labelledby="uploader-heading" className="lg:col-span-7">
          <h2 id="uploader-heading" className="sr-only">
            Image Upload & Inference
          </h2>

          {!result && !loading && (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={cn(
                'relative flex flex-col items-center justify-center border-2 border-dashed p-10 text-center transition-colors',
                isDragging
                  ? 'border-teal bg-teal/5'
                  : 'border-border hover:border-muted-foreground/60',
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".npy,.npz,.png,.tif,.tiff"
                onChange={handleFileChange}
                className="sr-only"
                aria-label="Upload 4-channel satellite file"
              />

              <div className="flex size-14 items-center justify-center rounded-full bg-ocean">
                <FileUp className="size-7 text-muted-foreground" aria-hidden="true" />
              </div>

              <h3 className="mt-4 font-serif text-2xl">Upload satellite chip</h3>

              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Drag and drop your file here, or click to browse. Supported formats:
                <code className="mx-1 font-mono text-xs">.npy</code>,
                <code className="mx-1 font-mono text-xs">.npz</code>, or 4-channel
                <code className="mx-1 font-mono text-xs">.png</code> /
                <code className="mx-1 font-mono text-xs">.tiff</code> (shape 128×128×4).
              </p>

              <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-foreground px-5 py-2.5 text-xs font-medium uppercase tracking-wider text-background transition-colors hover:bg-teal"
                >
                  Browse Files
                </button>

                <button
                  type="button"
                  onClick={loadSyntheticSample}
                  className="flex items-center gap-2 border border-border bg-ocean px-4 py-2.5 font-mono text-xs text-muted-foreground transition-colors hover:border-teal hover:text-foreground"
                >
                  <Sparkles className="size-3.5 text-signal" aria-hidden="true" />
                  Load Sample Synthetic Chip
                </button>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="flex flex-col items-center justify-center border border-border p-14 text-center">
              <RefreshCw className="size-8 animate-spin text-teal" aria-hidden="true" />
              <p className="mt-4 font-serif text-2xl">Running CNN inference...</p>
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                Parsing 128×128×4 array · normalizing by 255 · computing forward pass
              </p>
              {file && (
                <p className="mt-4 font-mono text-xs text-muted-foreground">File: {file.name}</p>
              )}
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="border border-destructive/50 bg-destructive/10 p-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden="true" />
                <div className="space-y-2">
                  <h3 className="font-medium text-destructive">Inference / Validation Error</h3>
                  <p className="text-sm text-destructive/90">{error}</p>
                  <button
                    type="button"
                    onClick={reset}
                    className="mt-3 inline-flex items-center gap-2 bg-destructive px-4 py-2 text-xs font-medium text-destructive-foreground hover:bg-destructive/90"
                  >
                    Try Another File
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Successful Prediction Display */}
          {result && !loading && (
            <div className="border border-border p-6 md:p-8">
              <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-border pb-4">
                <div>
                  <SectionEyebrow index="RESULT">Model Inference Complete</SectionEyebrow>
                  <h3 className="mt-2 font-serif text-3xl">Estimated Sustained Wind</h3>
                </div>

                {isSyntheticSample ? (
                  <DataLabel kind="sample">Synthetic test tensor · not real satellite data</DataLabel>
                ) : (
                  <DataLabel kind="prediction">ML Prediction</DataLabel>
                )}
              </div>

              {/* Intensity Hero Number */}
              <div className="mt-8 grid gap-6 sm:grid-cols-2">
                <div className="border-b border-border pb-6 sm:border-b-0 sm:border-r sm:pr-6">
                  <p className="font-mono text-xs text-muted-foreground uppercase tracking-wider">
                    Maximum Sustained Wind
                  </p>
                  <div className="mt-2 flex items-baseline gap-3">
                    <span className="font-mono text-5xl font-semibold text-teal md:text-6xl">
                      {result.predicted_wind_knots.toFixed(1)}
                    </span>
                    <span className="font-mono text-xl text-muted-foreground">knots</span>
                  </div>
                  <p className="mt-2 font-mono text-sm text-muted-foreground">
                    ≈ {(result.predicted_wind_knots * 1.852).toFixed(1)} km/h
                  </p>
                </div>

                <div className="sm:pl-2">
                  <p className="font-mono text-xs text-muted-foreground uppercase tracking-wider">
                    Illustrative IMD Classification
                  </p>
                  {(() => {
                    const cat = imdCategory(result.predicted_wind_knots)
                    return (
                      <>
                        <p className={cn('mt-2 font-serif text-2xl font-medium', cat.tone)}>
                          {cat.label}
                        </p>
                        <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
                          Categorization mapped from predicted knots using Indian Meteorological
                          Department wind scales. For official warnings, consult your national meteorological agency.
                        </p>
                      </>
                    )
                  })()}
                </div>
              </div>

              {/* Input & Preprocessing Metadata */}
              <dl className="mt-8 grid grid-cols-2 gap-4 border-t border-border pt-6 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted-foreground">Input Tensor Shape</dt>
                  <dd className="mt-1 font-mono text-foreground">
                    {result.input_shape.join(' × ')}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Preprocessing</dt>
                  <dd className="mt-1 font-mono text-xs text-foreground">
                    {result.preprocessing}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Source File</dt>
                  <dd className="mt-1 truncate font-mono text-xs text-foreground" title={file?.name}>
                    {file?.name || 'Uploaded chip'}
                  </dd>
                </div>
              </dl>

              {/* Notes from Backend */}
              {result.notes && result.notes.length > 0 && (
                <div className="mt-6 border-t border-border pt-4">
                  <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    Model & Channel Notes
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
                    {result.notes.map((note, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span aria-hidden="true" className="mt-1 size-1 shrink-0 bg-signal" />
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-8 flex gap-4 border-t border-border pt-6">
                <button
                  type="button"
                  onClick={reset}
                  className="bg-foreground px-5 py-2.5 text-xs font-medium uppercase tracking-wider text-background transition-colors hover:bg-teal"
                >
                  Upload Another File
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Methodology & Model Architecture Sidebar */}
        <section aria-labelledby="specs-heading" className="lg:col-span-5">
          <SectionEyebrow index="SPECS">Model Architecture</SectionEyebrow>
          <h2 id="specs-heading" className="mt-2 font-serif text-2xl">
            Huber Loss CNN
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            The wind estimation model uses a convolutional neural network retrained with Huber loss
            (delta = 10.0) to resist outliers and extreme intensity spikes.
          </p>

          <div className="mt-6 space-y-3">
            <Disclosure title="Input channels & dimensions" defaultOpen>
              The model requires an exact tensor of shape <code className="font-mono">128×128×4</code>.
              Unlike consumer photographs with 3 channels (RGB), cyclone imagery uses satellite sensors
              capturing distinct thermal, visible, and infrared bands. Because channel semantics were not
              formally documented in the source dataset, supplying a fake fourth channel or an ordinary photo
              is mathematically invalid.
            </Disclosure>

            <Disclosure title="Held-out evaluation metrics">
              Evaluated on 4,228 unseen cyclone images from Kaggle&apos;s Cyclone Image Dataset:
              <ul className="mt-2 list-disc pl-5 space-y-1">
                <li>
                  <strong>MAE</strong>: {MODEL_SPEC.cnn.testMae} knots (vs. 14.90 knots on earlier MSE model)
                </li>
                <li>
                  <strong>RMSE</strong>: {MODEL_SPEC.cnn.testRmse} knots (vs. 19.94 knots on earlier MSE model)
                </li>
                <li>
                  <strong>Best Validation MAE</strong>: 12.01 knots at epoch 18
                </li>
              </ul>
            </Disclosure>

            <Disclosure title="Scientific disclaimer">
              This model was developed for research and hackathon experimentation. It has not been
              calibrated against real-time operational weather agency protocols. Never rely on this
              tool for emergency evacuation or life-safety decisions.
            </Disclosure>
          </div>
        </section>
      </div>
    </div>
  )
}
