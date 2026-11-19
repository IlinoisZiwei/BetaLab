import { routes, VideoThumbnail } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["communityScreen"]

export function CommunityPage({
  communitySearch,
  setCommunitySearch,
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
}: Props) {
  return (
    <main className="screen with-header community-feed">
      <header className="community-feed-intro">
        <h1>Community</h1>
        <p>Climbing videos shared by the community.</p>
      </header>
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
          return (
            <button
              type="button"
              className="community-feed-card"
              key={video.id}
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
          )
        })}
        {communityResults.length === 0 && (
          <div className="community-feed-empty">
            <strong>
              {communityVideos.length
                ? "No videos match these filters"
                : "No public videos yet"}
            </strong>
            <p>
              {communityVideos.length
                ? "Try a different search or filter."
                : "Videos shared publicly will appear here."}
            </p>
          </div>
        )}
      </div>
    </main>
  )
}
