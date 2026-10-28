import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, getEvalRun, listEvalRuns, resolveFileUrl } from '../api.ts'
import type { CategoryMetrics, EvalResultRow, EvalRunDetail, EvalRunSummary } from '../api.ts'
import { Dialog } from '../components/Dialog.tsx'
import { InfoTip } from '../components/InfoTip.tsx'
import { Button } from '../components/Button.tsx'
import { stepIndex } from '../step.ts'
import { Alert } from '../components/Alert.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'
import { ConfusionMatrix } from '../components/ConfusionMatrix.tsx'
import { FailureGrid } from '../components/FailureGrid.tsx'
import { Icon } from '../components/Icon.tsx'
import { bestOtherDelta, filterFailures, pickDefaultRun, runTag, shadeLevel } from '../eval-view.ts'
import type { FailureKind } from '../eval-view.ts'

const GLOSSARY: Record<string, string> = {
  F1: 'Balance of precision and recall in one number, from 0 to 1. Higher is better.',
  Precision: 'Of the images flagged FAIL (defective), the share that really were defective.',
  Recall: 'Of the truly defective images, the share that were flagged FAIL.',
  AUROC: 'How well the confidence score ranks defective images above good ones. 0.5 is chance, 1 is perfect.',
  Accuracy: 'Share of all images where the verdict matched the label.',
  'True fail': 'Defective image correctly flagged FAIL.',
  'True pass': 'Good image correctly passed.',
  'False fail': 'Good image wrongly flagged FAIL (false alarm).',
  Missed: 'Defective image wrongly passed (a defect that slipped through).',
  Ablation: 'Same images scored three ways: SAM only (segmentation alone), + judge (a model reviews each detection), + reference (the judge also compares against a known-good image).',
  IoU: 'Overlap between the detected region and the true defect mask, from 0 to 1.',
  confidence: 'How sure the system is that the image is defective.',
}

function Term({ term, children }: { term: string; children?: string }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1">
      {children ?? term}
      <InfoTip term={term} text={GLOSSARY[term]} />
    </span>
  )
}

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

const MODE_NAMES: Record<string, string> = {
  sam_only: 'SAM only',
  sam_judge: 'SAM + judge',
  sam_judge_ref: 'SAM + judge + reference',
}

function modeName(mode: string): string {
  return MODE_NAMES[mode] ?? mode
}

function groupKey(run: EvalRunSummary): string {
  return JSON.stringify([run.source, run.seed, [...run.categories].sort()])
}

function Metric({ value, className = '' }: { value: number | null; className?: string }): JSX.Element {
  if (value === null) return <span className={`num text-ink-3 ${className}`}>—</span>
  return <span className={`num ${value === 0 ? 'text-ink-3' : ''} ${className}`}>{value.toFixed(3)}</span>
}

function Bar({ value, height, tone }: { value: number | null; height: number; tone: 'data' | 'muted' }): JSX.Element {
  const pct = Math.min(1, Math.max(0, value ?? 0)) * 100
  return (
    <div className="w-full rounded-sm bg-sunken" style={{ height }}>
      <div className={`h-full rounded-sm ${tone === 'data' ? 'bg-data' : 'bg-line-strong'}`} style={{ width: `${pct.toFixed(1)}%` }} />
    </div>
  )
}

function Delta({ value }: { value: number | null }): JSX.Element | null {
  if (value === null) return null
  const text = Math.abs(value).toFixed(3)
  if (text === '0.000') return <div className="num text-xs text-ink-3">= 0.000</div>
  return value > 0 ? (
    <div className="num text-xs text-pass">▲ +{text}</div>
  ) : (
    <div className="num text-xs text-fail">▼ −{text}</div>
  )
}

function Kpi({ label, value, delta, accent = false }: { label: string; value: number | null; delta: number | null; accent?: boolean }): JSX.Element {
  return (
    <div>
      <dt className="text-xs text-ink-3"><Term term={label} /></dt>
      <dd className="mt-0.5 text-[26px] font-medium leading-tight">
        <Metric value={value} className={accent ? 'text-data' : ''} />
      </dd>
      <Delta value={delta} />
    </div>
  )
}

const SHADE_PCT = [0, 8, 16, 26, 38]

function shade(value: number | null): string | undefined {
  const level = shadeLevel(value)
  return level === null || level === 0 ? undefined : `color-mix(in srgb, var(--data) ${SHADE_PCT[level]}%, transparent)`
}

function MetricsTable({ perCategory }: { perCategory: Record<string, CategoryMetrics> }): JSX.Element {
  const names = Object.keys(perCategory).sort()
  const th = 'py-2 text-right font-medium'
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line-strong text-xs text-ink-3">
            <th className="py-2 pr-3 text-left font-medium">Category</th>
            <th className={`${th} pl-3`}><Term term="F1" /></th>
            <th className={`${th} pl-3`}><Term term="Precision" /></th>
            <th className={`${th} pl-3`}><Term term="Recall" /></th>
            <th className={`${th} pl-3`}><Term term="AUROC" /></th>
          </tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const m = perCategory[name]
            return (
              <tr key={name} className="border-b border-line last:border-b-0">
                <td className="py-2 pr-3 font-medium">{name}</td>
                {[m.f1, m.precision, m.recall, m.auroc].map((v, i) => (
                  <td key={i} className="px-3 py-2 text-right" style={{ background: shade(v) }}>
                    <Metric value={v} className="text-ink" />
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function FailureDetail({ row }: { row: EvalResultRow }): JSX.Element {
  // Parent keys this component by row, so the broken flag resets per row.
  const [imgBroken, setImgBroken] = useState<boolean>(false)
  return (
    <div className="p-3.5">
      <p className="text-sm font-medium">
        {row.category} · {row.image}
      </p>
      <p className="mt-1 text-[13px] text-ink-2">
        Label {row.label}, verdict {row.verdict}
        {row.defectType !== '' && `, defect ${row.defectType}`}
        {' · '}
        <Term term="confidence" /> {(row.confidence * 100).toFixed(1)}% · {row.nDetections} detections
        {row.iou !== null && (
          <>
            {' · '}
            <Term term="IoU" /> {row.iou.toFixed(3)}
          </>
        )}
      </p>
      {row.imageUrl === null ? (
        <EmptyState icon="file" title="No image for this row" className="mt-3">
          The row has an absolute or escaping dataset path.
        </EmptyState>
      ) : imgBroken ? (
        <EmptyState icon="alert" title="Image file missing" className="mt-3">
          Dataset image not present under data/: the file behind this row is missing.
        </EmptyState>
      ) : (
        <img
          src={resolveFileUrl(row.imageUrl)}
          alt={`${row.category} ${row.image}`}
          className="mt-3 block max-h-[480px] max-w-full rounded-sm border border-line"
          onError={() => setImgBroken(true)}
        />
      )}
    </div>
  )
}

export default function Eval(): JSX.Element {
  const [runs, setRuns] = useState<EvalRunSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [detail, setDetail] = useState<EvalRunDetail | null>(null)
  const [failedId, setFailedId] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedFailure, setSelectedFailure] = useState<number>(-1)
  const [kindFilter, setKindFilter] = useState<FailureKind | ''>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')

  useEffect(() => {
    const controller = new AbortController()
    listEvalRuns(controller.signal)
      .then((loaded) => {
        setRuns(loaded)
        if (loaded.length > 0) setSelectedId(pickDefaultRun(loaded))
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load eval runs.'))
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (selectedId === '') return
    const controller = new AbortController()
    getEvalRun(selectedId, controller.signal)
      .then((loaded) => {
        setDetail(loaded)
        setFailedId('')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load run detail.'))
        setFailedId(selectedId)
      })
    return () => controller.abort()
  }, [selectedId])

  const selectRun = (id: string): void => {
    setSelectedId(id)
    setSelectedFailure(-1)
    setKindFilter('')
    setCategoryFilter('')
  }

  const current = detail !== null && detail.summary.runId === selectedId ? detail : null
  const detailLoading = selectedId !== '' && current === null && failedId !== selectedId
  const summary = current?.summary ?? null
  const metrics = summary?.metrics ?? null
  const allFailures = current === null ? [] : filterFailures(current.results, '', '')
  // Sorted by category so dialog Prev/Next follows the grouped grid order.
  const failures: EvalResultRow[] = filterFailures(allFailures, kindFilter, categoryFilter).sort((a, b) =>
    a.category.localeCompare(b.category),
  )
  const activeFailure = selectedFailure >= 0 && selectedFailure < failures.length ? failures[selectedFailure] : null

  const ablation: EvalRunSummary[] = []
  if (summary !== null) {
    const key = groupKey(summary)
    const seen = new Set<string>()
    for (const run of runs) {
      if (groupKey(run) !== key || seen.has(run.mode)) continue
      seen.add(run.mode)
      ablation.push(run)
    }
  }
  const bestId = pickDefaultRun(ablation)
  const nImages = summary === null ? null : (summary.nGood ?? 0) + (summary.nDefective ?? 0)

  return (
    <section aria-label="Eval">
      <PageHeader title="Eval" subtitle="Runs scored on MVTec AD. Launch new runs from the CLI." />

      {error !== null && <Alert className="mb-4">{error}</Alert>}

      {loading ? (
        <EmptyState title="Loading runs…" />
      ) : runs.length === 0 ? (
        <EmptyState icon="chart" title="No runs yet.">
          Run an evaluation from the CLI to produce a run, then return here to browse it.
        </EmptyState>
      ) : (
        <div className="grid items-start gap-4 min-[1001px]:grid-cols-[260px_minmax(0,1fr)]">
          <Panel>
            <PanelHeader title={`${runs.length} ${runs.length === 1 ? 'run' : 'runs'}`} />
            <ul>
              {runs.map((run) => {
                const f1 = run.metrics?.overall.f1 ?? null
                return (
                  <li key={run.runId} className="border-b border-line last:border-b-0">
                    <button
                      type="button"
                      onClick={() => selectRun(run.runId)}
                      aria-current={run.runId === selectedId ? 'true' : undefined}
                      className={`flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-sm ${
                        run.runId === selectedId ? 'bg-sunken' : 'hover:bg-sunken'
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink">{modeName(run.mode)}</span>
                        <span className="block truncate font-mono text-xs text-ink-3">{runTag(run.runId, run.mode)}</span>
                        <span className="mt-1 block w-24">
                          <Bar value={f1} height={4} tone="data" />
                        </span>
                      </span>
                      <Metric value={f1} className="shrink-0" />
                    </button>
                  </li>
                )
              })}
            </ul>
          </Panel>

          <div className="flex min-w-0 flex-col gap-4">
            {summary === null ? (
              <EmptyState title={detailLoading ? 'Loading run detail…' : 'Run detail unavailable'} />
            ) : (
              <>
                {ablation.length >= 2 && (
                  <Panel>
                    <PanelHeader title={<>Ablation · same seed, same N images <InfoTip term="Ablation" text={GLOSSARY.Ablation} /></>} />
                    <p className="px-3.5 pt-3 text-[13px] text-ink-3">
                      F1 for the same images under SAM only, + judge and + reference.
                    </p>
                    <ul className="flex flex-col gap-2.5 p-3.5">
                      {ablation.map((run) => {
                        const f1 = run.metrics?.overall.f1 ?? null
                        return (
                          <li key={run.runId} className="grid grid-cols-[minmax(0,12rem)_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm">
                            <span className="truncate">
                              {modeName(run.mode)}
                              {run.runId === bestId && (
                                <span className="ml-2 inline-flex items-center gap-1 rounded-sm bg-pass-tint px-1.5 text-xs font-medium text-pass">
                                  <Icon name="check" className="size-3" />
                                  Best
                                </span>
                              )}
                            </span>
                            <Bar value={f1} height={10} tone={run.runId === summary.runId ? 'data' : 'muted'} />
                            <Metric value={f1} className="text-right" />
                          </li>
                        )
                      })}
                    </ul>
                  </Panel>
                )}

                <Panel>
                  <PanelHeader
                    title={
                      <>
                        {modeName(summary.mode)} <span className="font-mono font-normal text-ink-3">{summary.runId}</span>
                      </>
                    }
                  >
                    <span className="num text-xs text-ink-3">
                      {summary.source}
                      {summary.seed !== null && ` · seed ${summary.seed}`} · {summary.categories.length}{' '}
                      {summary.categories.length === 1 ? 'category' : 'categories'} · {nImages} images
                    </span>
                  </PanelHeader>
                  {metrics === null ? (
                    <div className="p-3.5">
                      <EmptyState icon="chart" title="No metrics recorded for this run" />
                    </div>
                  ) : (
                    <div className="flex flex-col gap-4 p-3.5">
                      <p className="text-[13px] text-ink-3">
                        How well this run separated good from defective images. FAIL means flagged as defective.
                      </p>
                      <dl className="grid grid-cols-3 gap-4 min-[1001px]:grid-cols-5">
                        <Kpi label="F1" value={metrics.overall.f1} delta={bestOtherDelta(summary, ablation, 'f1')} accent />
                        <Kpi label="Precision" value={metrics.overall.precision} delta={bestOtherDelta(summary, ablation, 'precision')} />
                        <Kpi label="Recall" value={metrics.overall.recall} delta={bestOtherDelta(summary, ablation, 'recall')} />
                        <Kpi label="AUROC" value={metrics.overall.auroc} delta={bestOtherDelta(summary, ablation, 'auroc')} />
                        <Kpi label="Accuracy" value={metrics.overall.accuracy} delta={bestOtherDelta(summary, ablation, 'accuracy')} />
                      </dl>
                      <ConfusionMatrix
                        counts={metrics.overall}
                        term={(name) => (
                          <Term term={name} />
                        )}
                      />
                      <MetricsTable perCategory={metrics.perCategory} />
                    </div>
                  )}
                </Panel>

                <Panel>
                  <PanelHeader title={`Failure examples (${allFailures.length})`} />
                  <p className="px-3.5 pt-3 text-[13px] text-ink-3">
                    Images where the verdict disagreed with the label. Select one to open it.
                  </p>
                  {allFailures.length === 0 ? (
                    <div className="p-3.5">
                      <EmptyState icon="check" title="No failures in this run — every verdict matches its label." />
                    </div>
                  ) : (
                    <>
                      <FailureGrid
                        rows={allFailures}
                        kind={kindFilter}
                        category={categoryFilter}
                        onKind={(k) => {
                          setKindFilter(k)
                          setSelectedFailure(-1)
                        }}
                        onCategory={(c) => {
                          setCategoryFilter(c)
                          setSelectedFailure(-1)
                        }}
                        filtered={failures}
                        onOpen={setSelectedFailure}
                      />
                      <Dialog
                        open={activeFailure !== null}
                        title={activeFailure === null ? '' : `Failure ${selectedFailure + 1} of ${failures.length}`}
                        onClose={() => setSelectedFailure(-1)}
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowLeft') setSelectedFailure(stepIndex(selectedFailure, -1, failures.length))
                          else if (e.key === 'ArrowRight') setSelectedFailure(stepIndex(selectedFailure, 1, failures.length))
                        }}
                      >
                        {activeFailure !== null && (
                          <>
                            <FailureDetail key={`${activeFailure.category}-${activeFailure.image}`} row={activeFailure} />
                            <div className="flex justify-between border-t border-line px-3.5 py-2.5">
                              <Button disabled={selectedFailure <= 0} onClick={() => setSelectedFailure(selectedFailure - 1)}>
                                Prev
                              </Button>
                              <Button
                                disabled={selectedFailure >= failures.length - 1}
                                onClick={() => setSelectedFailure(selectedFailure + 1)}
                              >
                                Next
                              </Button>
                            </div>
                          </>
                        )}
                      </Dialog>
                    </>
                  )}
                </Panel>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
