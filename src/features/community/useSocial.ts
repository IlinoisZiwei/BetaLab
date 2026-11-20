import { useEffect, useRef, useState, type MutableRefObject } from "react"
import { ApiError, api, type Session, type UserVideo } from "../../api"
import { isSocialVideoId, isUserVideoId, SAMPLE_SOCIAL_IDS, shareLink, socialApi, videoShareUrl, type SavedVideo, type SocialSummary } from "./social"

type Options = {
  session: Session | null
  authEpoch: MutableRefObject<number>
  flash: (message: string) => void
  /** The session is gone (401): return to sign-in. */
  onExpired: () => void
  /** Every uploaded video currently listed anywhere; their counts are fetched once per session. */
  visibleVideos: UserVideo[]
  /** A shared link (?video=<id>) resolved after sign-in. */
  onOpenShared: (videoId: string, video: UserVideo | null) => void
}

const emptySummary: SocialSummary = { like_count: 0, comment_count: 0, share_count: 0, liked: false, saved: false }

/**
 * B: persistent Community interactions for the signed-in account - video likes
 * and saves, want-to-try routes, like/comment/share counts, sharing and the
 * danmaku preference. Bundled samples are examples and cannot be liked or saved.
 */
export function useSocial({ session, authEpoch, flash, onExpired, visibleVideos, onOpenShared }: Options) {
  const [social, setSocial] = useState<Record<string, SocialSummary>>({})
  const [savedVideos, setSavedVideos] = useState<SavedVideo[]>([])
  const [wantedRoutes, setWantedRoutes] = useState<string[]>([])
  // N2.7: accounts this user follows. Following never unlocks private content.
  const [following, setFollowing] = useState<string[]>([])
  const requested = useRef(new Set<string>())
  const pending = useRef(new Set<string>())
  // Danmaku preference is per browser; off by default for people who prefer reduced motion.
  const [danmakuOn, setDanmakuOn] = useState(() => {
    try {
      const stored = localStorage.getItem("betalab.danmaku")
      if (stored) return stored === "on"
    } catch { /* storage unavailable */ }
    return !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  })
  const pendingShared = useRef<string | null>(new URLSearchParams(window.location.search).get("video"))

  const failed = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) onExpired()
    else flash((error as Error).message)
  }

  const reset = () => {
    setSocial({}); setSavedVideos([]); setWantedRoutes([]); setFollowing([])
    requested.current = new Set(); pending.current = new Set()
  }

  const refreshSaved = async () => {
    const epoch = authEpoch.current
    try {
      const result = await socialApi.savedVideos()
      if (epoch === authEpoch.current) setSavedVideos(result.items)
    } catch (error) {
      if (epoch === authEpoch.current && !(error instanceof ApiError && error.status === 401)) flash((error as Error).message)
    }
  }

  // Saved videos and wanted routes belong to the account: load once per sign-in.
  useEffect(() => {
    if (!session) return
    const epoch = authEpoch.current
    void refreshSaved()
    socialApi.wantedRoutes()
      .then(result => { if (epoch === authEpoch.current) setWantedRoutes(result.items.map(item => item.route_id)) })
      .catch(() => {})
    socialApi.following()
      .then(result => { if (epoch === authEpoch.current) setFollowing(result.items.map(item => item.id)) })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.user.id])

  // Counts for every uploaded video on screen, once per id per session.
  const idsKey = [...visibleVideos.map(video => video.id), ...savedVideos.map(video => video.id), ...SAMPLE_SOCIAL_IDS].join(",")
  useEffect(() => {
    if (!session || !idsKey) return
    const missing = idsKey.split(",").filter(id => isSocialVideoId(id) && !requested.current.has(id))
    if (!missing.length) return
    missing.forEach(id => requested.current.add(id))
    const epoch = authEpoch.current
    socialApi.summaries(missing)
      .then(items => { if (epoch === authEpoch.current) setSocial(current => ({ ...items, ...current })) })
      .catch(() => missing.forEach(id => requested.current.delete(id)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.user.id, idsKey])

  // Open a shared link once signed in; fetch the video, which may be outside the loaded feed pages.
  useEffect(() => {
    const id = pendingShared.current
    if (!session || !id) return
    pendingShared.current = null
    const url = new URL(window.location.href)
    url.searchParams.delete("video")
    window.history.replaceState(null, "", url.toString())
    if (!isUserVideoId(id)) { onOpenShared(id, null); return }
    const epoch = authEpoch.current
    api<UserVideo>(`/videos/${encodeURIComponent(id)}`)
      .then(video => { if (epoch === authEpoch.current) onOpenShared(id, video) })
      .catch(() => { if (epoch === authEpoch.current) flash("This video is private or no longer available.") })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.user.id])

  const toggleSocial = async (videoId: string, field: "liked" | "saved") => {
    if (!isSocialVideoId(videoId)) return
    if (!session) { onExpired(); return }
    const key = `${field}:${videoId}`
    if (pending.current.has(key)) return
    pending.current.add(key)
    const epoch = authEpoch.current
    const before = social[videoId] ?? emptySummary
    const next = !before[field]
    setSocial(current => {
      const base = current[videoId] ?? emptySummary
      return { ...current, [videoId]: { ...base, [field]: next, like_count: field === "liked" ? Math.max(0, base.like_count + (next ? 1 : -1)) : base.like_count } }
    })
    try {
      if (field === "liked") {
        const result = await socialApi.setLiked(videoId, next, session.csrf_token)
        if (epoch === authEpoch.current) setSocial(current => ({ ...current, [videoId]: { ...(current[videoId] ?? before), liked: result.liked, like_count: result.like_count } }))
      } else {
        await socialApi.setSaved(videoId, next, session.csrf_token)
        if (epoch === authEpoch.current) { void refreshSaved(); flash(next ? "Saved to My Library" : "Removed from saved") }
      }
    } catch (error) {
      if (epoch !== authEpoch.current) return
      setSocial(current => ({ ...current, [videoId]: { ...(current[videoId] ?? before), [field]: before[field], like_count: field === "liked" ? before.like_count : (current[videoId] ?? before).like_count } }))
      failed(error)
    } finally {
      pending.current.delete(key)
    }
  }

  const toggleWanted = async (routeId: string) => {
    if (!session) { onExpired(); return }
    const key = `want:${routeId}`
    if (pending.current.has(key)) return
    pending.current.add(key)
    const epoch = authEpoch.current
    const was = wantedRoutes.includes(routeId)
    setWantedRoutes(ids => (was ? ids.filter(id => id !== routeId) : [...ids, routeId]))
    try {
      await socialApi.setWanted(routeId, !was, session.csrf_token)
    } catch (error) {
      if (epoch !== authEpoch.current) return
      setWantedRoutes(ids => (was ? [...new Set([...ids, routeId])] : ids.filter(id => id !== routeId)))
      failed(error)
    } finally {
      pending.current.delete(key)
    }
  }

  const toggleFollow = async (userId: string) => {
    if (!session) { onExpired(); return }
    if (!isUserVideoId(userId) || userId === session.user.id) return
    const key = `follow:${userId}`
    if (pending.current.has(key)) return
    pending.current.add(key)
    const epoch = authEpoch.current
    const was = following.includes(userId)
    setFollowing(ids => (was ? ids.filter(id => id !== userId) : [...ids, userId]))
    try {
      const result = await socialApi.setFollowing(userId, !was, session.csrf_token)
      if (epoch === authEpoch.current) setFollowing(ids => (result.following ? [...new Set([...ids, userId])] : ids.filter(id => id !== userId)))
    } catch (error) {
      if (epoch !== authEpoch.current) return
      setFollowing(ids => (was ? [...new Set([...ids, userId])] : ids.filter(id => id !== userId)))
      failed(error)
    } finally {
      pending.current.delete(key)
    }
  }

  const updateCommentCount = (videoId: string, total: number) =>
    setSocial(current => ({ ...current, [videoId]: { ...(current[videoId] ?? emptySummary), comment_count: total } }))

  const shareVideo = async (video: { id: string; title: string }) => {
    const url = videoShareUrl(video.id)
    const result = await shareLink(video.title, url)
    if (result === "copied") flash("Link copied. People signed in to this BetaLab can open it.")
    else if (result === "failed") flash(`Copy this link: ${url}`)
    if ((result === "shared" || result === "copied") && isSocialVideoId(video.id) && session) {
      const epoch = authEpoch.current
      try {
        const counted = await socialApi.share(video.id, session.csrf_token)
        if (epoch === authEpoch.current) setSocial(current => ({ ...current, [video.id]: { ...(current[video.id] ?? emptySummary), share_count: counted.share_count } }))
      } catch { /* the link was still shared; only the counter missed */ }
    }
  }

  const toggleDanmaku = () => setDanmakuOn(on => {
    try { localStorage.setItem("betalab.danmaku", on ? "off" : "on") } catch { /* not persisted */ }
    return !on
  })

  /** After the owner deletes a video, drop it from saved and counts. */
  const forgetVideo = (videoId: string) => {
    setSavedVideos(items => items.filter(video => video.id !== videoId))
    setSocial(items => { const next = { ...items }; delete next[videoId]; return next })
  }

  return {
    social, savedVideos, wantedRoutes, danmakuOn, following,
    toggleSocial, toggleWanted, toggleFollow, updateCommentCount, shareVideo, toggleDanmaku, forgetVideo, reset,
  }
}
