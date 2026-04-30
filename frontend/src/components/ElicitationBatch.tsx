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
      <div className="flex items-start gap-3">
        <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
          <span className="font-display text-xs font-semibold">R</span>
        </div>
        <div className="flex-1 min-w-0 flex flex-col gap-1.5 pt-0.5">
          {pairs.map((p, i) => (
            <p key={i} className="text-sm leading-relaxed">
              <span className="text-ink-400">{p.question}: </span>
              <span className="text-ink-700">{p.answer}</span>
            </p>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <span className="font-display text-xs font-semibold">R</span>
      </div>

      <div className="flex-1 min-w-0 flex flex-col gap-4 pt-0.5">
        <div className="rounded-2xl border border-ink-200/70 bg-white p-5 shadow-sm flex flex-col gap-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <span className="text-[0.65rem] uppercase tracking-[0.16em] text-ink-400 font-semibold">
                Question
              </span>
              <span className="font-display text-sm text-ink-700">
                {currentIdx + 1} <span className="text-ink-400">of {total}</span>
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setCurrentIdx(i => Math.max(0, i - 1))}
                disabled={currentIdx === 0}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-cream-100 disabled:opacity-20 transition-colors"
                aria-label="Previous"
              >
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-ink-700">
                  <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <button
                onClick={() => setCurrentIdx(i => Math.min(total - 1, i + 1))}
                disabled={currentIdx === total - 1}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-cream-100 disabled:opacity-20 transition-colors"
                aria-label="Next"
              >
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5 text-ink-700">
                  <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>

          {/* Question */}
          <p className="text-base font-display text-ink-900 leading-snug">{current.question}</p>

          {/* Options */}
          <div className="flex flex-col gap-1">
            {current.options
              .filter(opt => !/^(type\s+(other|your|own|in\b)|other(\s*\(|$))/i.test(opt.trim()))
              .map((opt) => (
                <Option
                  key={opt}
                  label={opt}
                  checked={answer.selected.includes(opt)}
                  onToggle={() => toggleOption(opt)}
                />
              ))}

            <div className="flex items-center gap-3 px-1.5 py-1.5">
              <Checkbox checked={!!answer.text.trim()} />
              <input
                type="text"
                value={answer.text}
                onChange={e => setText(e.target.value)}
                placeholder="Type your own answer…"
                className="flex-1 bg-transparent outline-none text-sm text-ink-900 placeholder-ink-400"
              />
            </div>
          </div>

          {/* Progress dots + Submit */}
          <div className="flex items-center justify-between pt-2">
            {total > 1 ? (
              <div className="flex gap-1.5 items-center">
                {questions.map((_, i) => {
                  const a = answers[i]
                  const hasAnswer = (a?.selected.length ?? 0) > 0 || (a?.text.trim().length ?? 0) > 0
                  return (
                    <button
                      key={i}
                      onClick={() => setCurrentIdx(i)}
                      className={`h-1.5 rounded-full transition-all ${
                        i === currentIdx
                          ? 'bg-teal-700 w-6'
                          : hasAnswer
                          ? 'bg-teal-700/40 w-1.5'
                          : 'bg-ink-300 w-1.5'
                      }`}
                      aria-label={`Question ${i + 1}`}
                    />
                  )
                })}
              </div>
            ) : <div />}

            <button
              onClick={submit}
              disabled={!hasAllAnswers}
              className="px-5 py-2 rounded-full text-sm font-medium bg-teal-700 text-cream-50 hover:bg-teal-600 disabled:bg-ink-200 disabled:text-ink-400 disabled:cursor-not-allowed transition-all"
            >
              Submit
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
