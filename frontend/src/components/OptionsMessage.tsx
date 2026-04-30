import { useState, type KeyboardEvent } from 'react'

type Props = {
  id: string
  content: string
  options: string[]
  answered: boolean
  onSend: (content: string, msgId: string) => void
}

export function OptionsMessage({ id, content, options, answered, onSend }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [text, setText] = useState('')

  const toggle = (opt: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(opt) ? next.delete(opt) : next.add(opt)
      return next
    })
  }

  const submit = () => {
    const parts = [...selected]
    if (text.trim()) parts.push(text.trim())
    if (!parts.length) return
    onSend(parts.join(', '), id)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') { e.preventDefault(); submit() }
  }

  if (answered) {
    return (
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
          <span className="font-display text-xs font-semibold">R</span>
        </div>
        <p className="text-sm text-ink-700 leading-relaxed pt-1">{content}</p>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <span className="font-display text-xs font-semibold">R</span>
      </div>

      <div className="flex-1 min-w-0 flex flex-col gap-4 pt-0.5">
        <p className="text-sm text-ink-900 leading-relaxed">{content}</p>

        <div className="rounded-2xl border border-ink-200/70 bg-white p-4 flex flex-col gap-3 shadow-sm">
          <div className="flex flex-col gap-1">
            {options.map((opt) => (
              <Option
                key={opt}
                label={opt}
                checked={selected.has(opt)}
                onToggle={() => toggle(opt)}
              />
            ))}

            <div className="flex items-center gap-3 px-1.5 py-1.5">
              <Checkbox checked={!!text.trim()} />
              <input
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Type your own answer…"
                className="flex-1 bg-transparent outline-none text-sm text-ink-900 placeholder-ink-400"
              />
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={submit}
              disabled={selected.size === 0 && !text.trim()}
              className="px-5 py-2 rounded-full text-sm font-medium bg-teal-700 text-cream-50 hover:bg-teal-600 disabled:bg-ink-200 disabled:text-ink-400 disabled:cursor-not-allowed transition-all"
            >
              Continue
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Option({ label, checked, onToggle }: { label: string; checked: boolean; onToggle: () => void }) {
  return (
    <label
      onClick={onToggle}
      className={`flex items-center gap-3 px-1.5 py-1.5 rounded-lg cursor-pointer transition-colors ${
        checked ? 'bg-teal-50' : 'hover:bg-cream-100'
      }`}
    >
      <Checkbox checked={checked} />
      <span className={`text-sm transition-colors ${checked ? 'text-teal-700 font-medium' : 'text-ink-700'}`}>
        {label}
      </span>
    </label>
  )
}

function Checkbox({ checked }: { checked: boolean }) {
  return (
    <div className={`w-4 h-4 rounded-md border-[1.5px] flex items-center justify-center shrink-0 transition-all ${
      checked
        ? 'bg-teal-700 border-teal-700'
        : 'border-ink-300'
    }`}>
      {checked && (
        <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.5" className="w-2.5 h-2.5">
          <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}
