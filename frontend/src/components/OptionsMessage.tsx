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
      <div className="flex justify-start">
        <p className="text-sm text-gray-800 leading-relaxed">{content}</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-800 leading-relaxed">{content}</p>

      <div className="flex flex-col gap-2">
        {options.map((opt) => (
          <label
            key={opt}
            onClick={() => toggle(opt)}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
              selected.has(opt)
                ? 'bg-[#1a3f6f] border-[#1a3f6f]'
                : 'border-gray-300 group-hover:border-[#1a3f6f]'
            }`}>
              {selected.has(opt) && (
                <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.5" className="w-2.5 h-2.5">
                  <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
            <span className="text-sm text-gray-700 group-hover:text-gray-900 transition-colors">{opt}</span>
          </label>
        ))}

        {/* Type your own row */}
        <div className="flex items-center gap-2.5">
          <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
            text.trim() ? 'bg-[#1a3f6f] border-[#1a3f6f]' : 'border-gray-300'
          }`}>
            {text.trim() && (
              <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.5" className="w-2.5 h-2.5">
                <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type your own..."
            className="flex-1 bg-transparent outline-none text-sm text-gray-700 placeholder-gray-400"
          />
        </div>
      </div>

      <button
        onClick={submit}
        disabled={selected.size === 0 && !text.trim()}
        className="self-start px-4 py-1.5 rounded-full text-sm bg-[#1a3f6f] text-white disabled:opacity-30 hover:bg-[#15315a] transition-colors"
      >
        Submit
      </button>
    </div>
  )
}
