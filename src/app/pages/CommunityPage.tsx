import { routes, VideoThumbnail } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["communityScreen"]

export function CommunityPage({
  communitySearch,
  setCommunitySearch,
  communityAudience,
  setCommunityAudience,
  communityGymFilter,
  setCommunityGymFilter,
  catalogGyms,
  communityGradeFilter,
  setCommunityGradeFilter,
  catalogRoutes,
  communityResults,
  setCommunityVideoId,
  setExpandedCommunityDescription,
  go,
  communityVideos,
  publicHasMore,
  publicLoading,
  publicError,
  loadMorePublic,
  retryPublic,
  session,
  following,
  toggleFollow,
}: Props) {
  return (
    <main className="screen with-header community-feed">
      <header className="community-feed-intro">
        <h1>Community</h1>
        <p>Climbing videos shared by the community.</p>
      </header>
      <nav className="community-audience-tabs" aria-label="Community video feed">
        <button
          type="button"
          className={communityAudience === "all" ? "is-active" : ""}
          aria-pressed={communityAudience === "all"}
          onClick={() => setCommunityAudience("all")}
        >
          All
        </button>
        <button
          type="button"
          className={communityAudience === "following" ? "is-active" : ""}
          aria-pressed={communityAudience === "following"}
          onClick={() => setCommunityAudience("following")}
        >
          Following
        </button>
      </nav>
      <div className="community-search">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 4.5 4.5" />
        </svg>
        <input
          aria-label="Search community videos"
          value={communitySearch}
          onChange={(event) => setCommunitySearch(event.target.value)}
          placeholder="Search videos, climbers, routes"
        />
        {communitySearch && (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => setCommunitySearch("")}
          >
            ×
          </button>
        )}
      </div>
      <div className="community-filters">
        <select
          aria-label="Filter by gym"
          value={communityGymFilter}
          onChange={(event) => setCommunityGymFilter(event.target.value)}
        >
          <option>All gyms</option>
          {catalogGyms.map((gym) => (
            <option key={gym.name}>{gym.name}</option>
          ))}
        </select>
        <select
          aria-label="Filter by grade"
          value={communityGradeFilter}
          onChange={(event) => setCommunityGradeFilter(event.target.value)}
        >
          <option>All grades</option>
          {[...new Set(catalogRoutes.map((route) => route.grade))]
            .sort()
            .map((grade) => (
              <option key={grade}>{grade}</option>
            ))}
        </select>
      </div>
      <div className="community-feed-list">
        {communityResults.map((video) => {
          const route =
            catalogRoutes.find((item) => item.id === video.route_id) ??
            routes.find((item) => item.id === video.route_id)
          const isFollowing = following.includes(video.owner_id)
          const author = video.display_name || video.username || "Community member"
          return (
            <article className="community-feed-entry" key={video.id}>
            <button
              type="button"
              className="community-feed-card"
              onClick={() => {
                setCommunityVideoId(video.id)
                setExpandedCommunityDescription(null)
                go("communityVideo")
              }}
            >
              <span className="community-feed-thumbnail">
                <VideoThumbnail
                  src={video.content_url}
                  alt={`${video.title} video first frame`}
                />
                <span className="community-feed-play" aria-hidden="true">
                  ▶
                </span>
              </span>
              <span className="community-feed-card-body">
                <strong>{video.title}</strong>
                <span className="community-feed-meta">
                  {video.is_preset_beta
                    ? `${video.display_name} · Public · Preset Beta`
                    : video.is_preset_sample
                      ? "Public · Preset sample"
                      : video.display_name ||
                        video.username ||
                        "Community member"}
                  {route
                    ? ` · ${route.gym} · ${route.name} · ${route.grade}`
                    : ""}
                </span>
              </span>
            </button>
            <footer className="community-feed-author-row">
              <span className="community-feed-author-name">{author}</span>
              <span className="community-feed-badge">Public</span>
              {(video.is_preset_sample || video.is_preset_beta) && (
                <span className="community-feed-badge is-preset">Preset</span>
              )}
              {!video.is_preset_sample && video.owner_id !== "preset" && session && video.owner_id !== session.user.id && (
                <button
                  type="button"
                  className={`community-feed-follow${isFollowing ? " is-following" : ""}`}
                  aria-pressed={isFollowing}
                  aria-label={`${isFollowing ? "Unfollow" : "Follow"} ${author}`}
                  onClick={() => void toggleFollow(video.owner_id)}
                >
                  {isFollowing ? "Following" : "+ Follow"}
                </button>
              )}
            </footer>
            </article>
          )
        })}
        {publicLoading && communityResults.length === 0 && (
          <p className="community-feed-status" role="status">Loading community videos…</p>
        )}
        {publicError && (
          <div className="community-feed-error" role="alert">
            <p>{publicError}</p>
            <button type="button" className="btn btn-outline" onClick={() => void retryPublic()}>Try again</button>
          </div>
        )}
        {publicHasMore && !publicError && (
          <button type="button" className="btn btn-outline community-load-more" disabled={publicLoading} onClick={() => void loadMorePublic()}>
            {publicLoading ? "Loading…" : "Load more videos"}
          </button>
        )}
        {communityResults.length === 0 && !publicLoading && (
          <div className="community-feed-empty">
            <strong>
              {communityAudience === "following"
                ? "No videos from people you follow yet"
                : communityVideos.length
                ? "No videos match these filters"
                : "No public videos yet"}
            </strong>
            <p>
              {communityAudience === "following"
                ? "Follow a climber to see their public videos here."
                : communityVideos.length
                ? "Try a different search or filter."
                : "Videos shared publicly will appear here."}
            </p>
          </div>
        )}
      </div>
    </main>
  )
}
