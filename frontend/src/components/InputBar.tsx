import { useState, useRef, type KeyboardEvent } from 'react'

type Props = {
  onSend: (content: string) => void
  disabled: boolean
  placeholder?: string
}

export function InputBar({ onSend, disabled, placeholder = 'Reply...' }: Props) {
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
    <div className="px-4 pb-4 pt-2">
      <div className="max-w-3xl mx-auto flex items-center gap-3 bg-[#f7f6f3] rounded-3xl px-4">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onInput={onInput}
          placeholder={placeholder}
          rows={1}
          disabled={disabled}
          className="flex-1 bg-transparent resize-none outline-none text-sm text-gray-800 placeholder-gray-400 leading-relaxed max-h-40 disabled:opacity-50 py-2.5"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="flex items-center justify-center shrink-0 text-gray-600 disabled:opacity-30 hover:text-gray-900 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M12 20.25a.75.75 0 01-.75-.75V6.31l-4.72 4.72a.75.75 0 01-1.06-1.06l6-6a.75.75 0 011.06 0l6 6a.75.75 0 11-1.06 1.06L12.75 6.31V19.5a.75.75 0 01-.75.75z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
      <p className="text-center text-xs text-gray-400 mt-2">AI can make mistakes. Verify important info.</p>
    </div>
  )
}
