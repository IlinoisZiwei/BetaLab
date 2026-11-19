import type { Plugin } from 'vite'
import fs from 'node:fs'
import path from 'node:path'

/**
 * Reports the sources of dependencies linked from outside node_modules (pnpm
 * or npm workspaces, `file:`, `link:`) under `node_modules/<name>/`, the way
 * installed packages appear in sourcemaps. Vite otherwise reports their real
 * path, such as `libraries/<name>/`.
 */
export function figmaLinkedPackageSourcemaps(projectRoot: string): Plugin {
  const packageJson = JSON.parse(fs.readFileSync(path.resolve(projectRoot, 'package.json'), 'utf8'))
  const linkedPackages = Object.keys({ ...packageJson.dependencies, ...packageJson.devDependencies }).flatMap((name) => {
    const installedDir = path.resolve(projectRoot, 'node_modules', name)
    try {
      const realDir = fs.realpathSync(installedDir)
      return realDir.split(path.sep).includes('node_modules') ? [] : [{ installedDir, realDir }]
    } catch {
      return []
    }
  })
  const sourceMappingUrl = /\/\/# sourceMappingURL=(\S+)\s*$/

  function installedPath(file: string) {
    const linked = linkedPackages.find(({ realDir }) => file.startsWith(realDir + path.sep))
    return linked && path.join(linked.installedDir, path.relative(linked.realDir, file))
  }
  function readSourceMap(file: string, code: string) {
    const url = sourceMappingUrl.exec(code)?.[1]
    try {
      if (url?.startsWith('data:')) {
        return { map: JSON.parse(Buffer.from(url.split(',')[1], 'base64').toString()), mapDir: path.dirname(file) }
      }
      if (url) {
        const mapFile = path.resolve(path.dirname(file), url)
        return { map: JSON.parse(fs.readFileSync(mapFile, 'utf8')), mapDir: path.dirname(mapFile) }
      }
    } catch {}
    // Without a usable input map, map every line to itself.
    const mappings = code.split('\n').map((_, i) => (i ? 'AACA' : 'AAAA'))
    const map = { version: 3, sources: [file], sourcesContent: [code], names: [], mappings: mappings.join(';') }
    return { map, mapDir: path.dirname(file) }
  }

  return {
    name: 'figma-linked-package-sourcemaps',
    enforce: 'pre',
    load(id) {
      // Leave queried imports such as ?raw and ?url to Vite's own loaders.
      if (id.includes('?') || !/\.[cm]?[jt]sx?$/.test(id) || !installedPath(id)) return null

      const code = fs.readFileSync(id, 'utf8')
      const { map, mapDir } = readSourceMap(id, code)
      const sourceRoot = path.resolve(mapDir, map.sourceRoot ?? '')
      map.sources = map.sources.map((source: string) => {
        const original = path.resolve(sourceRoot, source)
        return installedPath(original) ?? original
      })
      delete map.sourceRoot
      return { code: code.replace(sourceMappingUrl, ''), map }
    },
  }
}
