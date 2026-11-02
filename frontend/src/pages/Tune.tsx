import { useEffect, useState } from 'react'
import type { JSX } from 'react'
import { ApiError, getTuneRun, listTuneRuns } from '../api.ts'
import type { TuneRunDetail, TuneRunSummary } from '../api.ts'
import { Alert } from '../components/Alert.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { PageHeader } from '../components/PageHeader.tsx'
import { Panel, PanelHeader } from '../components/Panel.tsx'
import { diffRules } from '../tune-view.ts'

function errorDetail(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback
}

function Kpi({ label, value, accent = false }: { label: string; value: number; accent?: boolean }): JSX.Element {
  return (
    <div>
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className={`num mt-0.5 text-[26px] font-medium leading-tight ${accent ? 'text-data' : ''}`}>{value.toFixed(3)}</dd>
    </div>
  )
}

const LINE_STYLE = {
  same: 'text-ink-2',
  added: 'bg-pass-tint text-pass',
  removed: 'bg-fail-tint text-fail line-through',
}
const LINE_MARK = { same: ' ', added: '+', removed: '−' }

export default function Tune(): JSX.Element {
  const [runs, setRuns] = useState<TuneRunSummary[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<TuneRunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ctl = new AbortController()
    listTuneRuns(ctl.signal)
      .then((list) => {
        setRuns(list)
        setSelected((cur) => cur ?? list[0]?.runId ?? null)
      })
      .catch((e) => !ctl.signal.aborted && setError(errorDetail(e, 'Could not load tune runs.')))
    return () => ctl.abort()
  }, [])

  useEffect(() => {
    if (selected === null) return
    const ctl = new AbortController()
    getTuneRun(selected, ctl.signal)
      .then(setDetail)
      .catch((e) => !ctl.signal.aborted && setError(errorDetail(e, 'Could not load the run.')))
    return () => ctl.abort()
  }, [selected])

  return (
    <>
      <PageHeader title="Tune" subtitle="Judge rules rewritten from the judge's own mistakes, scored on held-out real images." />
      {error && <Alert>{error}</Alert>}
      {runs !== null && runs.length === 0 && (
        <EmptyState icon="sliders" title="No tune runs yet">
          Run python -m app.tune.run --category bottle in backend/ to record one.
        </EmptyState>
      )}
      {runs !== null && runs.length > 0 && (
        <div className="grid grid-cols-[18rem_minmax(0,1fr)] items-start gap-4 max-[900px]:grid-cols-1">
          <Panel>
            <PanelHeader title="Runs" />
            <ul className="divide-y divide-line">
              {runs.map((run) => (
                <li key={run.runId}>
                  <button
                    type="button"
                    onClick={() => setSelected(run.runId)}
                    aria-current={run.runId === selected ? 'true' : undefined}
                    className={`flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-sm ${run.runId === selected ? 'bg-sunken' : 'hover:bg-sunken'}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">{run.category}</span>
                      <span className="block truncate font-mono text-xs text-ink-3">{run.runId}</span>
                    </span>
                    <span className="num shrink-0 text-xs text-ink-2">
                      {run.beforeF1.toFixed(3)} → {run.afterF1.toFixed(3)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
          {detail && detail.runId === selected && (
            <div className="flex min-w-0 flex-col gap-4">
              <Panel>
                <PanelHeader title={<>{detail.category} <span className="font-mono font-normal text-ink-3">{detail.runId}</span></>}>
                  <span className="num text-xs text-ink-3">{detail.adapter}{detail.seed !== null && ` · seed ${detail.seed}`}</span>
                </PanelHeader>
                <dl className="grid grid-cols-2 gap-4 p-3.5">
                  <Kpi label="Held-out F1 before" value={detail.heldoutBefore} />
                  <Kpi label="Held-out F1 after" value={detail.heldoutAfter} accent />
                </dl>
              </Panel>
              <Panel>
                <PanelHeader title="Rounds" />
                {detail.rounds.length === 0 ? (
                  <p className="p-3.5 text-sm text-ink-3">The judge made no mistakes on the tune set, so the rules were not revised.</p>
                ) : (
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-line-strong text-xs text-ink-3">
                        <th className="px-3.5 py-2 text-left font-medium">Round</th>
                        <th className="py-2 text-right font-medium">Tune F1</th>
                        <th className="px-3 py-2 text-left font-medium">Result</th>
                        <th className="py-2 pr-3.5 text-left font-medium">Rationale</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.rounds.map((r) => (
                        <tr key={r.round} className="border-b border-line align-top last:border-b-0">
                          <td className="num px-3.5 py-2">{r.round}</td>
                          <td className="num py-2 text-right">{r.f1.toFixed(3)}</td>
                          <td className={`px-3 py-2 font-medium ${r.accepted ? 'text-pass' : 'text-ink-3'}`}>{r.accepted ? 'Accepted' : 'Rejected'}</td>
                          <td className="py-2 pr-3.5 text-ink-2">{r.rationale}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Panel>
              <Panel>
                <PanelHeader title="Rules, initial to final" />
                <pre className="overflow-x-auto p-3.5 font-mono text-xs leading-relaxed">
                  {diffRules(detail.initialRules, detail.finalRules).map((line, i) => (
                    <div key={i} className={`whitespace-pre-wrap px-1 ${LINE_STYLE[line.kind]}`}>
                      {LINE_MARK[line.kind]} {line.text}
                    </div>
                  ))}
                </pre>
              </Panel>
            </div>
          )}
        </div>
      )}
    </>
  )
}
