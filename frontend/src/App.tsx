import { useEffect, useRef, useState } from 'react'
import { useChat } from './hooks/useChat'
import { MessageBubble } from './components/MessageBubble'
import { InputBar } from './components/InputBar'
import { Sidebar } from './components/Sidebar'
import { ListingCard } from './components/ListingCard'
import { ListingMap } from './components/ListingMap'
import type { ListingProfile } from './hooks/useChat'
import './index.css'

export default function App() {
  const {
    messages,
    isThinking,
    connected,
    connectionState,
    sessions,
    sendMessage,
    newChat,
    switchSession,
    deleteSession,
    deleteAllSessions,
    abortRun,
  } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const [showMobileListings, setShowMobileListings] = useState(false)
  const currentId = localStorage.getItem('rental_session_id') ?? ''
  const isInitial = messages.length === 0

  // Extract latest listings for right rail + mobile drawer.
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

      <div className="flex-1 min-w-0 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="min-w-0 flex flex-col h-screen">
          <header className="h-14 shrink-0 border-b border-gray-200 px-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${connectionState === 'connected' ? 'bg-green-500' : connectionState === 'error' ? 'bg-amber-500' : 'bg-gray-400'}`} />
              <p className="text-sm font-medium text-gray-700">Real Estate AIgent</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={newChat}
                className="text-xs px-2.5 py-1.5 rounded-full border border-gray-300 text-gray-700 hover:bg-gray-100"
              >
                New chat
              </button>
              <button
                onClick={abortRun}
                disabled={!isThinking}
                className="text-xs px-2.5 py-1.5 rounded-full border border-amber-300 text-amber-700 hover:bg-amber-50 disabled:opacity-40"
              >
                Abort run
              </button>
              <button
                onClick={deleteAllSessions}
                className="text-xs px-2.5 py-1.5 rounded-full border border-red-300 text-red-600 hover:bg-red-50"
              >
                Delete all
              </button>
            </div>
          </header>

          {isInitial ? (
            <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
              <div className="max-w-3xl w-full mb-6 text-center">
                <h1 className="text-3xl font-semibold text-gray-900 mb-2">Hi there!</h1>
                <p className="text-base text-gray-500">Ready to find your next apartment?</p>
              </div>
              <div className="max-w-3xl w-full">
                <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="What are you looking for?" />
              </div>
            </div>
          ) : (
            <>
              <main className="flex-1 overflow-y-auto px-4 pt-4 pb-8">
                <div className="max-w-3xl mx-auto flex flex-col gap-6">
                  {messages.map((m) => (
                    <MessageBubble key={m.id} message={m} onSend={sendMessage} />
                  ))}
                  <div ref={bottomRef} />
                </div>
              </main>
              <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="Reply..." />
            </>
          )}

          {hasListings && (
            <div className="lg:hidden border-t border-gray-200 p-3">
              <button
                onClick={() => setShowMobileListings(v => !v)}
                className="w-full text-sm px-3 py-2 rounded-lg bg-gray-100 text-gray-700"
              >
                {showMobileListings ? 'Hide listings' : `Show ${latestListings.length} listings`}
              </button>
              {showMobileListings && (
                <div className="mt-3 max-h-80 overflow-y-auto flex flex-col gap-3">
                  {latestListings.map((l, i) => <ListingCard key={i} listing={l} />)}
                </div>
              )}
            </div>
          )}
        </section>

        {hasListings && (
          <aside className="hidden lg:flex border-l border-gray-200 flex-col h-screen">
            <div className="px-4 pt-4 pb-3 shrink-0">
              <p className="text-sm font-semibold text-gray-700">{latestListings.length} listings found</p>
            </div>
            <div className="h-52 shrink-0 px-4">
              <div className="w-full h-full rounded-xl overflow-hidden bg-gray-100">
                <ListingMap listings={latestListings} />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
              {latestListings.map((l, i) => (
                <ListingCard key={i} listing={l} />
              ))}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
