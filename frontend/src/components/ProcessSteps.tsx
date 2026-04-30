import { useState, useEffect } from 'react'
import type { ProcessStep, AgentStatus } from '../hooks/useChat'

function Countdown({ waitSeconds, startedAt }: { waitSeconds: number, startedAt: number }) {
  const [remaining, setRemaining] = useState(() =>
    Math.max(0, waitSeconds - Math.floor((Date.now() - startedAt) / 1000))
  )
  useEffect(() => {
    if (remaining <= 0) return
    const t = setInterval(() => setRemaining(r => Math.max(0, r - 1)), 1000)
    return () => clearInterval(t)
  }, [])
  return <span className="text-coral-500 font-medium">retrying in {remaining}s</span>
}

function AgentRow({ agent }: { agent: AgentStatus }) {
  const isWaiting = !!(agent.wait_seconds && agent.wait_started_at)
  const statusColor = agent.finished
    ? agent.disqualified ? 'text-coral-500' : 'text-teal-700'
    : isWaiting ? 'text-coral-500' : 'text-ink-400'

  const slug = (() => {
    try {
      const u = new URL(agent.url)
      const path = u.pathname.replace(/\/$/, '').split('/').filter(Boolean)
      return path[path.length - 1] || u.hostname
    } catch { return agent.hostname }
  })()

  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="shrink-0">
        {agent.finished ? (
          <span className={`text-xs font-bold ${statusColor}`}>
            {agent.disqualified ? '✗' : '✓'}
          </span>
        ) : (
          <span className={`w-2 h-2 rounded-full inline-block shrink-0 ${isWaiting ? 'bg-coral-500' : 'bg-teal-600 animate-pulse'}`} />
        )}
      </span>
      <a
        href={agent.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[0.72rem] text-ink-600 hover:text-teal-700 hover:underline truncate max-w-[200px] font-mono"
        title={agent.url}
      >
        {slug}
      </a>
      <span className={`text-[0.68rem] ml-auto shrink-0 ${statusColor}`}>
        {isWaiting && agent.wait_started_at
          ? <Countdown waitSeconds={agent.wait_seconds!} startedAt={agent.wait_started_at} />
          : agent.finished
          ? agent.disqualified ? 'filtered' : 'done'
          : agent.status}
      </span>
    </div>
  )
}

type Props = {
  steps: ProcessStep[]
  isRunning: boolean
}

export function ProcessSteps({ steps, isRunning }: Props) {
  const [manualExpanded, setManualExpanded] = useState<Set<number>>(new Set())
  const [manualCollapsed, setManualCollapsed] = useState<Set<number>>(new Set())

  const lastIdx = steps.length - 1

  const isAutoExpanded = (i: number) => {
    if (manualCollapsed.has(i)) return false
    if (manualExpanded.has(i)) return true
    // Auto-expand: the active step and the listing-research step (always show agents)
    const isActive = i === lastIdx && isRunning
    const isAgentStep = steps[i]?.node === 'listing_agent' || steps[i]?.agents?.length
    return isActive || !!isAgentStep
  }

  const toggle = (i: number) => {
    const currently = isAutoExpanded(i)
    setManualExpanded(prev => { const s = new Set(prev); currently ? s.delete(i) : s.add(i); return s })
    setManualCollapsed(prev => { const s = new Set(prev); currently ? s.add(i) : s.delete(i); return s })
  }

  // Overall progress — from the listing_agent step's done/total
  const agentStep = [...steps].reverse().find(s => s.done !== undefined && s.total !== undefined)
  const overallPct = agentStep ? Math.round((agentStep.done! / Math.max(agentStep.total!, 1)) * 100) : 0
  const showOverall = agentStep && agentStep.total! > 0

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
        {/* Header row */}
        <div className="flex items-center justify-between mb-1">
          <p className="text-[0.65rem] uppercase tracking-[0.16em] text-ink-400 font-semibold">
            {isRunning ? 'Working on it' : 'Completed'}
          </p>
          {!isRunning && steps.length > 0 && (
            <span className="text-[0.65rem] text-teal-700 font-medium">
              Done in {steps.reduce((sum, s) => sum + (s.elapsed ?? 0), 0).toFixed(1)}s
            </span>
          )}
        </div>

        {/* Overall progress bar */}
        {showOverall && (
          <div className="mb-2 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-[0.68rem] text-ink-500">
                Researching {agentStep!.done} of {agentStep!.total} listings
              </span>
              <span className="text-[0.68rem] text-ink-400 font-mono">{overallPct}%</span>
            </div>
            <div className="w-full h-1.5 bg-ink-100 rounded-full overflow-hidden">
              <div
                className="h-1.5 bg-teal-700 rounded-full transition-all duration-500"
                style={{ width: `${overallPct}%` }}
              />
            </div>
          </div>
        )}

        {steps.map((step, i) => {
          const isLast = i === steps.length - 1
          const active = isLast && isRunning
          const agents = step.agents ?? []
          const hasAgents = agents.length > 0
          const hasDetail = step.detail.length > 0 || hasAgents
          const expanded = isAutoExpanded(i)
          const finishedAgents = agents.filter(a => a.finished)
          const disqualifiedAgents = agents.filter(a => a.disqualified)

          return (
            <div key={i} className="flex flex-col">
              <button
                type="button"
                className={`flex items-center gap-2.5 py-1 text-sm text-left w-full transition-colors ${hasDetail ? 'cursor-pointer hover:text-ink-900' : 'cursor-default'}`}
                onClick={() => hasDetail && toggle(i)}
                disabled={!hasDetail}
              >
                {/* Status dot */}
                {active ? (
                  <span className="w-3.5 h-3.5 border-2 border-ink-200 border-t-teal-700 rounded-full animate-spin shrink-0" />
                ) : (
                  <span className="w-4 h-4 rounded-full bg-teal-50 border border-teal-200/60 flex items-center justify-center shrink-0">
                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-2.5 h-2.5 text-teal-700">
                      <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}

                <span className={`flex-1 min-w-0 ${active ? 'text-ink-900 font-medium' : 'text-ink-700'}`}>
                  {step.label}
                </span>

                {/* Agent summary counts (collapsed) */}
                {hasAgents && !expanded && finishedAgents.length > 0 && (
                  <span className="text-[0.65rem] text-ink-400 shrink-0">
                    {finishedAgents.length - disqualifiedAgents.length} kept
                    {disqualifiedAgents.length > 0 && `, ${disqualifiedAgents.length} filtered`}
                  </span>
                )}

                {!active && step.elapsed !== undefined && (
                  <span className="text-[0.7rem] text-ink-400 font-mono shrink-0">{step.elapsed}s</span>
                )}

                {hasDetail && (
                  <svg viewBox="0 0 20 20" fill="currentColor"
                    className={`w-3 h-3 text-ink-400 ml-1 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}>
                    <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                  </svg>
                )}
              </button>

              {/* Expanded detail */}
              {hasDetail && expanded && (
                <div className="ml-6 mb-1.5 flex flex-col gap-0.5 pl-2 border-l border-ink-200/60 mt-0.5">
                  {/* Text details (non-URL) */}
                  {step.detail
                    .filter(item => !item.startsWith('http'))
                    .map((item, j) => (
                      <span key={j} className="text-[0.75rem] text-ink-500 leading-snug">{item}</span>
                    ))}

                  {/* Agent rows */}
                  {hasAgents && (
                    <div className="flex flex-col gap-0.5 mt-0.5">
                      {agents.map((agent, j) => (
                        <AgentRow key={j} agent={agent} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
