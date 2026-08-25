import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/views/admin/AccountsView.vue'), 'utf8')

describe('admin AccountsView priority column preference', () => {
  it('does not hide priority for fresh preferences', () => {
    expect(source).toContain("const DEFAULT_HIDDEN_COLUMNS = ['today_stats', 'proxy', 'notes', 'scheduler_score', 'rate_multiplier']")
    expect(source).not.toContain("const DEFAULT_HIDDEN_COLUMNS = ['today_stats', 'proxy', 'notes', 'priority'")
  })

  it('keeps priority available as a sortable column', () => {
    expect(source).toContain("'priority',")
    expect(source).toContain("{ key: 'priority', label: t('admin.accounts.columns.priority'), sortable: true }")
  })
})
