import { create } from 'zustand'
import type { Citation } from '@/types/api'

interface StreamStore {
  tokens: string
  isStreaming: boolean
  queryId: string | null
  citations: Citation[]
  append: (token: string, queryId: string) => void
  complete: (citations: Citation[]) => void
  clear: () => void
}

export const useStreamStore = create<StreamStore>((set) => ({
  tokens: '',
  isStreaming: false,
  queryId: null,
  citations: [],

  append: (token, queryId) =>
    set((s) => ({ tokens: s.tokens + token, isStreaming: true, queryId })),

  complete: (citations) =>
    set({ isStreaming: false, citations }),

  clear: () =>
    set({ tokens: '', isStreaming: false, queryId: null, citations: [] }),
}))
