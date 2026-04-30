import { useState, useRef, useEffect } from 'react'

export type SortKey = 'best' | 'price-asc' | 'price-desc' | 'commute' | 'sqft-desc'

const SORT_LABELS: Record<SortKey, string> = {
  'best': 'Best match',
  'price-asc': 'Price: Low → High',
  'price-desc': 'Price: High → Low',
  'commute': 'Shortest commute',
  'sqft-desc': 'Largest space',
}

export type FilterState = {
  petsOnly: boolean
  favoritesOnly: boolean
  hideDisqualified: boolean
}

type Props = {
  total: number
  visible: number
  sort: SortKey
  onSortChange: (s: SortKey) => void
  filter: FilterState
  onFilterChange: (f: FilterState) => void
  favoritesCount: number
  onShare: () => void
  onExport: () => void
}

export function ListingControls({
  total,
  visible,
  sort,
  onSortChange,
  filter,
  onFilterChange,
  favoritesCount,
  onShare,
  onExport,
}: Props) {
  const [sortOpen, setSortOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const sortRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) setSortOpen(false)
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const toggle = (key: keyof FilterState) => onFilterChange({ ...filter, [key]: !filter[key] })

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        {/* Sort */}
        <div ref={sortRef} className="relative">
          <button
            onClick={() => setSortOpen(v => !v)}
            className="text-xs px-3 py-1.5 rounded-full bg-white border border-ink-200/70 text-ink-700 hover:border-teal-600 hover:text-teal-700 transition-colors flex items-center gap-1.5 font-medium"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-3 h-3">
              <path d="M3 5h10M5 8h6M7 11h2" strokeLinecap="round" />
            </svg>
            {SORT_LABELS[sort]}
            <svg viewBox="0 0 16 16" fill="currentColor" className={`w-2.5 h-2.5 transition-transform ${sortOpen ? 'rotate-180' : ''}`}>
              <path d="M4 6l4 4 4-4z" />
            </svg>
          </button>
          {sortOpen && (
            <div className="absolute top-full left-0 mt-1 z-20 bg-white rounded-xl border border-ink-200/70 shadow-lg overflow-hidden min-w-[180px]">
              {(Object.keys(SORT_LABELS) as SortKey[]).map(k => (
                <button
                  key={k}
                  onClick={() => { onSortChange(k); setSortOpen(false) }}
                  className={`block w-full text-left text-xs px-3 py-2 transition-colors ${
                    sort === k ? 'bg-teal-50 text-teal-700 font-medium' : 'text-ink-700 hover:bg-cream-100'
                  }`}
                >
                  {SORT_LABELS[k]}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Filters */}
        <FilterPill active={filter.favoritesOnly} onClick={() => toggle('favoritesOnly')}>
          ♡ Saved {favoritesCount > 0 && `(${favoritesCount})`}
        </FilterPill>
        <FilterPill active={filter.petsOnly} onClick={() => toggle('petsOnly')}>
          🐾 Pets OK
        </FilterPill>
        <FilterPill active={filter.hideDisqualified} onClick={() => toggle('hideDisqualified')}>
          Hide filtered
        </FilterPill>

        {/* Spacer */}
        <div className="ml-auto flex items-center gap-1">
          <div ref={menuRef} className="relative">
            <button
              onClick={() => setMenuOpen(v => !v)}
              className="w-8 h-8 rounded-full bg-white border border-ink-200/70 flex items-center justify-center text-ink-700 hover:border-teal-600 hover:text-teal-700 transition-colors"
              aria-label="More actions"
              title="More actions"
            >
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <circle cx="3" cy="8" r="1.4" />
                <circle cx="8" cy="8" r="1.4" />
                <circle cx="13" cy="8" r="1.4" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute top-full right-0 mt-1 z-20 bg-white rounded-xl border border-ink-200/70 shadow-lg overflow-hidden min-w-[160px]">
                <button
                  onClick={() => { onShare(); setMenuOpen(false) }}
                  className="block w-full text-left text-xs px-3 py-2 text-ink-700 hover:bg-cream-100 transition-colors"
                >
                  Copy share link
                </button>
                <button
                  onClick={() => { onExport(); setMenuOpen(false) }}
                  className="block w-full text-left text-xs px-3 py-2 text-ink-700 hover:bg-cream-100 transition-colors"
                >
                  Export as CSV
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {visible !== total && (
        <p className="text-[0.7rem] text-ink-400">
          Showing {visible} of {total}
        </p>
      )}
    </div>
  )
}

function FilterPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
        active
          ? 'bg-teal-700 text-cream-50 border-teal-700'
          : 'bg-white border-ink-200/70 text-ink-700 hover:border-teal-600 hover:text-teal-700'
      }`}
    >
      {children}
    </button>
  )
}
