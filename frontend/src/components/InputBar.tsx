import { useState, useRef, type KeyboardEvent } from 'react'

type Props = {
  onSend: (content: string) => void
  disabled: boolean
  placeholder?: string
}

export function InputBar({ onSend, disabled, placeholder = 'Reply…' }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  return (
    <div className="px-4 pb-5 pt-3 bg-gradient-to-t from-cream-50/80 via-cream-50/50 to-transparent backdrop-blur-[2px]">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-white rounded-2xl px-4 py-2.5 border border-ink-200/70 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.08)] focus-within:border-teal-600/60 focus-within:shadow-[0_2px_18px_-4px_rgba(15,118,110,0.18)] transition-all">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            onInput={onInput}
            placeholder={placeholder}
            rows={1}
            disabled={disabled}
            className="flex-1 bg-transparent resize-none outline-none text-sm text-ink-900 placeholder-ink-400 leading-relaxed max-h-40 disabled:opacity-50 py-1.5"
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="flex items-center justify-center shrink-0 w-9 h-9 rounded-xl bg-teal-700 text-white disabled:bg-ink-200 disabled:text-ink-400 hover:bg-teal-600 transition-all hover:scale-105 disabled:hover:scale-100"
            aria-label="Send"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M12 20.25a.75.75 0 01-.75-.75V6.31l-4.72 4.72a.75.75 0 01-1.06-1.06l6-6a.75.75 0 011.06 0l6 6a.75.75 0 11-1.06 1.06L12.75 6.31V19.5a.75.75 0 01-.75.75z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
        <p className="text-center text-[0.7rem] text-ink-400 mt-2.5">
          AI can make mistakes. Always verify listings independently.
        </p>
      </div>
    </div>
  )
}
