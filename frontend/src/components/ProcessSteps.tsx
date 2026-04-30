import { useState, useEffect } from 'react'
import type { ProcessStep, AgentStatus } from '../hooks/useChat'

function Countdown({ waitSeconds, startedAt }: { waitSeconds: number, startedAt: number }) {
  const [remaining, setRemaining] = useState(() =>
    Math.max(0, waitSeconds - Math.floor((Date.now() - startedAt) / 1000))
  )
  useEffect(() => {
    if (remaining <= 0) return
    const t = setInterval(() => {
      setRemaining(r => Math.max(0, r - 1))
    }, 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="text-coral-500">rate limited · retrying in {remaining}s</span>
}

type Props = {
  steps: ProcessStep[]
  isRunning: boolean
}

export function ProcessSteps({ steps, isRunning }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggle = (i: number) =>
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })

  if (steps.length === 0 && isRunning) {
    return (
      <div className="flex items-center gap-2.5 text-sm text-ink-500 pl-10">
        <span className="w-3.5 h-3.5 border-2 border-ink-200 border-t-teal-700 rounded-full animate-spin shrink-0" />
        <span className="italic font-display">Thinking…</span>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 w-full">
      <div className="w-7 h-7 rounded-full bg-cream-200 text-teal-700 flex items-center justify-center shrink-0 mt-0.5 border border-ink-200/60">
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 3a1 1 0 011 1v3.59l2.7 2.7a1 1 0 11-1.4 1.42l-3-3A1 1 0 017 8V4a1 1 0 011-1z" />
        </svg>
      </div>

      <div className="flex-1 min-w-0 rounded-2xl border border-ink-200/60 bg-white/60 backdrop-blur-sm px-4 py-3 flex flex-col gap-1">
        <p className="text-[0.65rem] uppercase tracking-[0.16em] text-ink-400 font-semibold mb-1">
          Working on it
        </p>

        {steps.map((step, i) => {
          const isLast = i === steps.length - 1
          const active = isLast && isRunning
          const hasDetail = step.detail.length > 0 || (step.agents && step.agents.length > 0)
          const isExpanded = expanded.has(i)
          const isProgress = step.done !== undefined && step.total !== undefined
          const pct = isProgress ? Math.round((step.done! / Math.max(step.total!, 1)) * 100) : 0

          return (
            <div key={i} className="flex flex-col">
              <button
                type="button"
                className={`flex items-center gap-2.5 py-1 text-sm text-left transition-colors ${hasDetail ? 'cursor-pointer hover:text-ink-900' : 'cursor-default'}`}
                onClick={() => hasDetail && toggle(i)}
                aria-expanded={hasDetail ? isExpanded : undefined}
                disabled={!hasDetail}
              >
                {active ? (
                  <span className="w-3.5 h-3.5 border-2 border-ink-200 border-t-teal-700 rounded-full animate-spin shrink-0" />
                ) : (
                  <span className="w-4 h-4 rounded-full bg-teal-50 flex items-center justify-center shrink-0">
                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-2.5 h-2.5 text-teal-700">
                      <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}

                <span className={active ? 'text-ink-900 font-medium' : 'text-ink-700'}>{step.label}</span>
                {!active && step.elapsed !== undefined && (
                  <span className="text-[0.7rem] text-ink-400 ml-1 font-mono">{step.elapsed}s</span>
                )}

                {hasDetail && (
                  <svg viewBox="0 0 20 20" fill="currentColor"
                    className={`w-3 h-3 text-ink-400 ml-auto transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                )}
              </button>

              {isProgress && (
                <div className="ml-6 mt-1 mb-1 flex items-center gap-2.5">
                  <div className="w-40 h-1.5 bg-ink-100 rounded-full overflow-hidden">
                    <div className="h-1.5 bg-teal-700 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-[0.7rem] text-ink-500 font-mono">{step.done}/{step.total}</span>
                </div>
              )}

              {hasDetail && isExpanded && (
                <div className="ml-6 mt-1 mb-1.5 flex flex-col gap-1 pl-2 border-l border-ink-200/60">
                  {step.detail
                    .filter(item => !(item.startsWith('http') && step.label.startsWith('Researching listings')))
                    .map((item, j) => (
                      item.startsWith('http') ? (
                        <a key={j} href={item} target="_blank" rel="noreferrer"
                          className="text-[0.75rem] text-teal-700 hover:underline truncate max-w-[24rem] font-mono">
                          {item}
                        </a>
                      ) : (
                        <span key={j} className="text-[0.78rem] text-ink-500">{item}</span>
                      )
                    ))}
                </div>
              )}

              {step.agents && step.agents.length > 0 && isExpanded && (
                <div className="ml-6 mt-1 mb-1.5 flex flex-col gap-1 pl-2 border-l border-ink-200/60">
                  {step.agents.map((agent: AgentStatus, j: number) => (
                    <div key={j} className="flex items-center gap-2 text-[0.75rem]">
                      {agent.finished ? (
                        <span className={agent.disqualified ? 'text-coral-500' : 'text-teal-700'}>
                          {agent.disqualified ? '✗' : '✓'}
                        </span>
                      ) : (
                        <span className="w-2 h-2 border border-ink-200 border-t-teal-700 rounded-full animate-spin shrink-0" />
                      )}
                      <a href={agent.url.split('#')[0]} target="_blank" rel="noopener noreferrer"
                        className="text-ink-500 shrink-0 font-mono hover:text-ink-900 hover:underline truncate max-w-[200px]">
                        {agent.url.replace(/^https?:\/\/[^/]+\//, '').replace(/#.*$/, '').replace(/\/$/, '') || agent.hostname}
                      </a>
                      {agent.wait_seconds && agent.wait_started_at ? (
                        <Countdown waitSeconds={agent.wait_seconds} startedAt={agent.wait_started_at} />
                      ) : (
                        <span className="text-ink-400 truncate">{agent.status}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
