import { useEffect, useRef, useState, useCallback } from 'react'

export type AgentStatus = {
  url: string
  hostname: string
  status: string
  finished: boolean
  disqualified?: boolean
  wait_seconds?: number
  wait_started_at?: number
}

export type ProcessStep = {
  node: string
  round?: number
  label: string
  detail: string[]
  done?: number
  total?: number
  agents?: AgentStatus[]
}

export type ListingProfile = {
  url: string
  disqualified?: boolean
  disqualify_reason?: string
  price?: number
  bedrooms?: number
  bathrooms?: number
  address?: string
  floor?: number
  sqft?: number
  amenities?: string[]
  images?: string[]
  commute_times?: Record<string, string>
  nearby_places?: Record<string, string>
  pet_friendly?: boolean
  pet_deposit?: number
  furnishing?: string
  views?: boolean
  modern_finishes?: boolean
  natural_light?: boolean
  spacious?: boolean
  condition?: string
  notes?: string
  description?: string
}

export type Message = {
  id: string
  role: 'user' | 'assistant' | 'process' | 'listings'
  content: string
  options?: string[]
  answered?: boolean
  steps?: ProcessStep[]
  isRunning?: boolean
  listings?: ListingProfile[]
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
  const [connectionState, setConnectionState] = useState<'connected' | 'disconnected' | 'error'>('disconnected')
  const [sessions, setSessions] = useState<SessionMeta[]>(loadSessions)
  const ws = useRef<WebSocket | null>(null)
  const sessionId = useRef(getOrCreateCurrentId())
  const titleSet = useRef(false)
  const processId = useRef<string | null>(null)
  const processInjected = useRef(false)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttempt = useRef(0)
  const manualClose = useRef(false)

  const reconnect = useCallback((sid: string) => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 30000)
    reconnectAttempt.current += 1
    reconnectTimer.current = setTimeout(() => {
      if (!manualClose.current) connectSocket(sid) // eslint-disable-line @typescript-eslint/no-use-before-define
    }, delay)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const connectSocket = useCallback((sid: string) => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    manualClose.current = false

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/${sid}`)
    ws.current = socket

    socket.onopen = () => {
      reconnectAttempt.current = 0
      setConnected(true)
      setConnectionState('connected')
    }
    socket.onclose = () => {
      setConnected(false)
      setConnectionState('disconnected')
      if (!manualClose.current) reconnect(sid)
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'message') {
        setMessages(prev => [...prev, { id: generateId(), role: data.role, content: data.content }])

      } else if (data.type === 'options') {
        setMessages(prev => [...prev, {
          id: generateId(), role: 'assistant', content: data.content,
          options: data.options, answered: false,
        }])

      } else if (data.type === 'listings') {
        if (!processInjected.current) {
          processInjected.current = true
          const stored = localStorage.getItem(`rental_process_${sid}`)
          if (stored) {
            try {
              const steps = JSON.parse(stored) as ProcessStep[]
              if (steps.length > 0)
                setMessages(prev => [...prev, { id: generateId(), role: 'process', content: '', steps, isRunning: false }])
            } catch {}
          }
        }
        setMessages(prev => [...prev, { id: generateId(), role: 'listings', content: '', listings: data.listings }])

      } else if (data.type === 'process_start') {
        localStorage.removeItem(`rental_process_${sid}`)
        processInjected.current = true
        const pid = generateId()
        processId.current = pid
        setIsThinking(true)
        setConnectionState('connected')
        setMessages(prev => [...prev, { id: pid, role: 'process', content: '', steps: [], isRunning: true }])

      } else if (data.type === 'process_step') {
        const pid = processId.current
        if (!pid) return
        const step: ProcessStep = { node: data.node, round: data.round, label: data.label, detail: data.detail || [], done: data.done, total: data.total }
        setMessages(prev => prev.map(m => m.id === pid ? { ...m, steps: [...(m.steps || []), step] } : m))

      } else if (data.type === 'process_step_update') {
        const pid = processId.current
        if (!pid) return
        setMessages(prev => prev.map(m => m.id === pid ? {
          ...m,
          steps: m.steps?.map(s => s.node === data.node && (!data.round || s.round === data.round)
            ? {
                ...s,
                label: data.label,
                done: data.done,
                total: data.total,
                detail: data.detail_item ? [...(s.detail || []), data.detail_item] : s.detail,
              }
            : s) || []
        } : m))

      } else if (data.type === 'agent_update') {
        const pid = processId.current
        if (!pid) return
        setMessages(prev => prev.map(m => m.id === pid ? {
          ...m,
          steps: m.steps?.map(s => s.node === data.node && (!data.round || s.round === data.round) ? {
            ...s,
            agents: (() => {
              const existing = (s.agents || [])
              const idx = existing.findIndex(a => a.url === data.url)
              const updated: AgentStatus = { url: data.url, hostname: data.hostname, status: data.status, finished: data.finished ?? false, disqualified: data.disqualified, wait_seconds: data.wait_seconds, wait_started_at: data.wait_seconds ? Date.now() : undefined }
              return idx >= 0 ? existing.map((a, i) => i === idx ? updated : a) : [...existing, updated]
            })()
          } : s) || []
        } : m))

      } else if (data.type === 'debug_log') {
        console.log(`[listing_agent] ${data.msg}`)

      } else if (data.type === 'process_end') {
        const pid = processId.current
        if (pid) {
          setMessages(prev => {
            const updated = prev.map(m => m.id === pid ? { ...m, isRunning: false } : m)
            const processMsg = updated.find(m => m.id === pid)
            if (processMsg?.steps?.length) {
              localStorage.setItem(`rental_process_${sid}`, JSON.stringify(processMsg.steps))
            }
            return updated
          })
        }
        processId.current = null
        setIsThinking(false)

      } else if (data.type === 'error') {
        const pid = processId.current
        if (pid) setMessages(prev => prev.map(m => m.id === pid ? { ...m, isRunning: false } : m))
        processId.current = null
        setIsThinking(false)
        setConnectionState('error')
        setMessages(prev => [...prev, { id: generateId(), role: 'assistant', content: `Error: ${data.content}` }])

      } else if (data.type === 'connection_state') {
        const state = data.state === 'connected' || data.state === 'error' ? data.state : 'disconnected'
        setConnectionState(state)
      }
    }
  }, [reconnect])

  const connect = useCallback((sid: string) => {
    manualClose.current = true
    ws.current?.close()
    setMessages([])
    setIsThinking(false)
    setConnected(false)
    setConnectionState('disconnected')
    titleSet.current = false
    processId.current = null
    processInjected.current = false
    reconnectAttempt.current = 0
    connectSocket(sid)
  }, [connectSocket])

  useEffect(() => {
    connectSocket(sessionId.current)

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const state = ws.current?.readyState
        if (state === WebSocket.CLOSED || state === WebSocket.CLOSING) {
          reconnectAttempt.current = 0
          connectSocket(sessionId.current)
        }
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      manualClose.current = true
      ws.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [connectSocket])

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

  const abortRun = useCallback(() => {
    const sid = sessionId.current
    fetch(`/abort/${sid}`, { method: 'POST' })
    setIsThinking(false)
  }, [])

  return {
    messages,
    isThinking,
    connected,
    connectionState,
    sessions,
    sendMessage,
    newChat,
    switchSession,
    deleteSession,
    deleteAllSessions,
    abortRun,
  }
}
