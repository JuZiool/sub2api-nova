import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const currentDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(currentDir, '..')
const read = (path: string) => readFileSync(resolve(srcRoot, path), 'utf8')

describe('mobile detail layouts', () => {
  it('stacks admin order details until the small breakpoint', () => {
    const view = read('../views/admin/orders/AdminOrdersView.vue')
    const detail = read('admin/payment/AdminOrderDetail.vue')

    expect(view).toContain('data-testid="admin-order-detail-grid" class="grid grid-cols-1 gap-4 sm:grid-cols-2"')
    expect(view).toContain('class="break-all text-sm font-medium')
    expect(detail).toContain('data-testid="admin-order-summary-grid" class="grid grid-cols-1 gap-4 sm:grid-cols-2"')
  })

  it('stacks long user error fields and account stats on narrow screens', () => {
    const errorDetail = read('user/UserErrorDetailModal.vue')
    const accountStats = read('admin/account/AccountStatsModal.vue')

    expect(errorDetail).toContain('data-testid="user-error-detail-grid" class="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2"')
    expect(errorDetail.match(/break-all text-gray-900/g)).toHaveLength(2)
    expect(accountStats).toContain('data-testid="account-stats-grid" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"')
  })
})
