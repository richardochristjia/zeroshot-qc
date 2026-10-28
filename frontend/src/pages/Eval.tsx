import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, getEvalRun, listEvalRuns, resolveFileUrl } from '../api.ts'
import type { CategoryMetrics, EvalResultRow, EvalRunDetail, EvalRunSummary } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

function isFailure(row: EvalResultRow): boolean {
  return (row.label === 'good' && row.verdict === 'FAIL') || (row.label === 'defective' && row.verdict === 'PASS')
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

function Kpi({ label, value, accent = false }: { label: string; value: number | null; accent?: boolean }): JSX.Element {
  return (
    <div>
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="mt-0.5 text-[26px] font-medium leading-tight">
        <Metric value={value} className={accent ? 'text-data' : ''} />
      </dd>
    </div>
  )
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
            <th className="w-[28%] px-3 py-2 text-left font-medium min-[641px]:w-[32%]">F1</th>
            <th className={`${th} pl-3`}>F1</th>
            <th className={`${th} pl-3`}>Precision</th>
            <th className={`${th} pl-3`}>Recall</th>
            <th className={`${th} pl-3`}>AUROC</th>
          </tr>
        </thead>
        <tbody>
          {names.map((name) => {
            const m = perCategory[name]
            return (
              <tr key={name} className="border-b border-line last:border-b-0">
                <td className="py-2 pr-3 font-medium">{name}</td>
                <td className="px-3 py-2">
                  <div role="img" aria-label={`F1 for ${name}: ${m.f1.toFixed(3)}`}>
                    <Bar value={m.f1} height={6} tone="data" />
                  </div>
                </td>
                <td className="py-2 pl-3 text-right"><Metric value={m.f1} /></td>
                <td className="py-2 pl-3 text-right"><Metric value={m.precision} /></td>
                <td className="py-2 pl-3 text-right"><Metric value={m.recall} /></td>
                <td className="py-2 pl-3 text-right"><Metric value={m.auroc} /></td>
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
    <div className="border-t border-line p-3.5">
      <p className="text-sm font-medium">
        {row.category} · {row.image}
      </p>
      <p className="mt-1 text-[13px] text-ink-2">
        Label {row.label}, verdict {row.verdict}
        {row.defectType !== '' && `, defect ${row.defectType}`}
        {` · confidence ${(row.confidence * 100).toFixed(1)}% · ${row.nDetections} detections`}
        {row.iou !== null && ` · IoU ${row.iou.toFixed(3)}`}
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

  useEffect(() => {
    const controller = new AbortController()
    listEvalRuns(controller.signal)
      .then((loaded) => {
        setRuns(loaded)
        if (loaded.length > 0) setSelectedId(loaded[0].runId)
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
  }

  const current = detail !== null && detail.summary.runId === selectedId ? detail : null
  const detailLoading = selectedId !== '' && current === null && failedId !== selectedId
  const summary = current?.summary ?? null
  const metrics = summary?.metrics ?? null
  const failures: EvalResultRow[] = current === null ? [] : current.results.filter(isFailure)
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
                        <span className="block truncate font-mono text-xs text-ink-3">{run.runId}</span>
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
                      <dl className="grid grid-cols-3 gap-4 min-[1001px]:grid-cols-5">
                        <Kpi label="F1" value={metrics.overall.f1} accent />
                        <Kpi label="Precision" value={metrics.overall.precision} />
                        <Kpi label="Recall" value={metrics.overall.recall} />
                        <Kpi label="AUROC" value={metrics.overall.auroc} />
                        <Kpi label="Accuracy" value={metrics.overall.accuracy} />
                      </dl>
                      <p className="num text-[13px] text-ink-2">
                        True fail {metrics.overall.tp} · True pass {metrics.overall.tn} · False fail {metrics.overall.fp} ·
                        Missed {metrics.overall.fn}
                      </p>
                      <MetricsTable perCategory={metrics.perCategory} />
                    </div>
                  )}
                </Panel>

                {ablation.length >= 2 && (
                  <Panel>
                    <PanelHeader title="Ablation · same seed, same N images" />
                    <ul className="flex flex-col gap-2.5 p-3.5">
                      {ablation.map((run) => {
                        const f1 = run.metrics?.overall.f1 ?? null
                        return (
                          <li key={run.runId} className="grid grid-cols-[minmax(0,12rem)_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm">
                            <span className="truncate">{modeName(run.mode)}</span>
                            <Bar value={f1} height={10} tone={run.runId === summary.runId ? 'data' : 'muted'} />
                            <Metric value={f1} className="text-right" />
                          </li>
                        )
                      })}
                    </ul>
                  </Panel>
                )}

                <Panel>
                  <PanelHeader title={`Failure examples (${failures.length})`} />
                  {failures.length === 0 ? (
                    <div className="p-3.5">
                      <EmptyState icon="check" title="No failures in this run — every verdict matches its label." />
                    </div>
                  ) : (
                    <>
                      <ul>
                        {failures.map((row, index) => (
                          <li key={`${row.category}-${row.image}-${index}`} className="border-b border-line last:border-b-0">
                            <button
                              type="button"
                              onClick={() => setSelectedFailure(index)}
                              aria-current={index === selectedFailure ? 'true' : undefined}
                              className={`w-full px-3.5 py-2 text-left text-sm ${index === selectedFailure ? 'bg-sunken' : 'hover:bg-sunken'}`}
                            >
                              {row.category} · {row.image} — label {row.label}, verdict {row.verdict}
                              {row.imageUrl === null && ' (no image)'}
                            </button>
                          </li>
                        ))}
                      </ul>
                      {activeFailure !== null ? (
                        <FailureDetail key={`${activeFailure.category}-${activeFailure.image}`} row={activeFailure} />
                      ) : (
                        <div className="border-t border-line p-3.5">
                          <EmptyState icon="eye" title="Select a failure above to view its image." />
                        </div>
                      )}
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
