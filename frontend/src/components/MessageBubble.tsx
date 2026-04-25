import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../hooks/useChat'
import { OptionsMessage } from './OptionsMessage'
import { ProcessSteps } from './ProcessSteps'

type Props = {
  message: Message
  onSend: (content: string, msgId: string) => void
}

export function MessageBubble({ message, onSend }: Props) {
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
      <div className="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none flex-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
    </div>
  )
}
