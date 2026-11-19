import { useEffect, useReducer } from "react"
import { api, type Session, type UserVideo } from "../../api"
import { emptyVideos, videoReducer } from "./videoState"

type Options = {
  session: Session | null
  screen: string
  routeId: string
  onError: (message: string) => void
}

export function useVideoLibrary({
  session,
  screen,
  routeId,
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
  useEffect(() => {
    if (!session || screen !== "community") return
    const controller = new AbortController()
    void api<{ items: UserVideo[] }>("/videos?owned=false&limit=100", {
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted)
          dispatch({ type: "replace", list: "public", videos: result.items })
      })
      .catch((error) => {
        if (!controller.signal.aborted) onError(error.message)
      })
    return () => controller.abort()
  }, [session?.user.id, screen])
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
    resetVideos: () => dispatch({ type: "reset" }),
  }
}
