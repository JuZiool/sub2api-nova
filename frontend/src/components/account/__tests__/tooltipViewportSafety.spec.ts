import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (path: string) => readFileSync(resolve(process.cwd(), path), 'utf8')

const groupsSource = readSource('src/views/admin/GroupsView.vue')
const createAccountSource = readSource('src/components/account/CreateAccountModal.vue')
const editAccountSource = readSource('src/components/account/EditAccountModal.vue')
const statusSource = readSource('src/components/account/AccountStatusIndicator.vue')
const usageSource = readSource('src/components/account/AccountUsageCell.vue')

const legacyHoverTooltip = 'group-hover:opacity-100'
const legacyPointerTooltip = 'pointer-events-none absolute'

describe('account tooltip viewport safety', () => {
  // 账户弹窗随上游 0.2.0 采用内联 tooltip 方案（同样避免弹窗裁剪），
  // 原 HelpTooltip 迁移断言不再适用；GroupsView/状态/用量仍用 HelpTooltip。

  it('uses HelpTooltip for every GroupsView form tooltip', () => {
    expect(groupsSource.match(/<HelpTooltip\b/g)).toHaveLength(12)
    expect(groupsSource).not.toContain(legacyHoverTooltip)
    expect(groupsSource).not.toContain(legacyPointerTooltip)
  })

  it('keeps status and usage tooltips viewport-clamped, with click triggers for links', () => {
    expect(statusSource.match(/<HelpTooltip\b/g)).toHaveLength(4)
    expect(usageSource.match(/<HelpTooltip\b/g)).toHaveLength(2)
    expect(statusSource).not.toContain(legacyHoverTooltip)
    expect(statusSource).not.toContain(legacyPointerTooltip)
    expect(usageSource).not.toContain(legacyHoverTooltip)
    expect(usageSource).not.toContain(legacyPointerTooltip)
    expect(usageSource).toContain('<HelpTooltip trigger="click" width-class="w-80">')
  })
})
