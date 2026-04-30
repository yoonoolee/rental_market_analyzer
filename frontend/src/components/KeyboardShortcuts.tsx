import { useEffect } from 'react'

type Props = {
  open: boolean
  onClose: () => void
}

const SHORTCUTS: Array<[string[], string]> = [
  [['⌘', 'K'], 'New search'],
  [['⌘', 'B'], 'Toggle sidebar'],
  [['⌘', '/'], 'Show this menu'],
  [['?'], 'Show this menu'],
  [['J'], 'Next listing'],
  [['K'], 'Previous listing'],
  [['F'], 'Favorite focused listing'],
  [['C'], 'Add focused to compare'],
  [['Esc'], 'Close dialogs'],
]

export function KeyboardShortcuts({ open, onClose }: Props) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-ink-200/60 overflow-hidden animate-drawer-up">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-200/60">
          <div>
            <p className="text-[0.65rem] uppercase tracking-[0.18em] text-ink-400 font-medium">Keyboard</p>
            <h2 className="font-display text-lg font-medium text-ink-900">Shortcuts</h2>
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
        <div className="p-5 flex flex-col gap-2">
          {SHORTCUTS.map(([keys, label]) => (
            <div key={label + keys.join('-')} className="flex items-center justify-between">
              <span className="text-sm text-ink-700">{label}</span>
              <div className="flex items-center gap-1">
                {keys.map(k => (
                  <kbd
                    key={k}
                    className="font-mono text-[0.7rem] font-semibold bg-cream-100 text-ink-700 border border-ink-200/70 px-1.5 py-0.5 rounded-md min-w-[1.6rem] text-center"
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
