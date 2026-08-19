import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import OrderStatsCards from '../OrderStatsCards.vue'
import type { DashboardStats } from '@/types/payment'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

const stats: DashboardStats = {
  today_amount: { USD: 12 },
  total_amount: { USD: 120 },
  today_count: 2,
  total_count: 20,
  avg_amount: { USD: 6 },
  daily_series: [],
  payment_methods: [],
  top_users: {},
}

describe('OrderStatsCards', () => {
  it('uses a single-column mobile grid with shrinkable card content', () => {
    const wrapper = mount(OrderStatsCards, {
      props: { stats },
      global: {
        stubs: {
          Icon: true,
        },
      },
    })

    expect(wrapper.get('[data-testid="order-stats-grid"]').classes()).toEqual(expect.arrayContaining([
      'grid-cols-1',
      'sm:grid-cols-2',
      'lg:grid-cols-4',
    ]))

    const cards = wrapper.findAll('.card')
    expect(cards).toHaveLength(4)
    for (const card of cards) {
      expect(card.classes()).toContain('min-w-0')
      expect(card.get('.flex-1').classes()).toContain('min-w-0')
    }
  })
})
