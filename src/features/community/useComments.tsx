import type { Session } from "../../api"
import { CommentSection } from "./CommentSection"
import { socialVideoKey } from "./social"

type Options = {
  session: Session | null
  /** The session is gone (401): return to sign-in. */
  onExpired: () => void
  /** Keeps feed counters in step after posting or deleting. */
  onCountChange: (videoId: string, total: number) => void
}

/**
 * Persistent comments (B2.4). Pages keep calling renderComments(source) with
 * "attempt:<video id>" or "beta:<preset id>". Uploads and bundled samples
 * ("a1" → "sample-a1", "b1" → "preset-beta-b1") all get shared comments.
 */
export function useComments({ session, onExpired, onCountChange }: Options) {
  const renderComments = (source: string) => {
    const videoId = socialVideoKey(source.slice(source.indexOf(":") + 1))
    return <CommentSection key={videoId} videoId={videoId} session={session} onSignIn={onExpired} onCountChange={onCountChange} />
  }
  return { renderComments }
}
