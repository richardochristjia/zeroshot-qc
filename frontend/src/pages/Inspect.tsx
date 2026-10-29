import { useCallback, useEffect, useRef, useState } from 'react'
import type { DragEvent, JSX } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ApiError, inspectImage, listProfiles, referenceImageUrl, resolveFileUrl } from '../api.ts'
import type { Detection, DefectRuling, InspectionResult, ProductProfile } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { Button } from '../components/Button.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { Field } from '../components/Field.tsx'
import { Icon } from '../components/Icon.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'
import { VerdictBadge } from '../components/VerdictBadge.tsx'
import { boxPercent } from '../geometry.ts'

type Status = 'idle' | 'loading-profiles' | 'ready' | 'inspecting' | 'done'

function formatSize(det: Detection): string {
  return det.areaMm2 !== null ? `${det.areaMm2.toFixed(1)} mm²` : `${det.areaPx} px`
}

const DETECT_TEXT = 'text-[#18181a]'
const HIGHLIGHT = 'shadow-[0_0_0_3px_color-mix(in_srgb,var(--ink)_35%,transparent)]'

interface BoxProps {
  detection: Detection
  index: number
  real: boolean
  highlighted: boolean
  naturalWidth: number
  naturalHeight: number
  onHover: (id: string | null) => void
}

function DetectionBox({ detection, index, real, highlighted, naturalWidth, naturalHeight, onHover }: BoxProps): JSX.Element | null {
  const pos = boxPercent(detection.bbox, naturalWidth, naturalHeight)
  if (pos === null) return null
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      tabIndex={0}
      aria-label={`${index}: ${detection.label}, ${real ? 'defect' : 'cleared'}`}
      onPointerEnter={() => onHover(detection.id)}
      onPointerLeave={() => onHover(null)}
      onFocus={() => onHover(detection.id)}
      onBlur={() => onHover(null)}
      className={`absolute rounded-[2px] border-2 transition-shadow ${real ? 'border-fail' : 'border-detect'} ${highlighted ? HIGHLIGHT : ''}`}
      style={{ left: `${pos.left}%`, top: `${pos.top}%`, width: `${pos.width}%`, height: `${pos.height}%` }}
    >
      <span
        className={`absolute -left-0.5 -top-[22px] h-5 min-w-5 rounded-t-[2px] px-1.5 font-mono text-xs font-semibold leading-5 ${real ? 'bg-fail text-on-fail' : `bg-detect ${DETECT_TEXT}`}`}
      >
        {index}
      </span>
    </motion.div>
  )
}

function basename(path: string): string {
  return path.split('/').pop() ?? path
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
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [refFailedUrl, setRefFailedUrl] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const debounceRef = useRef<number | null>(null)
  const fileRef = useRef<File | null>(null)
  fileRef.current = file
  const profileRef = useRef<string>('')
  profileRef.current = profileId
  const inputRef = useRef<HTMLInputElement | null>(null)

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

  const pickFile = (picked: File | null): void => {
    if (previewUrl !== null) URL.revokeObjectURL(previewUrl)
    setResult(null)
    setError(null)
    setHoveredId(null)
    setNaturalSize({ w: 0, h: 0 })
    if (picked === null) {
      setFile(null)
      setPreviewUrl(null)
      return
    }
    setFile(picked)
    setPreviewUrl(URL.createObjectURL(picked))
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    pickFile(event.target.files?.item(0) ?? null)
    event.target.value = ''
  }

  const dropProps = {
    onDragOver: (event: DragEvent) => {
      event.preventDefault()
      setDragOver(true)
    },
    onDragLeave: () => setDragOver(false),
    onDrop: (event: DragEvent) => {
      event.preventDefault()
      setDragOver(false)
      const dropped = event.dataTransfer.files.item(0)
      if (dropped !== null && dropped.type.startsWith('image/')) pickFile(dropped)
      else setError('Drop an image file (PNG or JPG).')
    },
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

  const profile = profiles.find((p) => p.id === profileId) ?? null
  const shownImage = result?.overlayUrl ?? previewUrl
  const verdict = result?.verdict ?? null
  const rulingById = new Map<string, DefectRuling>(verdict?.rulings.map((r) => [r.detectionId, r]) ?? [])
  const inspecting = status === 'inspecting'
  const refUrl = profile?.referenceImage ? referenceImageUrl(profile.referenceImage) : null
  const refMissing = refUrl === null || refFailedUrl === refUrl
  const refTitle = refUrl === null ? 'No reference set for this profile' : `Reference image not found: ${profile?.referenceImage}`

  const submitLabel = inspecting ? 'Inspecting…' : result !== null ? 'Inspect again' : 'Inspect'
  const submit = (
    <Button variant="primary" icon="scan" onClick={handleSubmit} disabled={file === null || profileId === '' || inspecting}>
      {submitLabel}
    </Button>
  )

  const hiddenInput = (
    <input ref={inputRef} type="file" accept="image/*" aria-label="Image file" onChange={handleFileChange} className="sr-only" />
  )

  return (
    <section aria-label="Inspect">
      <PageHeader title="Inspect" subtitle="Segment candidates, then judge them against the profile rules.">
        <div className="grid items-end gap-3 grid-cols-[minmax(180px,240px)_minmax(0,1fr)_auto] max-[1000px]:grid-cols-1">
          <Field label="Profile">
            <select className="ctl" value={profileId} onChange={(event) => setProfileId(event.target.value)}>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id})
                </option>
              ))}
            </select>
          </Field>
          <div className="flex min-w-0 flex-col gap-1 text-[13px] font-medium text-ink-2">
            Image
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              {...dropProps}
              className={`flex min-h-9 min-w-0 items-center gap-2.5 rounded-md border border-dashed px-2.5 py-1 text-left text-[13px] font-normal text-ink-2 ${dragOver ? 'border-accent bg-sunken' : 'border-line-strong bg-surface'}`}
            >
              {previewUrl !== null && file !== null ? (
                <>
                  <img src={previewUrl} alt="" className="h-7 w-7 rounded-[3px] object-cover" />
                  <span className="min-w-0 truncate">
                    <b className="font-medium text-ink">{file.name}</b>
                    {naturalSize.w > 0 && <span className="num"> · {naturalSize.w}×{naturalSize.h}</span>}
                  </span>
                </>
              ) : (
                <>
                  <Icon name="upload" />
                  Drop an image or click to choose
                </>
              )}
            </button>
            {hiddenInput}
          </div>
          {submit}
        </div>
      </PageHeader>

      <AnimatePresence>
        {error !== null && (
          <motion.div key="err" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="mb-4">
            <Alert>{error}</Alert>
          </motion.div>
        )}
      </AnimatePresence>

      {file === null ? (
        <div className="grid gap-4 grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)] max-[1000px]:grid-cols-1">
          <div {...dropProps}>
          <EmptyState
            icon="upload"
            title="Drop a part photo here"
            className={`h-full min-h-72 justify-center ${dragOver ? 'border-accent bg-sunken' : ''}`}
            action={
              <Button icon="upload" onClick={() => inputRef.current?.click()}>
                Choose file
              </Button>
            }
          >
            PNG or JPG. It is judged against the selected profile.
          </EmptyState>
          </div>
          <Panel>
            <PanelHeader title={profile?.name ?? 'Profile'} />
            <div className="flex flex-col gap-3 p-3.5 text-sm">
              {profile === null ? (
                <p className="text-ink-2">{status === 'loading-profiles' ? 'Loading profiles…' : 'No profiles found.'}</p>
              ) : (
                <>
                  <div>
                    <h2>Rules</h2>
                    <p className="mt-1 whitespace-pre-wrap">{profile.rules || 'No rules set.'}</p>
                  </div>
                  <div>
                    <h2>Looks for</h2>
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {profile.defectPrompts.map((prompt) => (
                        <li key={prompt} className="rounded-full border border-line-strong px-2 py-0.5 text-xs text-ink-2">
                          {prompt}
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              )}
              <div>
                <Button variant="primary" icon="scan" disabled>
                  Inspect
                </Button>
              </div>
            </div>
          </Panel>
        </div>
      ) : (
        <div className="grid items-start gap-4 grid-cols-[minmax(0,2fr)_minmax(340px,0.95fr)] max-[1000px]:grid-cols-1">
          <div>
            <div className="grid items-start gap-3 grid-cols-2 max-[640px]:grid-cols-1">
              <Panel aria-label="Reference">
                <PanelHeader title={<><Icon name="check" />Reference</>}>
                  {profile?.referenceImage && <span className="mono truncate text-ink-3">{basename(profile.referenceImage)}</span>}
                </PanelHeader>
                <div className="bg-sunken">
                  {refMissing ? (
                    <EmptyState icon="file" title={refTitle} className="m-3" />
                  ) : (
                    <img
                      src={refUrl}
                      alt={`Reference for ${profile?.name ?? 'profile'}`}
                      className="block h-auto w-full"
                      onError={() => setRefFailedUrl(refUrl)}
                    />
                  )}
                </div>
              </Panel>
              <Panel aria-label="Under test">
                <PanelHeader title={<><Icon name="scan" />Under test</>}>
                  {result !== null && (
                    <span className="num text-xs text-ink-2">
                      {result.detections.length} candidate{result.detections.length === 1 ? '' : 's'}
                    </span>
                  )}
                </PanelHeader>
                <div className="relative bg-sunken">
                  {shownImage !== null && shownImage !== undefined && (
                    <img
                      src={resolveFileUrl(shownImage)}
                      alt={result !== null ? `Inspection overlay for ${result.profileId}` : 'Uploaded image preview'}
                      className="block h-auto w-full"
                      onLoad={(event) => {
                        const img = event.currentTarget
                        if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                          setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight })
                        }
                      }}
                    />
                  )}
                  {result !== null &&
                    result.detections.map((det, i) => (
                      <DetectionBox
                        key={det.id}
                        detection={det}
                        index={i + 1}
                        real={rulingById.get(det.id)?.isRealDefect ?? false}
                        highlighted={hoveredId === det.id}
                        naturalWidth={naturalSize.w}
                        naturalHeight={naturalSize.h}
                        onHover={setHoveredId}
                      />
                    ))}
                </div>
                {result !== null && result.detections.length === 0 && (
                  <p role="status" className="border-t border-line px-3.5 py-2 text-[13px] text-ink-2">
                    No defects detected. The image is shown unmarked.
                  </p>
                )}
              </Panel>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
              <span><i className="mr-1.5 inline-block h-3 w-3 rounded-[2px] border-2 border-fail align-[-2px]" />Ruled a defect</span>
              <span><i className="mr-1.5 inline-block h-3 w-3 rounded-[2px] border-2 border-detect align-[-2px]" />Cleared by judge</span>
              <span className="text-ink-3">Hover a box or a ruling to link them</span>
            </div>
          </div>

          <Panel aria-label="Verdict">
            <PanelHeader title={<><Icon name="list" />Verdict</>} />
            <AnimatePresence mode="wait" initial={false}>
            {verdict === null || result === null ? (
              <p className="p-4 text-sm text-ink-2">Press Inspect to get a verdict with per-detection reasons.</p>
            ) : (
              <motion.div
                key={result.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
              >
                <div className="border-b border-line p-4">
                  <div className="flex items-baseline gap-3">
                    <VerdictBadge verdict={verdict.verdict} />
                    <span className="num text-sm text-ink-2">confidence {(verdict.confidence * 100).toFixed(1)}%</span>
                    {!verdict.partMatches && <span className="text-sm font-medium text-fail">Wrong part</span>}
                  </div>
                  <p className="mt-2 text-sm">{verdict.summary}</p>
                </div>
                <div className="flex items-baseline justify-between px-4 pt-3">
                  <h2>Rulings · {result.detections.length} candidate{result.detections.length === 1 ? '' : 's'}</h2>
                  {verdict.missedDefects.length > 0 && (
                    <span className="num text-xs text-ink-2">{verdict.missedDefects.length} missed defect{verdict.missedDefects.length === 1 ? '' : 's'}</span>
                  )}
                </div>
                {verdict.rulings.length > 0 ? (
                  <ol className="m-0 list-none p-1.5">
                    {verdict.rulings.map((ruling, pos) => {
                      const di = result.detections.findIndex((d) => d.id === ruling.detectionId)
                      const det = di >= 0 ? result.detections[di] : null
                      const n = di >= 0 ? di + 1 : pos + 1
                      const label = det?.label ?? ruling.detectionId
                      return (
                        <motion.li
                          key={ruling.detectionId}
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.2, ease: 'easeOut', delay: pos * 0.04 }}
                          tabIndex={0}
                          aria-label={`${n}: ${label}, ${ruling.isRealDefect ? 'defect' : 'cleared'}`}
                          onPointerEnter={() => setHoveredId(ruling.detectionId)}
                          onPointerLeave={() => setHoveredId(null)}
                          onFocus={() => setHoveredId(ruling.detectionId)}
                          onBlur={() => setHoveredId(null)}
                          className={`grid grid-cols-[26px_minmax(0,1fr)] gap-2.5 rounded-sm px-2 py-2.5 ${hoveredId === ruling.detectionId ? 'bg-sunken' : ''}`}
                        >
                          <span
                            className={`inline-flex h-[22px] w-[22px] items-center justify-center rounded-[3px] font-mono text-xs font-semibold ${ruling.isRealDefect ? 'bg-fail text-on-fail' : `bg-detect ${DETECT_TEXT}`}`}
                          >
                            {n}
                          </span>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 text-sm">
                              <b className="font-medium">{label}</b>
                              {ruling.isRealDefect ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-fail-tint px-2 py-px text-xs font-medium text-fail">
                                  <Icon name="alert" />Defect
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded-full border border-line-strong px-2 py-px text-xs text-ink-2">
                                  <Icon name="check" />Cleared
                                </span>
                              )}
                              {det !== null && (
                                <span className="num text-xs text-ink-3">score {det.score.toFixed(2)} · {formatSize(det)}</span>
                              )}
                            </div>
                            <p className="mt-0.5 text-[13px] text-ink-2">{ruling.reason}</p>
                            {ruling.ruleViolated !== null && (
                              <p className="mt-1 text-xs text-ink-3">Rule cited: {ruling.ruleViolated}</p>
                            )}
                          </div>
                        </motion.li>
                      )
                    })}
                  </ol>
                ) : (
                  <p className="px-4 py-3 text-sm text-ink-2">No rulings: nothing was detected.</p>
                )}
                {verdict.missedDefects.length > 0 && (
                  <p className="px-4 pb-3 text-sm text-ink-2">Missed defects: {verdict.missedDefects.join(', ')}</p>
                )}
                <dl className="m-0 grid grid-cols-3 border-t border-line">
                  {([['Segment', result.timingsMs.segment], ['Judge', result.timingsMs.judge], ['Total', result.timingsMs.total]] as const).map(([name, ms], i) => (
                    <div key={name} className={`px-3.5 py-2.5 ${i > 0 ? 'border-l border-line' : ''}`}>
                      <dt className="flex items-center gap-1 text-xs text-ink-3"><Icon name="clock" />{name}</dt>
                      <dd className="num m-0 text-[15px] font-medium">{ms.toFixed(0)} ms</dd>
                    </div>
                  ))}
                </dl>
              </motion.div>
            )}
            </AnimatePresence>
            <div className="border-t border-line p-3.5">
              <Field
                label={<span className="inline-flex items-center gap-1.5"><Icon name="pencil" />Rules override</span>}
                hint="Applies to this run only. Clear it to go back to the profile rules."
              >
                <textarea
                  className="ctl"
                  value={rulesText}
                  onChange={(event) => setRulesText(event.target.value)}
                  rows={4}
                  placeholder="Edit rules in plain English to re-judge the same image…"
                />
              </Field>
              {inspecting && rulesText.trim() !== '' && (
                <p role="status" className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-3">
                  <i className="h-2 w-2 rounded-full bg-detect" aria-hidden="true" />
                  Re-judging with edited rules · segmentation reused
                </p>
              )}
            </div>
          </Panel>
        </div>
      )}
    </section>
  )
}
