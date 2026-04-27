import { useEffect, useState } from 'react'
import { APIProvider, Map, Marker, InfoWindow, useMapsLibrary } from '@vis.gl/react-google-maps'
import type { ListingProfile } from '../hooks/useChat'

type PinnedListing = {
  listing: ListingProfile
  lat: number
  lng: number
}

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string

function Markers({ listings }: { listings: ListingProfile[] }) {
  const geocodingLib = useMapsLibrary('geocoding')
  const [pinned, setPinned] = useState<PinnedListing[]>([])
  const [selected, setSelected] = useState<PinnedListing | null>(null)

  useEffect(() => {
    if (!geocodingLib) return
    const geocoder = new geocodingLib.Geocoder()
    const results: PinnedListing[] = []

    const tasks = listings
      .filter(l => l.address)
      .map(listing =>
        new Promise<void>(resolve => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          geocoder.geocode({ address: listing.address! }, (res: any, status: any) => {
            if (status === 'OK' && res?.[0]) {
              const loc = res[0].geometry.location
              results.push({ listing, lat: loc.lat(), lng: loc.lng() })
            }
            resolve()
          })
        })
      )

    Promise.all(tasks).then(() => setPinned([...results]))
  }, [geocodingLib, listings])

  const makeBubbleIcon = (price: number | undefined) => {
    const text = price ? `$${price.toLocaleString()}` : '?'
    const w = Math.max(52, text.length * 8 + 16)
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="28">
      <rect x="0" y="0" width="${w}" height="28" rx="14" fill="#111827"/>
      <text x="${w / 2}" y="19" text-anchor="middle" fill="white" font-size="12"
        font-family="system-ui,-apple-system,sans-serif" font-weight="700">${text}</text>
    </svg>`
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const g = (window as any).google?.maps
    return {
      url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
      scaledSize: g ? new g.Size(w, 28) : undefined,
      anchor: g ? new g.Point(w / 2, 14) : undefined,
    }
  }

  return (
    <>
      {pinned.map((p, i) => (
        <Marker
          key={i}
          position={{ lat: p.lat, lng: p.lng }}
          onClick={() => setSelected(p)}
          icon={makeBubbleIcon(p.listing.price)}
        />
      ))}

      {selected && (
        <InfoWindow
          position={{ lat: selected.lat, lng: selected.lng }}
          onCloseClick={() => setSelected(null)}
        >
          <div className="text-xs flex flex-col gap-0.5 min-w-32">
            <p className="font-semibold text-gray-900">${selected.listing.price?.toLocaleString()}/mo</p>
            {(selected.listing.bedrooms != null || selected.listing.bathrooms != null) && (
              <p className="text-gray-500">
                {selected.listing.bedrooms != null ? `${selected.listing.bedrooms} bd` : ''}
                {selected.listing.bedrooms != null && selected.listing.bathrooms != null ? ' · ' : ''}
                {selected.listing.bathrooms != null ? `${selected.listing.bathrooms} ba` : ''}
              </p>
            )}
            <p className="text-gray-500">{selected.listing.address}</p>
            <a href={selected.listing.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline mt-1">
              View listing →
            </a>
          </div>
        </InfoWindow>
      )}
    </>
  )
}

export function ListingMap({ listings }: { listings: ListingProfile[] }) {
  const addressedListings = listings.filter(l => l.address)
  if (!addressedListings.length) return null

  return (
    <APIProvider apiKey={API_KEY}>
      <Map
        defaultCenter={{ lat: 37.8716, lng: -122.2727 }}
        defaultZoom={12}
        style={{ width: '100%', height: '100%' }}
        disableDefaultUI
        zoomControl
      >
        <Markers listings={addressedListings} />
      </Map>
    </APIProvider>
  )
}
