import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import type { UserDashboardStats as UserDashboardStatsData } from '@/api/usage'
import UserDashboardStats from '../UserDashboardStats.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key
  })
}))

const stats: UserDashboardStatsData = {
  total_api_keys: 0,
  active_api_keys: 0,
  total_requests: 0,
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_cache_creation_tokens: 0,
  total_cache_read_tokens: 0,
  total_tokens: 0,
  total_cost: 0,
  total_actual_cost: 0,
  today_requests: 0,
  today_input_tokens: 0,
  today_output_tokens: 0,
  today_cache_creation_tokens: 0,
  today_cache_read_tokens: 0,
  today_tokens: 0,
  today_cost: 0,
  today_actual_cost: 0,
  average_duration_ms: 0,
  rpm: 0,
  tpm: 0,
  by_platform: []
}

describe('UserDashboardStats', () => {
  it('uses one-column stat grids below the small breakpoint', () => {
    const wrapper = mount(UserDashboardStats, {
      props: {
        stats,
        balance: 0,
        isSimple: false
      },
      global: {
        stubs: {
          Icon: true
        }
      }
    })

    for (const testId of ['user-dashboard-core-stats', 'user-dashboard-token-stats']) {
      expect(wrapper.get(`[data-testid="${testId}"]`).classes()).toEqual(expect.arrayContaining([
        'grid-cols-1',
        'sm:grid-cols-2',
        'lg:grid-cols-4'
      ]))
    }
  })
})
