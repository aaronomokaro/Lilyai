import { create } from 'zustand'

interface ProgressStore {
  step: string | null
  intent: string | null
  setProgress: (step: string, intent?: string) => void
  clear: () => void
}

export const useProgressStore = create<ProgressStore>((set) => ({
  step: null,
  intent: null,
  setProgress: (step, intent) => set({ step, intent: intent ?? null }),
  clear: () => set({ step: null, intent: null }),
}))
