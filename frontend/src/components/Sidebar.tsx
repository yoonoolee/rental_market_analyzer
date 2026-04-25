import type { SessionMeta } from '../hooks/useChat'

type Props = {
  sessions: SessionMeta[]
  currentId: string
  onNewChat: () => void
  onSwitch: (id: string) => void
}

export function Sidebar({ sessions, currentId, onNewChat, onSwitch }: Props) {
  return (
    <aside className="group w-12 hover:w-64 h-screen bg-[#f7f6f3] flex flex-col shrink-0 transition-all duration-200 overflow-hidden">

      {/* Header: collapsed = logo only, expanded = logo + TEMP NAME */}
      <div className="flex items-center gap-2 px-3 pt-4 pb-2 shrink-0">
        {/* Logo — always visible, anchored left */}
        <img src="/logo.png" alt="Logo" className="w-6 h-6 object-contain shrink-0" />
        {/* TEMP NAME — fades in when expanded */}
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm font-semibold text-gray-700 whitespace-nowrap">
          TEMP NAME
        </span>
      </div>

      {/* New Chat button: collapsed = icon only, expanded = icon + label */}
      <div className="px-2 pb-2 shrink-0">
        <button
          onClick={onNewChat}
          title="New Chat"
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-gray-500 hover:text-gray-800 hover:bg-gray-200 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 shrink-0">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm whitespace-nowrap">
            New Chat
          </span>
        </button>
      </div>

      {/* Session list — only visible when expanded */}
      <div className="flex-1 overflow-y-auto px-2 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-4">No past conversations</p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSwitch(s.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
              s.id === currentId
                ? 'bg-gray-200 text-gray-900 font-medium'
                : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'
            }`}
          >
            {s.title}
          </button>
        ))}
      </div>
    </aside>
  )
}
