import { useState, type Dispatch, type SetStateAction } from "react"
import type { Screen } from "../../app/shared"

type Options = {
  signedIn: boolean
  profile: { name: string }
  go: (screen: Screen) => void
  setAccountMode: Dispatch<SetStateAction<"signin" | "signup">>
}

export function useComments({
  signedIn,
  profile,
  go,
  setAccountMode,
}: Options) {
  const [expandedComposer, setExpandedComposer] = useState<string | null>(null)
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({})
  const [comments, setComments] = useState<{
    id: string
    source: string
    text: string
    author: string
    parentId?: string
    liked?: boolean
  }[]>([])
  const [replyTargets, setReplyTargets] =
    useState<Record<string, string | null>>({})
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({})
  const [expandedReplies, setExpandedReplies] = useState<string[]>([])

  const renderCommentItem = (c: typeof comments[number], isReply = false) => {
    const replies = comments.filter(
      (item) => item.source === c.source && item.parentId === c.id,
    )
    return (
      <article
        className={`comment-item${isReply ? " comment-reply" : ""}`}
        key={c.id}
      >
        <span className="comment-avatar" aria-hidden="true">
          {c.author.slice(0, 1).toUpperCase()}
        </span>
        <div className="comment-content">
          <div className="comment-byline">
            <strong>{c.author}</strong>
            <span>Just now</span>
          </div>
          <p>{c.text}</p>
          <div className="comment-actions">
            <button
              type="button"
              aria-pressed={!!c.liked}
              className={c.liked ? "is-liked" : ""}
              onClick={() => {
                if (!signedIn) {
                  setAccountMode("signin")
                  go("account")
                  return
                }
                setComments((items) =>
                  items.map((item) =>
                    item.id === c.id ? { ...item, liked: !item.liked } : item,
                  ),
                )
              }}
            >
              <span aria-hidden="true">{c.liked ? "♥" : "♡"}</span>{" "}
              {c.liked ? "Liked · 1" : "Like"}
            </button>
            <button
              type="button"
              onClick={() =>
                setReplyTargets((targets) => ({ ...targets, [c.source]: c.id }))
              }
            >
              Reply
            </button>
            <button
              type="button"
              aria-label="Delete my comment"
              onClick={() => {
                setComments((items) =>
                  items.filter(
                    (item) => item.id !== c.id && item.parentId !== c.id,
                  ),
                )
                setReplyTargets((targets) => ({ ...targets, [c.source]: null }))
              }}
            >
              Delete
            </button>
          </div>
          {replyTargets[c.source] === c.id && (
            <div className="inline-reply-composer">
              <label htmlFor={`reply-${c.id}`}>Replying to {c.author}</label>
              <div className="comment-input-wrap">
                <textarea
                  id={`reply-${c.id}`}
                  aria-label={`Reply to ${c.author}`}
                  placeholder="Write a reply…"
                  maxLength={500}
                  value={replyDrafts[c.id] ?? ""}
                  onChange={(e) =>
                    setReplyDrafts((d) => ({ ...d, [c.id]: e.target.value }))
                  }
                />
                <div className="reply-compose-actions">
                  <button
                    type="button"
                    className="comment-delete"
                    onClick={() =>
                      setReplyTargets((targets) => ({
                        ...targets,
                        [c.source]: null,
                      }))
                    }
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="comment-post"
                    disabled={signedIn && !(replyDrafts[c.id] ?? "").trim()}
                    onClick={() => {
                      if (!signedIn) {
                        setAccountMode("signin")
                        go("account")
                        return
                      }
                      const text = (replyDrafts[c.id] ?? "").trim()
                      if (!text) return
                      const rootId = c.parentId ?? c.id
                      setComments((items) => [
                        ...items,
                        {
                          id: crypto.randomUUID(),
                          source: c.source,
                          text: isReply ? `@${c.author} ${text}` : text,
                          author: profile.name || "You",
                          parentId: rootId,
                        },
                      ])
                      setReplyDrafts((d) => ({ ...d, [c.id]: "" }))
                      setReplyTargets((targets) => ({
                        ...targets,
                        [c.source]: null,
                      }))
                      setExpandedReplies((ids) =>
                        ids.includes(rootId) ? ids : [...ids, rootId],
                      )
                    }}
                  >
                    {signedIn ? "Post reply" : "Sign in to reply"}
                  </button>
                </div>
              </div>
            </div>
          )}
          {!isReply && replies.length > 0 && (
            <>
              <button
                type="button"
                className="replies-toggle"
                aria-expanded={expandedReplies.includes(c.id)}
                onClick={() =>
                  setExpandedReplies((ids) =>
                    ids.includes(c.id)
                      ? ids.filter((id) => id !== c.id)
                      : [...ids, c.id],
                  )
                }
              >
                {expandedReplies.includes(c.id)
                  ? "Hide replies"
                  : `View ${replies.length} ${
                      replies.length === 1 ? "reply" : "replies"
                    }`}
              </button>
              {expandedReplies.includes(c.id) && (
                <div className="comment-replies">
                  {replies.map((reply) => renderCommentItem(reply, true))}
                </div>
              )}
            </>
          )}
        </div>
      </article>
    )
  }
  const renderComments = (source: string) => (
    <section className="comment-section" aria-label="Comments">
      <div className="comments-heading">
        <h2>Comments</h2>
        <span className="comment-count">
          {comments.filter((c) => c.source === source).length}
        </span>
      </div>
      {comments.filter((c) => c.source === source).length === 0 && (
        <div className="comments-empty">
          <strong>Start the conversation</strong>
          <p>Share a thought or ask about this beta.</p>
        </div>
      )}
      <div className="comment-list" aria-live="polite">
        {comments
          .filter((c) => c.source === source && !c.parentId)
          .map((c) => renderCommentItem(c))}
      </div>
      <div
        className={`comment-composer compact-composer${
          expandedComposer === source ? " is-expanded" : ""
        }`}
        onBlur={(e) => {
          if (
            !e.currentTarget.contains(e.relatedTarget as Node | null) &&
            !(commentDrafts[source] ?? "").trim()
          )
            setExpandedComposer(null)
        }}
      >
        <span className="comment-avatar" aria-hidden="true">
          {signedIn ? (profile.name || "You").slice(0, 1).toUpperCase() : "○"}
        </span>
        <div className="comment-input-wrap">
          <textarea
            rows={1}
            onFocus={() => setExpandedComposer(source)}
            aria-label="Write a comment"
            placeholder="Add a comment…"
            maxLength={500}
            value={commentDrafts[source] ?? ""}
            onChange={(e) =>
              setCommentDrafts((d) => ({ ...d, [source]: e.target.value }))
            }
          />
          <div className="comment-compose-footer">
            <span>
              {(commentDrafts[source] ?? "").length > 400
                ? `${(commentDrafts[source] ?? "").length}/500`
                : ""}
            </span>
            <button
              type="button"
              className="comment-post"
              disabled={signedIn && !(commentDrafts[source] ?? "").trim()}
              onClick={() => {
                if (!signedIn) {
                  setAccountMode("signin")
                  go("account")
                  return
                }
                const text = (commentDrafts[source] ?? "").trim()
                if (!text) return
                setComments((c) => [
                  ...c,
                  {
                    id: crypto.randomUUID(),
                    source,
                    text,
                    author: profile.name || "You",
                  },
                ])
                setCommentDrafts((d) => ({ ...d, [source]: "" }))
                setExpandedComposer(null)
              }}
            >
              {signedIn ? "Post" : "Sign in to post"}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
  return {
    renderComments,
    setComments,
    setCommentDrafts,
    setReplyDrafts,
    setReplyTargets,
    setExpandedReplies,
  }
}
