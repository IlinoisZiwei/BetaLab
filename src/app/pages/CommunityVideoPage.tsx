import { routes, CommunityVideoPlayer } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["communityVideoScreen"]

export function CommunityVideoPage({
  communityVideos,
  communityVideoId,
  catalogRoutes,
  expandedCommunityDescription,
  back,
  likedBeta,
  toggle,
  setLikedBeta,
  savedBeta,
  setSavedBeta,
  setComputeVideo,
  setExpandedCommunityDescription,
}: Props) {
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
                    aria-label="Like video"
                    aria-pressed={likedBeta.includes(video.id)}
                    onClick={() => toggle(video.id, likedBeta, setLikedBeta)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    aria-label="Save video"
                    aria-pressed={savedBeta.includes(video.id)}
                    onClick={() => toggle(video.id, savedBeta, setSavedBeta)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
                    </svg>
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
    </main>
  )
}
