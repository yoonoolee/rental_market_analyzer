import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../hooks/useChat'
import { OptionsMessage } from './OptionsMessage'
import { ProcessSteps } from './ProcessSteps'
import { ListingCard } from './ListingCard'

type Props = {
  message: Message
  onSend: (content: string, msgId: string) => void
}

export function MessageBubble({ message, onSend }: Props) {
  if (message.role === 'listings') {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-xs text-gray-400">Found {message.listings?.length} listings</p>
        <div className="flex gap-3 overflow-x-auto pb-2">
          {message.listings?.map((l, i) => <ListingCard key={i} listing={l} />)}
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
        <div className="max-w-[75%] bg-[#f7f6f3] rounded-2xl px-4 py-3 text-sm text-gray-800 leading-relaxed text-left">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start">
      <div className="assistant-message flex-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
    </div>
  )
}
