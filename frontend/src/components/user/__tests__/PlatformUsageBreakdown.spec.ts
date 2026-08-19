import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

import PlatformUsageBreakdown from '../PlatformUsageBreakdown.vue'

describe('PlatformUsageBreakdown', () => {
  it('uses the viewport-clamped shared tooltip for platform details', () => {
    const wrapper = mount(PlatformUsageBreakdown, {
      props: {
        today: 1,
        total: 2,
        byPlatform: [{ platform: 'openai', today_actual_cost: 1, total_actual_cost: 2 }],
      },
      global: {
        stubs: {
          Teleport: true,
          Icon: true,
        },
      },
    })

    expect(wrapper.findComponent({ name: 'HelpTooltip' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'HelpTooltip' }).props('widthClass')).toBe(
      'w-max max-w-[calc(100vw-2rem)]',
    )
    expect(wrapper.findComponent({ name: 'HelpTooltip' }).props('trigger')).toBe('click')
    expect(wrapper.html()).not.toContain('left-full')
    expect(wrapper.html()).not.toContain('min-w-[220px]')
  })
})
