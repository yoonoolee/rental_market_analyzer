import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../hooks/useChat'

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  if (isUser) {
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
