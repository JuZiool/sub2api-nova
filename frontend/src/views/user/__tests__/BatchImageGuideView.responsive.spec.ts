import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, '../BatchImageGuideView.vue'), 'utf8')

describe('BatchImageGuideView responsive overlays', () => {
  it('stacks detail actions below the small breakpoint', () => {
    expect(source).toContain(
      'data-testid="batch-detail-actions" class="flex w-full flex-col gap-3 sm:flex-row sm:justify-end"',
    )
    expect(source).toContain('btn btn-secondary w-full justify-center sm:w-auto')
    expect(source).toContain('btn btn-primary inline-flex w-full min-w-[112px] items-center justify-center sm:w-auto')
  })

  it('clamps the prompt popover to the viewport gutter', () => {
    expect(source).toContain('max-w-[calc(100vw-2rem)]')
    expect(source).toContain('const width = Math.max(0, Math.min(440, viewportWidth - 32))')
    expect(source).not.toContain('Math.max(320, viewportWidth - 32)')
  })
})
