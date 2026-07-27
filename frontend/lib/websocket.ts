import type { WsEvent } from '@/types/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

// Convert https:// → wss://, http:// → ws://
const wsBase = API_URL.replace(/^https/, 'wss').replace(/^http/, 'ws')

let socket: WebSocket | null = null
let currentUserId: string | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

type MessageHandler = (event: WsEvent) => void
const handlers = new Set<MessageHandler>()

export function subscribeWs(fn: MessageHandler) {
  handlers.add(fn)
  return () => handlers.delete(fn)
}

export function connectWs(userId: string) {
  if (socket && socket.readyState === WebSocket.OPEN && currentUserId === userId) return
  currentUserId = userId
  _connect()
}

function _connect() {
  if (!currentUserId) return
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }

  socket = new WebSocket(`${wsBase}/ws/${currentUserId}`)

  socket.onmessage = (e) => {
    try {
      const data: WsEvent = JSON.parse(e.data)
      handlers.forEach((fn) => fn(data))
    } catch {}
  }

  socket.onclose = () => {
    reconnectTimer = setTimeout(_connect, 2500)
  }

  socket.onerror = () => {
    socket?.close()
  }
}

export function disconnectWs() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  socket?.close()
  socket = null
  currentUserId = null
}
