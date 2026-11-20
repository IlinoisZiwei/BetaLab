import { useEffect, useRef, useState } from "react"
import { ApiError, type Session } from "../../api"
import { announceDanmaku, COMMENT_MAX, formatCommentTime, formatVideoTime, isUserVideoId, socialApi, type CommentItem } from "./social"

type Props = {
  videoId: string
  session: Session | null
  /** Called when the user must sign in (not signed in, or the session expired). */
  onSignIn: () => void
  /** Keeps counters elsewhere (feed badges) in step; counts replies too. */
  onCountChange?: (videoId: string, total: number) => void
  /** Current playback second of this video; new top-level comments are pinned there (danmaku). */
  getCurrentTime?: () => number | undefined
  /** Jump the video to a comment's timestamp. Timestamps are plain text when omitted. */
  onSeek?: (seconds: number) => void
}

type Thread = { items: CommentItem[]; total: number; open: boolean; loading: boolean; error: string }

const PAGE = 20
const REPLY_PAGE = 10
const name = (author: { display_name: string; username: string }) => author.display_name || author.username

/**
 * TikTok-style comments for an uploaded video: comment likes, one level of
 * replies (replying to a reply @-mentions its author) and timestamps that
 * jump the video. Bundled samples show a notice instead.
 */
export function CommentSection({ videoId, session, onSignIn, onCountChange, getCurrentTime, onSeek }: Props) {
  const [items, setItems] = useState<CommentItem[]>([])
  const [total, setTotal] = useState(0)
  const [allTotal, setAllTotal] = useState(0)
  const [threads, setThreads] = useState<Record<string, Thread>>({})
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState("")
  const [draft, setDraft] = useState("")
  const [replyTarget, setReplyTarget] = useState<CommentItem | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [posting, setPosting] = useState(false)
  const [actionError, setActionError] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const request = useRef(0)
  const input = useRef<HTMLTextAreaElement>(null)
  const userId = session?.user.id ?? null
  const interactive = isUserVideoId(videoId)

  const handleError = (error: unknown, fallback: (message: string) => void) => {
    if (error instanceof ApiError && error.status === 401) return onSignIn()
    fallback((error as Error).message)
  }
  const setCounts = (top: number, all: number) => {
    setTotal(top); setAllTotal(all); onCountChange?.(videoId, all)
  }

  const load = async (offset: number) => {
    const run = ++request.current
    setLoading(true); setLoadError("")
    try {
      const page = await socialApi.comments(videoId, offset, PAGE)
      if (run !== request.current) return
      setItems(current => (offset === 0 ? page.items : [...current, ...page.items.filter(c => !current.some(x => x.id === c.id))]))
      setCounts(page.total, page.total_with_replies ?? page.total)
    } catch (error) {
      if (run === request.current) handleError(error, setLoadError)
    } finally {
      if (run === request.current) setLoading(false)
    }
  }

  useEffect(() => {
    setItems([]); setTotal(0); setAllTotal(0); setThreads({}); setDraft(""); setReplyTarget(null)
    setExpanded(false); setActionError(""); setLoadError("")
    if (interactive && userId) void load(0)
    else request.current++
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, userId])

  const loadReplies = async (parent: CommentItem, offset: number) => {
    setThreads(t => ({ ...t, [parent.id]: { ...(t[parent.id] ?? { items: [], total: parent.reply_count }), open: true, loading: true, error: "" } }))
    try {
      const page = await socialApi.replies(parent.id, offset, REPLY_PAGE)
      setThreads(t => {
        const current = t[parent.id]?.items ?? []
        const merged = offset === 0 ? page.items : [...current, ...page.items.filter(r => !current.some(x => x.id === r.id))]
        return { ...t, [parent.id]: { items: merged, total: page.total, open: true, loading: false, error: "" } }
      })
    } catch (error) {
      handleError(error, message => setThreads(t => ({ ...t, [parent.id]: { ...(t[parent.id] ?? { items: [], total: parent.reply_count, open: true }), loading: false, error: message } })))
    }
  }

  const startReply = (comment: CommentItem) => {
    if (!session) return onSignIn()
    setReplyTarget(comment); setExpanded(true)
    requestAnimationFrame(() => input.current?.focus())
  }

  const post = async () => {
    if (!session) return onSignIn()
    const text = draft.trim()
    if (!text || posting) return
    setPosting(true); setActionError("")
    const now = replyTarget ? undefined : getCurrentTime?.()
    try {
      const comment = await socialApi.addComment(videoId, {
        body: text,
        parent_id: replyTarget?.id ?? null,
        time_s: now !== undefined && Number.isFinite(now) ? Math.round(now * 100) / 100 : null,
      }, session.csrf_token)
      if (comment.parent_id) {
        const rootId = comment.parent_id
        setItems(current => current.map(c => (c.id === rootId ? { ...c, reply_count: c.reply_count + 1 } : c)))
        setThreads(t => {
          const thread = t[rootId] ?? { items: [], total: 0, open: true, loading: false, error: "" }
          return { ...t, [rootId]: { ...thread, items: [...thread.items, comment], total: thread.total + 1, open: true } }
        })
        setCounts(total, allTotal + 1)
      } else {
        setItems(current => [...current, comment])
        setCounts(total + 1, allTotal + 1)
        if (comment.time_s !== null) announceDanmaku(videoId, { id: comment.id, body: comment.body, time_s: comment.time_s, author: name(comment.author), mine: true })
      }
      setDraft(""); setReplyTarget(null); setExpanded(false)
    } catch (error) {
      handleError(error, setActionError)
    } finally {
      setPosting(false)
    }
  }

  const patchComment = (id: string, patch: Partial<CommentItem>) => {
    setItems(current => current.map(c => (c.id === id ? { ...c, ...patch } : c)))
    setThreads(t => Object.fromEntries(Object.entries(t).map(([key, thread]) => [key, { ...thread, items: thread.items.map(c => (c.id === id ? { ...c, ...patch } : c)) }])))
  }

  const toggleLike = async (comment: CommentItem) => {
    if (!session) return onSignIn()
    if (busy === `like:${comment.id}`) return
    setBusy(`like:${comment.id}`)
    const next = !comment.liked
    patchComment(comment.id, { liked: next, like_count: Math.max(0, comment.like_count + (next ? 1 : -1)) })
    try {
      const result = await socialApi.setCommentLiked(comment.id, next, session.csrf_token)
      patchComment(comment.id, { liked: result.liked, like_count: result.like_count })
    } catch (error) {
      patchComment(comment.id, { liked: comment.liked, like_count: comment.like_count })
      handleError(error, setActionError)
    } finally {
      setBusy(null)
    }
  }

  const remove = async (comment: CommentItem) => {
    if (!session || busy) return
    setBusy(`delete:${comment.id}`); setActionError("")
    try {
      await socialApi.deleteComment(comment.id, session.csrf_token)
      if (comment.parent_id) {
        const rootId = comment.parent_id
        setItems(current => current.map(c => (c.id === rootId ? { ...c, reply_count: Math.max(0, c.reply_count - 1) } : c)))
        setThreads(t => t[rootId] ? { ...t, [rootId]: { ...t[rootId], items: t[rootId].items.filter(r => r.id !== comment.id), total: Math.max(0, t[rootId].total - 1) } } : t)
        setCounts(total, Math.max(0, allTotal - 1))
      } else {
        // Deleting a top-level comment removes its whole thread on the server.
        setItems(current => current.filter(c => c.id !== comment.id))
        setCounts(Math.max(0, total - 1), Math.max(0, allTotal - 1 - comment.reply_count))
        if (replyTarget && (replyTarget.id === comment.id || replyTarget.parent_id === comment.id)) setReplyTarget(null)
      }
    } catch (error) {
      handleError(error, setActionError)
    } finally {
      setBusy(null)
    }
  }

  const renderReplies = (parent: CommentItem) => {
    const thread = threads[parent.id]
    const count = thread?.total ?? parent.reply_count
    if (!count && !thread?.items.length) return null
    if (!thread?.open) return <button type="button" className="replies-toggle" onClick={() => void loadReplies(parent, 0)}>View {count} {count === 1 ? "reply" : "replies"}</button>
    return <>
      <div className="comment-replies">{thread.items.map(reply => renderComment(reply, true))}</div>
      {thread.error && <p className="comments-error-inline" role="alert">{thread.error}</p>}
      <div className="reply-controls">
        {thread.items.length < thread.total && <button type="button" className="replies-toggle" disabled={thread.loading} onClick={() => void loadReplies(parent, thread.items.length)}>{thread.loading ? "Loading…" : `View ${thread.total - thread.items.length} more`}</button>}
        <button type="button" className="replies-toggle" onClick={() => setThreads(t => ({ ...t, [parent.id]: { ...thread, open: false } }))}>Hide replies</button>
      </div>
    </>
  }

  function renderComment(comment: CommentItem, isReply = false) {
    return <article className={`comment-item${isReply ? " comment-reply" : ""}`} key={comment.id}>
      <span className="comment-avatar" aria-hidden="true">{name(comment.author).slice(0, 1).toUpperCase()}</span>
      <div className="comment-content">
        <div className="comment-byline"><strong>{name(comment.author)}</strong><span>{formatCommentTime(comment.created_at)}</span></div>
        <p>
          {comment.reply_to && <span className="comment-mention">@{name(comment.reply_to)} </span>}
          {comment.time_s !== null && (onSeek
            ? <button type="button" className="comment-time" aria-label={`Jump to ${formatVideoTime(comment.time_s)}`} onClick={() => onSeek(comment.time_s!)}>{formatVideoTime(comment.time_s)}</button>
            : <span className="comment-time">{formatVideoTime(comment.time_s)}</span>)}
          {comment.body}
        </p>
        <div className="comment-actions">
          <button type="button" onClick={() => startReply(comment)}>Reply</button>
          {comment.can_delete && <button type="button" aria-label="Delete my comment" disabled={busy === `delete:${comment.id}`} onClick={() => void remove(comment)}>{busy === `delete:${comment.id}` ? "Deleting…" : "Delete"}</button>}
        </div>
        {!isReply && renderReplies(comment)}
      </div>
      <button type="button" className={`comment-like${comment.liked ? " is-liked" : ""}`} aria-pressed={comment.liked} aria-label={`${comment.liked ? "Unlike" : "Like"} comment (${comment.like_count})`} onClick={() => void toggleLike(comment)}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /></svg>
        <span>{comment.like_count || ""}</span>
      </button>
    </article>
  }

  if (!interactive) {
    return <section className="comment-section" aria-label="Comments">
      <div className="comments-heading"><h2>Comments</h2></div>
      <div className="comments-empty"><strong>Sample video</strong><p>Comments are available on videos uploaded by climbers.</p></div>
    </section>
  }

  const currentTime = !replyTarget ? getCurrentTime?.() : undefined
  return <section className="comment-section" aria-label="Comments">
    <div className="comments-heading"><h2>Comments</h2><span className="comment-count">{allTotal}</span></div>
    {loadError && <div className="comments-error" role="alert"><p>{loadError}</p><button type="button" className="comment-post" onClick={() => void load(0)}>Try again</button></div>}
    {!loadError && loading && items.length === 0 && <p className="comments-status" role="status">Loading comments…</p>}
    {!loadError && !loading && items.length === 0 && <div className="comments-empty"><strong>Start the conversation</strong><p>Share a thought or ask about this beta.</p></div>}
    <div className="comment-list" aria-live="polite">{items.map(comment => renderComment(comment))}</div>
    {items.length < total && !loadError && <button type="button" className="replies-toggle comments-more" disabled={loading} onClick={() => void load(items.length)}>{loading ? "Loading…" : `Show more comments (${total - items.length})`}</button>}
    {actionError && <p className="comments-error-inline" role="alert">{actionError}</p>}
    <div className={`comment-composer compact-composer${expanded ? " is-expanded" : ""}`} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null) && !draft.trim() && !replyTarget) setExpanded(false) }}>
      <span className="comment-avatar" aria-hidden="true">{session ? (session.user.display_name || "You").slice(0, 1).toUpperCase() : "○"}</span>
      <div className="comment-input-wrap">
        {replyTarget && <div className="replying-to"><span>Replying to <b>@{name(replyTarget.author)}</b></span><button type="button" aria-label="Cancel reply" onClick={() => { setReplyTarget(null); setExpanded(!!draft.trim()) }}>×</button></div>}
        <textarea ref={input} rows={1} onFocus={() => setExpanded(true)} aria-label={replyTarget ? `Reply to ${name(replyTarget.author)}` : "Write a comment"} placeholder={replyTarget ? "Write a reply…" : "Add a comment…"} maxLength={COMMENT_MAX} value={draft} onChange={e => setDraft(e.target.value)} />
        <div className="comment-compose-footer">
          <span>{draft.length > 400 ? `${draft.length}/${COMMENT_MAX}` : expanded && currentTime !== undefined && Number.isFinite(currentTime) ? `Appears as danmaku at ${formatVideoTime(currentTime)}` : ""}</span>
          <button type="button" className="comment-post" disabled={!!session && (!draft.trim() || posting)} onClick={() => void post()}>{!session ? "Sign in to post" : posting ? "Posting…" : replyTarget ? "Reply" : "Post"}</button>
        </div>
      </div>
    </div>
  </section>
}
