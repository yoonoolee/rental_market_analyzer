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
  return <span className="text-orange-400">rate limited — retrying in {remaining}s</span>
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
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="w-3.5 h-3.5 border-2 border-gray-300 border-t-gray-500 rounded-full animate-spin shrink-0" />
        Thinking...
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
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
              className={`flex items-center gap-2 py-0.5 text-sm text-left ${hasDetail ? 'cursor-pointer' : 'cursor-default'}`}
              onClick={() => hasDetail && toggle(i)}
              aria-expanded={hasDetail ? isExpanded : undefined}
              disabled={!hasDetail}
            >
              {active ? (
                <span className="w-3.5 h-3.5 border-2 border-gray-300 border-t-gray-500 rounded-full animate-spin shrink-0" />
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-gray-400 shrink-0">
                  <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                </svg>
              )}

              <span className="text-gray-600">{step.label}</span>

              {hasDetail && (
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                  className={`w-3 h-3 text-gray-400 ml-auto transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              )}
            </button>

            {isProgress && (
              <div className="ml-5 mt-1 mb-0.5 flex items-center gap-2">
                <div className="w-32 h-1 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-1 bg-[#1a3f6f] rounded-full transition-all" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs text-gray-400">{step.done}/{step.total}</span>
              </div>
            )}

            {hasDetail && isExpanded && (
              <div className="ml-5 mt-1 mb-1 flex flex-col gap-0.5">
                {step.detail
                  .filter(item => !(item.startsWith('http') && step.label.startsWith('Researching listings')))
                  .map((item, j) => (
                    item.startsWith('http') ? (
                      <a key={j} href={item} target="_blank" rel="noreferrer"
                        className="text-xs text-[#1a3f6f] hover:underline truncate max-w-[22rem]">
                        {item}
                      </a>
                    ) : (
                      <span key={j} className="text-xs text-gray-500">{item}</span>
                    )
                  ))}
              </div>
            )}

            {step.agents && step.agents.length > 0 && isExpanded && (
              <div className="ml-5 mt-1 mb-1 flex flex-col gap-0.5">
                {step.agents.map((agent: AgentStatus, j: number) => (
                  <div key={j} className="flex items-center gap-1.5 text-xs">
                    {agent.finished ? (
                      <span className={agent.disqualified ? 'text-red-400' : 'text-green-600'}>
                        {agent.disqualified ? '✗' : '✓'}
                      </span>
                    ) : (
                      <span className="w-2 h-2 border border-gray-300 border-t-gray-500 rounded-full animate-spin shrink-0" />
                    )}
                    <a href={agent.url.split('#')[0]} target="_blank" rel="noopener noreferrer" className="text-gray-400 shrink-0 font-mono hover:text-gray-600 hover:underline truncate max-w-[200px]">
                      {agent.url.replace(/^https?:\/\/[^/]+\//, '').replace(/#.*$/, '').replace(/\/$/, '') || agent.hostname}
                    </a>
                    {agent.wait_seconds && agent.wait_started_at ? (
                      <Countdown waitSeconds={agent.wait_seconds} startedAt={agent.wait_started_at} />
                    ) : (
                      <span className="text-gray-500 truncate">{agent.status}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
