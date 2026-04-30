import { useState } from 'react'
import type { ListingProfile } from '../hooks/useChat'

export function ListingCard({ listing, preferences }: { listing: ListingProfile, preferences?: Record<string, unknown> }) {
  const [imgIdx, setImgIdx] = useState(0)
  const [favorited, setFavorited] = useState(false)
  const images = listing.images?.filter(Boolean) ?? []
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

  return (
    <article className={`group rounded-2xl bg-white overflow-hidden flex flex-col transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_12px_30px_-12px_rgba(0,0,0,0.18)] border ${listing.disqualified ? 'border-coral-500/30 opacity-90' : 'border-ink-200/60 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.06)]'}`}>
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
        {images.length > 0 ? (
          <div className="relative h-60 bg-ink-100 overflow-hidden">
            <img
              src={images[imgIdx]}
              alt="listing"
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
              referrerPolicy="no-referrer"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />

            {images.length > 1 && (
              <>
                <button
                  onClick={() => setImgIdx(i => Math.max(0, i - 1))}
                  disabled={imgIdx === 0}
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 text-ink-900 shadow-md flex items-center justify-center text-base disabled:opacity-0 hover:scale-110 transition-all"
                  aria-label="Previous photo"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                    <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  onClick={() => setImgIdx(i => Math.min(images.length - 1, i + 1))}
                  disabled={imgIdx === images.length - 1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 text-ink-900 shadow-md flex items-center justify-center text-base disabled:opacity-0 hover:scale-110 transition-all"
                  aria-label="Next photo"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                    <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>

                {/* Dot indicators */}
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1">
                  {images.slice(0, 6).map((_, i) => (
                    <span
                      key={i}
                      className={`rounded-full transition-all ${
                        i === imgIdx ? 'w-1.5 h-1.5 bg-white' : 'w-1 h-1 bg-white/60'
                      }`}
                    />
                  ))}
                  {images.length > 6 && (
                    <span className="text-[0.65rem] text-white ml-1.5 font-medium">+{images.length - 6}</span>
                  )}
                </div>
              </>
            )}

            {/* Favorite */}
            <button
              onClick={() => setFavorited(f => !f)}
              className="absolute top-3 right-3 w-8 h-8 rounded-full bg-white/85 backdrop-blur-sm flex items-center justify-center hover:bg-white transition-colors"
              aria-label="Save"
            >
              <svg
                viewBox="0 0 24 24"
                fill={favorited ? '#e35d4f' : 'none'}
                stroke={favorited ? '#e35d4f' : '#404040'}
                strokeWidth="2"
                className="w-4 h-4 transition-colors"
              >
                <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {/* Bedroom pill */}
            {listing.bedrooms != null && (
              <span className="absolute top-3 left-3 bg-white/95 backdrop-blur-sm text-[0.7rem] font-semibold text-ink-900 px-2.5 py-1 rounded-full shadow-sm">
                {listing.bedrooms === 0 ? 'Studio' : `${listing.bedrooms} bd`}
                {listing.bathrooms != null && ` · ${listing.bathrooms} ba`}
              </span>
            )}
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
        {/* Header — price + address + CTA */}
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

        {/* Feature pills */}
        {hasFeaturePills && (
          <div className="flex flex-wrap gap-1.5">
            {listing.pet_friendly === true && cares('pet') && (
              <Pill icon="🐾">Pets welcome</Pill>
            )}
            {listing.views === true && cares('view') && (
              <Pill icon="✦">Great views</Pill>
            )}
            {listing.furnishing && cares('furnish') && (
              <Pill>{listing.furnishing}</Pill>
            )}
            {listing.modern_finishes === true && cares('modern') && (
              <Pill>Modern finishes</Pill>
            )}
            {listing.natural_light === true && cares('light') && (
              <Pill icon="☀">Natural light</Pill>
            )}
            {listing.spacious === true && cares('spacious') && (
              <Pill>Spacious</Pill>
            )}
          </div>
        )}

        {/* Commute */}
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

        {/* Nearby */}
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

        {/* Details grid */}
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

        {/* Amenities */}
        {amenities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {amenities.slice(0, 8).map((item) => (
              <span key={item} className="text-[0.7rem] px-2 py-1 rounded-md bg-teal-50 text-teal-700 border border-teal-600/15 font-medium">
                {item}
              </span>
            ))}
          </div>
        )}

        {/* Description */}
        {(listing.notes || listing.description) && (
          <p className="text-sm text-ink-500 leading-relaxed italic font-display border-l-2 border-teal-600/30 pl-3 mt-1">
            {listing.notes || listing.description}
          </p>
        )}
      </div>
    </article>
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
