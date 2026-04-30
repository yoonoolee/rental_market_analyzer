import { useState, useEffect } from 'react'
import type { ListingProfile } from '../hooks/useChat'

type Props = {
  listing: ListingProfile
  preferences?: Record<string, unknown>
  isFavorite?: boolean
  isComparing?: boolean
  onToggleFavorite?: (url: string) => void
  onToggleCompare?: (url: string) => void
  onShare?: (url: string) => void
  onHover?: (url: string | null) => void
  matchScore?: number
  matchReasons?: string[]
  focused?: boolean
}

export function ListingCard({
  listing,
  preferences,
  isFavorite,
  isComparing,
  onToggleFavorite,
  onToggleCompare,
  onShare,
  onHover,
  matchScore,
  matchReasons,
  focused,
}: Props) {
  const [scoreTooltip, setScoreTooltip] = useState(false)
  const [reasonsOpen, setReasonsOpen] = useState(false)
  const [imgIdx, setImgIdx] = useState(0)
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [failedImgs, setFailedImgs] = useState<Set<number>>(new Set())
  const images = (listing.images?.filter(Boolean) ?? []).map(
    url => `/imgproxy?url=${encodeURIComponent(url)}`
  )
  const visibleImages = images.filter((_, i) => !failedImgs.has(i))
  const amenities = listing.amenities?.filter(Boolean) ?? []

  const prefText = [
    ...((preferences?.hard_requirements as string[]) || []),
    ...((preferences?.soft_constraints as string[]) || []),
    ...((preferences?.trade_off_rules as string[]) || []),
    (preferences?.lifestyle_notes as string) || '',
  ].join(' ').toLowerCase()

  const cares = (term: string) => prefText.includes(term)

  const details: Array<[string, string | undefined]> = [
    ['Size', listing.sqft ? `${listing.sqft} sqft` : undefined],
    ['Floor', listing.floor != null ? `Floor ${listing.floor}` : undefined],
    cares('furnish') ? ['Furnishing', listing.furnishing] : ['Furnishing', undefined],
    ['Condition', listing.condition],
    cares('pet') ? ['Pet deposit', listing.pet_deposit != null ? `$${listing.pet_deposit}` : undefined] : ['Pet deposit', undefined],
  ]

  const hasFeaturePills =
    (listing.pet_friendly === true && cares('pet')) ||
    (listing.views === true && cares('view')) ||
    (listing.furnishing && cares('furnish')) ||
    (listing.modern_finishes === true && cares('modern')) ||
    (listing.natural_light === true && cares('light')) ||
    (listing.spacious === true && cares('spacious'))

  // Lightbox keyboard nav
  useEffect(() => {
    if (!lightboxOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightboxOpen(false)
      if (e.key === 'ArrowLeft') setImgIdx(i => Math.max(0, i - 1))
      if (e.key === 'ArrowRight') setImgIdx(i => Math.min(visibleImages.length - 1, i + 1))
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [lightboxOpen, images.length])

  const cardClasses = [
    'group rounded-2xl bg-white overflow-hidden flex flex-col transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_12px_30px_-12px_rgba(0,0,0,0.18)] border',
    listing.disqualified ? 'border-coral-500/30 opacity-90' : 'border-ink-200/60 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.06)]',
    isComparing ? 'listing-comparing' : '',
    focused ? 'listing-focused' : '',
  ].filter(Boolean).join(' ')

  return (
    <>
    <article
      className={cardClasses}
      onMouseEnter={() => onHover?.(listing.url)}
      onMouseLeave={() => onHover?.(null)}
    >
      {listing.disqualified && (
        <div className="px-4 py-2 bg-coral-500/5 border-b border-coral-500/20 text-[0.7rem] text-coral-600 flex items-center gap-1.5">
          <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 shrink-0">
            <path fillRule="evenodd" d="M8 16A8 8 0 108 0a8 8 0 000 16zM7 4a1 1 0 012 0v4a1 1 0 11-2 0V4zm1 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <span className="truncate"><span className="font-semibold uppercase tracking-wider text-[0.6rem]">Filtered: </span>{listing.disqualify_reason || 'did not match hard requirements'}</span>
        </div>
      )}

      {/* Image area */}
      <div className="relative">
        {visibleImages.length > 0 ? (
          <div className="relative h-60 bg-ink-100 overflow-hidden cursor-zoom-in" onClick={() => setLightboxOpen(true)}>
            <img
              src={visibleImages[Math.min(imgIdx, visibleImages.length - 1)]}
              alt="listing"
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
              onError={() => setFailedImgs(s => { const n = new Set(s); n.add(images.indexOf(visibleImages[Math.min(imgIdx, visibleImages.length - 1)])); return n })}
            />

            {visibleImages.length > 1 && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); setImgIdx(i => Math.max(0, i - 1)) }}
                  disabled={imgIdx === 0}
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 text-ink-900 shadow-md flex items-center justify-center text-base disabled:opacity-0 hover:scale-110 transition-all"
                  aria-label="Previous photo"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                    <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setImgIdx(i => Math.min(visibleImages.length - 1, i + 1)) }}
                  disabled={imgIdx === visibleImages.length - 1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 text-ink-900 shadow-md flex items-center justify-center text-base disabled:opacity-0 hover:scale-110 transition-all"
                  aria-label="Next photo"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                    <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>

                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1">
                  {visibleImages.slice(0, 6).map((_, i) => (
                    <span
                      key={i}
                      className={`rounded-full transition-all ${
                        i === imgIdx ? 'w-1.5 h-1.5 bg-white' : 'w-1 h-1 bg-white/60'
                      }`}
                    />
                  ))}
                  {visibleImages.length > 6 && (
                    <span className="text-[0.65rem] text-white ml-1.5 font-medium">+{visibleImages.length - 6}</span>
                  )}
                </div>
              </>
            )}

            {/* Top-right action stack */}
            <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5">
              <button
                onClick={(e) => { e.stopPropagation(); onToggleFavorite?.(listing.url) }}
                className="w-8 h-8 rounded-full bg-white/85 backdrop-blur-sm flex items-center justify-center hover:bg-white transition-colors"
                aria-label={isFavorite ? 'Remove from saved' : 'Save'}
                title={isFavorite ? 'Saved' : 'Save'}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill={isFavorite ? '#e35d4f' : 'none'}
                  stroke={isFavorite ? '#e35d4f' : '#404040'}
                  strokeWidth="2"
                  className="w-4 h-4 transition-colors"
                >
                  <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {onToggleCompare && (
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleCompare(listing.url) }}
                  className={`w-8 h-8 rounded-full backdrop-blur-sm flex items-center justify-center transition-all ${
                    isComparing
                      ? 'bg-teal-700 text-white'
                      : 'bg-white/85 text-ink-700 hover:bg-white'
                  }`}
                  aria-label={isComparing ? 'Remove from compare' : 'Add to compare'}
                  title={isComparing ? 'In compare' : 'Compare'}
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-3.5 h-3.5">
                    <rect x="2" y="3" width="5" height="10" rx="1" />
                    <rect x="9" y="3" width="5" height="10" rx="1" />
                  </svg>
                </button>
              )}
              {onShare && (
                <button
                  onClick={(e) => { e.stopPropagation(); onShare(listing.url) }}
                  className="w-8 h-8 rounded-full bg-white/85 backdrop-blur-sm flex items-center justify-center hover:bg-white transition-colors text-ink-700"
                  aria-label="Copy link"
                  title="Copy link"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-3.5 h-3.5">
                    <path d="M6.5 9.5l3-3M5 8l-1.5 1.5a2.5 2.5 0 003.5 3.5L8.5 11.5M11 8l1.5-1.5a2.5 2.5 0 00-3.5-3.5L7.5 4.5" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </div>

            {/* Top-left: bedrooms + match score */}
            <div className="absolute top-3 left-3 flex flex-col items-start gap-1.5">
              {listing.bedrooms != null && (
                <span className="bg-white/95 backdrop-blur-sm text-[0.7rem] font-semibold text-ink-900 px-2.5 py-1 rounded-full shadow-sm">
                  {listing.bedrooms === 0 ? 'Studio' : `${listing.bedrooms} bd`}
                  {listing.bathrooms != null && ` · ${listing.bathrooms} ba`}
                </span>
              )}
              {matchScore != null && (
                <div className="relative">
                  <button
                    className={`text-cream-50 text-[0.7rem] font-bold px-2.5 py-1 rounded-full shadow-sm flex items-center gap-1 transition-colors ${
                      matchScore >= 80 ? 'bg-teal-700 hover:bg-teal-600' : matchScore >= 60 ? 'bg-teal-600 hover:bg-teal-700' : 'bg-ink-500 hover:bg-ink-700'
                    }`}
                    onMouseEnter={() => setScoreTooltip(true)}
                    onMouseLeave={() => setScoreTooltip(false)}
                    onClick={(e) => { e.stopPropagation(); setScoreTooltip(v => !v) }}
                    aria-label={`Match score ${matchScore}%`}
                  >
                    {matchScore}% match
                  </button>
                  {scoreTooltip && matchReasons && matchReasons.length > 0 && (
                    <div className="absolute left-0 top-full mt-1.5 z-30 bg-ink-900 text-cream-50 rounded-xl p-3 shadow-xl min-w-[180px] max-w-[220px] animate-fade-in">
                      <p className="text-[0.6rem] uppercase tracking-wider text-ink-400 mb-1.5 font-semibold">Why this score</p>
                      <ul className="flex flex-col gap-1">
                        {matchReasons.map((r, i) => (
                          <li key={i} className="text-[0.72rem] leading-snug flex items-start gap-1.5">
                            <span className="text-teal-400 mt-0.5 shrink-0">✓</span>
                            <span>{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="h-60 bg-ink-100 flex items-center justify-center text-ink-400 text-sm">
            <div className="flex flex-col items-center gap-2">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8 opacity-50">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
              <span className="text-xs">No photos available</span>
            </div>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-5 flex flex-col gap-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {listing.price != null ? (
              <p className="font-display text-2xl font-semibold text-ink-900 leading-none tracking-tight">
                ${listing.price.toLocaleString()}
                <span className="font-sans text-sm font-normal text-ink-500 ml-1">/mo</span>
              </p>
            ) : (
              <p className="font-display text-lg font-medium text-ink-400 leading-none italic">
                Price on request
              </p>
            )}
            {listing.address && (
              <p className="text-sm text-ink-500 mt-2 truncate">{listing.address}</p>
            )}
          </div>
          <a
            href={listing.url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs font-medium px-3.5 py-2 rounded-full bg-ink-900 text-cream-50 hover:bg-teal-700 transition-colors flex items-center gap-1"
          >
            View
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
              <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        </div>

        {hasFeaturePills && (
          <div className="flex flex-wrap gap-1.5">
            {listing.pet_friendly === true && cares('pet') && <Pill icon="🐾">Pets welcome</Pill>}
            {listing.views === true && cares('view') && <Pill icon="✦">Great views</Pill>}
            {listing.furnishing && cares('furnish') && <Pill>{listing.furnishing}</Pill>}
            {listing.modern_finishes === true && cares('modern') && <Pill>Modern finishes</Pill>}
            {listing.natural_light === true && cares('light') && <Pill icon="☀">Natural light</Pill>}
            {listing.spacious === true && cares('spacious') && <Pill>Spacious</Pill>}
          </div>
        )}

        {listing.commute_times && Object.keys(listing.commute_times).length > 0 && (
          <div className="rounded-xl bg-cream-100 px-3.5 py-3 flex flex-col gap-1.5">
            <p className="text-[0.62rem] uppercase tracking-[0.16em] text-ink-400 font-semibold">Commute</p>
            {Object.entries(listing.commute_times).map(([dest, time]) => {
              const label = typeof time === 'string' ? time : JSON.stringify(time)
              return (
                <div key={dest} className="flex items-center gap-2 text-sm">
                  <span className="text-ink-400 text-xs">→</span>
                  <span className="text-ink-900 font-medium">{label}</span>
                  <span className="text-ink-500 truncate">to {dest}</span>
                </div>
              )
            })}
          </div>
        )}

        {listing.nearby_places && Object.keys(listing.nearby_places).length > 0 && (
          <div className="rounded-xl bg-cream-100 px-3.5 py-3 flex flex-col gap-1.5">
            <p className="text-[0.62rem] uppercase tracking-[0.16em] text-ink-400 font-semibold">Nearby</p>
            {Object.entries(listing.nearby_places).map(([type, info]) => {
              let label: string
              if (typeof info === 'string') {
                label = info
              } else {
                const p = info as { name?: string; distance_meters?: number }
                const dist = p.distance_meters ? ` · ${(p.distance_meters / 1609).toFixed(1)} mi` : ''
                label = (p.name ?? type) + dist
              }
              return (
                <div key={type} className="flex items-center gap-2 text-sm text-ink-700">
                  <span className="text-ink-400 text-xs">·</span>
                  <span className="truncate">{label}</span>
                </div>
              )
            })}
          </div>
        )}

        {details.some(([, v]) => v) && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 pt-1">
            {details.map(([label, value]) => value ? (
              <div key={label}>
                <dt className="text-[0.65rem] uppercase tracking-wider text-ink-400 font-medium">{label}</dt>
                <dd className="text-sm text-ink-700 truncate mt-0.5">{value}</dd>
              </div>
            ) : null)}
          </dl>
        )}

        {amenities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {amenities.slice(0, 8).map((item) => (
              <span key={item} className="text-[0.7rem] px-2 py-1 rounded-md bg-teal-50 text-teal-700 border border-teal-600/15 font-medium">
                {item}
              </span>
            ))}
          </div>
        )}

        {/* Agent's take */}
        {(listing.notes || listing.description) && (
          <div className="rounded-xl bg-cream-100/80 border border-ink-200/50 px-3.5 py-3 flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 text-teal-700 shrink-0">
                <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm.75 11.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM8 4a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 4z" />
              </svg>
              <p className="text-[0.6rem] uppercase tracking-[0.16em] text-teal-700 font-semibold">Agent's take</p>
            </div>
            <p className="text-[0.82rem] text-ink-600 leading-relaxed font-display italic">
              {listing.notes || listing.description}
            </p>
          </div>
        )}

        {/* Inline match reasoning */}
        {matchScore != null && matchReasons && matchReasons.length > 0 && (
          <div className="border border-ink-200/50 rounded-xl overflow-hidden">
            <button
              onClick={() => setReasonsOpen(v => !v)}
              className="w-full flex items-center justify-between px-3.5 py-2.5 text-left hover:bg-cream-100/60 transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${matchScore >= 80 ? 'bg-teal-700' : matchScore >= 60 ? 'bg-teal-600' : 'bg-ink-400'}`} />
                <span className="text-[0.72rem] font-semibold text-ink-700">
                  {matchScore}% match
                </span>
                <span className="text-[0.68rem] text-ink-400">· why?</span>
              </div>
              <svg viewBox="0 0 16 16" fill="currentColor" className={`w-3 h-3 text-ink-400 transition-transform ${reasonsOpen ? 'rotate-180' : ''}`}>
                <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 011.06 0L8 8.94l2.72-2.72a.75.75 0 111.06 1.06l-3.25 3.25a.75.75 0 01-1.06 0L4.22 7.28a.75.75 0 010-1.06z" clipRule="evenodd" />
              </svg>
            </button>
            {reasonsOpen && (
              <div className="px-3.5 pb-3 flex flex-col gap-1 border-t border-ink-200/50 pt-2.5 bg-cream-50/60">
                {matchReasons.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 text-[0.75rem] text-ink-600 leading-snug">
                    <span className="text-teal-600 shrink-0 mt-0.5">✓</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </article>

    {/* Lightbox */}
    {lightboxOpen && visibleImages.length > 0 && (
      <div className="fixed inset-0 z-[60] bg-ink-900/95 flex items-center justify-center animate-fade-in" onClick={() => setLightboxOpen(false)}>
        <button
          onClick={(e) => { e.stopPropagation(); setLightboxOpen(false) }}
          className="absolute top-5 right-5 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors z-10"
          aria-label="Close"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
            <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
          </svg>
        </button>
        <div className="absolute top-5 left-5 text-cream-50 text-sm font-mono">
          {imgIdx + 1} / {visibleImages.length}
        </div>

        <img
          src={visibleImages[Math.min(imgIdx, visibleImages.length - 1)]}
          alt=""
          className="max-w-[92vw] max-h-[88vh] object-contain rounded-md shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        />

        {visibleImages.length > 1 && (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); setImgIdx(i => Math.max(0, i - 1)) }}
              disabled={imgIdx === 0}
              className="absolute left-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors disabled:opacity-30"
              aria-label="Previous"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
                <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setImgIdx(i => Math.min(visibleImages.length - 1, i + 1)) }}
              disabled={imgIdx === visibleImages.length - 1}
              className="absolute right-6 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors disabled:opacity-30"
              aria-label="Next"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
                <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </>
        )}
      </div>
    )}
    </>
  )
}

function Pill({ children, icon }: { children: React.ReactNode; icon?: string }) {
  return (
    <span className="text-[0.7rem] px-2.5 py-1 rounded-full bg-ink-100 text-ink-700 font-medium inline-flex items-center gap-1">
      {icon && <span className="text-xs">{icon}</span>}
      {children}
    </span>
  )
}
