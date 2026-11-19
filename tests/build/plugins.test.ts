import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { figmaSiteConfiguration } from '../../vite/plugins/figmaSiteConfiguration.ts'
import { figmaErrorOverlayReplay } from '../../vite/plugins/figmaErrorOverlayReplay.ts'
import { figmaReactRefreshBoundaryFallback } from '../../vite/plugins/figmaReactRefreshBoundaryFallback.ts'
import { figmaMakeKitPlugin } from '../../vite/plugins/figmaMakeKitPlugin.ts'
import { figmaLinkedPackageSourcemaps } from '../../vite/plugins/figmaLinkedPackageSourcemaps.ts'

// Exercise plugin contracts directly without changing the application or starting a solver.
test('site metadata escapes text, keeps slots and emits noindex robots', () => {
  const plugin: any = figmaSiteConfiguration({
    title: 'Climb < & >', language: 'en!', robots: { index: false },
    customScripts: { bodyEnd: '<span>custom</span>' },
  })
  const result = plugin.transformIndexHtml.handler('<!-- figma:lang --> <!-- figma:title --> <!-- figma:body-end -->')
  assert.equal(result.html, 'en Climb &lt; &amp; &gt; <span>custom</span>')
  assert.ok(result.tags.some((tag: any) => tag.attrs.name === 'robots' && tag.attrs.content === 'noindex, nofollow'))
  let asset: any
  plugin.generateBundle.call({ emitFile: (value: any) => { asset = value } })
  assert.equal(asset.fileName, 'robots.txt')
  assert.equal(asset.source, 'User-agent: *\nDisallow: /\n')
})

test('error replay remembers errors and clears them after successful updates', () => {
  const plugin: any = figmaErrorOverlayReplay()
  let connect: any
  const sent: unknown[] = []
  const ws = { send: (value: unknown) => sent.push(value), on: (_: string, fn: any) => { connect = fn } }
  plugin.configureServer({ ws })
  const error = { type: 'error', err: { message: 'bad build' } }
  ws.send(error)
  const replayed: string[] = []
  connect({ send: (value: string) => replayed.push(value) })
  assert.deepEqual(replayed, [JSON.stringify(error)])
  ws.send({ type: 'update', updates: [] })
  connect({ send: (value: string) => replayed.push(value) })
  assert.equal(replayed.length, 1)
  assert.equal(sent.length, 2)
})

test('losing a React refresh boundary triggers full reload and invalidation', async () => {
  const plugin: any = figmaReactRefreshBoundaryFallback()
  const sent: unknown[] = [], invalidated: unknown[] = []
  const server = { ws: { send: (value: unknown) => sent.push(value) },
    moduleGraph: { invalidateModule: (value: unknown) => invalidated.push(value) } }
  plugin.configureServer(server)
  plugin.transform('registerExportsForReactRefresh', '/src/Page.tsx')
  plugin.transform('export { Page } from "./Page"', '/src/Page.tsx')
  await Promise.resolve()
  const module = { id: '/src/Page.tsx', importers: new Set() }
  assert.deepEqual(plugin.handleHotUpdate({ modules: [module], server, timestamp: 1 }), [])
  assert.deepEqual(invalidated, [module])
  assert.ok(sent.every((value: any) => value.type === 'full-reload'))
  assert.equal(sent.length, 2)
})

test('Make kit stays dev-only and exposes only its virtual module', () => {
  const plugin: any = figmaMakeKitPlugin({ storiesGlob: '/src/**/*.stories.tsx' })
  assert.equal(plugin.apply, 'serve')
  const id = plugin.resolveId('virtual:figma-stories')
  assert.equal(plugin.load(id), 'export const stories = import.meta.glob(["/src/**/*.stories.tsx"])')
  assert.equal(plugin.resolveId('unrelated'), null)
  assert.equal(plugin.load('unrelated'), null)
})

test('linked sourcemaps resolve from the project root, preserve raw queries and map linked files', () => {
  const temp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'betalab-plugin-')))
  try {
    const root = path.join(temp, 'app'), linked = path.join(temp, 'linked')
    fs.mkdirSync(path.join(root, 'node_modules'), { recursive: true })
    fs.mkdirSync(linked)
    fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ dependencies: { sample: 'file:../linked' } }))
    fs.symlinkSync(linked, path.join(root, 'node_modules/sample'), 'dir')
    const file = path.join(linked, 'index.js')
    fs.writeFileSync(file, 'export const value = 1\n')
    const plugin: any = figmaLinkedPackageSourcemaps(root)
    assert.equal(plugin.load(file + '?raw'), null)
    const loaded = plugin.load(file)
    assert.equal(loaded.code, 'export const value = 1\n')
    assert.deepEqual(loaded.map.sources, [path.join(root, 'node_modules/sample/index.js')])
    assert.equal(loaded.map.sourceRoot, undefined)
  } finally { fs.rmSync(temp, { recursive: true, force: true }) }
})
