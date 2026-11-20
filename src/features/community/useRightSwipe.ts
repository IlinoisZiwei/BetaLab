import { useRef } from "react"
import type { MouseEvent, PointerEvent, TouchEvent } from "react"

/** Controls and open sheets keep their own gestures. */
const IGNORE = 'button,a,input,textarea,select,[role="slider"],[role="dialog"]'
const DISTANCE = 64

const isRightSwipe = (dx: number, dy: number) => dx > DISTANCE && Math.abs(dx) > Math.abs(dy) * 1.5

/**
 * N2.8: a right swipe (touch) or right drag (mouse) on a Community video.
 * Left swipe stays "back" (useNavigation / App) and vertical swipes keep
 * scrolling between videos, so only clearly horizontal rightward moves count.
 * A drag that triggered the action swallows the click that follows, so the
 * video does not also toggle play/pause.
 */
export function useRightSwipe(onSwipe: (startedOn: Element) => void) {
  const start = useRef<{ x: number; y: number; target: Element } | null>(null)
  const swallowClick = useRef(false)
  const ignored = (target: EventTarget | null) => !!(target as Element | null)?.closest?.(IGNORE)

  return {
    onTouchStart: (event: TouchEvent) => {
      if (ignored(event.target) || event.touches.length !== 1) { start.current = null; return }
      start.current = { x: event.touches[0].clientX, y: event.touches[0].clientY, target: event.target as Element }
    },
    onTouchEnd: (event: TouchEvent) => {
      const from = start.current
      start.current = null
      const touch = event.changedTouches[0]
      if (from && touch && isRightSwipe(touch.clientX - from.x, touch.clientY - from.y)) onSwipe(from.target)
    },
    onPointerDown: (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || event.button !== 0 || ignored(event.target)) return
      const from = { x: event.clientX, y: event.clientY, target: event.target as Element }
      // The app shell may capture the pointer, so listen for the release on window.
      const up = (release: globalThis.PointerEvent) => {
        if (release.pointerId !== event.pointerId) return
        window.removeEventListener("pointerup", up)
        if (isRightSwipe(release.clientX - from.x, release.clientY - from.y)) {
          swallowClick.current = true
          window.setTimeout(() => { swallowClick.current = false }, 300)
          onSwipe(from.target)
        }
      }
      window.addEventListener("pointerup", up)
    },
    onClickCapture: (event: MouseEvent) => {
      if (!swallowClick.current) return
      swallowClick.current = false
      event.preventDefault()
      event.stopPropagation()
    },
  }
}
