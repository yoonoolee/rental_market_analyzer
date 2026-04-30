import { useEffect } from 'react'
import type { ListingProfile } from '../hooks/useChat'

type Props = {
  open: boolean
  onClose: () => void
  listings: ListingProfile[]
  onRemove: (url: string) => void
}

export function CompareDrawer({ open, onClose, listings, onRemove }: Props) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const rows: Array<[string, (l: ListingProfile) => string]> = [
    ['Price', l => l.price ? `$${l.price.toLocaleString()}/mo` : '—'],
    ['Bedrooms', l => l.bedrooms != null ? (l.bedrooms === 0 ? 'Studio' : String(l.bedrooms)) : '—'],
    ['Bathrooms', l => l.bathrooms != null ? String(l.bathrooms) : '—'],
    ['Size', l => l.sqft ? `${l.sqft} sqft` : '—'],
    ['Floor', l => l.floor != null ? `Floor ${l.floor}` : '—'],
    ['Pets', l => l.pet_friendly === true ? 'Yes' : l.pet_friendly === false ? 'No' : '—'],
    ['Furnishing', l => l.furnishing || '—'],
    ['Condition', l => l.condition || '—'],
    ['Address', l => l.address || '—'],
    ['Amenities', l => (l.amenities && l.amenities.length) ? l.amenities.slice(0, 6).join(', ') : '—'],
  ]

  // Compute "best" per row to highlight (price/sqft only — measurable comparisons)
  const bestPriceUrl = (() => {
    const withPrice = listings.filter(l => l.price != null)
    if (!withPrice.length) return null
    return withPrice.reduce((min, l) => (l.price! < (min.price ?? Infinity) ? l : min), withPrice[0]).url
  })()
  const bestSqftUrl = (() => {
    const withSqft = listings.filter(l => l.sqft != null)
    if (!withSqft.length) return null
    return withSqft.reduce((max, l) => (l.sqft! > (max.sqft ?? 0) ? l : max), withSqft[0]).url
  })()

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6 animate-fade-in">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-5xl max-h-[90vh] bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl border border-ink-200/60 flex flex-col overflow-hidden animate-drawer-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-200/60 shrink-0">
          <div>
            <p className="text-[0.65rem] uppercase tracking-[0.18em] text-ink-400 font-medium">
              Side-by-side
            </p>
            <h2 className="font-display text-xl font-medium text-ink-900">
              Comparing {listings.length} {listings.length === 1 ? 'home' : 'homes'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-cream-100 flex items-center justify-center text-ink-500 hover:text-ink-900 transition-colors"
            aria-label="Close"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-5">
          {listings.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-ink-500">Pick listings from the rail to compare them.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse min-w-[640px]">
                <thead>
                  <tr>
                    <th className="text-left text-[0.65rem] uppercase tracking-wider text-ink-400 font-semibold pb-3 pr-4 align-bottom"> </th>
                    {listings.map(l => (
                      <th key={l.url} className="text-left pb-3 pr-4 align-bottom min-w-[180px]">
                        <div className="flex flex-col gap-2">
                          {l.images?.[0] && (
                            <div className="h-24 w-full rounded-lg overflow-hidden bg-ink-100">
                              <img src={l.images[0]} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                            </div>
                          )}
                          <div className="flex items-start justify-between gap-2">
                            <p className="font-display text-sm font-semibold text-ink-900 leading-tight line-clamp-2">
                              {l.address || 'Unnamed listing'}
                            </p>
                            <button
                              onClick={() => onRemove(l.url)}
                              className="shrink-0 w-5 h-5 rounded-full text-ink-400 hover:text-coral-500 hover:bg-coral-500/10 flex items-center justify-center"
                              title="Remove from compare"
                            >
                              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-2.5 h-2.5">
                                <path d="M2 2l8 8M10 2l-8 8" strokeLinecap="round" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([label, fn]) => (
                    <tr key={label} className="border-t border-ink-200/60">
                      <td className="text-[0.7rem] uppercase tracking-wider text-ink-400 font-semibold py-3 pr-4 align-top">{label}</td>
                      {listings.map(l => {
                        const isBest =
                          (label === 'Price' && bestPriceUrl === l.url && listings.length > 1) ||
                          (label === 'Size' && bestSqftUrl === l.url && listings.length > 1)
                        return (
                          <td
                            key={l.url}
                            className={`text-sm py-3 pr-4 align-top ${
                              isBest ? 'text-teal-700 font-semibold' : 'text-ink-700'
                            }`}
                          >
                            {fn(l)}
                            {isBest && (
                              <span className="ml-1.5 inline-block text-[0.6rem] uppercase tracking-wider text-teal-700 bg-teal-50 px-1.5 py-0.5 rounded-full font-bold">
                                Best
                              </span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}

                  {/* Commute rows — one per destination, dynamic */}
                  {(() => {
                    const allDests = new Set<string>()
                    listings.forEach(l => l.commute_times && Object.keys(l.commute_times).forEach(k => allDests.add(k)))
                    return Array.from(allDests).map(dest => (
                      <tr key={`commute-${dest}`} className="border-t border-ink-200/60">
                        <td className="text-[0.7rem] uppercase tracking-wider text-ink-400 font-semibold py-3 pr-4 align-top">→ {dest}</td>
                        {listings.map(l => {
                          const v = l.commute_times?.[dest]
                          return (
                            <td key={l.url} className="text-sm text-ink-700 py-3 pr-4 align-top">
                              {typeof v === 'string' ? v : '—'}
                            </td>
                          )
                        })}
                      </tr>
                    ))
                  })()}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        {listings.length > 0 && (
          <div className="border-t border-ink-200/60 px-6 py-3 flex items-center justify-end gap-2 shrink-0 bg-cream-50/60">
            {listings.map(l => (
              <a
                key={l.url}
                href={l.url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium px-3 py-1.5 rounded-full bg-ink-900 text-cream-50 hover:bg-teal-700 transition-colors max-w-[180px] truncate"
              >
                Open {l.address?.split(',')[0] || 'listing'} ↗
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
