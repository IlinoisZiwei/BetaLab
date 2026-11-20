import { useState, useEffect } from "react"
import type { Screen } from "../shared"

/** True when the touch started in something that scrolls sideways (e.g. a strip of cards). */
function insideHorizontalScroller(target: Element | null) {
  for (let element = target; element && element !== document.body; element = element.parentElement) {
    const overflow = getComputedStyle(element).overflowX
    if ((overflow === "auto" || overflow === "scroll") && element.scrollWidth > element.clientWidth) return true
  }
  return false
}

export function useNavigation() {
  const [screen, setScreen] = useState<Screen>("home")
  const [history, setHistory] = useState<Screen[]>([])
  const [notice, setNotice] = useState("")
  const go = (next: Screen) => {
    setHistory((items) => [...items, screen])
    setScreen(next)
    setNotice("")
  }

  const back = () => {
    const previous = history.at(-1) ?? "home"
    setHistory((items) => items.slice(0, -1))
    setScreen(previous)
    setNotice("")
  }

  useEffect(() => {
    const element = document.querySelector(".phone-content")
    if (!element) return
    let start: { x: number; y: number } | null = null
    const begin = (event: TouchEvent) => {
      start = null
      if (
        (event.target as Element).closest(
          'input,textarea,select,[role="slider"],[data-horizontal-swipe]',
        )
      )
        return
      const touch = event.touches[0]
      start = { x: touch.clientX, y: touch.clientY }
    }
    const move = (event: TouchEvent) => {
      if (!start) return
      const touch = event.touches[0],
        dx = touch.clientX - start.x,
        dy = touch.clientY - start.y
      // Horizontal swipes are app gestures (left = back, right = author page on
      // Community videos). Claim them so the phone's browser does not run its own
      // history swipe and leave the app, except inside sideways-scrolling strips.
      if (
        Math.abs(dx) > 12 &&
        Math.abs(dx) > Math.abs(dy) * 1.5 &&
        event.cancelable &&
        !insideHorizontalScroller(event.target as Element)
      )
        event.preventDefault()
    }
    const end = (event: TouchEvent) => {
      if (!start) return
      const touch = event.changedTouches[0],
        dx = touch.clientX - start.x,
        dy = touch.clientY - start.y
      start = null
      if (dx < -55 && Math.abs(dx) > Math.abs(dy) * 1.5 && history.length)
        back()
    }
    element.addEventListener("touchstart", begin as EventListener, {
      passive: true,
    })
    element.addEventListener("touchmove", move as EventListener, {
      passive: false,
    })
    element.addEventListener("touchend", end as EventListener)
    return () => {
      element.removeEventListener("touchstart", begin as EventListener)
      element.removeEventListener("touchmove", move as EventListener)
      element.removeEventListener("touchend", end as EventListener)
    }
  }, [history, screen])

  const flash = (message: string) => {
    setNotice(message)
    window.setTimeout(() => setNotice(""), 2200)
  }
  return {
    screen,
    setScreen,
    history,
    setHistory,
    notice,
    setNotice,
    go,
    back,
    flash,
  }
}
