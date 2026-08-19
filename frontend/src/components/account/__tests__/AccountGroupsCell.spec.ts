import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

import AccountGroupsCell from '../AccountGroupsCell.vue'
import type { Group } from '@/types'

vi.mock('vue-i18n', async () => {
  const actual = await vi.importActual<typeof import('vue-i18n')>('vue-i18n')
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
    }),
  }
})

const groups = [
  { id: 1, name: 'One', platform: 'anthropic' },
  { id: 2, name: 'Two', platform: 'openai' },
  { id: 3, name: 'Three', platform: 'gemini' },
] as unknown as Group[]

const mountedWrappers: VueWrapper[] = []
const originalInnerHeight = window.innerHeight

afterEach(() => {
  mountedWrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  Object.defineProperty(window, 'innerHeight', {
    configurable: true,
    value: originalInnerHeight,
  })
  vi.restoreAllMocks()
})

describe('AccountGroupsCell', () => {
  it('keeps the complete group popover inside a 320px viewport', async () => {
    const wrapper = mount(AccountGroupsCell, {
      attachTo: document.body,
      props: {
        groups,
        maxDisplay: 2,
      },
      global: {
        stubs: {
          GroupBadge: {
            template: '<span />',
          },
        },
      },
    })
    mountedWrappers.push(wrapper)

    const trigger = wrapper.get<HTMLElement>('[data-testid="account-groups-more"]')
    vi.spyOn(document.documentElement, 'clientWidth', 'get').mockReturnValue(320)
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      value: 568,
    })
    vi.spyOn(trigger.element, 'getBoundingClientRect').mockReturnValue({
      x: 276,
      y: 100,
      top: 100,
      right: 308,
      bottom: 124,
      left: 276,
      width: 32,
      height: 24,
      toJSON: () => ({}),
    })

    await trigger.trigger('click')
    await nextTick()

    const popover = document.body.querySelector<HTMLElement>('[data-testid="account-groups-popover"]')
    expect(popover).not.toBeNull()
    expect(popover!.style.left).toBe('16px')
    expect(popover!.style.width).toBe('288px')
    expect(popover!.style.top).toBe('132px')
    expect(parseFloat(popover!.style.left) + parseFloat(popover!.style.width)).toBeLessThanOrEqual(304)
  })
})
