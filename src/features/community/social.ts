// B: Community interactions API (comments, likes, saves, shares, danmaku, wanted routes, follows). Contract: README "Backend and API contracts".
import { api, type UserVideo } from "../../api"

type PublicAuthor = { id: string; username: string; display_name: string }
export type CommentItem = {
  id: string
  video_id: string
  /** Top-level comment this reply belongs to; null for top-level comments. */
  parent_id: string | null
  body: string
  /** Playback second when posted (top-level only); shown as danmaku. */
  time_s: number | null
  created_at: string
  author: PublicAuthor
  /** Set when replying to a reply: whom it answers (@name). */
  reply_to: PublicAuthor | null
  like_count: number
  liked: boolean
  reply_count: number
  can_delete: boolean
}
export type CommentPage = { items: CommentItem[]; total: number; total_with_replies?: number; limit: number; offset: number }
export type DanmakuItem = { id: string; body: string; time_s: number; author: string; mine: boolean }
export type SocialSummary = { like_count: number; comment_count: number; share_count: number; liked: boolean; saved: boolean }
export type SocialStats = { likes_received: number; saves_received: number; followers: number; following: number }
export type SavedUpload = UserVideo & { saved_at: string; is_preset_sample?: false }
/** A saved bundled sample: the server only knows its id; the app holds its media. */
export type SavedSample = { id: string; title: string; duration_seconds: number; is_preset_sample: true; saved_at: string }
export type SavedVideo = SavedUpload | SavedSample
export const isSavedUpload = (video: SavedVideo): video is SavedUpload => !video.is_preset_sample

/** GET /api/users/{id}/profile: what anyone signed in may see of an account (N2.8). */
export type PublicProfile = {
  id: string
  username: string
  display_name: string
  joined_at: string | null
  bio?: string
  /** Honors account visibility and the Library profile setting. */
  account_visibility: "public" | "private"
  is_me: boolean
  follower_count: number
  following_count: number
  following: boolean
  public_video_count: number
  videos: (UserVideo & { username: string; display_name: string })[]
  limit: number
  offset: number
}

export const COMMENT_MAX = 500

/** Uploaded videos and accounts use UUID ids. */
export const isUserVideoId = (id: string | null | undefined): id is string =>
  !!id && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)

/** Bundled sample and preset Beta videos (e.g. "sample-a1", "preset-beta-b1"). */
export const isSampleVideoId = (id: string | null | undefined): id is string =>
  !!id && /^(sample|preset-beta)-[a-z0-9-]+$/.test(id)

/** Videos that take likes, saves, comments, danmaku and shares: uploads and bundled samples. */
export const isSocialVideoId = (id: string | null | undefined): id is string =>
  isUserVideoId(id) || isSampleVideoId(id)

/** Every bundled sample the server knows (backend/db/migrations/014_social_sample_videos.sql). */
export const SAMPLE_SOCIAL_IDS = ["sample-a1", "sample-a2", "sample-a3", "preset-beta-b1", "preset-beta-b2", "preset-beta-b3"]

/**
 * The social id of a video as pages name it: sample attempts ("a1") and preset
 * Beta climbers ("b1") map to their Community ids; uploads keep their UUID.
 */
export const socialVideoKey = (id: string) =>
  /^a\d+$/.test(id) ? `sample-${id}` : /^b\d+$/.test(id) ? `preset-beta-${id}` : id

export const socialApi = {
  comments: (videoId: string, offset = 0, limit = 20) =>
    api<CommentPage>(`/videos/${encodeURIComponent(videoId)}/comments?limit=${limit}&offset=${offset}`),
  replies: (commentId: string, offset = 0, limit = 20) =>
    api<CommentPage>(`/comments/${encodeURIComponent(commentId)}/replies?limit=${limit}&offset=${offset}`),
  addComment: (videoId: string, input: { body: string; time_s?: number | null; parent_id?: string | null }, csrf: string) =>
    api<CommentItem>(`/videos/${encodeURIComponent(videoId)}/comments`, { method: "POST", body: input, csrf }),
  setCommentLiked: (commentId: string, liked: boolean, csrf: string) =>
    api<{ liked: boolean; like_count: number }>(`/comments/${encodeURIComponent(commentId)}/like`, { method: liked ? "PUT" : "DELETE", csrf }),
  danmaku: (videoId: string) => api<{ items: DanmakuItem[] }>(`/videos/${encodeURIComponent(videoId)}/danmaku`),
  share: (videoId: string, csrf: string) =>
    api<{ share_count: number }>(`/videos/${encodeURIComponent(videoId)}/share`, { method: "POST", csrf }),
  deleteComment: (commentId: string, csrf: string) =>
    api<void>(`/comments/${encodeURIComponent(commentId)}`, { method: "DELETE", csrf }),
  setLiked: (videoId: string, liked: boolean, csrf: string) =>
    api<{ liked: boolean; like_count: number }>(`/videos/${encodeURIComponent(videoId)}/like`, { method: liked ? "PUT" : "DELETE", csrf }),
  setSaved: (videoId: string, saved: boolean, csrf: string) =>
    api<{ saved: boolean }>(`/videos/${encodeURIComponent(videoId)}/save`, { method: saved ? "PUT" : "DELETE", csrf }),
  /** Fetches summaries for any number of ids, 100 per request; other ids are skipped. */
  summaries: async (ids: string[]) => {
    const unique = [...new Set(ids.filter(isSocialVideoId))]
    const result: Record<string, SocialSummary> = {}
    for (let i = 0; i < unique.length; i += 100) {
      const chunk = unique.slice(i, i + 100)
      Object.assign(result, (await api<{ items: Record<string, SocialSummary> }>(`/social/videos?ids=${chunk.join(",")}`)).items)
    }
    return result
  },
  savedVideos: () => api<{ items: SavedVideo[] }>("/me/saved-videos?limit=100"),
  following: () => api<{ items: { id: string; username: string; display_name: string; followed_at: string }[] }>("/me/following"),
  stats: () => api<SocialStats>("/me/social-stats"),
  setFollowing: (userId: string, following: boolean, csrf: string) =>
    api<{ following: boolean; follower_count: number }>(`/users/${encodeURIComponent(userId)}/follow`, { method: following ? "PUT" : "DELETE", csrf }),
  profile: (userId: string, offset = 0, limit = 20) =>
    api<PublicProfile>(`/users/${encodeURIComponent(userId)}/profile?limit=${limit}&offset=${offset}`),
  wantedRoutes: () => api<{ items: { route_id: string; created_at: string }[] }>("/me/wanted-routes"),
  setWanted: (routeId: string, wanted: boolean, csrf: string) =>
    api<{ wanted: boolean }>(`/routes/${encodeURIComponent(routeId)}/want`, { method: wanted ? "PUT" : "DELETE", csrf }),
}

export function formatCommentTime(iso: string, now = Date.now()) {
  const seconds = Math.max(0, (now - Date.parse(iso)) / 1000)
  if (seconds < 60) return "Just now"
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`
  return new Date(iso).toLocaleDateString()
}

export const formatVideoTime = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`

/** Lets a just-posted timed comment fly across the video at once, without refetching danmaku. */
const DANMAKU_EVENT = "betalab:danmaku-posted"
export const announceDanmaku = (videoId: string, item: DanmakuItem) =>
  window.dispatchEvent(new CustomEvent(DANMAKU_EVENT, { detail: { videoId, item } }))
export const onDanmakuPosted = (handler: (videoId: string, item: DanmakuItem) => void) => {
  const listener = (event: Event) => {
    const { videoId, item } = (event as CustomEvent<{ videoId: string; item: DanmakuItem }>).detail
    handler(videoId, item)
  }
  window.addEventListener(DANMAKU_EVENT, listener)
  return () => window.removeEventListener(DANMAKU_EVENT, listener)
}

/** Link that opens a Community video in this app (after sign-in). Only works on the same BetaLab server. */
export const videoShareUrl = (videoId: string) => {
  const url = new URL(import.meta.env.BASE_URL, window.location.origin)
  url.searchParams.set("video", videoId)
  return url.toString()
}

/** System share sheet on phones; copy to clipboard elsewhere (also over plain-HTTP LAN, where the Clipboard API is unavailable). */
export async function shareLink(title: string, url: string): Promise<"shared" | "copied" | "cancelled" | "failed"> {
  if (typeof navigator.share === "function" && window.matchMedia?.("(pointer: coarse)").matches) {
    try { await navigator.share({ title, url }); return "shared" }
    catch (error) { if ((error as DOMException).name === "AbortError") return "cancelled" }
  }
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(url); return "copied" }
  } catch { /* fall through to the legacy path */ }
  const field = document.createElement("textarea")
  field.value = url
  field.setAttribute("readonly", "")
  field.style.position = "fixed"; field.style.opacity = "0"
  document.body.appendChild(field)
  field.select()
  let ok = false
  try { ok = document.execCommand("copy") } catch { ok = false }
  field.remove()
  return ok ? "copied" : "failed"
}
