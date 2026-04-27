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
    sessions,
    preferences,
    sendMessage,
    newChat,
    switchSession,
    deleteSession,
    deleteAllSessions,
  } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const [showMobileListings, setShowMobileListings] = useState(false)

  const scrollToListing = (url: string) => {
    cardRefs.current.get(url)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
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

      <div className="flex-1 min-w-0 min-h-0 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_28rem]" style={{height: '100vh'}}>
        <section className="min-w-0 flex flex-col h-screen">
          <div className="h-11 shrink-0 flex items-center px-4">
            <button
              onClick={deleteAllSessions}
              className="text-xs px-3 py-1.5 rounded-full bg-red-50 text-red-500 hover:bg-red-100 hover:text-red-600 transition-colors font-medium"
            >
              DELETE ALL CHATS (TEMP)
            </button>
          </div>

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
                  {messages.filter(m => m.role !== 'listings').map((m) => (
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
                  {latestListings.map((l, i) => <ListingCard key={i} listing={l} preferences={preferences} />)}
                </div>
              )}
            </div>
          )}
        </section>

        {hasListings && (
          <aside className="hidden lg:block overflow-y-auto" style={{height: '100vh'}}>
            <div className="px-4 pt-4 pb-3">
              <p className="text-sm font-semibold text-gray-700">{latestListings.length} listings found</p>
            </div>
            <div className="h-72 px-4 mb-4">
              <div className="w-full h-full rounded-xl overflow-hidden">
                <ListingMap listings={latestListings} onSelect={l => scrollToListing(l.url)} />
              </div>
            </div>
            <div className="px-4 pb-8 flex flex-col gap-6">
              {latestListings.map((l, i) => (
                <div key={i} ref={el => { if (el) cardRefs.current.set(l.url, el); else cardRefs.current.delete(l.url) }}>
                  <ListingCard listing={l} preferences={preferences} />
                </div>
              ))}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
