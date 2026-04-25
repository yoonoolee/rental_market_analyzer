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

      {/* Option chips */}
      <div className="flex flex-col gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => toggle(opt)}
            className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
              selected.has(opt)
                ? 'bg-[#1a3f6f] text-white border-[#1a3f6f]'
                : 'bg-white text-gray-700 border-gray-300 hover:border-[#1a3f6f] hover:text-[#1a3f6f]'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>

      {/* Free text + send */}
      <div className="flex items-center gap-2 bg-[#f7f6f3] rounded-3xl px-4 py-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Or type your own..."
          className="flex-1 bg-transparent outline-none text-sm text-gray-800 placeholder-gray-400"
        />
        <button
          onClick={submit}
          disabled={selected.size === 0 && !text.trim()}
          className="text-gray-600 disabled:opacity-30 hover:text-gray-900 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M12 20.25a.75.75 0 01-.75-.75V6.31l-4.72 4.72a.75.75 0 01-1.06-1.06l6-6a.75.75 0 011.06 0l6 6a.75.75 0 11-1.06 1.06L12.75 6.31V19.5a.75.75 0 01-.75.75z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  )
}
