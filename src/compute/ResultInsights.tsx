import { InputReview } from './InputReview'
import { useEffect, useRef, useState } from 'react'
import { classifyResult, type Task } from './results'
import { seekToMoment } from './seek'

export function ResultInsights({ task, csrf }: { task: Task | null; csrf?: string }) {
  const result = task?.state === 'succeeded' ? task.result : undefined
  const groups = result ? classifyResult(result) : null
  const player = useRef<HTMLVideoElement>(null)
  const pending = useRef<AbortController | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { pending.current?.abort(); setMessage(''); setError(''); return () => pending.current?.abort() }, [task?.id])
  async function jump(seconds: number) {
    if (!player.current || !result) return
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller; setError('')
    try {
      const reached = await seekToMoment(player.current, seconds, (result.frame_count - 1) / result.fps, controller.signal)
      if (!controller.signal.aborted) setMessage(`Diagnostic preview paused at ${reached.toFixed(2)}s`)
    } catch (e) { if (!controller.signal.aborted) setError((e as Error).message) }
  }
  const inputOnly = result?.algorithm_version === 'video-inputs-v1'
  const playable = !!result && !result.is_mock && !!result.artifacts.video
  return <section className="result-insights" aria-label="Result categories">
    {result && <>
      <p className="compute-warning">{inputOnly ? 'Input preparation complete — review required' : result.is_mock ? 'Mock result' : 'Diagnostic preview'} · Baseline: {result.baseline_status}. This is not a verified climbing recommendation.</p>
      <a href={'/api/videos/' + result.source_video_id + '/content'} target="_blank" rel="noreferrer">Open original video</a>
      {playable && <video key={task!.id} ref={player} controls preload="metadata" aria-label={inputOnly ? 'Input reference video' : task!.kind === 'analyze' ? 'Source analysis video' : 'Personal skeleton video'}
        src={'/api/tasks/' + task!.id + '/artifacts/' + (result.artifacts.display_video ? 'display_video' : 'video')} onError={() => setError('Video unavailable. Check source access or reopen the result.')} />}
      <details><summary>Result provenance and quality</summary><p>Source recording: {result.source_video_id}</p><p>Algorithm: {result.algorithm_version}</p>
        <p>Source analysis version: {result.source_analysis_version}</p><p>Checks performed: {result.quality.check_scope}</p>
        {result.quality.warnings.map(w => <p key={w}>{w}</p>)}
      </details>
    </>}
    {inputOnly && <InputReview key={task!.id} taskId={task!.id} csrf={csrf} />}
    {error && <p role="alert">{error}</p>}<p role="status" aria-live="polite">{message}</p>
    <section aria-label="Diagnostic issues"><h3>Diagnostic issues</h3><p>Model checks and missing evidence, not technique recommendations. Time links target the diagnostic video above.</p>
      {!result ? <p>No completed analysis is available yet. Start or retry analysis above, or check My Library.</p>
        : result.is_mock ? <p>This is a mock result. No real diagnostic issues are reported.</p>
        : !groups?.diagnostics.length && !groups?.insufficient.length ? <p>No diagnostic entries were returned. This does not mean the movement passed validation.</p> : null}
      {groups?.diagnostics.map(moment => <article className="result-issue" key={moment.id}>
        <strong>{moment.kind === 'contact_gap' ? 'Contact mismatch' : 'Unconfirmed evidence'} · {moment.title}</strong>
        <p>{moment.explanation}</p>{moment.gap_cm != null && <p>Reported gap: {moment.gap_cm.toFixed(2)} cm</p>}
        <button type="button" disabled={!playable} data-moment={moment.id} onClick={() => void jump(moment.at_seconds)}>View moment · {moment.at_seconds.toFixed(2)}s</button>
      </article>)}
      {groups?.insufficient.map((suggestion, index) => <article className="result-issue" key={index}><strong>Insufficient evidence</strong>
        <p>{suggestion.observed_movement}</p><p>{suggestion.explanation}</p><p>No technique recommendation is supported.</p>
        {/* Suggestion timestamps belong to their source video, not an arbitrary task artifact. */}
        <a href={'/api/videos/' + suggestion.video_id + '/content#t=' + suggestion.at_seconds} target="_blank" rel="noreferrer">View original moment · {suggestion.at_seconds.toFixed(2)}s</a>
      </article>)}
      {!!groups?.invalidEntries && <p role="status">Some entries were withheld because their source or time information is inconsistent.</p>}
    </section>
    <section aria-label="Technique results"><h3>Technique results</h3>
      {!groups?.techniques.length && <p>{result?.technique_status === 'blocked' ? 'Technique comparison is blocked.' : result?.technique_status === 'no_improvement' ? 'No improved technique was reported.' : 'No real technique comparison results are available.'} This flow does not run technique comparison.</p>}
      {!!groups?.pendingCandidates && <p>Uncompared candidates were not promoted to technique results.</p>}
      {groups?.techniques.map((s, index) => <article className="result-issue" key={index}><strong>Model comparison result · {s.technique}</strong>
        <p>{s.observed_movement}</p><p>{s.explanation}</p><p>A model candidate, not verified climbing advice.</p>
        <a href={'/api/videos/' + s.video_id + '/content#t=' + s.at_seconds} target="_blank" rel="noreferrer">View original moment · {s.at_seconds.toFixed(2)}s</a>
      </article>)}
    </section>
    <details className="result-examples"><summary>Example suggestions · illustration only</summary>
      <p>These examples explain the interface. They are not observations or advice for your uploaded video, and are not linked to its timeline.</p>
      <article><strong>Example · Drop knee</strong><p>Illustrative observation: hips move away from the wall during a reach.</p><p>Illustrative suggestion: turning the hip inward may reduce the reach distance.</p></article>
      {groups?.examples.map((s, index) => <article key={index}><strong>{result?.is_mock ? 'Mock example' : 'Example'} · {s.technique}</strong><p>{s.observed_movement}</p><p>{s.explanation}</p></article>)}
    </details>
  </section>
}
