import { AppButton, MediaVideo, PlaybackButton } from "../shared"
import type { AppController } from "../useAppController"
import { socialVideoKey } from "../../features/community/social"

type Props = AppController["pages"]["betaDetailScreen"]

export function BetaPage({
  selectedBeta,
  betaOrigin,
  social,
  workspaceBetaId,
  toggleSocial,
  selectedGym,
  selectedRoute,
  setComputeVideo,
  renderComments,
}: Props) {
  const socialId = socialVideoKey(workspaceBetaId)
  return (
    <main className="screen with-header beta-detail-page">
      <header className="beta-video-info">
        <div className="beta-author-line">
          <h1>{selectedBeta.name}</h1>
          <span>Original climber</span>
          {betaOrigin === "community" && (
            <div className="beta-icon-actions">
              <button
                type="button"
                aria-label="Like video"
                title={
                  social[socialId]?.liked
                    ? "Unlike video"
                    : "Like video"
                }
                aria-pressed={!!social[socialId]?.liked}
                onClick={() => void toggleSocial(socialId, "liked")}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
                </svg>
              </button>
              <button
                type="button"
                aria-label="Save beta"
                title={
                  social[socialId]?.saved
                    ? "Remove saved beta"
                    : "Save beta"
                }
                aria-pressed={!!social[socialId]?.saved}
                onClick={() => void toggleSocial(socialId, "saved")}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" />
                </svg>
              </button>
            </div>
          )}
        </div>
        <p className="beta-route-line">
          {selectedGym} <span>{selectedRoute.grade}</span>
        </p>
        <p className="beta-climber-measurements">
          Original climber: {selectedBeta.height} cm height ·{" "}
          {selectedBeta.wingspan} cm arm span
        </p>
      </header>

      <section className="beta-detail-video">
        <div className="video-frame">
          <MediaVideo routeId={selectedRoute.id} />
        </div>
        <div className="player-controls">
          <PlaybackButton />
          <input
            aria-label="Community beta timeline"
            type="range"
            min="0"
            max="18"
            defaultValue="6"
          />
          <span>00:06 / {selectedBeta.time}</span>
        </div>
        <AppButton
          className="generate-entry"
          onClick={() => {
            setComputeVideo({
              id: workspaceBetaId,
              title: selectedBeta.name,
              is_preset_beta: true,
            })
          }}
        >
          Skeleton Preview
        </AppButton>
      </section>
      {renderComments(`beta:${workspaceBetaId}`)}
    </main>
  )
}
