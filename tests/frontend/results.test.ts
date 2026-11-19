import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyResult, type Result } from '../../src/compute/results.ts'
const result = (): Result => ({ kind: 'analyze', is_mock: false, source_video_id: 'video-a', baseline_status: 'failed',
  technique_status: 'blocked', algorithm_version: 'fixture', source_analysis_version: 'fixture', frame_count: 301, fps: 30,
  quality: { warnings: [], evidence: 'low_confidence', check_scope: 'geometry_only' }, artifacts: {},
  moments: [{ id: 'gap', kind: 'contact_gap', frame: 30, end_frame: 31, at_seconds: 1, media: 'video', limb: 'left_hand', title: 'Gap', explanation: 'fixture' }],
  suggestions: [{ video_id: 'video-a', at_seconds: 1, evidence: 'example', technique: 'drop knee', observed_movement: 'example', explanation: 'example' },
    { video_id: 'video-a', at_seconds: 1, evidence: 'model_candidate', technique: 'flagging', observed_movement: 'candidate', explanation: 'candidate' },
    { video_id: 'video-a', at_seconds: 1, evidence: 'insufficient', technique: 'not supported', observed_movement: 'occluded', explanation: 'not enough evidence' }] })
test('failed baseline keeps examples, diagnostics and unvalidated candidates separate without mutation', () => {
  const r=result(), original=JSON.stringify(r), groups=classifyResult(r)
  assert.equal(groups.diagnostics.length,1); assert.equal(groups.examples.length,1); assert.equal(groups.insufficient.length,1)
  assert.equal(groups.techniques.length,0); assert.equal(groups.pendingCandidates,1); assert.equal(JSON.stringify(r),original)
})
test('mock findings cannot become real diagnostics or technique results', () => {
  const r=result(); r.is_mock=true; r.baseline_status='passed';r.technique_status='compared';r.quality.check_scope='full_model'
  const groups=classifyResult(r);assert.equal(groups.examples.length,3);assert.equal(groups.diagnostics.length,0);assert.equal(groups.techniques.length,0)
})
test('foreign source and invalid native-frame times are withheld', () => {
  const r=result();r.suggestions[1].video_id='different-video';r.moments[0].at_seconds=2
  r.suggestions[2].at_seconds=Infinity
  const groups=classifyResult(r);assert.equal(groups.invalidEntries,3);assert.equal(groups.diagnostics.length,0);assert.equal(groups.insufficient.length,0)
})
test('only a non-mock full-model compared result can show a model comparison candidate', () => {
  const r=result();r.baseline_status='passed';r.technique_status='compared'
  assert.equal(classifyResult(r).techniques.length,0)
  r.quality.check_scope='full_model';assert.equal(classifyResult(r).techniques.length,1)
  r.quality.evidence='insufficient';assert.equal(classifyResult(r).techniques.length,0)
})
