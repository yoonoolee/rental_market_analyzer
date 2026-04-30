import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../hooks/useChat'
import { OptionsMessage } from './OptionsMessage'
import { ElicitationBatch } from './ElicitationBatch'
import { ProcessSteps } from './ProcessSteps'
import { ListingCard } from './ListingCard'

type Props = {
  message: Message
  onSend: (content: string, msgId: string) => void
}

export function MessageBubble({ message, onSend }: Props) {
  if (message.role === 'listings') {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-[0.7rem] uppercase tracking-[0.16em] text-ink-400 font-medium">
          {message.listings?.length} matches found
        </p>
        <div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1">
          {message.listings?.map((l, i) => (
            <div key={i} className="shrink-0 w-80">
              <ListingCard listing={l} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (message.role === 'process') {
    return (
      <div className="flex justify-start">
        <ProcessSteps steps={message.steps || []} isRunning={message.isRunning ?? false} />
      </div>
    )
  }

  if (message.batch !== undefined) {
    return (
      <ElicitationBatch
        id={message.id}
        questions={message.batch}
        answered={message.answered ?? false}
        answeredPairs={message.answeredPairs}
        onSend={onSend}
      />
    )
  }

  if (message.options !== undefined) {
    return (
      <OptionsMessage
        id={message.id}
        content={message.content}
        options={message.options}
        answered={message.answered ?? false}
        onSend={onSend}
      />
    )
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] bg-teal-700 text-cream-50 rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed shadow-[0_2px_8px_-2px_rgba(15,118,110,0.25)]">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <span className="font-display text-xs font-semibold">R</span>
      </div>
      <div className="assistant-message flex-1 min-w-0 overflow-hidden pt-0.5">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
    </div>
  )
}
