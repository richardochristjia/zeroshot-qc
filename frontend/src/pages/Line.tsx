import { useCallback, useEffect, useRef, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, inspectImage, listProfiles, referenceImageUrl } from '../api.ts'
import type { InspectionResult, ProductProfile } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { Button } from '../components/Button.tsx'
import { Icon } from '../components/Icon.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'
import { VerdictBadge } from '../components/VerdictBadge.tsx'
import { FRAME_H, FRAME_W, HOLD_MS, arm, idleState, pause, step, toGray } from '../line-trigger.ts'
import type { Phase, TriggerState } from '../line-trigger.ts'

const SAMPLE_MS = 100
const MUTE_KEY = 'zqc-line-mute'
const RIBBON_MAX = 40
const THUMBS_MAX = 8

type CamState = { kind: 'starting' } | { kind: 'live' } | { kind: 'error'; title: string; body: string }

interface Entry {
  n: number
  verdict: 'PASS' | 'FAIL'
  result: InspectionResult
  thumbUrl: string | null
}

const STATUS_TEXT: Record<Phase | 'inspecting', string> = {
  idle: 'Paused. Press Arm with the tray empty.',
  armed: 'Watching for a part',
  settling: 'Part found. Hold still…',
  'waiting-clear': 'Done. Remove the part.',
  inspecting: 'Inspecting part',
}

const DOT: Record<Phase | 'inspecting', string> = {
  idle: 'bg-[#a3a6ad]',
  armed: 'bg-[#63caa1]',
  settling: 'bg-[#f3b852]',
  'waiting-clear': 'bg-[#a3a6ad]',
  inspecting: 'bg-[#9dbce3] animate-pulse',
}

function cameraError(err: unknown): CamState {
  const name = err instanceof DOMException ? err.name : ''
  if (name === 'NotAllowedError') {
    return { kind: 'error', title: 'Camera blocked', body: 'The browser was refused camera access. Allow it in the address bar, then try again.' }
  }
  if (name === 'NotFoundError') return { kind: 'error', title: 'No camera found.', body: 'Connect a camera, then try again.' }
  return { kind: 'error', title: 'Camera failed to start', body: 'Another app may be using it. Close it and try again.' }
}

function readMuted(): boolean {
  try {
    return window.localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false
  }
}

function toBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
}

export default function Line(): JSX.Element {
  const [profiles, setProfiles] = useState<ProductProfile[]>([])
  const [profileId, setProfileId] = useState('')
  const [cam, setCam] = useState<CamState>({ kind: 'starting' })
  const [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState<Phase>('idle')
  const [busyN, setBusyN] = useState<number | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [selectedN, setSelectedN] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ghost, setGhost] = useState(true)
  const [refFailedUrl, setRefFailedUrl] = useState<string | null>(null)
  const [muted, setMuted] = useState(readMuted)
  const [flashKey, setFlashKey] = useState(0)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const sampleRef = useRef<HTMLCanvasElement | null>(null)
  const triggerRef = useRef<TriggerState>(idleState())
  const busyRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const audioRef = useRef<AudioContext | null>(null)
  const nextNRef = useRef(1)
  const entriesRef = useRef<Entry[]>([])
  const profileRef = useRef('')
  const mutedRef = useRef(muted)
  useEffect(() => {
    entriesRef.current = entries
    profileRef.current = profileId
    mutedRef.current = muted
  })

  useEffect(() => {
    const controller = new AbortController()
    listProfiles(controller.signal)
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length > 0) setProfileId(loaded[0].id)
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof ApiError ? err.detail : 'Could not load profiles.')
      })
    return () => controller.abort()
  }, [])

  const setTrigger = useCallback((next: TriggerState): void => {
    triggerRef.current = next
    setPhase(next.phase)
  }, [])

  /** Grab a 64x48 grayscale frame, or null while the video has no picture. */
  const sampleFrame = useCallback((): Uint8Array | null => {
    const video = videoRef.current
    if (video === null || video.readyState < 2 || video.videoWidth === 0) return null
    const canvas = (sampleRef.current ??= Object.assign(document.createElement('canvas'), { width: FRAME_W, height: FRAME_H }))
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (ctx === null) return null
    ctx.drawImage(video, 0, 0, FRAME_W, FRAME_H)
    return toGray(ctx.getImageData(0, 0, FRAME_W, FRAME_H).data)
  }, [])

  const ensureAudio = (): void => {
    try {
      audioRef.current ??= new AudioContext()
      void audioRef.current.resume()
    } catch {
      // No Web Audio: the tone is simply skipped.
    }
  }

  const beep = (): void => {
    const ctx = audioRef.current
    if (ctx === null || mutedRef.current) return
    for (const offset of [0, 0.28]) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'square'
      osc.frequency.value = 880
      gain.gain.value = 0.12
      osc.connect(gain).connect(ctx.destination)
      osc.start(ctx.currentTime + offset)
      osc.stop(ctx.currentTime + offset + 0.18)
    }
  }

  const capture = useCallback(async (): Promise<void> => {
    const video = videoRef.current
    const activeProfile = profileRef.current
    if (busyRef.current || video === null || video.videoWidth === 0 || activeProfile === '') return
    busyRef.current = true
    const n = nextNRef.current
    setBusyN(n)
    setError(null)
    setSelectedN(null)
    setFlashKey((k) => k + 1)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      canvas.getContext('2d')?.drawImage(video, 0, 0)
      const blob = await toBlob(canvas)
      if (blob === null) throw new Error('Could not capture the frame.')
      const result = await inspectImage({ image: blob, filename: `line-${n}.jpg`, profileId: activeProfile, signal: controller.signal })
      nextNRef.current = n + 1
      const thumbUrl = URL.createObjectURL(blob)
      setEntries((prev) => {
        // Only the last THUMBS_MAX thumbnails are shown; free the older blobs.
        const kept = prev.map((e, i) => {
          if (e.thumbUrl !== null && i < prev.length - (THUMBS_MAX - 1)) {
            URL.revokeObjectURL(e.thumbUrl)
            return { ...e, thumbUrl: null }
          }
          return e
        })
        return [...kept, { n, verdict: result.verdict.verdict, result, thumbUrl }]
      })
      if (result.verdict.verdict === 'FAIL') beep()
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof ApiError ? err.detail : err instanceof Error ? err.message : 'Inspection failed.')
      if (triggerRef.current.phase !== 'idle') setTrigger({ ...triggerRef.current, phase: 'waiting-clear' })
    } finally {
      if (abortRef.current === controller) {
        busyRef.current = false
        setBusyN(null)
      }
    }
  }, [setTrigger])

  // Camera stream and sampling loop. Restarts on profile change; cleanup
  // stops the tracks, the timer and any in-flight request.
  useEffect(() => {
    const video = videoRef.current
    let cancelled = false
    let stream: MediaStream | null = null
    let timer: number | null = null
    const start = async (): Promise<void> => {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setCam({
          kind: 'error',
          title: 'Camera needs a secure address',
          body: 'Open this page over https (localhost also works). Browsers block the camera on plain http.',
        })
        return
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        if (video !== null) {
          video.srcObject = stream
          await video.play().catch(() => undefined)
        }
        setCam({ kind: 'live' })
        timer = window.setInterval(() => {
          if (triggerRef.current.phase === 'idle') return
          const frame = sampleFrame()
          if (frame === null) return
          const out = step(triggerRef.current, frame, performance.now())
          triggerRef.current = out.state
          setPhase((p) => (p === out.state.phase ? p : out.state.phase))
          if (out.capture) void capture()
        }, SAMPLE_MS)
      } catch (err: unknown) {
        if (!cancelled) setCam(cameraError(err))
      }
    }
    void start()
    return () => {
      cancelled = true
      if (timer !== null) window.clearInterval(timer)
      stream?.getTracks().forEach((t) => t.stop())
      if (video !== null) video.srcObject = null
      abortRef.current?.abort()
      abortRef.current = null
      busyRef.current = false
      setBusyN(null)
      setTrigger(pause())
    }
  }, [attempt, profileId, capture, sampleFrame, setTrigger])

  const releaseAll = useCallback((): void => {
    void audioRef.current?.close()
    entriesRef.current.forEach((e) => e.thumbUrl !== null && URL.revokeObjectURL(e.thumbUrl))
  }, [])
  useEffect(() => releaseAll, [releaseAll])

  const live = cam.kind === 'live'
  const inspecting = busyN !== null
  const profile = profiles.find((p) => p.id === profileId) ?? null
  const refUrl = profile?.referenceImage ? referenceImageUrl(profile.referenceImage) : null
  const refMissing = refUrl === null || refFailedUrl === refUrl
  const shownPhase: Phase | 'inspecting' = inspecting ? 'inspecting' : phase

  const toggleArm = (): void => {
    if (phase !== 'idle') {
      setTrigger(pause())
      return
    }
    ensureAudio()
    const frame = sampleFrame()
    if (frame !== null) setTrigger(arm(frame))
  }

  const captureNow = (): void => {
    ensureAudio()
    void capture()
  }

  const toggleMute = (value: boolean): void => {
    setMuted(value)
    try {
      window.localStorage.setItem(MUTE_KEY, value ? '1' : '0')
    } catch {
      // Storage blocked: the choice lasts for this page view only.
    }
  }

  const reset = (): void => {
    entries.forEach((e) => e.thumbUrl !== null && URL.revokeObjectURL(e.thumbUrl))
    setEntries([])
    setSelectedN(null)
    setError(null)
    nextNRef.current = 1
  }

  const total = entries.length
  const fails = entries.filter((e) => e.verdict === 'FAIL').length
  const passes = total - fails
  const yieldText = total === 0 ? '—' : `${((passes / total) * 100).toFixed(1)}%`
  const last = entries.length > 0 ? entries[entries.length - 1] : null
  const shown = (selectedN !== null ? entries.find((e) => e.n === selectedN) : undefined) ?? last
  const ribbon = entries.slice(-RIBBON_MAX)
  const thumbs = entries.slice(-THUMBS_MAX).reverse()

  const verdictTone = inspecting || shown === null ? 'bg-sunken' : shown.verdict === 'PASS' ? 'bg-pass-tint' : 'bg-fail-tint'
  const firstViolated = shown?.result.verdict.rulings.find((r) => r.ruleViolated)?.ruleViolated ?? null

  return (
    <section aria-label="Line">
      <PageHeader title="Line" subtitle="Point a camera at the line. Each part is inspected once.">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <select className="ctl w-auto!" aria-label="Profile" value={profileId} onChange={(event) => setProfileId(event.target.value)}>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
          <label className="inline-flex min-h-9 items-center gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              className="accent-accent"
              checked={ghost && !refMissing}
              disabled={refMissing}
              title={refMissing ? 'No reference image for this profile' : undefined}
              onChange={(event) => setGhost(event.target.checked)}
            />
            Reference ghost
          </label>
          <label className="inline-flex min-h-9 items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" className="accent-accent" checked={muted} onChange={(event) => toggleMute(event.target.checked)} />
            Mute
          </label>
          <Button icon="camera" onClick={captureNow} disabled={!live || profileId === '' || inspecting}>
            Capture now
          </Button>
          <Button variant="primary" icon={phase === 'idle' ? 'play' : 'pause'} onClick={toggleArm} disabled={!live || profileId === ''}>
            {phase === 'idle' ? 'Arm' : 'Pause'}
          </Button>
        </div>
      </PageHeader>

      <div className="grid items-start gap-4 grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] max-[860px]:grid-cols-1">
        <div className="relative aspect-[4/3] overflow-hidden rounded-md bg-[#26272b]">
          <video ref={videoRef} poster="data:image/gif;base64,R0lGODlhAQABAAAAACw=" muted playsInline aria-label="Camera feed" className="absolute inset-0 h-full w-full object-cover" />
          {refUrl !== null && ghost && !refMissing && (
            <img
              src={refUrl}
              alt=""
              onError={() => setRefFailedUrl(refUrl)}
              className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-30"
            />
          )}
          {live && (
            <>
              <div
                role="status"
                aria-live="polite"
                className="absolute left-3 top-3 flex items-center gap-2 rounded-sm bg-[#111214]/80 px-2.5 py-1.5 text-sm font-medium text-[#ebeae6]"
              >
                <span className={`h-2 w-2 rounded-full ${DOT[shownPhase]}`} />
                {shownPhase === 'inspecting' ? `${STATUS_TEXT.inspecting} ${busyN}…` : STATUS_TEXT[shownPhase]}
              </div>
              <div className="absolute inset-x-0 bottom-0 h-1 bg-white/10">
                {shownPhase === 'settling' && (
                  <div className="h-full bg-[#f3b852]" style={{ animation: `line-hold ${HOLD_MS}ms linear infinite` }} />
                )}
              </div>
            </>
          )}
          <div
            key={flashKey}
            className="pointer-events-none absolute inset-0 bg-white opacity-0"
            style={flashKey > 0 ? { animation: 'line-flash 250ms ease-out' } : undefined}
          />
          {cam.kind === 'error' && (
            <div className="absolute inset-0 grid place-content-center justify-items-center gap-3 bg-sunken p-6 text-center text-ink">
              <Icon name="camera" className="!h-6 !w-6 text-ink-3" />
              <h2 className="text-base! text-ink!">{cam.title}</h2>
              <p className="max-w-[42ch] text-sm text-ink-2">{cam.body}</p>
              <Button icon="refresh" onClick={() => {
                  setCam({ kind: 'starting' })
                  setAttempt((a) => a + 1)
                }}>
                Try again
              </Button>
            </div>
          )}
          {cam.kind === 'starting' && <div className="absolute inset-0 grid place-content-center bg-sunken text-sm text-ink-2">Starting camera…</div>}
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          {error !== null && <Alert>{error}</Alert>}
          <div aria-live="polite" className={`grid min-h-28 content-start gap-2 rounded-md p-5 ${verdictTone}`}>
            {inspecting ? (
              <>
                <p className="text-[28px] font-medium leading-none text-ink-3">Inspecting…</p>
                {last !== null && (
                  <p className="text-sm text-ink-2">
                    Last result: {last.verdict} (part {last.n})
                  </p>
                )}
              </>
            ) : shown === null ? (
              <>
                <p className="text-[28px] font-medium leading-none text-ink-3">No part yet</p>
                <p className="text-sm text-ink-2">Press Arm with the tray empty, then place a part.</p>
              </>
            ) : (
              <>
                <VerdictBadge verdict={shown.verdict} size={64} />
                <p className="num flex flex-wrap gap-x-4 text-sm text-ink-2">
                  <span>Part {shown.n}</span>
                  <span>Confidence {shown.result.verdict.confidence.toFixed(2)}</span>
                  <span>{(shown.result.timingsMs.total / 1000).toFixed(1)} s</span>
                </p>
                <p className="max-w-[60ch] text-base">{shown.result.verdict.summary}</p>
                {shown.verdict === 'FAIL' && firstViolated !== null && (
                  <p className="text-sm text-ink-2">
                    Rule: <q className="text-ink">{firstViolated}</q>
                  </p>
                )}
              </>
            )}
          </div>

          <Panel aria-label="This session">
            <PanelHeader title="This session">
              <Button icon="refresh" className="min-h-8" onClick={reset} disabled={total === 0 && error === null}>
                Reset
              </Button>
            </PanelHeader>
            <div className="grid gap-4 p-4">
              <dl className="num grid grid-cols-2 gap-3">
                {(
                  [
                    ['Parts', String(total), ''],
                    ['Pass', String(passes), 'text-pass'],
                    ['Fail', String(fails), 'text-fail'],
                    ['Yield', yieldText, ''],
                  ] as const
                ).map(([label, value, tone]) => (
                  <div key={label} className="grid gap-0.5">
                    <dt className="text-[13px] text-ink-2">{label}</dt>
                    <dd className={`m-0 text-[26px] font-medium leading-tight ${tone}`}>{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="grid gap-1.5">
                <h2>Last {RIBBON_MAX} parts</h2>
                {ribbon.length === 0 ? (
                  <p className="text-sm text-ink-3">No parts yet.</p>
                ) : (
                <div
                  role="img"
                  aria-label={`Last ${ribbon.length} parts: ${ribbon.filter((e) => e.verdict === 'FAIL').length} fail, ${ribbon.filter((e) => e.verdict === 'PASS').length} pass. Tall bars are fails.`}
                  className="flex h-7 items-end gap-[3px]"
                >
                  {ribbon.map((e) => (
                    <i key={e.n} className={`block max-w-3.5 flex-1 rounded-[2px] ${e.verdict === 'FAIL' ? 'h-full bg-fail' : 'h-[55%] bg-pass'}`} />
                  ))}
                </div>
                )}
                <div className="flex justify-between text-[13px] text-ink-3">
                  <span>older</span>
                  <span>latest</span>
                </div>
                <h2 className="mt-2.5">Latest captures</h2>
                {thumbs.length === 0 ? (
                  <p className="text-sm text-ink-3">Captured parts appear here.</p>
                ) : (
                  <div className="grid grid-cols-4 gap-2">
                    {thumbs.map((e) => (
                      <button
                        key={e.n}
                        type="button"
                        aria-label={`Part ${e.n}: ${e.verdict}`}
                        aria-current={shown?.n === e.n ? 'true' : undefined}
                        onClick={() => setSelectedN(e.n)}
                        className={`relative aspect-square overflow-hidden rounded-sm bg-[#26272b] p-0 ${shown?.n === e.n ? 'outline-2 outline-offset-2 outline-ink' : ''}`}
                      >
                        {e.thumbUrl !== null && <img src={e.thumbUrl} alt="" className="h-full w-full object-cover" />}
                        <span
                          className={`absolute bottom-1 left-1 rounded-[3px] bg-surface px-1.5 text-xs font-semibold ${e.verdict === 'PASS' ? 'text-pass' : 'text-fail'}`}
                        >
                          {e.n} {e.verdict}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </section>
  )
}
