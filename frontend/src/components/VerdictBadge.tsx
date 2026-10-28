import { Icon } from './Icon.tsx'

export function VerdictBadge({ verdict, size = 34 }: { verdict: 'PASS' | 'FAIL' | string; size?: number }) {
  const pass = verdict === 'PASS'
  return (
    <span
      className={`inline-flex items-center gap-2 font-semibold leading-none tracking-wide ${pass ? 'text-pass' : 'text-fail'}`}
      style={{ fontSize: size }}
    >
      <Icon name={pass ? 'check' : 'x'} className="!h-[0.85em] !w-[0.85em]" />
      {verdict}
    </span>
  )
}
