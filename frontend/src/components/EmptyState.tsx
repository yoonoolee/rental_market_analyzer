type Props = {
  title: string
  description?: string
  icon?: 'search' | 'home' | 'alert'
  action?: { label: string; onClick: () => void }
}

const ICONS = {
  search: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-7 h-7">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" strokeLinecap="round" />
    </svg>
  ),
  home: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-7 h-7">
      <path d="M3 12l9-9 9 9M5 10v10h14V10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-7 h-7">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
    </svg>
  ),
}

export function EmptyState({ title, description, icon = 'search', action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-12">
      <div className="w-14 h-14 rounded-2xl bg-cream-200 text-teal-700 flex items-center justify-center mb-4 border border-ink-200/40">
        {ICONS[icon]}
      </div>
      <h3 className="font-display text-lg font-medium text-ink-900 mb-1.5">{title}</h3>
      {description && (
        <p className="text-sm text-ink-500 max-w-xs leading-relaxed">{description}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 text-sm font-medium px-4 py-2 rounded-full bg-teal-700 text-cream-50 hover:bg-teal-600 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
