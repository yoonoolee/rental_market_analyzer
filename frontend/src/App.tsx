import { useEffect, useRef } from 'react'
import { useChat } from './hooks/useChat'
import { MessageBubble } from './components/MessageBubble'
import { InputBar } from './components/InputBar'
import { Sidebar } from './components/Sidebar'
import { ListingCard } from './components/ListingCard'
import type { ListingProfile } from './hooks/useChat'
import './index.css'

export default function App() {
  const { messages, isThinking, connected, sessions, sendMessage, newChat, switchSession, deleteSession, deleteAllSessions } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentId = localStorage.getItem('rental_session_id') ?? ''
  const isInitial = messages.length === 0

  // extract latest listings from message history for the right panel
  const latestListings: ListingProfile[] = messages.findLast(m => m.role === 'listings')?.listings ?? []
  const hasListings = latestListings.length > 0

  useEffect(() => {
    if (!isInitial) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isThinking, isInitial])

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onNewChat={newChat}
        onSwitch={switchSession}
        onDelete={deleteSession}
      />

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0 relative">
        {/* Delete all button top-left */}
        <div className="absolute top-3 left-4 z-10">
          <button
            onClick={deleteAllSessions}
            className="text-xs text-red-400 hover:text-red-600 transition-colors font-medium"
          >
            DELETE ALL CHATS (TEMP)
          </button>
        </div>

        {isInitial ? (
          <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
            <div className="max-w-3xl w-full mb-6 text-center">
              <h1 className="text-3xl font-semibold text-gray-900 mb-2">Hi there!</h1>
              <p className="text-base text-gray-400">Ready to find your next apartment?</p>
            </div>
            <div className="max-w-3xl w-full">
              <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="What are you looking for?" />
            </div>
          </div>
        ) : (
          <>
            <main className="flex-1 overflow-y-auto px-4 pt-16 pb-8">
              <div className="max-w-2xl mx-auto flex flex-col gap-6">
                {messages.filter(m => m.role !== 'listings').map((m) => (
                  <MessageBubble key={m.id} message={m} onSend={sendMessage} />
                ))}
                <div ref={bottomRef} />
              </div>
            </main>
            <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="Reply..." />
          </>
        )}
      </div>

      {/* Listings panel */}
      {hasListings && (
        <div className="w-96 shrink-0 flex flex-col h-screen">
          <div className="px-4 pt-4 pb-3 shrink-0">
            <p className="text-sm font-semibold text-gray-700">{latestListings.length} listings found</p>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
            {latestListings.map((l, i) => (
              <ListingCard key={i} listing={l} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
