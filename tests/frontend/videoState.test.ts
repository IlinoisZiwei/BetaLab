import { test } from 'node:test'
import assert from 'node:assert/strict'
import { emptyVideos, videoReducer } from '../../src/features/videos/videoState.ts'
import type { UserVideo } from '../../src/api.ts'
const video = (values: Partial<UserVideo> = {}): UserVideo => ({ id: 'video-1', owner_id: 'alice', route_id: 'r1', visibility: 'private', share_as_beta: false,
  original_name: 'clip.mp4', title: 'Climb', description: '', media_type: 'video/mp4', size_bytes: 20, duration_seconds: 4,
  created_at: '2026-11-19T12:00:00Z', content_url: '/api/videos/video-1/content', ...values })

test('upload, public sharing and privacy reversal update every collection without duplicates', () => {
  const initial = emptyVideos()
  let state = videoReducer(initial, { type: 'upsert', video: video(), routeId: 'r1' })
  assert.equal(state.owned.length, 1); assert.equal(state.public.length, 0); assert.equal(state.beta.length, 0)
  const shared = video({ visibility: 'public', share_as_beta: true })
  state = videoReducer(state, { type: 'upsert', video: shared, routeId: 'r1' })
  state = videoReducer(state, { type: 'upsert', video: shared, routeId: 'r1' })
  assert.equal(state.owned.length, 1); assert.equal(state.public.length, 1); assert.equal(state.beta.length, 1)
  state = videoReducer(state, { type: 'upsert', video: video(), routeId: 'r1' })
  assert.equal(state.owned.length, 1); assert.equal(state.public.length, 0); assert.equal(state.beta.length, 0)
  assert.deepEqual(initial, emptyVideos())
})

test('route-scoped beta, deletion and account reset retain collection boundaries', () => {
  let state = videoReducer(emptyVideos(), { type: 'upsert', video: video({ visibility: 'public', share_as_beta: true }), routeId: 'another-route' })
  assert.equal(state.beta.length, 0); assert.equal(state.public.length, 1)
  state = videoReducer(state, { type: 'remove', id: 'video-1' }); assert.deepEqual(state, emptyVideos())
  state = videoReducer(state, { type: 'replace', list: 'public', videos: [video({ owner_id: 'bob' })] })
  assert.equal(state.owned.length, 0)
  assert.deepEqual(videoReducer(state, { type: 'reset' }), emptyVideos())
})

test('editing title and description updates the same video in owned, public and beta lists', () => {
  const original = video({visibility:'public',share_as_beta:true})
  let state = videoReducer(emptyVideos(), {type:'upsert',video:original,routeId:'r1'})
  const edited = {...original,title:'New title',description:'New description'}
  state = videoReducer(state,{type:'upsert',video:edited,routeId:'r1'})
  for (const list of [state.owned,state.public,state.beta]) {
    assert.equal(list.length,1)
    assert.equal(list[0].id,original.id)
    assert.equal(list[0].title,'New title')
    assert.equal(list[0].description,'New description')
  }
})
