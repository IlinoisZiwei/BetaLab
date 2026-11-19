import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import { once } from 'node:events'
import type { AddressInfo } from 'node:net'
import fs from 'node:fs'
import path from 'node:path'
import { createServer } from 'vite'

test('extracted Vite plugins retain dev HTML, kit, API proxy and private-file denial', async () => {
  const upstream = createHttpServer((req, res) => {
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ path: req.url }))
  })
  upstream.listen(0, '127.0.0.1')
  await once(upstream, 'listening')
  const previous = process.env.BETALAB_API_TARGET
  process.env.BETALAB_API_TARGET = `http://127.0.0.1:${(upstream.address() as AddressInfo).port}`
  const privateFile = path.resolve('backend/compute/runs', `vite-deny-${process.pid}.txt`)
  fs.mkdirSync(path.dirname(privateFile), { recursive: true })
  fs.writeFileSync(privateFile, 'private-regression-sentinel')
  let server: Awaited<ReturnType<typeof createServer>> | undefined
  try {
    server = await createServer({ server: { host: '127.0.0.1', port: 0, strictPort: false }, logLevel: 'silent' })
    await server.listen()
    const base = `http://127.0.0.1:${(server.httpServer!.address() as AddressInfo).port}`
    for (const route of ['/', '/compute.html']) {
      const html = await (await fetch(base + route)).text()
      assert.ok(html.includes('name="robots" content="noindex, nofollow"'))
      assert.ok(!html.includes('<!-- figma:title -->'))
    }
    assert.equal(await (await fetch(base + '/robots.txt')).text(), 'User-agent: *\nDisallow: /\n')
    const kit = await (await fetch(base + '/.figma/make/kit.html')).text()
    assert.ok(kit.includes('figma-make-kit-root'))
    const stories = await fetch(base + '/@id/__x00__virtual:figma-stories')
    assert.equal(stories.status, 200)
    assert.ok((await stories.text()).includes('export const stories'))
    for (const prefix of ['auth/me', 'profile', 'gyms', 'routes', 'tasks', 'notifications', 'videos']) {
      assert.deepEqual(await (await fetch(base + '/api/' + prefix)).json(), { path: '/api/' + prefix })
    }
    for (const route of ['/backend/compute/runs/' + path.basename(privateFile), '/@fs' + privateFile]) {
      const response = await fetch(base + route)
      assert.equal(response.status, 403)
      assert.ok(!(await response.text()).includes('private-regression-sentinel'))
    }
  } finally {
    await server?.close()
    await new Promise<void>((resolve) => upstream.close(() => resolve()))
    fs.rmSync(privateFile, { force: true })
    if (previous === undefined) delete process.env.BETALAB_API_TARGET
    else process.env.BETALAB_API_TARGET = previous
  }
})
