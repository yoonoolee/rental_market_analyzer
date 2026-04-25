import { useEffect, useRef, useState, useCallback } from 'react'

export type ProcessStep = {
  node: string
  label: string
  detail: string[]
  done?: number
  total?: number
}

export type Message = {
  id: string
  role: 'user' | 'assistant' | 'process'
  content: string
  options?: string[]
  answered?: boolean
  steps?: ProcessStep[]
  isRunning?: boolean
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
  try { return JSON.parse(localStorage.getItem('rental_sessions') || '[]') }
  catch { return [] }
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
  const processId = useRef<string | null>(null)

  const connect = useCallback((sid: string) => {
    ws.current?.close()
    setMessages([])
    setIsThinking(false)
    setConnected(false)
    titleSet.current = false
    processId.current = null

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/${sid}`)
    ws.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'message') {
        setMessages(prev => [...prev, { id: generateId(), role: data.role, content: data.content }])

      } else if (data.type === 'options') {
        setMessages(prev => [...prev, {
          id: generateId(), role: 'assistant', content: data.content,
          options: data.options, answered: false,
        }])

      } else if (data.type === 'process_start') {
        const pid = generateId()
        processId.current = pid
        setIsThinking(true)
        setMessages(prev => [...prev, { id: pid, role: 'process', content: '', steps: [], isRunning: true }])

      } else if (data.type === 'process_step') {
        const pid = processId.current
        if (!pid) return
        const step: ProcessStep = { node: data.node, label: data.label, detail: data.detail || [], done: data.done, total: data.total }
        setMessages(prev => prev.map(m => m.id === pid ? { ...m, steps: [...(m.steps || []), step] } : m))

      } else if (data.type === 'process_step_update') {
        const pid = processId.current
        if (!pid) return
        setMessages(prev => prev.map(m => m.id === pid ? {
          ...m,
          steps: m.steps?.map(s => s.node === data.node
            ? { ...s, label: data.label, done: data.done, total: data.total }
            : s) || []
        } : m))

      } else if (data.type === 'process_end') {
        const pid = processId.current
        if (pid) setMessages(prev => prev.map(m => m.id === pid ? { ...m, isRunning: false } : m))
        processId.current = null
        setIsThinking(false)

      } else if (data.type === 'error') {
        const pid = processId.current
        if (pid) setMessages(prev => prev.map(m => m.id === pid ? { ...m, isRunning: false } : m))
        processId.current = null
        setIsThinking(false)
        setMessages(prev => [...prev, { id: generateId(), role: 'assistant', content: `Error: ${data.content}` }])
      }
    }
  }, [])

  useEffect(() => {
    connect(sessionId.current)
    return () => ws.current?.close()
  }, [connect])

  const sendMessage = useCallback((content: string, optionsMsgId?: string) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return
    const sid = sessionId.current

    if (!titleSet.current) {
      titleSet.current = true
      const title = content.length > 40 ? content.slice(0, 40) + '…' : content
      setSessions(prev => {
        const exists = prev.find(s => s.id === sid)
        const updated = exists
          ? prev.map(s => s.id === sid ? { ...s, title } : s)
          : [{ id: sid, title, createdAt: Date.now() }, ...prev]
        saveSessions(updated)
        return updated
      })
    }

    if (optionsMsgId) {
      setMessages(prev => prev.map(m => m.id === optionsMsgId ? { ...m, answered: true } : m))
    }

    setMessages(prev => [...prev, { id: generateId(), role: 'user', content }])
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
    titleSet.current = true
    connect(id)
  }, [connect])

  const deleteSession = useCallback((id: string) => {
    fetch(`/sessions/${id}`, { method: 'DELETE' })
    setSessions(prev => {
      const updated = prev.filter(s => s.id !== id)
      saveSessions(updated)
      return updated
    })
    if (sessionId.current === id) {
      const id2 = generateId()
      localStorage.setItem('rental_session_id', id2)
      sessionId.current = id2
      connect(id2)
    }
  }, [connect])

  const deleteAllSessions = useCallback(() => {
    fetch('/sessions', { method: 'DELETE' })
    saveSessions([])
    setSessions([])
    const id = generateId()
    localStorage.setItem('rental_session_id', id)
    sessionId.current = id
    connect(id)
  }, [connect])

  return { messages, isThinking, connected, sessions, sendMessage, newChat, switchSession, deleteSession, deleteAllSessions }
}
