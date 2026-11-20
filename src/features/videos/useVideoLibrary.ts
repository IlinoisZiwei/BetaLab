import { useEffect, useReducer, useRef, useState } from "react"
import { api, type Session, type UserVideo } from "../../api"
import { emptyVideos, videoReducer } from "./videoState"

type Options = {
  session: Session | null
  screen: string
  routeId: string
  followingOnly: boolean
  onError: (message: string) => void
}

const PUBLIC_PAGE = 20

export function useVideoLibrary({
  session,
  screen,
  routeId,
  followingOnly,
  onError,
}: Options) {
  const [videos, dispatch] = useReducer(videoReducer, undefined, emptyVideos)
  useEffect(() => {
    if (!session) return
    const controller = new AbortController()
    void api<{ items: UserVideo[] }>("/videos?owned=true&limit=100", {
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted)
          dispatch({ type: "replace", list: "owned", videos: result.items })
      })
      .catch((error) => {
        if (!controller.signal.aborted) onError(error.message)
      })
    return () => controller.abort()
  }, [session?.user.id])
  // B2.3: the public feed loads PUBLIC_PAGE videos at a time. It refreshes when Community
  // opens, but not when returning from the full-screen viewer, so loaded pages are kept.
  const [publicHasMore, setPublicHasMore] = useState(false)
  const [publicLoading, setPublicLoading] = useState(false)
  const [publicError, setPublicError] = useState("")
  const publicRequest = useRef<AbortController | null>(null)
  const loadPublic = async (reset: boolean, keep?: UserVideo) => {
    if (!session) return
    publicRequest.current?.abort()
    const controller = new AbortController()
    publicRequest.current = controller
    setPublicLoading(true)
    setPublicError("")
    try {
      const offset = reset ? 0 : videos.public.length
      const result = await api<{ items: UserVideo[] }>(
        `/videos?owned=false&following=${followingOnly}&limit=${PUBLIC_PAGE}&offset=${offset}`,
        { signal: controller.signal },
      )
      if (controller.signal.aborted) return
      dispatch({ type: reset ? "replace" : "append", list: "public", videos: result.items })
      if (keep) dispatch({ type: "append", list: "public", videos: [keep] })
      setPublicHasMore(result.items.length === PUBLIC_PAGE)
    } catch (error) {
      if (!controller.signal.aborted) setPublicError((error as Error).message)
    } finally {
      if (!controller.signal.aborted) setPublicLoading(false)
    }
  }
  const lastScreen = useRef(screen)
  useEffect(() => {
    const previous = lastScreen.current
    lastScreen.current = screen
    if (session && screen === "community" && previous !== "communityVideo") void loadPublic(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.user.id, screen, followingOnly])
  useEffect(() => () => publicRequest.current?.abort(), [session?.user.id])
  useEffect(() => {
    if (!session || screen !== "workspace" || !routeId) return
    const controller = new AbortController()
    void api<{ items: UserVideo[] }>(
      `/videos?owned=false&route_id=${encodeURIComponent(routeId)}&share_as_beta=true&limit=100`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (!controller.signal.aborted)
          dispatch({ type: "replace", list: "beta", videos: result.items })
      })
      .catch((error) => {
        if (!controller.signal.aborted) onError(error.message)
      })
    return () => controller.abort()
  }, [session?.user.id, screen, routeId])

  function syncVideo(video: UserVideo) {
    const enriched = {
      ...video,
      username: session?.user.username,
      display_name: session?.user.display_name,
      height_cm: video.share_as_beta ? session?.user.height_cm : null,
      arm_span_cm: video.share_as_beta ? session?.user.arm_span_cm : null,
    }
    dispatch({ type: "upsert", video: enriched, routeId })
  }
  return {
    myVideos: videos.owned,
    publicVideos: videos.public,
    routeBetaVideos: videos.beta,
    syncVideo,
    removeVideo: (id: string) => dispatch({ type: "remove", id }),
    resetVideos: () => {
      publicRequest.current?.abort()
      setPublicHasMore(false)
      setPublicError("")
      setPublicLoading(false)
      dispatch({ type: "reset" })
    },
    publicHasMore,
    publicLoading,
    publicError,
    loadMorePublic: () => loadPublic(false),
    retryPublic: () => loadPublic(videos.public.length === 0),
    // Reload the first page; `keep` (a shared video outside it) stays in the feed for the viewer.
    refreshPublic: (keep?: UserVideo) => {
      if (keep) dispatch({ type: "append", list: "public", videos: [keep] })
      return loadPublic(true, keep)
    },
  }
}
