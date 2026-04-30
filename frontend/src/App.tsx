import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useChat } from './hooks/useChat'
import { useListingPrefs } from './hooks/useListingPrefs'
import { ToastProvider, useToast } from './hooks/useToast'
import { MessageBubble } from './components/MessageBubble'
import { InputBar } from './components/InputBar'
import { Sidebar } from './components/Sidebar'
import { ListingCard } from './components/ListingCard'
import { ListingMap } from './components/ListingMap'
import { ListingControls, type SortKey, type FilterState } from './components/ListingControls'
import { CompareDrawer } from './components/CompareDrawer'
import { KeyboardShortcuts } from './components/KeyboardShortcuts'
import { EmptyState } from './components/EmptyState'
import { SkeletonRail } from './components/SkeletonCard'
import type { ListingProfile } from './hooks/useChat'
import './index.css'

function computeMatchScore(
  listing: ListingProfile,
  preferences: Record<string, unknown>,
): { score: number; reasons: string[] } {
  const reasons: string[] = []
  let earned = 0
  let total = 0

  const hardReqs: string[] = (preferences.hard_requirements as string[]) || []
  const softConstraints: string[] = (preferences.soft_constraints as string[]) || []
  const tradeOffs: string[] = (preferences.trade_off_rules as string[]) || []
  const rawQuery: string = (preferences.raw_query as string) || ''

  // Use structured fields when available, fall back to raw_query for no-elicitation searches
  const allPrefText = [...hardReqs, ...softConstraints, ...tradeOffs, rawQuery].join(' ').toLowerCase()
  const searchText = allPrefText || ''
  if (!searchText.trim()) return { score: 0, reasons: [] }

  const cares = (term: string) => searchText.includes(term)

  // Parse budget — check structured fields first, then raw query
  // matches: "under $3000", "max $2500", "$3,000/mo", "below 3000", "budget 2800"
  let budget: number | undefined
  const budgetSources = hardReqs.length ? [...hardReqs, ...softConstraints] : [rawQuery]
  for (const src of budgetSources) {
    const m = src.match(/\$?([\d,]+)\s*(?:\/mo)?/i)
    if (m && src.toLowerCase().match(/under|max|below|budget|afford|up to/)) {
      const val = parseInt(m[1].replace(/,/g, ''))
      if (val > 500 && val < 20000) { budget = val; break }
    }
  }
  // Fallback: any dollar amount in the raw query that looks like rent
  if (!budget && rawQuery) {
    const m = rawQuery.match(/\$?([\d,]+)\s*(?:\/mo|per month)?/i)
    if (m) {
      const val = parseInt(m[1].replace(/,/g, ''))
      if (val > 500 && val < 20000) budget = val
    }
  }

  // Parse bedrooms — structured first, then raw query
  let minBeds: number | undefined
  const bedSources = hardReqs.length ? hardReqs : [rawQuery]
  for (const src of bedSources) {
    const m = src.match(/(\d)\s*(?:br|bed(?:room)?s?|bd)/i) || src.match(/(?:at least|minimum)\s*(\d)/i)
    if (m) { minBeds = parseInt(m[1]); break }
  }

  // Price vs. budget
  if (budget && listing.price) {
    total += 25
    if (listing.price <= budget) {
      const under = budget - listing.price
      earned += Math.round(15 + Math.min(10, (under / budget) * 50))
      reasons.push(`Within budget ($${under.toLocaleString()} under)`)
    } else {
      const over = listing.price - budget
      reasons.push(`$${over.toLocaleString()} over budget`)
    }
  }

  // Bedrooms
  if (minBeds != null && listing.bedrooms != null) {
    total += 20
    if (listing.bedrooms >= minBeds) {
      earned += 20
      reasons.push(`${listing.bedrooms} bd meets the ${minBeds} bd minimum`)
    } else {
      reasons.push(`Only ${listing.bedrooms} bd (need ${minBeds}+)`)
    }
  }

  // Pet friendly
  if (cares('pet')) {
    total += 15
    if (listing.pet_friendly === true) {
      earned += 15
      reasons.push('Pet friendly')
    } else {
      reasons.push('No pet policy confirmed')
    }
  }

  // Commute
  const commuteTimes = listing.commute_times ? Object.values(listing.commute_times) : []
  if (commuteTimes.length > 0) {
    total += 20
    const mins = commuteTimes.map(v => {
      const m = String(v).match(/(\d+)\s*min/i)
      return m ? parseInt(m[1]) : null
    }).filter((v): v is number => v !== null)
    if (mins.length > 0) {
      const shortest = Math.min(...mins)
      if (shortest <= 20) { earned += 20; reasons.push(`Fast commute (${shortest} min)`) }
      else if (shortest <= 35) { earned += 14; reasons.push(`Reasonable commute (${shortest} min)`) }
      else if (shortest <= 50) { earned += 8; reasons.push(`Long commute (${shortest} min)`) }
      else { reasons.push(`Very long commute (${shortest} min)`) }
    }
  }

  // Amenity matches
  const wantedAmenities: string[] = []
  if (cares('laundry') || cares('washer')) wantedAmenities.push('laundry')
  if (cares('gym') || cares('fitness')) wantedAmenities.push('gym')
  if (cares('parking')) wantedAmenities.push('parking')
  if (cares('dishwasher')) wantedAmenities.push('dishwasher')
  if (cares('pool')) wantedAmenities.push('pool')
  if (cares('balcony') || cares('deck') || cares('patio')) wantedAmenities.push('balcony')
  if (cares('in-unit') || cares('in unit')) wantedAmenities.push('in-unit')

  if (wantedAmenities.length > 0 && listing.amenities && listing.amenities.length > 0) {
    total += 20
    const listingAm = listing.amenities.join(' ').toLowerCase()
    const matched = wantedAmenities.filter(a => listingAm.includes(a))
    const pts = Math.round((matched.length / wantedAmenities.length) * 20)
    earned += pts
    if (matched.length > 0) {
      reasons.push(`Has ${matched.join(', ')}`)
    } else {
      reasons.push('Missing desired amenities')
    }
  }

  // Lifestyle feature bonuses
  if (cares('view') && listing.views) { earned += 5; total += 5; reasons.push('Has great views') }
  if (cares('modern') && listing.modern_finishes) { earned += 5; total += 5; reasons.push('Modern finishes') }
  if (cares('light') && listing.natural_light) { earned += 5; total += 5; reasons.push('Natural light') }
  if (cares('spacious') && listing.spacious) { earned += 5; total += 5; reasons.push('Spacious layout') }

  const score = total > 0 ? Math.min(100, Math.round((earned / total) * 100)) : 0
  return { score, reasons: reasons.slice(0, 5) }
}

const SAMPLE_PROMPTS = [
  '2BR in Berkeley under $3000, pet friendly, near BART',
  'Modern 1BR in Oakland, in-unit laundry, walkable to cafés',
  'Studio in San Francisco, under $2400, near Mission',
  'Family-friendly 3BR in Albany or El Cerrito with parking',
]

function AppInner() {
  const {
    messages,
    isThinking,
    connected,
    connectionState,
    sessions,
    preferences,
    sendMessage,
    newChat,
    switchSession,
    deleteSession,
    deleteAllSessions,
  } = useChat()
  const { notify } = useToast()
  const prefs = useListingPrefs()

  const bottomRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  const [showMobileListings, setShowMobileListings] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [sort, setSort] = useState<SortKey>('best')
  const [filter, setFilter] = useState<FilterState>({ petsOnly: false, favoritesOnly: false, hideDisqualified: false })
  const [compareOpen, setCompareOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [sidebarKey, setSidebarKey] = useState(0)
  const [hoveredUrl, setHoveredUrl] = useState<string | null>(null)
  const [focusedIdx, setFocusedIdx] = useState<number>(-1)

  const currentId = localStorage.getItem('rental_session_id') ?? ''
  const isInitial = messages.length === 0

  const latestListings: ListingProfile[] = messages.findLast(m => m.role === 'listings')?.listings ?? []
  const hasListings = latestListings.length > 0

  // Sort + filter pipeline
  const visibleListings = useMemo(() => {
    let result = [...latestListings]
    if (filter.favoritesOnly) result = result.filter(l => prefs.favorites.includes(l.url))
    if (filter.petsOnly) result = result.filter(l => l.pet_friendly === true)
    if (filter.hideDisqualified) result = result.filter(l => !l.disqualified)

    const cmp = (a: ListingProfile, b: ListingProfile) => {
      if (sort === 'price-asc') return (a.price ?? Infinity) - (b.price ?? Infinity)
      if (sort === 'price-desc') return (b.price ?? -Infinity) - (a.price ?? -Infinity)
      if (sort === 'sqft-desc') return (b.sqft ?? 0) - (a.sqft ?? 0)
      if (sort === 'commute') {
        const minCommute = (l: ListingProfile) => {
          const vals = Object.values(l.commute_times || {})
          if (!vals.length) return Infinity
          const mins = vals.map(v => {
            const m = String(v).match(/(\d+)\s*min/i)
            return m ? parseInt(m[1]) : Infinity
          })
          return Math.min(...mins)
        }
        return minCommute(a) - minCommute(b)
      }
      // best match — keep server order, push disqualified to bottom
      if (a.disqualified && !b.disqualified) return 1
      if (!a.disqualified && b.disqualified) return -1
      return 0
    }
    return result.sort(cmp)
  }, [latestListings, sort, filter, prefs.favorites])

  const compareListings = useMemo(
    () => prefs.compare.map(url => latestListings.find(l => l.url === url)).filter(Boolean) as ListingProfile[],
    [prefs.compare, latestListings],
  )

  const matchScores = useMemo(() => {
    const map = new Map<string, { score: number; reasons: string[] }>()
    // If the backend hasn't sent a preferences event yet, fall back to the first user message
    const firstUserMsg = messages.find(m => m.role === 'user')?.content ?? ''
    const effectivePrefs = Object.keys(preferences).length > 0
      ? preferences
      : firstUserMsg ? { raw_query: firstUserMsg } : {}
    latestListings.forEach(l => {
      const result = computeMatchScore(l, effectivePrefs)
      if (result.score > 0) map.set(l.url, result)
    })
    return map
  }, [latestListings, preferences, messages])

  const scrollToListing = (url: string) => {
    cardRefs.current.get(url)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const idx = visibleListings.findIndex(l => l.url === url)
    if (idx >= 0) setFocusedIdx(idx)
  }

  const handleShareList = useCallback(() => {
    const lines = compareListings.length > 0 ? compareListings : visibleListings.slice(0, 5)
    const text = lines.map(l => `• ${l.address || l.url}${l.price ? ` — $${l.price.toLocaleString()}/mo` : ''}\n  ${l.url}`).join('\n')
    navigator.clipboard.writeText(text || latestListings.map(l => l.url).join('\n'))
      .then(() => notify('Shortlist copied to clipboard', 'success'))
      .catch(() => notify('Could not copy to clipboard', 'error'))
  }, [compareListings, visibleListings, latestListings, notify])

  const handleExport = useCallback(() => {
    const headers = ['address', 'price', 'bedrooms', 'bathrooms', 'sqft', 'pet_friendly', 'url']
    const rows = visibleListings.map(l => [
      l.address || '',
      l.price ?? '',
      l.bedrooms ?? '',
      l.bathrooms ?? '',
      l.sqft ?? '',
      l.pet_friendly ?? '',
      l.url,
    ])
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `listings-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    notify(`Exported ${rows.length} listings`, 'success')
  }, [visibleListings, notify])

  const handleShareOne = useCallback((url: string) => {
    navigator.clipboard.writeText(url)
      .then(() => notify('Link copied', 'success'))
      .catch(() => notify('Could not copy', 'error'))
  }, [notify])

  const handleToggleFavorite = useCallback((url: string) => {
    prefs.toggleFavorite(url)
    notify(prefs.isFavorite(url) ? 'Removed from saved' : 'Saved to your shortlist', 'success')
  }, [prefs, notify])

  const handleToggleCompare = useCallback((url: string) => {
    const wasIn = prefs.isComparing(url)
    const wasFull = prefs.compare.length >= prefs.MAX_COMPARE
    prefs.toggleCompare(url)
    if (!wasIn && wasFull) {
      notify('Compare is full — replaced oldest', 'info')
    }
  }, [prefs, notify])

  // Connection state toasts
  useEffect(() => {
    if (connectionState === 'error') notify('Connection lost — retrying', 'error')
  }, [connectionState, notify])

  // Auto-scroll
  useEffect(() => {
    if (!isInitial) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking, isInitial])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing
      const tag = (e.target as HTMLElement)?.tagName
      const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable
      const meta = e.metaKey || e.ctrlKey

      if (meta && e.key === 'k') { e.preventDefault(); newChat(); return }
      if (meta && e.key === 'b') { e.preventDefault(); setSidebarKey(k => k + 1); window.dispatchEvent(new Event('toggle-sidebar')); return }
      if ((meta && e.key === '/') || (e.key === '?' && !isTyping)) { e.preventDefault(); setShortcutsOpen(true); return }
      if (e.key === 'Escape') { setCompareOpen(false); setShortcutsOpen(false); return }

      if (isTyping) return

      if (e.key === 'j') {
        e.preventDefault()
        setFocusedIdx(i => {
          const next = Math.min(visibleListings.length - 1, i + 1)
          const url = visibleListings[next]?.url
          if (url) cardRefs.current.get(url)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          return next
        })
      }
      if (e.key === 'k') {
        e.preventDefault()
        setFocusedIdx(i => {
          const next = Math.max(0, i - 1)
          const url = visibleListings[next]?.url
          if (url) cardRefs.current.get(url)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          return next
        })
      }
      if (e.key === 'f' && focusedIdx >= 0) {
        const url = visibleListings[focusedIdx]?.url
        if (url) handleToggleFavorite(url)
      }
      if (e.key === 'c' && focusedIdx >= 0) {
        const url = visibleListings[focusedIdx]?.url
        if (url) handleToggleCompare(url)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [newChat, visibleListings, focusedIdx, handleToggleFavorite, handleToggleCompare])

  const compareCount = prefs.compare.length

  return (
    <div className="flex h-screen bg-transparent">
      <Sidebar
        key={sidebarKey}
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
          <header className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-ink-200/40 bg-cream-50/40 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal-600' : 'bg-coral-500'}`} />
              <span className="text-xs text-ink-500 tracking-wide">
                {connected ? 'Connected' : 'Reconnecting…'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShortcutsOpen(true)}
                className="text-xs px-2.5 py-1.5 rounded-full text-ink-500 hover:text-ink-900 hover:bg-cream-100 transition-colors flex items-center gap-1.5"
                title="Keyboard shortcuts (?)"
              >
                <kbd className="font-mono text-[0.65rem] font-semibold bg-cream-100 text-ink-700 border border-ink-200/70 px-1 py-0.5 rounded">?</kbd>
                Shortcuts
              </button>

              {confirmReset ? (
                <>
                  <span className="text-xs text-ink-500">Clear all chats?</span>
                  <button
                    onClick={() => { deleteAllSessions(); setConfirmReset(false); notify('All chats cleared', 'success') }}
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
                >
                  Reset all
                </button>
              )}
            </div>
          </header>

          {isInitial ? (
            <div className="flex-1 relative overflow-hidden flex flex-col items-center justify-center px-6 pb-12">
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

                <div className="mt-10 flex items-center gap-6 text-[0.7rem] uppercase tracking-[0.16em] text-ink-400 font-medium">
                  <span className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-teal-700" />Zillow</span>
                  <span className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-teal-700" />Apartments.com</span>
                  <span className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-teal-700" />Live commute data</span>
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
                  {visibleListings.map((l, i) => {
                    const ms = matchScores.get(l.url)
                    return (
                      <ListingCard
                        key={i}
                        listing={l}
                        preferences={preferences}
                        isFavorite={prefs.isFavorite(l.url)}
                        isComparing={prefs.isComparing(l.url)}
                        onToggleFavorite={handleToggleFavorite}
                        onToggleCompare={handleToggleCompare}
                        onShare={handleShareOne}
                        matchScore={ms?.score}
                        matchReasons={ms?.reasons}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </section>

        {hasListings && (
          <aside className="hidden lg:block overflow-y-auto bg-cream-100/55 backdrop-blur-md border-l border-ink-200/40" style={{ height: '100vh' }}>
            <div className="px-5 pt-6 pb-4 sticky top-0 bg-cream-100/70 backdrop-blur-md z-10 border-b border-ink-200/40 flex flex-col gap-3">
              <div>
                <p className="text-[0.65rem] uppercase tracking-[0.18em] text-ink-400 mb-1 font-medium">Curated matches</p>
                <h2 className="font-display text-xl font-medium text-ink-900">
                  {latestListings.length} {latestListings.length === 1 ? 'home' : 'homes'} for you
                </h2>
              </div>

              <ListingControls
                total={latestListings.length}
                visible={visibleListings.length}
                sort={sort}
                onSortChange={setSort}
                filter={filter}
                onFilterChange={setFilter}
                favoritesCount={prefs.favorites.length}
                onShare={handleShareList}
                onExport={handleExport}
              />
            </div>

            <div className="px-5 pt-4 mb-5">
              <div className="w-full h-72 rounded-2xl overflow-hidden border border-ink-200/60 shadow-sm">
                <ListingMap
                  listings={visibleListings}
                  onSelect={l => scrollToListing(l.url)}
                  hoveredUrl={hoveredUrl}
                />
              </div>
            </div>

            <div className="px-5 pb-32 flex flex-col gap-5">
              {visibleListings.length === 0 ? (
                <EmptyState
                  icon="search"
                  title="No matches with these filters"
                  description="Try removing a filter or expanding the criteria."
                  action={{
                    label: 'Reset filters',
                    onClick: () => setFilter({ petsOnly: false, favoritesOnly: false, hideDisqualified: false }),
                  }}
                />
              ) : (
                visibleListings.map((l, i) => (
                  <div
                    key={i}
                    ref={el => { if (el) cardRefs.current.set(l.url, el); else cardRefs.current.delete(l.url) }}
                    className="fade-up"
                    style={{ animationDelay: `${Math.min(i * 50, 300)}ms` }}
                  >
                    <ListingCard
                      listing={l}
                      preferences={preferences}
                      isFavorite={prefs.isFavorite(l.url)}
                      isComparing={prefs.isComparing(l.url)}
                      onToggleFavorite={handleToggleFavorite}
                      onToggleCompare={handleToggleCompare}
                      onShare={handleShareOne}
                      onHover={setHoveredUrl}
                      focused={focusedIdx === i}
                      matchScore={matchScores.get(l.url)?.score}
                      matchReasons={matchScores.get(l.url)?.reasons}
                    />
                  </div>
                ))
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Loading skeletons (right rail while a search is in flight, no listings yet) */}
      {!hasListings && isThinking && !isInitial && (
        <div className="hidden lg:block fixed right-0 top-0 w-[30rem] h-screen overflow-y-auto bg-cream-100/55 backdrop-blur-md border-l border-ink-200/40 z-10">
          <div className="px-5 pt-6 pb-4 border-b border-ink-200/40">
            <p className="text-[0.65rem] uppercase tracking-[0.18em] text-ink-400 mb-1 font-medium">Searching…</p>
            <h2 className="font-display text-xl font-medium text-ink-900">Finding your matches</h2>
          </div>
          <div className="px-5 pt-5">
            <SkeletonRail />
          </div>
        </div>
      )}

      {/* Compare drawer */}
      <CompareDrawer
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        listings={compareListings}
        onRemove={(url) => prefs.toggleCompare(url)}
      />

      {/* Floating compare button */}
      {compareCount > 0 && !compareOpen && (
        <button
          onClick={() => setCompareOpen(true)}
          className="fixed bottom-6 right-6 z-40 px-4 py-3 rounded-full bg-teal-700 text-cream-50 shadow-lg hover:bg-teal-600 transition-all hover:scale-105 flex items-center gap-2 animate-toast-in"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-4 h-4">
            <rect x="2" y="3" width="5" height="10" rx="1" />
            <rect x="9" y="3" width="5" height="10" rx="1" />
          </svg>
          <span className="text-sm font-medium">Compare</span>
          <span className="bg-cream-50 text-teal-700 text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full">{compareCount}</span>
        </button>
      )}

      <KeyboardShortcuts open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  )
}
