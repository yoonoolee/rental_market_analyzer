import { useEffect, useRef, useState } from 'react'
import { useChat } from './hooks/useChat'
import { MessageBubble } from './components/MessageBubble'
import { InputBar } from './components/InputBar'
import { Sidebar } from './components/Sidebar'
import { ListingCard } from './components/ListingCard'
import { ListingMap } from './components/ListingMap'
import type { ListingProfile } from './hooks/useChat'
import './index.css'

const SAMPLE_PROMPTS = [
  '2BR in Berkeley under $3000, pet friendly, near BART',
  'Modern 1BR in Oakland, in-unit laundry, walkable to cafés',
  'Studio in San Francisco, under $2400, near Mission',
  'Family-friendly 3BR in Albany or El Cerrito with parking',
]

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
  const [confirmReset, setConfirmReset] = useState(false)

  const scrollToListing = (url: string) => {
    cardRefs.current.get(url)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const currentId = localStorage.getItem('rental_session_id') ?? ''
  const isInitial = messages.length === 0

  const latestListings: ListingProfile[] = messages.findLast(m => m.role === 'listings')?.listings ?? []
  const hasListings = latestListings.length > 0

  useEffect(() => {
    if (!isInitial) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isThinking, isInitial])

  return (
    <div className="flex h-screen bg-transparent">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onNewChat={newChat}
        onSwitch={switchSession}
        onDelete={deleteSession}
      />

      <div
        className={`flex-1 min-w-0 min-h-0 grid grid-cols-1 ${hasListings ? 'lg:grid-cols-[minmax(0,1fr)_30rem]' : ''}`}
        style={{ height: '100vh' }}
      >
        <section className="min-w-0 flex flex-col h-screen relative">
          {/* Top bar */}
          <header className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-ink-200/40 bg-cream-50/40 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  connected ? 'bg-teal-600' : 'bg-coral-500'
                }`}
              />
              <span className="text-xs text-ink-500 tracking-wide">
                {connected ? 'Connected' : 'Reconnecting…'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {confirmReset ? (
                <>
                  <span className="text-xs text-ink-500">Clear all chats?</span>
                  <button
                    onClick={() => { deleteAllSessions(); setConfirmReset(false) }}
                    className="text-xs px-3 py-1.5 rounded-full bg-coral-500 text-white hover:bg-coral-600 transition-colors font-medium"
                  >
                    Yes, clear
                  </button>
                  <button
                    onClick={() => setConfirmReset(false)}
                    className="text-xs px-3 py-1.5 rounded-full bg-ink-100 text-ink-700 hover:bg-ink-200 transition-colors"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setConfirmReset(true)}
                  className="text-xs px-3 py-1.5 rounded-full text-ink-500 hover:text-coral-600 hover:bg-coral-500/5 transition-colors font-medium"
                  title="Delete all sessions"
                >
                  Reset all
                </button>
              )}
            </div>
          </header>

          {isInitial ? (
            <div className="flex-1 relative overflow-hidden flex flex-col items-center justify-center px-6 pb-12">
              {/* Soft hero backdrop */}
              <div className="hero-backdrop absolute inset-0 pointer-events-none" aria-hidden="true">
                <div className="hero-photo" />
                <div className="hero-photo-tint" />
              </div>

              <div className="relative z-10 fade-up flex flex-col items-center w-full">
                <div className="max-w-2xl w-full mb-8 text-center">
                  <p className="text-xs uppercase tracking-[0.2em] text-teal-700 mb-3 font-medium">
                    Real Estate AIgent
                  </p>
                  <h1 className="font-display text-5xl md:text-6xl font-medium text-ink-900 mb-4 leading-[1.05]">
                    Find a place that<br />
                    <span className="italic text-teal-700">truly</span> feels like home.
                  </h1>
                  <p className="text-base text-ink-500 max-w-md mx-auto leading-relaxed">
                    Tell us what you're looking for. We'll search the listings, weigh the trade-offs, and bring back the matches that fit you.
                  </p>
                </div>

                <div className="max-w-2xl w-full">
                  <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="What kind of place are you looking for?" />
                </div>

                <div className="max-w-2xl w-full mt-6 flex flex-wrap gap-2 justify-center">
                  {SAMPLE_PROMPTS.map(prompt => (
                    <button
                      key={prompt}
                      onClick={() => sendMessage(prompt)}
                      disabled={!connected || isThinking}
                      className="text-xs px-3.5 py-2 rounded-full border border-ink-200 bg-white/80 backdrop-blur-sm text-ink-700 hover:border-teal-600 hover:text-teal-700 hover:bg-teal-50 transition-all disabled:opacity-40"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              <main className="flex-1 overflow-y-auto px-6 pt-6 pb-8">
                <div className="max-w-3xl mx-auto flex flex-col gap-7">
                  {messages.filter(m => m.role !== 'listings').map((m, idx) => (
                    <div key={m.id} className="fade-up" style={{ animationDelay: `${Math.min(idx * 30, 200)}ms` }}>
                      <MessageBubble message={m} onSend={sendMessage} />
                    </div>
                  ))}
                  <div ref={bottomRef} />
                </div>
              </main>
              <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder="Reply…" />
            </>
          )}

          {hasListings && (
            <div className="lg:hidden border-t border-ink-200 p-3 bg-white/70">
              <button
                onClick={() => setShowMobileListings(v => !v)}
                className="w-full text-sm px-4 py-2.5 rounded-xl bg-teal-600 text-white font-medium hover:bg-teal-700 transition-colors"
              >
                {showMobileListings ? 'Hide listings' : `View ${latestListings.length} matches`}
              </button>
              {showMobileListings && (
                <div className="mt-3 max-h-96 overflow-y-auto flex flex-col gap-3">
                  {latestListings.map((l, i) => <ListingCard key={i} listing={l} preferences={preferences} />)}
                </div>
              )}
            </div>
          )}
        </section>

        {hasListings && (
          <aside className="hidden lg:block overflow-y-auto bg-cream-100/55 backdrop-blur-md border-l border-ink-200/40" style={{ height: '100vh' }}>
            <div className="px-5 pt-6 pb-4 sticky top-0 bg-cream-100/70 backdrop-blur-md z-10 border-b border-ink-200/40">
              <p className="text-[0.65rem] uppercase tracking-[0.18em] text-ink-400 mb-1 font-medium">
                Curated matches
              </p>
              <h2 className="font-display text-xl font-medium text-ink-900">
                {latestListings.length} {latestListings.length === 1 ? 'home' : 'homes'} for you
              </h2>
            </div>

            <div className="px-5 pt-4 mb-5">
              <div className="w-full h-72 rounded-2xl overflow-hidden border border-ink-200/60 shadow-sm">
                <ListingMap listings={latestListings} onSelect={l => scrollToListing(l.url)} />
              </div>
            </div>

            <div className="px-5 pb-10 flex flex-col gap-5">
              {latestListings.map((l, i) => (
                <div
                  key={i}
                  ref={el => { if (el) cardRefs.current.set(l.url, el); else cardRefs.current.delete(l.url) }}
                  className="fade-up"
                  style={{ animationDelay: `${Math.min(i * 50, 300)}ms` }}
                >
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
