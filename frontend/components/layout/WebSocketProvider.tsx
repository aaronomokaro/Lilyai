'use client'

import { useEffect } from 'react'
import { connectWs, disconnectWs, subscribeWs } from '@/lib/websocket'
import { useStreamStore } from '@/stores/streamStore'
import { useProgressStore } from '@/stores/progressStore'
import type { WsEvent } from '@/types/api'

interface WebSocketProviderProps {
  userId: string
  children: React.ReactNode
}

export function WebSocketProvider({ userId, children }: WebSocketProviderProps) {
  useEffect(() => {
    connectWs(userId)

    const unsub = subscribeWs((event: WsEvent) => {
      if (event.event === 'orchestrator_progress') {
        useProgressStore.getState().setProgress(event.step, event.intent)
      } else if (event.event === 'query_token') {
        useStreamStore.getState().append(event.token, event.query_id)
      } else if (event.event === 'query_complete') {
        useStreamStore.getState().complete(event.citations)
        useProgressStore.getState().clear()
      }
    })

    return () => {
      unsub()
      disconnectWs()
    }
  }, [userId])

  return <>{children}</>
}
