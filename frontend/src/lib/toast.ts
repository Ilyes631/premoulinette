/**
 * Minimal toast store (no provider needed): call `toast(...)` from anywhere,
 * `<Toaster />` (mounted once in the app shell) renders the queue.
 */
import { useSyncExternalStore } from 'react'

export type ToastTone = 'neutral' | 'success' | 'error' | 'warning'

export interface ToastItem {
  id: number
  title: string
  description?: string
  tone: ToastTone
  durationMs: number
}

export interface ToastInput {
  title: string
  description?: string
  tone?: ToastTone
  durationMs?: number
}

const MAX_TOASTS = 4
let items: ToastItem[] = []
let nextId = 1
const listeners = new Set<() => void>()
const timers = new Map<number, ReturnType<typeof setTimeout>>()

function emit() {
  for (const listener of listeners) listener()
}

export function dismissToast(id: number): void {
  const timer = timers.get(id)
  if (timer) clearTimeout(timer)
  timers.delete(id)
  items = items.filter((t) => t.id !== id)
  emit()
}

export function toast(input: ToastInput): number {
  const item: ToastItem = {
    id: nextId++,
    title: input.title,
    description: input.description,
    tone: input.tone ?? 'neutral',
    durationMs: input.durationMs ?? (input.tone === 'error' ? 7000 : 4000),
  }
  items = [...items, item].slice(-MAX_TOASTS)
  timers.set(item.id, setTimeout(() => dismissToast(item.id), item.durationMs))
  emit()
  return item.id
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

const getSnapshot = () => items

export function useToasts(): ToastItem[] {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
