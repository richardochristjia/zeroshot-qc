import { useCallback, useEffect, useRef, useState } from 'react'
import type { JSX } from 'react'
import {
  ApiError,
  inspectImage,
  listProfiles,
  resolveFileUrl,
} from '../api.ts'
import type { Detection, InspectionResult, ProductProfile } from '../api.ts'

type Status = 'idle' | 'loading-profiles' | 'ready' | 'inspecting' | 'done'

function formatSize(det: Detection): string {
  const px = `${det.areaPx} px`
  if (det.areaMm2 !== null) return `${px} (${det.areaMm2.toFixed(1)} mm²)`
  return px
}

interface HoverBoxProps {
  detection: Detection
  naturalWidth: number
  naturalHeight: number
}

function HoverBox({ detection, naturalWidth, naturalHeight }: HoverBoxProps): JSX.Element | null {
  if (naturalWidth <= 0 || naturalHeight <= 0) return null
  const [x, y, w, h] = detection.bbox
  const left = (x / naturalWidth) * 100
  const top = (y / naturalHeight) * 100
  const width = (w / naturalWidth) * 100
  const height = (h / naturalHeight) * 100
  return (
    <div
      tabIndex={0}
      aria-label={`${detection.id} ${detection.label} ${formatSize(detection)}`}
      className="group absolute border-2 border-amber-400 outline-none focus:border-amber-600"
      style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
    >
      <span className="pointer-events-none absolute left-0 top-0 hidden whitespace-nowrap bg-neutral-900 px-1.5 py-0.5 text-xs text-white group-hover:block group-focus:block">
        {detection.id} · {detection.label} · {formatSize(detection)}
      </span>
    </div>
  )
}

export default function Inspect(): JSX.Element {
  const [profiles, setProfiles] = useState<ProductProfile[]>([])
  const [profileId, setProfileId] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [result, setResult] = useState<InspectionResult | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 })
  const [rulesText, setRulesText] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)
  const debounceRef = useRef<number | null>(null)
  const fileRef = useRef<File | null>(null)
  fileRef.current = file
  const profileRef = useRef<string>('')
  profileRef.current = profileId

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading-profiles')
    listProfiles(controller.signal)
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length > 0) setProfileId(loaded[0].id)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof ApiError ? err.detail : 'Could not load profiles.')
        setStatus('ready')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      if (previewUrl !== null) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  // Structured so the debounced rules edit plugs in: it will call this same
  // runner with (fileRef.current, profileId, editedRules). Empty/omitted
  // rules fall back to the profile rules on both ends (api.ts omits empty
  // `rules`; inspect.py sends None when falsy), so clearing restores them.
  const runInspect = useCallback(
    async (image: File, activeProfileId: string, rules?: string): Promise<void> => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setStatus('inspecting')
      setError(null)
      try {
        const inspection = await inspectImage({
          image,
          filename: image.name,
          profileId: activeProfileId,
          rules,
          signal: controller.signal,
        })
        setResult(inspection)
        setNaturalSize({ w: 0, h: 0 })
        setStatus('done')
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setResult(null)
        setStatus('ready')
        setError(err instanceof ApiError ? err.detail : 'Inspection failed.')
      }
    },
    [],
  )

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    const picked = event.target.files?.item(0) ?? null
    if (previewUrl !== null) URL.revokeObjectURL(previewUrl)
    setResult(null)
    setError(null)
    setNaturalSize({ w: 0, h: 0 })
    if (picked === null) {
      setFile(null)
      setPreviewUrl(null)
      return
    }
    setFile(picked)
    setPreviewUrl(URL.createObjectURL(picked))
  }

  const currentRules = rulesText.trim() === '' ? undefined : rulesText

  // Debounced judge-only re-run: re-posts the same in-memory image bytes
  // with edited rules (~500ms). Empty rules are omitted so the backend
  // restores profile rules. A new keystroke aborts the stale in-flight
  // request so it can never overwrite the newer verdict.
  useEffect(() => {
    if (result === null || fileRef.current === null || profileRef.current === '') return
    abortRef.current?.abort()
    if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
    const trimmed = rulesText.trim()
    debounceRef.current = window.setTimeout(() => {
      const image = fileRef.current
      const activeProfileId = profileRef.current
      if (image === null || activeProfileId === '') return
      void runInspect(image, activeProfileId, trimmed === '' ? undefined : rulesText)
    }, 500)
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rulesText])

  const handleSubmit = (): void => {
    if (file === null || profileId === '') return
    void runInspect(file, profileId, currentRules)
  }

  const shownImage = result?.overlayUrl ?? previewUrl
  const verdict = result?.verdict ?? null

  return (
    <section aria-label="Inspect">
      <h1 className="text-xl font-semibold">Inspect</h1>
      <p className="mt-2 text-sm">Upload an image and pick a profile to run an inspection.</p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Profile
          <select
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm"
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name} ({profile.id})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Image
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="text-sm"
          />
        </label>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={file === null || profileId === '' || status === 'inspecting'}
          className="rounded bg-neutral-900 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
        >
          {status === 'inspecting' ? 'Inspecting…' : 'Inspect'}
        </button>
      </div>

      {error !== null && (
        <p role="alert" className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}

      {shownImage === null || shownImage === undefined ? (
        <div className="mt-6 rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500">
          No image yet. Choose an image file above, then press Inspect.
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h2 className="text-sm font-semibold">Overlay</h2>
            <div className="relative mt-2 inline-block max-w-full">
              <img
                src={resolveFileUrl(shownImage)}
                alt={result !== null ? `Inspection overlay for ${result.profileId}` : 'Uploaded image preview'}
                className="block max-w-full"
                onLoad={(event) => {
                  const img = event.currentTarget
                  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                    setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
                  }
                }}
              />
              {result !== null &&
                result.detections.map((det) => (
                  <HoverBox
                    key={det.id}
                    detection={det}
                    naturalWidth={naturalSize.w}
                    naturalHeight={naturalSize.h}
                  />
                ))}
            </div>
            {result !== null && result.detections.length === 0 && (
              <p className="mt-2 text-sm text-neutral-500">
                No defects detected. The overlay shows the original image unmarked.
              </p>
            )}
          </div>

          <div>
            <h2 className="text-sm font-semibold">Verdict</h2>
            {verdict === null || result === null ? (
              <p className="mt-2 text-sm text-neutral-500">
                Press Inspect to get a verdict with per-detection reasons.
              </p>
            ) : (
              <div className="mt-2 rounded border border-neutral-300 px-4 py-3">
                <div className="flex items-baseline gap-3">
                  <span
                    className={`text-lg font-bold ${verdict.verdict === 'PASS' ? 'text-green-700' : 'text-red-700'}`}
                  >
                    {verdict.verdict}
                  </span>
                  <span className="text-sm text-neutral-600">
                    confidence {(verdict.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="mt-1 text-sm">{verdict.summary}</p>
                {verdict.rulings.length > 0 ? (
                  <ul className="mt-3 space-y-2">
                    {verdict.rulings.map((ruling) => (
                      <li key={ruling.detectionId} className="rounded bg-neutral-100 px-2 py-1.5 text-sm">
                        <span className="font-medium">{ruling.detectionId}</span>
                        {' — '}
                        {ruling.isRealDefect ? 'defect' : 'not a defect'}
                        {ruling.ruleViolated !== null && ` (rule: ${ruling.ruleViolated})`}
                        <span className="block text-neutral-700">{ruling.reason}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-neutral-500">No rulings: nothing was detected.</p>
                )}
                {verdict.missedDefects.length > 0 && (
                  <p className="mt-2 text-sm text-neutral-600">
                    Missed defects: {verdict.missedDefects.join(', ')}
                  </p>
                )}
                {status === 'inspecting' && rulesText.trim() !== '' && (
                  <p role="status" className="mt-2 text-sm text-neutral-500">
                    Re-judging with edited rules…
                  </p>
                )}
                <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-neutral-600">
                  <div>
                    <dt className="font-medium">Segment</dt>
                    <dd>{result.timingsMs.segment.toFixed(0)} ms</dd>
                  </div>
                  <div>
                    <dt className="font-medium">Judge</dt>
                    <dd>{result.timingsMs.judge.toFixed(0)} ms</dd>
                  </div>
                  <div>
                    <dt className="font-medium">Total</dt>
                    <dd>{result.timingsMs.total.toFixed(0)} ms</dd>
                  </div>
                </dl>
              </div>
            )}
          </div>
        </div>
      )}

      {file !== null && (
        <div className="mt-6">
          <label htmlFor="inspect-rules" className="text-sm font-semibold">
            Rules override
          </label>
          <textarea
            id="inspect-rules"
            value={rulesText}
            onChange={(event) => setRulesText(event.target.value)}
            rows={4}
            placeholder="Edit rules in plain English to re-judge the same image…"
            className="mt-2 block w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-neutral-500">
            Edits re-judge the same image after a short pause; segment results are reused so
            re-runs stay fast. Clearing the box restores the profile rules.
          </p>
        </div>
      )}
    </section>
  )
}
