/**
 * Vitest setup (jsdom): jest-dom matchers, DOM cleanup between tests and the few browser APIs
 * jsdom lacks (matchMedia, ResizeObserver, scrollIntoView, pointer capture) used by Radix / motion.
 */
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  try {
    window.localStorage.clear()
  } catch {
    // storage unavailable: nothing to reset
  }
})

if (typeof window !== 'undefined') {
  if (typeof window.matchMedia !== 'function') {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string): MediaQueryList => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: () => false,
      }),
    })
  }

  // jsdom defines scrollTo but only logs "Not implemented".
  Object.defineProperty(window, 'scrollTo', { writable: true, configurable: true, value: () => {} })

  if (typeof globalThis.ResizeObserver === 'undefined') {
    class ResizeObserverStub {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
  }

  if (typeof Element !== 'undefined') {
    const proto = Element.prototype as Element & {
      scrollIntoView?: () => void
      hasPointerCapture?: (id: number) => boolean
      releasePointerCapture?: (id: number) => void
    }
    proto.scrollIntoView ??= () => {}
    proto.hasPointerCapture ??= () => false
    proto.releasePointerCapture ??= () => {}
  }
}
