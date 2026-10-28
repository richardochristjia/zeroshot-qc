import { useEffect, useState } from 'react'
import { getHealth } from '../api.ts'

type State = 'checking' | 'ok' | 'down'

const dot: Record<State, string> = { checking: 'bg-ink-3', ok: 'bg-pass', down: 'bg-fail' }
const label: Record<State, string> = { checking: 'Checking backend', ok: 'Backend online', down: 'Backend unreachable' }

export function HealthDot() {
  const [state, setState] = useState<State>('checking')
  useEffect(() => {
    const controller = new AbortController()
    const poll = (): void => {
      getHealth(controller.signal).then(setState, () => undefined)
    }
    poll()
    const timer = window.setInterval(poll, 30_000)
    return () => {
      window.clearInterval(timer)
      controller.abort()
    }
  }, [])
  return (
    <div role="status" aria-label={label[state]} className="flex items-center gap-1.5 whitespace-nowrap text-[13px] text-ink-2">
      <i className={`h-2 w-2 rounded-full ${dot[state]}`} aria-hidden="true" />
      <span className="max-[1000px]:hidden">{label[state]}</span>
    </div>
  )
}
