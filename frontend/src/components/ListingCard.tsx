import { useState } from 'react'
import type { ListingProfile } from '../hooks/useChat'

export function ListingCard({ listing }: { listing: ListingProfile }) {
  const [imgIdx, setImgIdx] = useState(0)
  const images = listing.images?.filter(Boolean) ?? []

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden w-72 shrink-0 flex flex-col">

      {/* Image carousel */}
      {images.length > 0 ? (
        <div className="relative h-44 bg-gray-100">
          <img
            src={images[imgIdx]}
            alt="listing"
            className="w-full h-full object-cover"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          {images.length > 1 && (
            <>
              <button
                onClick={() => setImgIdx(i => Math.max(0, i - 1))}
                disabled={imgIdx === 0}
                className="absolute left-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-black/40 text-white flex items-center justify-center text-xs disabled:opacity-30"
              >‹</button>
              <button
                onClick={() => setImgIdx(i => Math.min(images.length - 1, i + 1))}
                disabled={imgIdx === images.length - 1}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-black/40 text-white flex items-center justify-center text-xs disabled:opacity-30"
              >›</button>
              <span className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded-full">
                {imgIdx + 1}/{images.length}
              </span>
            </>
          )}
        </div>
      ) : (
        <div className="h-44 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">No photos</div>
      )}

      {/* Details */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            {listing.price && (
              <p className="font-semibold text-gray-900">${listing.price.toLocaleString()}<span className="font-normal text-gray-500 text-sm">/mo</span></p>
            )}
            {listing.address && (
              <p className="text-xs text-gray-500 truncate">{listing.address}</p>
            )}
          </div>
          <a
            href={listing.url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 text-xs px-2 py-1 rounded-full bg-[#1a3f6f] text-white hover:bg-[#15315a] transition-colors"
          >
            View →
          </a>
        </div>

        {/* Pills */}
        <div className="flex flex-wrap gap-1">
          {listing.floor != null && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Floor {listing.floor}</span>
          )}
          {listing.pet_friendly === true && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Pets OK</span>
          )}
          {listing.furnishing && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{listing.furnishing}</span>
          )}
          {listing.views && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">Views</span>
          )}
        </div>

        {/* Commute times */}
        {listing.commute_times && Object.keys(listing.commute_times).length > 0 && (
          <div className="flex flex-col gap-0.5">
            {Object.entries(listing.commute_times).map(([dest, time]) => (
              <p key={dest} className="text-xs text-gray-500">🚇 <span className="text-gray-700">{time}</span> to {dest}</p>
            ))}
          </div>
        )}

        {/* Nearby places */}
        {listing.nearby_places && Object.keys(listing.nearby_places).length > 0 && (
          <div className="flex flex-col gap-0.5">
            {Object.entries(listing.nearby_places).map(([type, info]) => (
              <p key={type} className="text-xs text-gray-500">📍 {info}</p>
            ))}
          </div>
        )}

        {/* Notes / description */}
        {(listing.notes || listing.description) && (
          <p className="text-xs text-gray-500 leading-relaxed">{listing.notes || listing.description}</p>
        )}
      </div>
    </div>
  )
}
