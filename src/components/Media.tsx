import { useRef, useState, useEffect } from "react"
import movementRoutes from "../data/movementRoutes.json"
import { routeMedia } from "../app/demo"

export function MediaImage({
  routeId,
  wall = false,
  className = "",
}: {
  routeId: string
  wall?: boolean
  className?: string
}) {
  const media = routeMedia(routeId)
  return (
    <img
      className={`real-media-image ${className}`}
      src={wall ? media.wall : media.poster}
      alt={
        movementRoutes.find((route) => route.id === routeId)?.name ??
        (wall ? "Climbing wall and holds" : "Climbing recording preview")
      }
      loading="lazy"
    />
  )
}

export function MediaVideo({
  routeId,
  pose = false,
  seekTime,
  measurementLabel,
  sourceUrl,
}: {
  routeId: string
  pose?: boolean
  seekTime?: number
  measurementLabel?: string
  sourceUrl?: string
}) {
  const media = routeMedia(routeId)
  const ref = useRef<HTMLVideoElement>(null)
  const src = sourceUrl || (pose ? media.pose : media.video)
  const [playing, setPlaying] = useState(false)
  const [mediaError, setMediaError] = useState(false)
  useEffect(() => {
    setPlaying(false)
    setMediaError(false)
  }, [src])
  useEffect(() => {
    if (ref.current && seekTime !== undefined)
      ref.current.currentTime = seekTime
  }, [seekTime])
  if (!src)
    return (
      <p className="empty-state">
        {pose
          ? "No skeleton recording for this route yet."
          : "No video for this route yet. Add your climbing video to get started."}
      </p>
    )
  return (
    <>
      <video
        ref={ref}
        key={src}
        className="real-media-video"
        src={src}
        poster={pose ? undefined : media.poster}
        controls
        playsInline
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => {
          setPlaying(false)
          setMediaError(true)
        }}
      />
      {mediaError && (
        <p role="alert">
          This video could not be played. Check your connection, or upload an
          MP4 encoded with H.264.
        </p>
      )}
      {measurementLabel && (
        <span
          className={`video-body-label${playing ? " is-hidden" : ""}`}
          aria-hidden={playing}
        >
          {measurementLabel}
        </span>
      )}
    </>
  )
}

export function VideoThumbnail({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLVideoElement>(null)
  const revealFirstFrame = () => {
    const video = ref.current
    if (!video || video.readyState < 2) return
    video.currentTime = Math.min(0.1, video.duration || 0.1)
  }
  return (
    <video
      ref={ref}
      className="real-media-video-thumbnail"
      src={src}
      aria-label={alt}
      muted
      playsInline
      preload="metadata"
      onLoadedData={revealFirstFrame}
      onSeeked={(event) => event.currentTarget.pause()}
    />
  )
}

export function CommunityVideoPlayer({
  src,
  alt,
}: {
  src: string
  alt: string
}) {
  const ref = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const formatTime = (seconds: number) => {
    const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0
    return `${Math.floor(safeSeconds / 60)}:${String(Math.floor(safeSeconds % 60)).padStart(2, "0")}`
  }
  useEffect(() => {
    setCurrentTime(0)
    setDuration(0)
  }, [src])
  useEffect(() => {
    const video = ref.current
    if (!video) return
    const root = video.closest(".community-tiktok-scroll")
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.some(
          (entry) => entry.isIntersecting && entry.intersectionRatio >= 0.6,
        )
        if (visible) void video.play().catch(() => setPlaying(false))
        else video.pause()
      },
      { root, threshold: [0, 0.6, 1] },
    )
    observer.observe(video)
    return () => {
      observer.disconnect()
      video.pause()
    }
  }, [src])
  return (
    <div className="community-video-player">
      <video
        ref={ref}
        className="community-tiktok-video"
        src={src}
        aria-label={alt}
        playsInline
        loop
        preload="metadata"
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
        onDurationChange={(event) => setDuration(event.currentTarget.duration || 0)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onSeeked={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onClick={(event) => {
          const video = event.currentTarget
          if (video.paused) void video.play()
          else video.pause()
        }}
      />
      {!playing && (
        <button
          type="button"
          className="community-video-play-toggle"
          aria-label="Play video"
          onClick={() => void ref.current?.play()}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m8 5 12 7-12 7V5Z" />
          </svg>
        </button>
      )}
      <div
        className="community-video-scrubber"
        onClick={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <input
          type="range"
          min="0"
          max={duration || 0}
          step="0.01"
          value={Math.min(currentTime, duration || 0)}
          aria-label="Video timeline"
          aria-valuetext={`${formatTime(currentTime)} of ${formatTime(duration)}`}
          disabled={!duration}
          onChange={(event) => {
            const nextTime = Number(event.currentTarget.value)
            if (ref.current) ref.current.currentTime = nextTime
            setCurrentTime(nextTime)
          }}
        />
        <span aria-hidden="true">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>
    </div>
  )
}
