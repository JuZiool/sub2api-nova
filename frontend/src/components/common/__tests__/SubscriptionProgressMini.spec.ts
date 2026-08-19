import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

import SubscriptionProgressMini from '../SubscriptionProgressMini.vue'

const { subscriptionStore } = vi.hoisted(() => ({
  subscriptionStore: {
    activeSubscriptions: [
      {
        id: 1,
        group_id: 2,
        expires_at: '2099-01-01T00:00:00Z',
        daily_usage_usd: 1,
        group: {
          name: 'Mobile subscription',
          daily_limit_usd: 10,
          weekly_limit_usd: null,
          monthly_limit_usd: null
        }
      }
    ],
    hasActiveSubscriptions: true,
    fetchActiveSubscriptions: vi.fn().mockResolvedValue(undefined)
  }
}))

vi.mock('@/stores', () => ({
  useSubscriptionStore: () => subscriptionStore
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key
  })
}))

const mountedWrappers: VueWrapper[] = []
const originalInnerHeight = window.innerHeight

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  document.body.innerHTML = ''
  Object.defineProperty(window, 'innerHeight', {
    configurable: true,
    value: originalInnerHeight
  })
  subscriptionStore.fetchActiveSubscriptions.mockClear()
  vi.restoreAllMocks()
})

describe('SubscriptionProgressMini', () => {
  it('keeps the details panel inside a 320px viewport', async () => {
    const wrapper = mount(SubscriptionProgressMini, {
      attachTo: document.body,
      global: {
        stubs: {
          Icon: true,
          RouterLink: {
            template: '<a><slot /></a>'
          }
        }
      }
    })
    mountedWrappers.push(wrapper)

    const trigger = wrapper.get<HTMLButtonElement>('button')
    vi.spyOn(document.documentElement, 'clientWidth', 'get').mockReturnValue(320)
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      value: 568
    })
    vi.spyOn(trigger.element, 'getBoundingClientRect').mockReturnValue({
      x: 190,
      y: 16,
      top: 16,
      right: 260,
      bottom: 48,
      left: 190,
      width: 70,
      height: 32,
      toJSON: () => ({})
    })

    await trigger.trigger('click')
    await nextTick()

    const panel = document.body.querySelector<HTMLElement>('[data-testid="subscription-progress-panel"]')
    expect(panel).not.toBeNull()
    expect(panel!.style.left).toBe('16px')
    expect(panel!.style.width).toBe('288px')
    expect(panel!.style.top).toBe('56px')
    expect(parseFloat(panel!.style.left) + parseFloat(panel!.style.width)).toBeLessThanOrEqual(304)
  })
})
