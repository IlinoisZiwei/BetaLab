import type { ReactNode } from "react"
import { AttemptRecord, routes, AppButton, routeLabel, routeMedia, MediaImage, VideoThumbnail } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["libraryScreen"] & { computeContent?: ReactNode; pageIntro?: ReactNode }

export function LibraryPage({
  computeContent,
  pageIntro,
  libraryTab,
  setLibraryTab,
  catalogGyms,
  myVideos,
  catalogRoutes,
  setSelectedRoute,
  setSelectedGym,
  setActiveAttemptId,
  setHasAttempt,
  setWorkspaceEntry,
  setWorkspaceSource,
  go,
  libraryItems,
  openRoute,
  savedVideos,
  openSavedSample,
}: Props) {
  return (
    <main className="screen with-header library-page">
      {pageIntro}
      <div className="tabs library-tabs">
        <button
          className={libraryTab === "attempts" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("attempts")}
        >
          My Attempts
        </button>
        <button
          className={libraryTab === "saved" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("saved")}
        >
          Saved Beta
        </button>
        <button
          className={libraryTab === "wanted" ? "active" : ""}
          type="button"
          onClick={() => setLibraryTab("wanted")}
        >
          Want to Try
        </button>
        <button className={libraryTab === "skeletons" ? "active" : ""} type="button" onClick={() => setLibraryTab("skeletons")}>My Skeletons</button>
      </div>
      {libraryTab === "skeletons" && computeContent}
      {libraryTab === "attempts" && (
        <section className="library-history gym-attempt-groups">
          {catalogGyms
            .filter((gym) =>
              [...myVideos.map((video) => video.route_id)].some(
                (routeId) =>
                  catalogRoutes.find((route) => route.id === routeId)?.gym ===
                  gym.name,
              ),
            )
            .map((gym) => {
              const gymRoutes = catalogRoutes.filter(
                (route) =>
                  route.gym === gym.name &&
                  [...myVideos.map((video) => video.route_id)].includes(
                    route.id,
                  ),
              )
              const gymVideoCount = gymRoutes.reduce(
                (count, route) =>
                  count +
                  myVideos.filter((video) => video.route_id === route.id)
                    .length,
                0,
              )
              return (
                <details className="attempt-gym-group" key={gym.name}>
                  <summary>
                    <span>{gym.name}</span>
                    <small>
                      {gymVideoCount} {gymVideoCount === 1 ? "video" : "videos"}
                    </small>
                  </summary>
                  {gymRoutes.map((route) => {
                    const videos = myVideos.filter(
                      (video) => video.route_id === route.id,
                    )
                    const presets: AttemptRecord[] = []
                    return (
                      <details className="attempt-route-group" key={route.id}>
                        <summary>
                          <span>
                            {route.name} <small>{route.grade}</small>
                          </span>
                          <small>
                            {videos.length + presets.length}{" "}
                            {videos.length + presets.length === 1
                              ? "attempt"
                              : "attempts"}
                          </small>
                        </summary>
                        {presets.map((video) => (
                          <button
                            className="history-row"
                            type="button"
                            key={video.id}
                            onClick={() => {
                              setSelectedRoute(route)
                              setSelectedGym(route.gym)
                              setActiveAttemptId(video.id)
                              setHasAttempt(true)
                              setWorkspaceEntry("attempt")
                              setWorkspaceSource(
                                video.title ?? `Attempt ${video.id.slice(1)}`,
                              )
                              go("workspace")
                            }}
                          >
                            <span className="history-thumbnail">
                              <VideoThumbnail
                                src={routeMedia(route.id).video}
                                alt={`${video.title ?? "Sample attempt"} first frame`}
                              />
                              <span>{video.duration}</span>
                            </span>
                            <span className="history-entry-info">
                              <strong>
                                {video.title ?? `Attempt ${video.id.slice(1)}`}
                              </strong>
                              <span className="history-date">{video.date}</span>
                              <span className="history-status">
                                Sample · {video.status}
                              </span>
                            </span>
                            <span
                              className="history-entry-arrow"
                              aria-hidden="true"
                            >
                              ›
                            </span>
                          </button>
                        ))}
                        {videos.map((video) => (
                          <button
                            className="history-row"
                            type="button"
                            key={video.id}
                            onClick={() => {
                              setSelectedRoute(route)
                              setSelectedGym(route.gym)
                              setActiveAttemptId(video.id)
                              setHasAttempt(true)
                              setWorkspaceEntry("attempt")
                              setWorkspaceSource(video.title)
                              go("workspace")
                            }}
                          >
                            <span className="history-thumbnail">
                              <VideoThumbnail
                                src={video.content_url}
                                alt={`${video.title} first frame`}
                              />
                              <span>
                                {Math.floor(video.duration_seconds / 60)}:
                                {String(
                                  Math.floor(video.duration_seconds % 60),
                                ).padStart(2, "0")}
                              </span>
                            </span>
                            <span className="history-entry-info">
                              <strong>{video.title}</strong>
                              <span className="history-date">
                                {new Date(
                                  video.created_at,
                                ).toLocaleDateString()}
                              </span>
                              <span className="history-status">
                                {video.visibility === "public"
                                  ? "Public"
                                  : "Private"}
                                {video.description
                                  ? ` · ${video.description}`
                                  : ""}
                              </span>
                            </span>
                            <span
                              className="history-entry-arrow"
                              aria-hidden="true"
                            >
                              ›
                            </span>
                          </button>
                        ))}
                      </details>
                    )
                  })}
                </details>
              )
            })}
          {myVideos.length === 0 && (
            <div className="library-empty">
              <strong>No attempts yet</strong>
              <p>Upload a video from a route to see it here.</p>
            </div>
          )}
        </section>
      )}
      {libraryTab !== "attempts" && (
        <div className="library-list">
          {libraryItems.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => {
                if (item.target === "route") {
                  openRoute(routes.find((route) => route.id === item.id))
                } else if (item.target === "video") {
                  const video = myVideos.find((entry) => entry.id === item.id)
                  const route =
                    catalogRoutes.find((entry) => entry.id === item.routeId) ??
                    catalogRoutes[0]
                  if (video && route) {
                    setSelectedRoute(route)
                    setSelectedGym(route.gym)
                    setActiveAttemptId(video.id)
                    setHasAttempt(true)
                    setWorkspaceEntry("attempt")
                    setWorkspaceSource(video.title)
                    go("workspace")
                  }
                } else if (item.target === "saved") {
                  // B2.7: a saved Community video opens in the workspace like a route Beta;
                  // a saved bundled sample opens where it lives (Community viewer or Beta page).
                  const video = savedVideos.find((entry) => entry.id === item.id)
                  if (video?.is_preset_sample) {
                    openSavedSample(video)
                    return
                  }
                  const route =
                    catalogRoutes.find((entry) => entry.id === item.routeId) ??
                    routes.find((entry) => entry.id === item.routeId)
                  if (video && route) {
                    setSelectedRoute(route)
                    setSelectedGym(route.gym)
                    setActiveAttemptId(video.id)
                    setHasAttempt(true)
                    setWorkspaceEntry("attempt")
                    setWorkspaceSource(video.title)
                    go("workspace")
                  }
                }
              }}
            >
              {item.target === "saved" ? (
                <VideoThumbnail src={item.contentUrl} alt={`${item.label} first frame`} />
              ) : (
                <MediaImage
                  routeId={
                    item.target === "route"
                      ? item.id
                      : (routes.find((route) => route.name === item.label)?.id ??
                        "r1")
                  }
                  wall={item.target === "route"}
                />
              )}
              <span>
                <b>{routeLabel(item.label)}</b>
                <small>{item.meta}</small>
              </span>
              <span>→</span>
            </button>
          ))}
          {libraryItems.length === 0 && (
            <div className="library-empty">
              <span className="library-empty-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  {libraryTab === "saved" ? (
                    <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
                  ) : (
                    <>
                      <path d="m3 20 7-15 4 8 2-4 5 11H3Z" />
                      <path d="m7 11 3 2 2-2" />
                    </>
                  )}
                </svg>
              </span>
              <strong>
                {libraryTab === "saved"
                  ? "Keep a beta for later"
                  : "Find your next climb"}
              </strong>
              <p>
                {libraryTab === "saved"
                  ? "Save a community video to revisit it here."
                  : "Mark a route you’d like to try. It’ll be waiting here."}
              </p>
              <AppButton
                variant="outline"
                onClick={() =>
                  go(libraryTab === "saved" ? "community" : "gyms")
                }
              >
                Browse {libraryTab === "saved" ? "community" : "routes"}
              </AppButton>
            </div>
          )}
        </div>
      )}
    </main>
  )
}
