import { useEffect, useRef, useState } from "react"
import { isSocialVideoId, onDanmakuPosted, socialApi, type DanmakuItem } from "./social"

type Bullet = { key: string; text: string; lane: number; mine: boolean; travel: number }

const LANES = 4
const MAX_ON_SCREEN = 12
const MAX_CHARS = 40

/**
 * Bilibili-style danmaku over a Community slide. It finds the slide's <video>
 * itself, so the player component needs no changes. Comments fire when
 * playback crosses their timestamp (not on seeks), pause with the video, and
 * load lazily the first time the video plays. Decorative: the same comments
 * are readable in the comments sheet, so the layer is hidden from screen readers.
 */
export function Danmaku({ videoId, enabled }: { videoId: string; enabled: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const items = useRef<DanmakuItem[]>([])
  const enabledRef = useRef(enabled)
  const laneFreeAt = useRef<number[]>(Array(LANES).fill(0))
  const [bullets, setBullets] = useState<Bullet[]>([])
  const [paused, setPaused] = useState(true)
  enabledRef.current = enabled

  const spawn = (item: DanmakuItem) => {
    const width = host.current?.clientWidth ?? 360
    const now = performance.now()
    // Prefer a lane whose previous bullet has cleared the right edge.
    let lane = laneFreeAt.current.findIndex(t => t <= now)
    if (lane < 0) lane = laneFreeAt.current.indexOf(Math.min(...laneFreeAt.current))
    laneFreeAt.current[lane] = now + 1600
    const text = item.body.length > MAX_CHARS ? `${item.body.slice(0, MAX_CHARS)}…` : item.body
    setBullets(current => [...current.slice(-(MAX_ON_SCREEN - 1)), { key: `${item.id}:${now}`, text, lane, mine: item.mine, travel: width }])
  }

  useEffect(() => {
    setBullets([])
    items.current = []
    if (!isSocialVideoId(videoId)) return
    const video = host.current?.closest(".community-tiktok-slide")?.querySelector("video")
    if (!video) return
    let loaded = false
    let last = video.currentTime
    const load = () => {
      if (loaded) return
      loaded = true
      socialApi.danmaku(videoId).then(result => { items.current = result.items }).catch(() => { loaded = false })
    }
    const onPlay = () => { setPaused(false); load() }
    const onPause = () => setPaused(true)
    const onTime = () => {
      const t = video.currentTime
      // Only natural playback fires bullets; a jump (seek, loop restart) just moves the cursor.
      if (enabledRef.current && t > last && t - last < 1.5) {
        for (const item of items.current) if (item.time_s > last && item.time_s <= t) spawn(item)
      }
      last = t < last && t < 0.5 ? -0.001 : t // after looping, let 0:00 comments fire again
    }
    const onSeeked = () => { last = video.currentTime - 0.001 }
    video.addEventListener("play", onPlay)
    video.addEventListener("pause", onPause)
    video.addEventListener("timeupdate", onTime)
    video.addEventListener("seeked", onSeeked)
    if (!video.paused) onPlay()
    const stopListening = onDanmakuPosted((id, item) => {
      if (id !== videoId) return
      items.current = [...items.current, item].sort((a, b) => a.time_s - b.time_s)
      if (enabledRef.current) spawn(item)
    })
    return () => {
      video.removeEventListener("play", onPlay)
      video.removeEventListener("pause", onPause)
      video.removeEventListener("timeupdate", onTime)
      video.removeEventListener("seeked", onSeeked)
      stopListening()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId])

  useEffect(() => { if (!enabled) setBullets([]) }, [enabled])

  return <div ref={host} className={`danmaku-layer${paused ? " is-paused" : ""}`} aria-hidden="true">
    {bullets.map(bullet => <span
      key={bullet.key}
      className={`danmaku${bullet.mine ? " is-mine" : ""}`}
      style={{ top: `${bullet.lane * 34}px`, ["--travel" as string]: `${bullet.travel}px` }}
      onAnimationEnd={() => setBullets(current => current.filter(b => b.key !== bullet.key))}
    >{bullet.text}</span>)}
  </div>
}
