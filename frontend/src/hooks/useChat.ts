import { useEffect, useRef, useState, useCallback } from 'react'

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export type SessionMeta = {
  id: string
  title: string
  createdAt: number
}

function generateId() {
  return Math.random().toString(36).slice(2)
}

function loadSessions(): SessionMeta[] {
  try {
    return JSON.parse(localStorage.getItem('rental_sessions') || '[]')
  } catch {
    return []
  }
}

function saveSessions(sessions: SessionMeta[]) {
  localStorage.setItem('rental_sessions', JSON.stringify(sessions))
}

function getOrCreateCurrentId(): string {
  const existing = localStorage.getItem('rental_session_id')
  if (existing) return existing
  const id = generateId()
  localStorage.setItem('rental_session_id', id)
  return id
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [connected, setConnected] = useState(false)
  const [sessions, setSessions] = useState<SessionMeta[]>(loadSessions)
  const ws = useRef<WebSocket | null>(null)
  const sessionId = useRef(getOrCreateCurrentId())
  const titleSet = useRef(false)

  const connect = useCallback((sid: string) => {
    ws.current?.close()
    setMessages([])
    setIsThinking(false)
    setConnected(false)
    titleSet.current = false

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/${sid}`)
    ws.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'message') {
        setMessages((prev) => [...prev, { id: generateId(), role: data.role, content: data.content }])
      } else if (data.type === 'step_start') {
        setIsThinking(true)
      } else if (data.type === 'step_end') {
        setIsThinking(false)
      } else if (data.type === 'error') {
        setIsThinking(false)
        setMessages((prev) => [...prev, { id: generateId(), role: 'assistant', content: `Error: ${data.content}` }])
      }
    }
  }, [])

  useEffect(() => {
    connect(sessionId.current)
    return () => ws.current?.close()
  }, [connect])

  const sendMessage = useCallback((content: string) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return

    const sid = sessionId.current

    // Set session title from first user message
    if (!titleSet.current) {
      titleSet.current = true
      const title = content.length > 40 ? content.slice(0, 40) + '…' : content
      setSessions((prev) => {
        const exists = prev.find((s) => s.id === sid)
        const updated = exists
          ? prev.map((s) => s.id === sid ? { ...s, title } : s)
          : [{ id: sid, title, createdAt: Date.now() }, ...prev]
        saveSessions(updated)
        return updated
      })
    }

    setMessages((prev) => [...prev, { id: generateId(), role: 'user', content }])
    ws.current.send(JSON.stringify({ content }))
  }, [])

  const newChat = useCallback(() => {
    const id = generateId()
    localStorage.setItem('rental_session_id', id)
    sessionId.current = id
    connect(id)
  }, [connect])

  const switchSession = useCallback((id: string) => {
    localStorage.setItem('rental_session_id', id)
    sessionId.current = id
    titleSet.current = true // already has history
    connect(id)
  }, [connect])

  return { messages, isThinking, connected, sessions, sendMessage, newChat, switchSession }
}
