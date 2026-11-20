import { useState } from "react"
import { routes, CommunityVideoPlayer } from "../shared"
import type { AppController } from "../useAppController"
import { CommentSection } from "../../features/community/CommentSection"
import { Danmaku } from "../../features/community/Danmaku"

type Props = AppController["pages"]["communityVideoScreen"]

export function CommunityVideoPage({
  communityVideos,
  communityVideoId,
  catalogRoutes,
  expandedCommunityDescription,
  back,
  social,
  toggleSocial,
  shareVideo,
  danmakuOn,
  toggleDanmaku,
  session,
  expireSession,
  updateCommentCount,
  setComputeVideo,
  setExpandedCommunityDescription,
}: Props) {
  // B2.8: comments open in a bottom sheet over the playing video, TikTok-style.
  const [commentsFor, setCommentsFor] = useState<string | null>(null)
  const videoElement = (videoId: string) =>
    document.getElementById(`community-video-${videoId}`)?.querySelector("video") ?? null
  return (
    <main className="community-tiktok">
      {communityVideos.length === 0 ? (
        <div className="community-tiktok-empty">
          <strong>No public videos yet</strong>
          <span>Videos shared publicly will appear here.</span>
        </div>
      ) : (
        <div
          className="community-tiktok-scroll"
          key={communityVideoId ?? "community"}
        >
          {communityVideos.map((video) => {
            const route =
              catalogRoutes.find((item) => item.id === video.route_id) ??
              routes.find((item) => item.id === video.route_id)
            const expanded = expandedCommunityDescription === video.id
            return (
              <section
                className="community-tiktok-slide"
                id={`community-video-${video.id}`}
                key={video.id}
              >
                <CommunityVideoPlayer
                  src={video.content_url}
                  alt={`${video.title} video`}
                />
                <div className="community-tiktok-shade" />
                <Danmaku videoId={video.id} enabled={danmakuOn} />
                <div className="community-tiktok-top">
                  <button type="button" onClick={back} aria-label="Back">
                    ‹
                  </button>
                  <span aria-hidden="true" />
                </div>
                <aside
                  className="community-tiktok-actions"
                  aria-label="Video actions"
                >
                  <button
                    type="button"
                    aria-label={`Like video${social[video.id] ? ` (${social[video.id].like_count} likes)` : ""}`}
                    aria-pressed={!!social[video.id]?.liked}
                    onClick={() => void toggleSocial(video.id, "liked")}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
                    </svg>
                    {social[video.id] && <span className="action-count">{social[video.id].like_count}</span>}
                  </button>
                  <button
                    type="button"
                    aria-label="Save video"
                    aria-pressed={!!social[video.id]?.saved}
                    onClick={() => void toggleSocial(video.id, "saved")}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    className="comments-action"
                    aria-label={`Comments${social[video.id] ? ` (${social[video.id].comment_count})` : ""}`}
                    onClick={() => setCommentsFor(video.id)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M4 5h16v11H9l-5 4V5Z" />
                    </svg>
                    {social[video.id] && <span className="action-count">{social[video.id].comment_count}</span>}
                  </button>
                  <button
                    type="button"
                    className="share-action"
                    aria-label={`Share video${social[video.id] ? ` (${social[video.id].share_count} shares)` : ""}`}
                    onClick={() => void shareVideo(video)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M14 5l7 7-7 7v-4c-5 0-8 1.5-10 5 .5-5.5 3.5-10 10-11V5Z" />
                    </svg>
                    {social[video.id] && <span className="action-count">{social[video.id].share_count}</span>}
                  </button>
                  <button
                    type="button"
                    className={`danmaku-action${danmakuOn ? " is-on" : ""}`}
                    aria-label="Show danmaku"
                    aria-pressed={danmakuOn}
                    onClick={toggleDanmaku}
                  >
                    <span aria-hidden="true">弹</span>
                  </button>
                  <button
                    type="button"
                    aria-label="Generate beta"
                    onClick={() => setComputeVideo(video)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2ZM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" />
                    </svg>
                  </button>
                </aside>
                <div className="community-tiktok-caption">
                  <div className="community-tiktok-author">
                    <span>
                      {(video.display_name || video.username || "C")
                        .slice(0, 1)
                        .toUpperCase()}
                    </span>
                    <strong>
                      {video.display_name ||
                        video.username ||
                        "Community member"}
                    </strong>
                    <small>
                      {video.is_preset_beta
                        ? "Public · Preset Community Beta"
                        : video.is_preset_sample
                          ? "Public · Preset sample"
                          : route
                            ? `${route.gym} · ${route.grade}`
                            : "Community"}
                    </small>
                  </div>
                  <strong className="community-tiktok-title">
                    {video.title}
                  </strong>
                  {video.description && (
                    <button
                      className={`community-tiktok-description${
                        expanded ? " is-expanded" : ""
                      }`}
                      onClick={() =>
                        setExpandedCommunityDescription(
                          expanded ? null : video.id,
                        )
                      }
                    >
                      {video.description}
                      {video.description.length > 90 && (
                        <b>{expanded ? "  less" : "  more"}</b>
                      )}
                    </button>
                  )}
                </div>
              </section>
            )
          })}
        </div>
      )}
      {commentsFor && (
        <div className="comment-sheet-backdrop" onClick={() => setCommentsFor(null)}>
          <div
            className="comment-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Comments"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="comment-sheet-header">
              <span aria-hidden="true" />
              <button type="button" aria-label="Close comments" onClick={() => setCommentsFor(null)}>×</button>
            </div>
            <CommentSection
              videoId={commentsFor}
              session={session}
              onSignIn={expireSession}
              onCountChange={updateCommentCount}
              getCurrentTime={() => videoElement(commentsFor)?.currentTime}
              onSeek={(seconds) => {
                const element = videoElement(commentsFor)
                if (element) {
                  element.currentTime = seconds
                  void element.play().catch(() => {})
                }
                setCommentsFor(null)
              }}
            />
          </div>
        </div>
      )}
    </main>
  )
}
