/** Presentation-only classification of the existing C result contract.
 * No inference, optimization or conversion of examples into observations.
 */
export type Note = { id: string; task_id: string; event: string; read_at: string | null }
export type Body = { height_cm: number; arm_span_cm: number; provenance: string }
export type Moment = { id: string; kind: string; frame: number; end_frame: number; at_seconds: number;
  title: string; explanation: string; limb: string; media: string; gap_cm?: number | null }
export type Suggestion = { video_id: string; at_seconds: number; observed_movement: string;
  technique: string; explanation: string; evidence: 'example' | 'model_candidate' | 'insufficient' }
export type Result = { kind: string; is_mock: boolean; source_video_id: string; baseline_status: string;
  technique_status: string; algorithm_version: string; source_analysis_version: string;
  original_body?: Body; target_body?: Body; frame_count: number; fps: number;
  quality: { warnings: string[]; evidence: string; check_scope: string };
  suggestions: Suggestion[]; moments: Moment[]; artifacts: Record<string, unknown> }
export type Task = { id: string; kind: string; source_video_id: string; created_at: string; updated_at?: string; started_at?: string | null; finished_at?: string | null; state: string; stage: string;
  is_mock: boolean; result?: Result; error?: { message: string; retryable: boolean } }

export function classifyResult(result: Result) {
  const end = (result.frame_count - 1) / result.fps
  const timeValid = (time: number) => result.fps > 0 && Number.isFinite(end) && end >= 0 && Number.isFinite(time) && time >= 0 && time <= end
  const moments = (result.moments ?? []).filter(m => timeValid(m.at_seconds) && m.media === 'video'
    && ['contact_gap', 'unconfirmed_contact'].includes(m.kind) && Number.isInteger(m.frame)
    && Number.isInteger(m.end_frame) && m.frame >= 0 && m.end_frame >= m.frame && m.end_frame < result.frame_count
    && Math.abs(m.at_seconds - m.frame / result.fps) < 1e-6)
  const suggestions = result.suggestions ?? []
  const linked = suggestions.filter(s => s.video_id === result.source_video_id && timeValid(s.at_seconds))
  const compared = !result.is_mock && result.baseline_status === 'passed' && result.technique_status === 'compared'
    && result.quality.check_scope === 'full_model' && result.quality.evidence !== 'insufficient'
  return {
    diagnostics: result.is_mock ? [] : moments,
    examples: suggestions.filter(s => s.evidence === 'example' || result.is_mock),
    insufficient: result.is_mock ? [] : linked.filter(s => s.evidence === 'insufficient'),
    techniques: compared ? linked.filter(s => s.evidence === 'model_candidate') : [],
    pendingCandidates: compared || result.is_mock ? 0 : linked.filter(s => s.evidence === 'model_candidate').length,
    invalidEntries: (result.moments ?? []).length - moments.length + suggestions.filter(s => s.evidence !== 'example' && !linked.includes(s)).length,
  }
}
