import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, '../SubscriptionsView.vue'), 'utf8')

describe('SubscriptionsView responsive layout', () => {
  it('does not force the usage cell to 280px below the medium breakpoint', () => {
    expect(source).toContain('class="w-full min-w-0 space-y-2 md:min-w-[280px]"')
    expect(source).not.toContain('class="min-w-[280px] space-y-2"')
  })
})
