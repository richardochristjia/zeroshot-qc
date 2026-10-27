import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, getEvalRun, listEvalRuns, resolveFileUrl } from '../api.ts'
import type {
  CategoryMetrics,
  EvalResultRow,
  EvalRunDetail,
  EvalRunSummary,
} from '../api.ts'

type LoadStatus = 'loading' | 'ready' | 'loading-detail'

function errorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail
  return fallback
}

function isFailure(row: EvalResultRow): boolean {
  return (
    (row.label === 'good' && row.verdict === 'FAIL') ||
    (row.label === 'defective' && row.verdict === 'PASS')
  )
}

function formatMetric(value: number): string {
  return value.toFixed(3)
}

function formatNullable(value: number | null): string {
  return value === null ? '—' : formatMetric(value)
}

interface BarRowProps {
  name: string
  f1: number
}

function F1Bar({ name, f1 }: BarRowProps): JSX.Element {
  const clamped = Math.min(1, Math.max(0, f1))
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">{name}</span>
        <span className="text-neutral-600">{formatMetric(f1)}</span>
      </div>
      <div
        role="img"
        aria-label={`F1 for ${name}: ${formatMetric(f1)}`}
        className="mt-1 h-3 w-full rounded bg-neutral-200"
      >
        <div
          className="h-3 rounded bg-neutral-800"
          style={{ width: `${(clamped * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  )
}

interface MetricsTableProps {
  perCategory: Record<string, CategoryMetrics>
  overall: CategoryMetrics
}

function MetricsTable({ perCategory, overall }: MetricsTableProps): JSX.Element {
  const names = Object.keys(perCategory).sort()
  return (
    <table className="mt-2 w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-neutral-300 text-left text-neutral-600">
          <th className="py-1 pr-2 font-medium">Category</th>
          <th className="py-1 pr-2 font-medium">P</th>
          <th className="py-1 pr-2 font-medium">R</th>
          <th className="py-1 pr-2 font-medium">F1</th>
          <th className="py-1 pr-2 font-medium">Acc</th>
          <th className="py-1 pr-2 font-medium">AUROC</th>
          <th className="py-1 font-medium">n</th>
        </tr>
      </thead>
      <tbody>
        {names.map((name) => {
          const m = perCategory[name]
          return (
            <tr key={name} className="border-b border-neutral-100">
              <td className="py-1 pr-2 font-medium">{name}</td>
              <td className="py-1 pr-2">{formatMetric(m.precision)}</td>
              <td className="py-1 pr-2">{formatMetric(m.recall)}</td>
              <td className="py-1 pr-2">{formatMetric(m.f1)}</td>
              <td className="py-1 pr-2">{formatMetric(m.accuracy)}</td>
              <td className="py-1 pr-2">{formatNullable(m.auroc)}</td>
              <td className="py-1">{m.n}</td>
            </tr>
          )
        })}
        <tr className="font-semibold">
          <td className="py-1 pr-2">Overall</td>
          <td className="py-1 pr-2">{formatMetric(overall.precision)}</td>
          <td className="py-1 pr-2">{formatMetric(overall.recall)}</td>
          <td className="py-1 pr-2">{formatMetric(overall.f1)}</td>
          <td className="py-1 pr-2">{formatMetric(overall.accuracy)}</td>
          <td className="py-1 pr-2">{formatNullable(overall.auroc)}</td>
          <td className="py-1">{overall.n}</td>
        </tr>
      </tbody>
    </table>
  )
}

interface FailureDetailProps {
  row: EvalResultRow
}

function FailureDetail({ row }: FailureDetailProps): JSX.Element {
  const [imgBroken, setImgBroken] = useState<boolean>(false)
  useEffect(() => {
    setImgBroken(false)
  }, [row.imageUrl, row.image])
  return (
    <div className="mt-2 rounded border border-neutral-300 px-4 py-3">
      <p className="text-sm font-medium">
        {row.category} · {row.image}
      </p>
      <p className="mt-1 text-sm text-neutral-600">
        Label {row.label}, verdict {row.verdict}
        {row.defectType !== '' && `, defect ${row.defectType}`}
        {` · confidence ${(row.confidence * 100).toFixed(1)}% · ${row.nDetections} detections`}
        {row.iou !== null && ` · IoU ${formatMetric(row.iou)}`}
      </p>
      {row.imageUrl === null ? (
        <div className="mt-3 rounded border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
          No image available for this row (absolute or escaping dataset path).
        </div>
      ) : imgBroken ? (
        <div className="mt-3 rounded border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
          Dataset image not present under data/ — the file behind this row is missing.
        </div>
      ) : (
        <img
          src={resolveFileUrl(row.imageUrl)}
          alt={`${row.category} ${row.image}`}
          className="mt-3 block max-w-full"
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
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [selectedFailure, setSelectedFailure] = useState<number>(-1)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    listEvalRuns(controller.signal)
      .then((loaded) => {
        setRuns(loaded)
        if (loaded.length > 0) setSelectedId(loaded[0].runId)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load eval runs.'))
        setStatus('ready')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (selectedId === '') {
      setDetail(null)
      return
    }
    const controller = new AbortController()
    setStatus('loading-detail')
    setSelectedFailure(-1)
    getEvalRun(selectedId, controller.signal)
      .then((loaded) => {
        setDetail(loaded)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(errorDetail(err, 'Could not load run detail.'))
        setDetail(null)
        setStatus('ready')
      })
    return () => controller.abort()
  }, [selectedId])

  const metrics = detail === null ? null : detail.summary.metrics
  const failures: EvalResultRow[] =
    detail === null ? [] : detail.results.filter(isFailure)
  const activeFailure =
    selectedFailure >= 0 && selectedFailure < failures.length
      ? failures[selectedFailure]
      : null

  return (
    <section aria-label="Eval">
      <h1 className="text-xl font-semibold">Eval</h1>
      <p className="mt-2 text-sm">
        Browse evaluation runs, metrics, and failure examples. This view is read-only and
        never launches runs.
      </p>

      {error !== null && (
        <p
          role="alert"
          className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
        >
          {error}
        </p>
      )}

      {status === 'loading' ? (
        <p role="status" className="mt-6 text-sm text-neutral-500">
          Loading runs…
        </p>
      ) : runs.length === 0 ? (
        <div className="mt-6 rounded border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500">
          No runs yet. Run an evaluation from the CLI to produce a run, then return here
          to browse it.
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div>
            <h2 className="text-sm font-semibold">Runs</h2>
            <ul className="mt-2 space-y-1">
              {runs.map((run) => (
                <li key={run.runId}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(run.runId)}
                    aria-current={run.runId === selectedId ? 'true' : undefined}
                    className={`w-full rounded border px-3 py-2 text-left text-sm ${
                      run.runId === selectedId
                        ? 'border-neutral-900 bg-neutral-100 font-medium'
                        : 'border-neutral-300 bg-white'
                    }`}
                  >
                    <span className="block">{run.runId}</span>
                    <span className="block text-xs text-neutral-500">
                      {run.source}
                      {run.categories.length > 0 && ` · ${run.categories.join(', ')}`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="lg:col-span-2">
            {status === 'loading-detail' || detail === null ? (
              <p role="status" className="mt-2 text-sm text-neutral-500">
                Loading run detail…
              </p>
            ) : (
              <>
                <h2 className="text-sm font-semibold">
                  Metrics — {detail.summary.runId}
                </h2>
                {metrics === null ? (
                  <div className="mt-2 rounded border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
                    This run has no metrics yet.
                  </div>
                ) : (
                  <>
                    <MetricsTable
                      perCategory={metrics.perCategory}
                      overall={metrics.overall}
                    />
                    <h3 className="mt-6 text-sm font-semibold">F1 per category</h3>
                    <div className="mt-2 space-y-3">
                      {Object.keys(metrics.perCategory)
                        .sort()
                        .map((name) => {
                          const m: CategoryMetrics = metrics.perCategory[name]
                          return <F1Bar key={name} name={name} f1={m.f1} />
                        })}
                    </div>
                  </>
                )}

                <h2 className="mt-6 text-sm font-semibold">
                  Failure examples ({failures.length})
                </h2>
                {failures.length === 0 ? (
                  <div className="mt-2 rounded border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
                    No failures in this run — every verdict matches its label.
                  </div>
                ) : (
                  <>
                    <ul className="mt-2 space-y-1">
                      {failures.map((row, index) => (
                        <li key={`${row.category}-${row.image}-${index}`}>
                          <button
                            type="button"
                            onClick={() => setSelectedFailure(index)}
                            aria-current={index === selectedFailure ? 'true' : undefined}
                            className={`w-full rounded border px-3 py-2 text-left text-sm ${
                              index === selectedFailure
                                ? 'border-neutral-900 bg-neutral-100 font-medium'
                                : 'border-neutral-300 bg-white'
                            }`}
                          >
                            {row.category} · {row.image} — label {row.label}, verdict{' '}
                            {row.verdict}
                            {row.imageUrl === null && ' (no image)'}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {activeFailure !== null ? (
                      <FailureDetail
                        key={`${activeFailure.category}-${activeFailure.image}`}
                        row={activeFailure}
                      />
                    ) : (
                      <div className="mt-2 rounded border border-dashed border-neutral-300 px-4 py-8 text-center text-sm text-neutral-500">
                        Select a failure above to view its image.
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
