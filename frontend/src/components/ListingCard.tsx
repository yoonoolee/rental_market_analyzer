import { useState } from 'react'
import type { ListingProfile } from '../hooks/useChat'

export function ListingCard({ listing, preferences }: { listing: ListingProfile, preferences?: Record<string, unknown> }) {
  const [imgIdx, setImgIdx] = useState(0)
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

  return (
    <article className="rounded-2xl border border-gray-200 bg-white overflow-hidden flex flex-col shadow-sm">
      {listing.disqualified && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-200 text-xs text-red-700">
          Disqualified: {listing.disqualify_reason || 'did not match hard requirements'}
        </div>
      )}

      {/* Image carousel */}
      {images.length > 0 ? (
        <div className="relative h-52 bg-gray-100">
          <img
            src={images[imgIdx]}
            alt="listing"
            className="w-full h-full object-cover"
            referrerPolicy="no-referrer"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          {images.length > 1 && (
            <>
              <button onClick={() => setImgIdx(i => Math.max(0, i - 1))} disabled={imgIdx === 0}
                className="absolute left-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/40 text-white flex items-center justify-center text-sm disabled:opacity-30">‹</button>
              <button onClick={() => setImgIdx(i => Math.min(images.length - 1, i + 1))} disabled={imgIdx === images.length - 1}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/40 text-white flex items-center justify-center text-sm disabled:opacity-30">›</button>
              <span className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded-full">
                {imgIdx + 1}/{images.length}
              </span>
            </>
          )}
        </div>
      ) : (
        <div className="h-52 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">No photos</div>
      )}

      {/* Details */}
      <div className="p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            {listing.price != null && (
              <p className="text-xl font-semibold text-gray-900">${listing.price.toLocaleString()}<span className="font-normal text-gray-500 text-sm">/mo</span></p>
            )}
            {(listing.bedrooms != null || listing.bathrooms != null) && (
              <p className="text-sm text-gray-600 mt-0.5">
                {listing.bedrooms != null ? `${listing.bedrooms} bd` : ''}
                {listing.bedrooms != null && listing.bathrooms != null ? ' · ' : ''}
                {listing.bathrooms != null ? `${listing.bathrooms} ba` : ''}
              </p>
            )}
            {listing.address && <p className="text-sm text-gray-500 mt-0.5">{listing.address}</p>}
          </div>
          <a href={listing.url} target="_blank" rel="noreferrer"
            className="shrink-0 text-sm px-3 py-1.5 rounded-full bg-[#1a3f6f] text-white hover:bg-[#15315a] transition-colors">
            View →
          </a>
        </div>

        {/* Pills */}
        <div className="flex flex-wrap gap-1.5">
          {listing.pet_friendly === true && cares('pet') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">Pets OK</span>
          )}
          {listing.views === true && cares('view') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">Views</span>
          )}
          {listing.furnishing && cares('furnish') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">{listing.furnishing}</span>
          )}
          {listing.modern_finishes === true && cares('modern') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">Modern finishes</span>
          )}
          {listing.natural_light === true && cares('light') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">Natural light</span>
          )}
          {listing.spacious === true && cares('spacious') && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">Spacious</span>
          )}
        </div>

        {/* Commute times */}
        {listing.commute_times && Object.keys(listing.commute_times).length > 0 && (
          <div className="flex flex-col gap-1">
            {Object.entries(listing.commute_times).map(([dest, time]) => (
              <p key={dest} className="text-sm text-gray-500">🚇 <span className="text-gray-700">{time}</span> to {dest}</p>
            ))}
          </div>
        )}

        {/* Nearby places */}
        {listing.nearby_places && Object.keys(listing.nearby_places).length > 0 && (
          <div className="flex flex-col gap-1">
            {Object.entries(listing.nearby_places).map(([type, info]) => (
              <p key={type} className="text-sm text-gray-500">📍 {info}</p>
            ))}
          </div>
        )}

        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
          {details.map(([label, value]) => value ? (
            <div key={label}>
              <dt className="text-gray-400 text-xs">{label}</dt>
              <dd className="text-gray-600 truncate">{value}</dd>
            </div>
          ) : null)}
        </dl>

        {amenities.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {amenities.slice(0, 8).map((item) => (
              <span key={item} className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">{item}</span>
            ))}
          </div>
        )}

        {(listing.notes || listing.description) && (
          <p className="text-sm text-gray-500 leading-relaxed">{listing.notes || listing.description}</p>
        )}
      </div>
    </article>
  )
}
