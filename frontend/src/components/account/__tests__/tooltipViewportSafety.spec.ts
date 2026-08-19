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
  it('uses HelpTooltip for every GroupsView form tooltip', () => {
    expect(groupsSource.match(/<HelpTooltip\b/g)).toHaveLength(12)
    expect(groupsSource).not.toContain(legacyHoverTooltip)
    expect(groupsSource).not.toContain(legacyPointerTooltip)
  })

  it('migrates create and edit account tooltips', () => {
    expect(createAccountSource.match(/<HelpTooltip\b/g)).toHaveLength(3)
    expect(editAccountSource.match(/<HelpTooltip\b/g)).toHaveLength(2)
    expect(createAccountSource).not.toContain(legacyHoverTooltip)
    expect(createAccountSource).not.toContain(legacyPointerTooltip)
    expect(editAccountSource).not.toContain(legacyHoverTooltip)
    expect(editAccountSource).not.toContain(legacyPointerTooltip)
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
