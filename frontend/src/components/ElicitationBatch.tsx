import { useState } from 'react'
import type { ElicitationQuestion } from '../hooks/useChat'

type Answer = { selected: string[]; text: string }

type Props = {
  id: string
  questions: ElicitationQuestion[]
  answered: boolean
  answeredPairs?: { question: string; answer: string }[]
  onSend: (content: string, msgId: string) => void
}

export function ElicitationBatch({ id, questions, answered, answeredPairs, onSend }: Props) {
  const [currentIdx, setCurrentIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, Answer>>({})

  const current = questions[currentIdx]
  const answer = answers[currentIdx] ?? { selected: [], text: '' }
  const total = questions.length

  const toggleOption = (opt: string) => {
    setAnswers(prev => {
      const a = prev[currentIdx] ?? { selected: [], text: '' }
      const selected = a.selected.includes(opt)
        ? a.selected.filter(o => o !== opt)
        : [...a.selected, opt]
      return { ...prev, [currentIdx]: { ...a, selected } }
    })
  }

  const setText = (text: string) => {
    setAnswers(prev => {
      const a = prev[currentIdx] ?? { selected: [], text: '' }
      return { ...prev, [currentIdx]: { ...a, text } }
    })
  }

  const hasAllAnswers = questions.every((_, i) => {
    const a = answers[i]
    return (a?.selected.length ?? 0) > 0 || (a?.text.trim().length ?? 0) > 0
  })

  const submit = () => {
    const lines = questions.map((q, i) => {
      const a = answers[i]
      const parts = [...(a?.selected ?? [])]
      if (a?.text.trim()) parts.push(a.text.trim())
      if (!parts.length) return null
      return `Q: ${q.question}\nA: ${parts.join(', ')}`
    }).filter(Boolean)

    if (!lines.length) return
    onSend(lines.join('\n\n'), id)
  }

  if (answered) {
    const pairs = answeredPairs ?? questions.map((q, i) => {
      const a = answers[i]
      const parts = [...(a?.selected ?? [])]
      if (a?.text.trim()) parts.push(a.text.trim())
      return { question: q.question, answer: parts.join(', ') }
    }).filter(p => p.answer)
    return (
      <div className="flex flex-col gap-1">
        {pairs.map((p, i) => (
          <p key={i} className="text-sm text-gray-600 leading-relaxed">
            <span className="text-gray-400">{p.question}: </span>{p.answer}
          </p>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Navigation header */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{currentIdx + 1} / {total}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
            disabled={currentIdx === 0}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 disabled:opacity-20 transition-colors"
            aria-label="Previous question"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-gray-500">
              <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            onClick={() => setCurrentIdx(i => Math.min(total - 1, i + 1))}
            disabled={currentIdx === total - 1}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-gray-100 disabled:opacity-20 transition-colors"
            aria-label="Next question"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-gray-500">
              <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Question text */}
      <p className="text-sm text-gray-800 leading-relaxed">{current.question}</p>

      {/* Options */}
      <div className="flex flex-col gap-2">
        {current.options
          .filter(opt => !/^(type\s+(other|your|own|in\b)|other(\s*\(|$))/i.test(opt.trim()))
          .map((opt) => (
          <label
            key={opt}
            onClick={() => toggleOption(opt)}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
              answer.selected.includes(opt)
                ? 'bg-[#1a3f6f] border-[#1a3f6f]'
                : 'border-gray-300 group-hover:border-[#1a3f6f]'
            }`}>
              {answer.selected.includes(opt) && (
                <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.5" className="w-2.5 h-2.5">
                  <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
            <span className="text-sm text-gray-700 group-hover:text-gray-900 transition-colors">{opt}</span>
          </label>
        ))}

        {/* Custom text input with auto-selecting checkbox */}
        <div className="flex items-center gap-2.5">
          <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
            answer.text.trim() ? 'bg-[#1a3f6f] border-[#1a3f6f]' : 'border-gray-300'
          }`}>
            {answer.text.trim() && (
              <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.5" className="w-2.5 h-2.5">
                <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <input
            type="text"
            value={answer.text}
            onChange={e => setText(e.target.value)}
            placeholder="Type your own..."
            className="flex-1 bg-transparent outline-none text-sm text-gray-700 placeholder-gray-400"
          />
        </div>
      </div>

      {/* Progress dots */}
      {total > 1 && (
        <div className="flex gap-1.5 items-center">
          {questions.map((_, i) => {
            const a = answers[i]
            const hasAnswer = (a?.selected.length ?? 0) > 0 || (a?.text.trim().length ?? 0) > 0
            return (
              <button
                key={i}
                onClick={() => setCurrentIdx(i)}
                className={`w-1.5 h-1.5 rounded-full transition-all ${
                  i === currentIdx
                    ? 'bg-[#1a3f6f] w-3'
                    : hasAnswer
                    ? 'bg-[#1a3f6f] opacity-40'
                    : 'bg-gray-300'
                }`}
              />
            )
          })}
        </div>
      )}

      <button
        onClick={submit}
        disabled={!hasAllAnswers}
        className="self-end px-4 py-1.5 rounded-full text-sm bg-[#1a3f6f] text-white disabled:opacity-30 hover:bg-[#15315a] transition-colors"
      >
        Submit
      </button>
    </div>
  )
}
