import { useEffect, useRef, useState } from "react"
import { ApiError, type Session, type UserVideo } from "../../api"
import { VideoThumbnail } from "../../components/Media"
import { socialApi, type PublicProfile } from "./social"

type Props = {
  userId: string | null
  session: Session | null
  /** Ids the signed-in user follows (shared with the Community viewer's Follow button). */
  following: string[]
  toggleFollow: (userId: string) => Promise<void>
  /** Opens one of this author's public videos in the Community viewer. */
  openVideo: (video: UserVideo) => void
  openMyLibrary: () => void
  onExpired: () => void
}

const PAGE = 20

/**
 * N2.8: another climber's page, reached by tapping an author or swiping right
 * on their Community video. Shows only what the server returns for anyone:
 * identity, follow counts and public videos. No management actions, saved
 * items, Want to Try, skeletons or notifications, even on your own page.
 */
export function AuthorPage({ userId, session, following, toggleFollow, openVideo, openMyLibrary, onExpired }: Props) {
  const [profile, setProfile] = useState<PublicProfile | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const request = useRef(0)

  const load = async (offset: number) => {
    if (!userId) return
    const run = ++request.current
    setLoading(true)
    setError("")
    try {
      const page = await socialApi.profile(userId, offset, PAGE)
      if (run !== request.current) return
      setProfile(current =>
        offset && current ? { ...page, videos: [...current.videos, ...page.videos.filter(v => !current.videos.some(c => c.id === v.id))] } : page)
    } catch (caught) {
      if (run !== request.current) return
      if (caught instanceof ApiError && caught.status === 401) { onExpired(); return }
      setError(caught instanceof ApiError && caught.status === 404 ? "This climber's page isn't available." : (caught as Error).message)
    } finally {
      if (run === request.current) setLoading(false)
    }
  }

  useEffect(() => {
    setProfile(null)
    void load(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, session?.user.id])

  if (!userId) return <main className="screen with-header author-page"><p className="comments-status">No climber selected.</p></main>
  if (!profile) {
    return (
      <main className="screen with-header author-page">
        {error
          ? <div className="comments-error" role="alert"><p>{error}</p><button type="button" className="comment-post" onClick={() => void load(0)}>Try again</button></div>
          : <p className="comments-status" role="status">Loading climber…</p>}
      </main>
    )
  }

  const name = profile.display_name || profile.username
  const isFollowing = following.includes(profile.id)
  // The server count was read with the follow state at load time; keep it in step with toggles since.
  const followers = Math.max(0, profile.follower_count + (isFollowing === profile.following ? 0 : isFollowing ? 1 : -1))
  return (
    <main className="screen with-header author-page">
      <section className="author-hero" aria-label={`${name}'s profile`}>
        <span className="author-avatar" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
        <div className="author-identity">
          <h1>{name}</h1>
          <small>@{profile.username}</small>
        </div>
        <dl className="author-stats">
          <div><dt>Videos</dt><dd>{profile.public_video_count}</dd></div>
          <div><dt>Followers</dt><dd>{followers}</dd></div>
          <div><dt>Following</dt><dd>{profile.following_count}</dd></div>
        </dl>
        {profile.is_me ? (
          <div className="author-self-note">
            <p>This is how other climbers see your page.</p>
            <button type="button" className="comment-post" onClick={openMyLibrary}>Open My Page</button>
          </div>
        ) : (
          <button
            type="button"
            className={`author-follow${isFollowing ? " is-following" : ""}`}
            aria-pressed={isFollowing}
            onClick={() => void toggleFollow(profile.id)}
          >
            {isFollowing ? "Following" : "Follow"}
          </button>
        )}
      </section>
      <section className="author-videos" aria-label="Public videos">
        <h2>{profile.account_visibility === 'private' ? 'Private account' : 'Public videos'}</h2>
        {profile.videos.length === 0 ? (
          <div className="comments-empty"><strong>{profile.account_visibility === 'private' ? 'This account is private' : 'No videos shared on this profile'}</strong><p>{profile.account_visibility === 'private' ? 'This climber’s full profile is hidden.' : 'Only videos shared on this profile appear here.'}</p></div>
        ) : (
          <ul className="author-video-grid">
            {profile.videos.map(video => (
              <li key={video.id}>
                <button type="button" onClick={() => openVideo(video)} aria-label={`Play ${video.title}`}>
                  <VideoThumbnail src={video.content_url} alt={`${video.title} first frame`} />
                  <span>{video.title}</span>
                  {video.share_as_beta && <small>Community Beta</small>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <div className="comments-error" role="alert"><p>{error}</p><button type="button" className="comment-post" onClick={() => void load(profile.videos.length)}>Try again</button></div>}
        {profile.videos.length < profile.public_video_count && !error && (
          <button type="button" className="replies-toggle comments-more" disabled={loading} onClick={() => void load(profile.videos.length)}>
            {loading ? "Loading…" : "Load more videos"}
          </button>
        )}
        <p className="author-privacy-note">Profile sections follow the climber’s privacy settings. Private videos are never shown here.</p>
      </section>
    </main>
  )
}
