import { useEffect, useRef } from 'react'
import { useChat } from './hooks/useChat'
import { MessageBubble } from './components/MessageBubble'
import { ThinkingIndicator } from './components/ThinkingIndicator'
import { InputBar } from './components/InputBar'
import { Sidebar } from './components/Sidebar'
import './index.css'

export default function App() {
  const { messages, isThinking, connected, sessions, sendMessage, newChat, switchSession } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const currentId = localStorage.getItem('rental_session_id') ?? ''

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onNewChat={newChat}
        onSwitch={switchSession}
      />

      <div className="flex flex-col flex-1 min-w-0">
        <main className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-3xl mx-auto flex flex-col gap-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {isThinking && <ThinkingIndicator />}
            <div ref={bottomRef} />
          </div>
        </main>
        <InputBar onSend={sendMessage} disabled={!connected || isThinking} />
      </div>
    </div>
  )
}
