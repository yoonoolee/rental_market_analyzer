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
  const isInitial = messages.length === 0

  useEffect(() => {
    if (!isInitial) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isThinking, isInitial])

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onNewChat={newChat}
        onSwitch={switchSession}
      />

      <div className="flex flex-col flex-1 min-w-0">
        {isInitial ? (
          // Centered layout for initial state
          <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
            <div className="max-w-3xl w-full mb-6 text-center">
              <h1 className="text-3xl font-semibold text-gray-900 mb-2">Hi there!</h1>
              <p className="text-base text-gray-400">Ready to find your next apartment?</p>
            </div>
            <div className="max-w-3xl w-full">
              <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder={isInitial ? 'What are you looking for?' : 'Reply...'} />
            </div>
          </div>
        ) : (
          // Normal scrolling layout once conversation starts
          <>
            <main className="flex-1 overflow-y-auto px-4 pt-16 pb-8">
              <div className="max-w-3xl mx-auto flex flex-col gap-6">
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={m} />
                ))}
                {isThinking && <ThinkingIndicator />}
                <div ref={bottomRef} />
              </div>
            </main>
            <InputBar onSend={sendMessage} disabled={!connected || isThinking} placeholder={isInitial ? 'What are you looking for?' : 'Reply...'} />
          </>
        )}
      </div>
    </div>
  )
}
