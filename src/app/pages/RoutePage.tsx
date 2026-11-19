import movementRoutes from "../../data/movementRoutes.json"

import { MediaImage, VideoThumbnail } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["routeScreen"]

export function RoutePage({
  selectedGym,
  selectedRoute,
  openWorkspace,
  routeAttempts,
}: Props) {
  return (
    <main className="screen with-header route-detail-page">
      <div className="route-detail-heading">
        <h1>{selectedGym}</h1>
        <span>{selectedRoute.grade}</span>
      </div>
      {selectedRoute.archived && (
        <p className="archive-label">Archived — available for past attempts</p>
      )}
      <h2 className="route-photo-title">{selectedRoute.name}</h2>
      <MediaImage routeId={selectedRoute.id} wall className="route-image" />
      {movementRoutes.find((route) => route.id === selectedRoute.id)
        ?.reviewNote && (
        <p className="route-photo-note">
          Highlighted holds are awaiting route confirmation.
        </p>
      )}
      <button
        className="add-attempt-card"
        type="button"
        onClick={() =>
          openWorkspace(`New attempt — ${selectedRoute.name}`, "upload")
        }
      >
        <span className="add-video-symbol" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </span>
        <strong>Add my video</strong>
      </button>
      <div className="section-heading previous-attempts-heading">
        <h2>Previous attempts</h2>
        <span>{routeAttempts.length}</span>
      </div>
      <div className="attempt-history">
        {routeAttempts.map((attempt) => (
          <button
            type="button"
            key={attempt.id}
            onClick={() =>
              openWorkspace(
                `${attempt.date} · ${selectedRoute.name}`,
                "attempt",
                attempt.id,
              )
            }
          >
            <span className="attempt-cover">
              <VideoThumbnail
                src={attempt.sourceUrl}
                alt={`${attempt.title} first frame`}
              />
              <span className="attempt-play" aria-hidden="true">
                <svg viewBox="0 0 16 16">
                  <path d="m5 3 7 5-7 5Z" />
                </svg>
              </span>
            </span>
            <span>
              <b>{attempt.title}</b>
              <small>
                {attempt.date} · {attempt.duration}
              </small>
              <small>{attempt.status}</small>
            </span>
          </button>
        ))}
        {routeAttempts.length === 0 && (
          <div className="empty-state">
            <strong>No attempts yet</strong>
            <p>Add a video when you are ready.</p>
          </div>
        )}
      </div>
    </main>
  )
}
