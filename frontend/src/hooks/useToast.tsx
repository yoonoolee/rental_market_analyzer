import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type Toast = {
  id: string
  message: string
  kind: 'success' | 'error' | 'info'
}

type ToastCtx = {
  notify: (message: string, kind?: Toast['kind']) => void
}

const ctx = createContext<ToastCtx>({ notify: () => {} })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const notify = useCallback((message: string, kind: Toast['kind'] = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(prev => [...prev, { id, message, kind }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3200)
  }, [])

  return (
    <ctx.Provider value={{ notify }}>
      {children}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 items-center pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-2.5 rounded-full text-sm shadow-lg backdrop-blur-md border animate-toast-in flex items-center gap-2 ${
              t.kind === 'success'
                ? 'bg-teal-700/95 text-cream-50 border-teal-700'
                : t.kind === 'error'
                ? 'bg-coral-500/95 text-white border-coral-500'
                : 'bg-ink-900/90 text-cream-50 border-ink-900'
            }`}
          >
            {t.kind === 'success' && (
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
              </svg>
            )}
            {t.kind === 'error' && (
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 4a1 1 0 011 1v3a1 1 0 11-2 0V5a1 1 0 011-1zm0 7a1 1 0 100 2 1 1 0 000-2z" />
              </svg>
            )}
            {t.message}
          </div>
        ))}
      </div>
    </ctx.Provider>
  )
}

export const useToast = () => useContext(ctx)
