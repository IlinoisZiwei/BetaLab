import { test } from 'node:test'
import assert from 'node:assert/strict'
import { api, ApiError } from '../../src/api.ts'

test('shared client sends JSON, credentials, CSRF and idempotency headers', async t => {
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/tasks/analyze')
    assert.equal(init.credentials, 'same-origin')
    assert.equal(init.method, 'POST')
    assert.equal(init.body, '{"video_id":"v"}')
    const headers = new Headers(init.headers)
    assert.equal(headers.get('content-type'), 'application/json')
    assert.equal(headers.get('x-csrf-token'), 'csrf')
    assert.equal(headers.get('idempotency-key'), 'key')
    return Response.json({ id: 'task' })
  })
  assert.deepEqual(await api('/tasks/analyze', { method: 'POST', body: { video_id: 'v' }, csrf: 'csrf', headers: { 'Idempotency-Key': 'key' } }), { id: 'task' })
})

test('multipart keeps the browser boundary and original file body', async t => {
  const body = new FormData(); body.set('video', new Blob(['video']), 'sample.mp4')
  t.mock.method(globalThis, 'fetch', async (_url: string, init: RequestInit) => {
    assert.equal(init.body, body)
    assert.equal(new Headers(init.headers).has('content-type'), false)
    assert.equal(new Headers(init.headers).get('x-csrf-token'), 'csrf')
    return Response.json({ id: 'video' })
  })
  assert.deepEqual(await api('/videos', { method: 'POST', body, csrf: 'csrf' }), { id: 'video' })
})

test('empty responses, server errors and abort signals retain their contract', async t => {
  const controller = new AbortController()
  const fetch = t.mock.method(globalThis, 'fetch', async (_url: string, init: RequestInit) => {
    assert.equal(init.signal, controller.signal)
    return new Response(null, { status: 204 })
  })
  assert.equal(await api('/auth/logout', { method: 'POST', csrf: 'csrf', signal: controller.signal }), undefined)
  fetch.mock.mockImplementation(async () => Response.json({ error: { message: 'Denied' } }, { status: 403 }))
  await assert.rejects(api('/videos'), e => e instanceof ApiError && e.status === 403 && e.message === 'Denied')
  fetch.mock.mockImplementation(async () => { throw new TypeError('network') })
  await assert.rejects(api('/videos'), e => e instanceof ApiError && e.status === 0)
})
