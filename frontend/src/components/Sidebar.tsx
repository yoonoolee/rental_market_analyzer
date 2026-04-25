import type { SessionMeta } from '../hooks/useChat'

type Props = {
  sessions: SessionMeta[]
  currentId: string
  onNewChat: () => void
  onSwitch: (id: string) => void
  onDelete: (id: string) => void
}

export function Sidebar({ sessions, currentId, onNewChat, onSwitch, onDelete }: Props) {
  return (
    <aside className="group w-12 hover:w-64 h-screen bg-[#f7f6f3] flex flex-col shrink-0 transition-all duration-200 overflow-hidden">

      {/* Header */}
      <div className="flex items-center gap-2 px-3 pt-4 pb-2 shrink-0">
        <img src="/logo.png" alt="Logo" className="w-6 h-6 object-contain shrink-0" />
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm font-semibold text-gray-700 whitespace-nowrap">
          TEMP NAME
        </span>
      </div>

      {/* New Chat button */}
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

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-4">No past conversations</p>
        )}
        {sessions.map((s) => (
          <div key={s.id} className="group/item flex items-center rounded-lg overflow-hidden">
            <button
              onClick={() => onSwitch(s.id)}
              className={`flex-1 text-left px-3 py-2 text-sm truncate transition-colors ${
                s.id === currentId
                  ? 'bg-gray-200 text-gray-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-200 hover:text-gray-900'
              }`}
            >
              {s.title}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(s.id) }}
              className="opacity-0 group-hover/item:opacity-100 p-1.5 mr-1 text-gray-400 hover:text-red-500 transition-all shrink-0"
              title="Delete chat"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-3.5 h-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}
