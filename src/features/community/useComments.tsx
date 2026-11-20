import type { Session } from "../../api"
import { CommentSection } from "./CommentSection"

type Options = {
  session: Session | null
  /** The session is gone (401): return to sign-in. */
  onExpired: () => void
  /** Keeps feed counters in step after posting or deleting. */
  onCountChange: (videoId: string, total: number) => void
}

/**
 * Persistent comments (B2.4). Pages keep calling renderComments(source) with
 * "attempt:<video id>" or "beta:<preset id>"; uploaded videos get real,
 * shared comments and bundled presets show a notice instead.
 */
export function useComments({ session, onExpired, onCountChange }: Options) {
  const renderComments = (source: string) => {
    const videoId = source.slice(source.indexOf(":") + 1)
    return <CommentSection key={videoId} videoId={videoId} session={session} onSignIn={onExpired} onCountChange={onCountChange} />
  }
  return { renderComments }
}
