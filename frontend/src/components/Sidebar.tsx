import { useState, useEffect } from 'react'
import type { SessionMeta } from '../hooks/useChat'

type Props = {
  sessions: SessionMeta[]
  currentId: string
  onNewChat: () => void
  onSwitch: (id: string) => void
  onDelete: (id: string) => void
}

export function Sidebar({ sessions, currentId, onNewChat, onSwitch, onDelete }: Props) {
  const [expanded, setExpanded] = useState<boolean>(() => {
    try { return localStorage.getItem('sidebar_expanded') === '1' } catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem('sidebar_expanded', expanded ? '1' : '0') } catch { /* noop */ }
  }, [expanded])

  return (
    <aside
      className={`h-screen bg-cream-100/60 backdrop-blur-md border-r border-ink-200/40 flex flex-col shrink-0 transition-all duration-300 overflow-hidden ${
        expanded ? 'w-72' : 'w-14'
      }`}
    >
      {/* Brand + collapse toggle */}
      <div className="flex items-center gap-3 px-3 pt-4 pb-4 shrink-0 border-b border-ink-200/50">
        <button
          onClick={() => setExpanded(v => !v)}
          title={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          className="w-8 h-8 rounded-lg bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 shadow-sm hover:bg-teal-600 transition-colors"
        >
          <span className="font-display text-sm font-semibold leading-none">R</span>
        </button>

        {expanded && (
          <div className="whitespace-nowrap min-w-0 flex-1">
            <p className="font-display text-[0.95rem] font-semibold text-ink-900 leading-tight">Real Estate</p>
            <p className="text-[0.65rem] tracking-[0.18em] uppercase text-teal-700 font-medium leading-tight mt-0.5">AIgent</p>
          </div>
        )}

        {expanded && (
          <button
            onClick={() => setExpanded(false)}
            title="Collapse"
            aria-label="Collapse sidebar"
            className="w-7 h-7 flex items-center justify-center rounded-md text-ink-400 hover:text-ink-700 hover:bg-white transition-colors shrink-0"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
              <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>

      {/* New Chat */}
      <div className="px-2.5 pt-3 pb-2 shrink-0">
        <button
          onClick={onNewChat}
          title="New search"
          className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-ink-700 hover:bg-white hover:shadow-sm transition-all"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 shrink-0 text-teal-700">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          {expanded && (
            <span className="text-sm whitespace-nowrap font-medium">
              New search
            </span>
          )}
        </button>
      </div>

      {expanded && (
        <>
          <div className="px-4 pt-2 pb-1">
            <p className="text-[0.62rem] uppercase tracking-[0.18em] text-ink-400 font-medium">Recent</p>
          </div>

          <div className="flex-1 overflow-y-auto px-2 flex flex-col gap-0.5 pt-1">
            {sessions.length === 0 && (
              <p className="text-xs text-ink-400 text-center mt-6 px-3">
                Past searches will appear here.
              </p>
            )}
            {sessions.map((s) => {
              const isActive = s.id === currentId
              return (
                <div key={s.id} className="group/item flex items-center rounded-xl overflow-hidden">
                  <button
                    onClick={() => onSwitch(s.id)}
                    className={`flex-1 text-left px-3 py-2 text-sm truncate transition-colors min-w-0 ${
                      isActive
                        ? 'bg-white text-ink-900 font-medium shadow-sm'
                        : 'text-ink-700 hover:bg-white/70 hover:text-ink-900'
                    }`}
                  >
                    {s.title}
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(s.id) }}
                    className="opacity-0 group-hover/item:opacity-100 p-1.5 mr-1 text-ink-400 hover:text-coral-500 transition-all shrink-0"
                    title="Delete"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
                    </svg>
                  </button>
                </div>
              )
            })}
          </div>

          <div className="px-4 py-3 border-t border-ink-200/40 shrink-0">
            <p className="text-[0.65rem] text-ink-400 leading-relaxed">
              Powered by Anthropic, OpenAI, and the open web.
            </p>
          </div>
        </>
      )}

      {!expanded && <div className="flex-1" />}
    </aside>
  )
}
