import { useEffect, useState } from 'react'
import { APIProvider, Map, AdvancedMarker, InfoWindow, useMapsLibrary } from '@vis.gl/react-google-maps'
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

  return (
    <>
      {pinned.map((p, i) => (
        <AdvancedMarker
          key={i}
          position={{ lat: p.lat, lng: p.lng }}
          onClick={() => setSelected(p)}
        >
          <div className="bg-gray-900 text-white text-xs font-semibold px-2 py-1 rounded-full shadow-md whitespace-nowrap cursor-pointer hover:bg-gray-700 transition-colors">
            ${p.listing.price?.toLocaleString()}/mo
          </div>
        </AdvancedMarker>
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
            <a
              href={selected.listing.url}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline mt-1"
            >
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
  if (!addressedListings.length || !API_KEY) return null

  return (
    <APIProvider apiKey={API_KEY}>
      <Map
        defaultCenter={{ lat: 37.8716, lng: -122.2727 }}
        defaultZoom={12}
        mapId="rental-map"
        style={{ width: '100%', height: '100%' }}
        disableDefaultUI
        zoomControl
      >
        <Markers listings={addressedListings} />
      </Map>
    </APIProvider>
  )
}
