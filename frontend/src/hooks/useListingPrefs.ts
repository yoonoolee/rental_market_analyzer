import { useEffect, useState, useCallback } from 'react'

const FAV_KEY = 'rental_favorites'
const COMPARE_KEY = 'rental_compare'
const MAX_COMPARE = 3

function read(key: string): string[] {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function write(key: string, value: string[]) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* noop */
  }
}

export function useListingPrefs() {
  const [favorites, setFavorites] = useState<string[]>(() => read(FAV_KEY))
  const [compare, setCompare] = useState<string[]>(() => read(COMPARE_KEY))

  useEffect(() => write(FAV_KEY, favorites), [favorites])
  useEffect(() => write(COMPARE_KEY, compare), [compare])

  const toggleFavorite = useCallback((url: string) => {
    setFavorites(prev => prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url])
  }, [])

  const toggleCompare = useCallback((url: string) => {
    setCompare(prev => {
      if (prev.includes(url)) return prev.filter(u => u !== url)
      if (prev.length >= MAX_COMPARE) return [...prev.slice(1), url]
      return [...prev, url]
    })
  }, [])

  const clearCompare = useCallback(() => setCompare([]), [])

  return {
    favorites,
    compare,
    toggleFavorite,
    toggleCompare,
    clearCompare,
    isFavorite: (url: string) => favorites.includes(url),
    isComparing: (url: string) => compare.includes(url),
    MAX_COMPARE,
  }
}
