import { EditVideoForm } from "../../features/videos/EditVideoForm"
import { ResultInsights } from "../../compute/ResultInsights"

import { UploadAnalysis } from "../../compute/UploadAnalysis"

import { similarClimbers, betaCards, AppButton, signedDifference, MediaImage, MediaVideo, VideoThumbnail, PlaybackButton } from "../shared"
import type { AppController } from "../useAppController"

type Props = AppController["pages"]["workspaceScreen"]

export function WorkspacePage({
  selectedGym,
  selectedRoute,
  hasAttempt,
  isOwnUploadedVideo,
  setManageMode,
  manageMode,
  isPresetSample,
  activeAttempt,
  workspaceSource,
  jobs,
  activeAttemptId,
  workspaceEntry,
  communityBetaVideo,
  changeVideo,
  activeVideo,
  myVideos,
  deleteActiveVideo,
  session,
  setSourceResultTask,
  analysisPendingVideoId,
  setJobs,
  setComputeVideo,
  uploadState,
  cueTime,
  jumpToCueTime,
  selectedBeta,
  setUploadState,
  uploadInputRef,
  chooseUpload,
  back,
  selectedUploadUrl,
  selectedUpload,
  uploadError,
  generationMessage,
  uploadTitle,
  setUploadTitle,
  uploadDescription,
  setUploadDescription,
  uploadPrivacy,
  setUploadPrivacy,
  setShareAsBeta,
  shareAsBeta,
  saveUploadedAttempt,
  uploadProgress,
  uploadController,
  showOthersBeta,
  setBetaVisible,
  setSuggestionsVisible,
  setActiveTerm,
  sourceResultTask,
  routeBetaVideos,
  setAttemptRecords,
  setActiveAttemptId,
  setHasAttempt,
  setWorkspaceEntry,
  setWorkspaceSource,
  profile,
  setWorkspaceBetaId,
  setBetaOrigin,
  go,
  renderComments,
}: Props) {
  return (
    <main className="screen with-header workspace workspace-flow">
      <header className="workspace-video-header">
        <div className="workspace-title-row">
          <h1>
            {selectedGym}{" "}
            <span className="workspace-title-grade">{selectedRoute.grade}</span>
          </h1>
          {hasAttempt && isOwnUploadedVideo && (
            <button
              type="button"
              className="workspace-more"
              aria-label="Manage my video"
              onClick={() => setManageMode(manageMode ? null : "menu")}
            >
              ⋯
            </button>
          )}
        </div>
        <div className="workspace-info-line">
          {hasAttempt && (
            <p className="workspace-attempt-date">
              {isOwnUploadedVideo
                ? "My attempt"
                : isPresetSample
                  ? "Preset sample"
                  : "Community video"}{" "}
              <span aria-hidden="true">·</span>{" "}
              {activeAttempt?.date ?? workspaceSource.split(" · ")[0]}
            </p>
          )}
          {hasAttempt && activeAttempt && (
            <span className="video-status-inline" role="status">
              <span>
                {isPresetSample
                  ? "Public · Preset sample"
                  : activeAttempt.status.split(" · ")[0]}
              </span>
              {(!jobs[activeAttemptId] ||
                jobs[activeAttemptId] === "Ready") && (
                <>
                  <span className="status-divider" aria-hidden="true">
                    ·
                  </span>
                  <span className="video-ready">
                    <i aria-hidden="true" />
                    Video saved
                  </span>
                </>
              )}
            </span>
          )}
        </div>
      </header>
      {hasAttempt && isPresetSample && (
        <p className="sample-video-note">
          This is a preset sample. Upload your own video to edit its details or
          share it with the community.
        </p>
      )}
      {hasAttempt && activeVideo && (
        <section className="workspace-video-details" aria-label="Video details">
          <h2>{activeVideo.title}</h2>
          {activeVideo.description && <p>{activeVideo.description}</p>}
        </section>
      )}

      {hasAttempt && activeAttempt && (
        <>
          {isOwnUploadedVideo && manageMode && (
            <section className="video-management">
              {manageMode === "menu" && (
                <>
                  <button
                    className="btn btn-outline"
                    onClick={() => setManageMode("edit")}
                  >
                    Edit video
                  </button>
                  <button
                    className="btn btn-outline"
                    onClick={() => setManageMode("delete")}
                  >
                    Delete video
                  </button>
                </>
              )}
              {manageMode === "edit" && activeVideo && (
                <EditVideoForm key={activeVideo.id} video={activeVideo} save={changeVideo} close={() => setManageMode(null)} />
              )}
              {manageMode === "delete" && (
                <>
                  <strong>Delete this video?</strong>
                  <p>
                    This removes this attempt and its comments. Other attempts
                    remain.
                  </p>
                  <button
                    className="btn btn-outline"
                    onClick={() => setManageMode(null)}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-solid"
                    onClick={() => void deleteActiveVideo()}
                  >
                    Delete video
                  </button>
                </>
              )}
            </section>
          )}
          {isOwnUploadedVideo && activeVideo && session && (
            <UploadAnalysis
              key={`${session.user.id}:${activeVideo.id}`}
              video={activeVideo}
              session={session}
              onTask={setSourceResultTask}
              submissionPending={analysisPendingVideoId === activeVideo.id}
              onStatus={(label) =>
                setJobs((old) =>
                  old[activeVideo.id] === label
                    ? old
                    : { ...old, [activeVideo.id]: label },
                )
              }
            />
          )}
        </>
      )}
      {activeVideo && (
        <button
          className="btn btn-outline"
          onClick={() => setComputeVideo(activeVideo)}
        >
          Generate my skeleton
        </button>
      )}
      <section className="workspace-section video-section">
        {workspaceEntry === "upload" &&
          !hasAttempt &&
          uploadState !== "loading" && (
            <div className="section-heading">
              <h2>Add my video</h2>
            </div>
          )}
        {!(workspaceEntry === "upload" && !hasAttempt) && (
          <>
            <div className="video-frame">
              <MediaVideo
                routeId={selectedRoute.id}
                sourceUrl={activeAttempt?.contentUrl}
                seekTime={cueTime}
              />
            </div>
            <div className="player-controls">
              <PlaybackButton />
              <input
                aria-label="Video timeline"
                type="range"
                min="0"
                max="18"
                value={cueTime}
                onChange={(event) => jumpToCueTime(Number(event.target.value))}
              />
              <span>
                00:{String(Math.floor(cueTime)).padStart(2, "0")} / 00:18
              </span>
            </div>
          </>
        )}

        {workspaceEntry === "community" && (
          <div className="inline-action">
            <span>Viewing {selectedBeta.name} on this route.</span>
            <AppButton
              variant="outline"
              onClick={() => setUploadState("empty")}
            >
              Add my video
            </AppButton>
          </div>
        )}

        {uploadState !== "hidden" && uploadState !== "saved" && (
          <div className="inline-upload">
            {uploadState === "empty" && (
              <>
                <p className="upload-intro">
                  Choose a climbing video to review.
                </p>
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept="video/mp4,video/quicktime,.mp4,.mov"
                  hidden
                  onChange={(event) => chooseUpload(event.target.files?.[0])}
                />
                <AppButton onClick={() => uploadInputRef.current?.click()}>
                  Upload from device
                </AppButton>
                <AppButton
                  variant="text"
                  onClick={() => {
                    if (workspaceEntry === "upload" && !hasAttempt) back()
                    else setUploadState("hidden")
                  }}
                >
                  Cancel
                </AppButton>
              </>
            )}
            {uploadState === "preview" && (
              <>
                {selectedUploadUrl && (
                  <video
                    className="real-media-video"
                    src={selectedUploadUrl}
                    controls
                    playsInline
                  />
                )}
                {selectedUpload && (
                  <p>
                    {selectedUpload.name} ·{" "}
                    {(selectedUpload.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                )}
                {uploadError && (
                  <p role="alert">
                    {generationMessage ||
                      "Upload failed. Your selection is preserved. Try again."}
                  </p>
                )}
                <label className="field">
                  <span>Title</span>
                  <input
                    maxLength={120}
                    value={uploadTitle}
                    onChange={(event) => setUploadTitle(event.target.value)}
                    placeholder={
                      selectedUpload?.name.replace(/\.[^.]+$/, "") ||
                      "My climbing attempt"
                    }
                  />
                </label>
                <label className="field">
                  <span>Description (optional)</span>
                  <textarea
                    maxLength={500}
                    rows={3}
                    value={uploadDescription}
                    onChange={(event) =>
                      setUploadDescription(event.target.value)
                    }
                    placeholder="Add a note about this attempt"
                  />
                </label>
                <fieldset className="upload-privacy">
                  <legend>Visibility</legend>
                  <div className="privacy-options">
                    {(["Private", "Public"] as const).map((option) => (
                      <label
                        key={option}
                        className={uploadPrivacy === option ? "selected" : ""}
                      >
                        <input
                          type="radio"
                          name="video-privacy"
                          value={option}
                          checked={uploadPrivacy === option}
                          onChange={() => {
                            setUploadPrivacy(option)
                            if (option === "Private") setShareAsBeta(false)
                          }}
                        />
                        <span>{option}</span>
                      </label>
                    ))}
                  </div>
                  {uploadPrivacy && (
                    <p>
                      {uploadPrivacy === "Public"
                        ? "Shared with the community."
                        : "Only you can view it."}
                    </p>
                  )}
                  {uploadPrivacy === "Public" && (
                    <label className="share-beta-choice">
                      <input
                        type="checkbox"
                        checked={shareAsBeta}
                        onChange={(event) =>
                          setShareAsBeta(event.target.checked)
                        }
                      />
                      <span>
                        <strong>Share as beta</strong>
                        <small>
                          Also show this video in Community Beta for{" "}
                          {selectedGym} · {selectedRoute.grade}, and share your
                          height and wingspan for comparison.
                        </small>
                      </span>
                    </label>
                  )}
                </fieldset>
                <div className="inline-buttons">
                  <AppButton
                    variant="outline"
                    onClick={() => setUploadState("empty")}
                  >
                    Cancel
                  </AppButton>
                  <button
                    className="btn btn-solid"
                    type="button"
                    disabled={!uploadPrivacy || !selectedUpload}
                    onClick={saveUploadedAttempt}
                  >
                    {uploadError ? "Retry upload" : "Upload video"}
                  </button>
                </div>
                <p className="muted small">
                  MP4 or MOV · up to 90 seconds · 200 MB maximum. Stored on this
                  BetaLab server.
                </p>
              </>
            )}
            {uploadState === "loading" && (
              <p>
                <strong>
                  {uploadProgress < 100
                    ? `Uploading ${uploadProgress}%`
                    : "Checking video…"}
                </strong>{" "}
                {uploadProgress < 100
                  ? "Keep this browser tab open until transfer finishes."
                  : "Transfer complete. The server is verifying and saving your video."}{" "}
                <button
                  type="button"
                  onClick={() => uploadController.current?.abort()}
                >
                  Cancel upload
                </button>
              </p>
            )}
          </div>
        )}
      </section>

      {(hasAttempt || workspaceEntry !== "upload") && (
        <section className="workspace-section analysis-tools">
          <div
            className="workspace-mode-tabs"
            role="tablist"
            aria-label="Video tools"
          >
            <button
              type="button"
              role="tab"
              id="suggestions-tab"
              aria-controls="suggestions-panel"
              aria-selected={!showOthersBeta}
              disabled={!isOwnUploadedVideo || !hasAttempt}
              onClick={() => {
                setBetaVisible(false)
                setSuggestionsVisible(true)
              }}
            >
              Results & diagnostics
            </button>
            <button
              type="button"
              role="tab"
              id="others-tab"
              aria-controls="others-panel"
              aria-selected={showOthersBeta}
              onClick={() => {
                setBetaVisible(true)
                setSuggestionsVisible(false)
                setActiveTerm(null)
              }}
            >
              Community Beta
            </button>
          </div>
          {!showOthersBeta && isOwnUploadedVideo && hasAttempt && (
            <div
              className="suggestion-text compact-suggestions"
              id="suggestions-panel"
              role="tabpanel"
              aria-labelledby="suggestions-tab"
            >
              <ResultInsights
                csrf={session?.csrf_token}
                key={activeAttemptId}
                task={
                  sourceResultTask?.source_video_id === activeAttemptId
                    ? sourceResultTask
                    : null
                }
              />
            </div>
          )}
          {showOthersBeta && (
            <div
              className="beta-list-simple"
              id="others-panel"
              role="tabpanel"
              aria-labelledby="others-tab"
            >
              {routeBetaVideos.map((video) => (
                <button
                  className="beta-video-card"
                  type="button"
                  key={video.id}
                  onClick={() => {
                    setAttemptRecords((items) => [
                      {
                        id: video.id,
                        routeId: video.route_id,
                        date: new Date(video.created_at).toLocaleDateString(),
                        duration: `${Math.floor(video.duration_seconds / 60)}:${String(Math.floor(video.duration_seconds % 60)).padStart(2, "0")}`,
                        status: "Public",
                        contentUrl: video.content_url,
                        title: video.title,
                      },
                      ...items.filter((item) => item.id !== video.id),
                    ])
                    setActiveAttemptId(video.id)
                    setHasAttempt(true)
                    setWorkspaceEntry("attempt")
                    setWorkspaceSource(video.title)
                    setBetaVisible(false)
                    setSuggestionsVisible(false)
                  }}
                >
                  <span className="beta-card-thumbnail">
                    <VideoThumbnail
                      src={video.content_url}
                      alt={`${video.title} first frame`}
                    />
                    <span className="beta-card-duration">
                      {Math.floor(video.duration_seconds / 60)}:
                      {String(Math.floor(video.duration_seconds % 60)).padStart(
                        2,
                        "0",
                      )}
                    </span>
                  </span>
                  <span className="beta-card-details">
                    <b>{video.title}</b>
                    <span className="beta-card-measurements">
                      By {video.display_name || video.username}
                    </span>
                    <span className="beta-card-measurements">
                      <span>
                        Height{" "}
                        <strong>
                          {video.height_cm == null
                            ? "Not provided"
                            : `${Math.round(video.height_cm)} cm`}
                        </strong>
                      </span>
                      <span>
                        Wingspan{" "}
                        <strong>
                          {video.arm_span_cm == null
                            ? "Not provided"
                            : `${Math.round(video.arm_span_cm)} cm`}
                        </strong>
                      </span>
                    </span>
                    {(profile.height || profile.wingspan) && (
                      <small className="beta-card-difference">
                        {[
                          video.height_cm != null && profile.height
                            ? `Height ${signedDifference(Math.round(video.height_cm - Number(profile.height)))} cm`
                            : null,
                          video.arm_span_cm != null && profile.wingspan
                            ? `Wingspan ${signedDifference(Math.round(video.arm_span_cm - Number(profile.wingspan)))} cm`
                            : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "Add your measurements to compare"}
                      </small>
                    )}
                    <span className="beta-card-open">View beta ↗</span>
                  </span>
                </button>
              ))}
              {[...similarClimbers]
                .filter((climber) =>
                  betaCards.some(
                    (card) =>
                      card.id === climber.id &&
                      card.route === selectedRoute.name &&
                      card.gym === selectedGym,
                  ),
                )
                .sort((a, b) =>
                  profile.height && profile.wingspan
                    ? Math.abs(a.height - Number(profile.height)) +
                      Math.abs(a.wingspan - Number(profile.wingspan)) -
                      (Math.abs(b.height - Number(profile.height)) +
                        Math.abs(b.wingspan - Number(profile.wingspan)))
                    : 0,
                )
                .map((climber) => (
                  <button
                    className="beta-video-card"
                    type="button"
                    key={climber.id}
                    onClick={() => {
                      setWorkspaceBetaId(climber.id)
                      setBetaOrigin("workspace")
                      go("beta")
                    }}
                  >
                    <span className="beta-card-thumbnail">
                      <MediaImage routeId={selectedRoute.id} />
                      <span className="beta-card-duration">{climber.time}</span>
                    </span>
                    <span className="beta-card-details">
                      <b>{climber.name}</b>
                      <span className="beta-card-measurements">
                        <span>
                          Height <strong>{climber.height} cm</strong>
                        </span>
                        <span>
                          Arm span <strong>{climber.wingspan} cm</strong>
                        </span>
                      </span>
                      {profile.height && profile.wingspan && (
                        <small className="beta-card-difference">
                          Height{" "}
                          {signedDifference(
                            climber.height - Number(profile.height),
                          )}{" "}
                          cm · Arm span{" "}
                          {signedDifference(
                            climber.wingspan - Number(profile.wingspan),
                          )}{" "}
                          cm
                        </small>
                      )}
                      <span className="beta-card-open">
                        View beta <span aria-hidden="true">↗</span>
                      </span>
                    </span>
                  </button>
                ))}
            </div>
          )}
        </section>
      )}
      {hasAttempt &&
        activeAttempt?.status.startsWith("Public") &&
        renderComments(`attempt:${activeAttemptId}`)}
    </main>
  )
}
