import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, '../ProxiesView.vue'), 'utf8')

describe('ProxiesView responsive forms', () => {
  it('stacks host and port fields until the small breakpoint', () => {
    expect(source.match(/grid grid-cols-1 gap-4 sm:grid-cols-2/g)).toHaveLength(2)
    expect(source).not.toContain('class="grid grid-cols-2 gap-4"')
  })
})
