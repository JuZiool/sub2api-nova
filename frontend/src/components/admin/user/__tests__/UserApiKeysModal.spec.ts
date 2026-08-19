import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

import UserApiKeysModal from '../UserApiKeysModal.vue'
import type { AdminUser, ApiKey } from '@/types'

const { getUserApiKeys, getAllGroups, updateApiKeyGroup, appStore } = vi.hoisted(() => ({
  getUserApiKeys: vi.fn(),
  getAllGroups: vi.fn(),
  updateApiKeyGroup: vi.fn(),
  appStore: {
    showSuccess: vi.fn(),
    showError: vi.fn(),
  },
}))

vi.mock('@/api/admin', () => ({
  adminAPI: {
    users: {
      getUserApiKeys,
    },
    groups: {
      getAll: getAllGroups,
    },
    apiKeys: {
      updateApiKeyGroup,
    },
  },
}))

vi.mock('@/stores/app', () => ({
  useAppStore: () => appStore,
}))

vi.mock('vue-i18n', async () => {
  const actual = await vi.importActual<typeof import('vue-i18n')>('vue-i18n')
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
    }),
  }
})

const user = {
  id: 1,
  email: 'user@example.com',
  username: 'user',
} as AdminUser

const apiKey = {
  id: 7,
  user_id: 1,
  key: 'sk-test-abcdefghijklmnopqrstuvwxyz',
  name: 'Mobile key',
  status: 'active',
  group_id: null,
  group: null,
  created_at: '2026-01-01T00:00:00Z',
} as unknown as ApiKey

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

describe('UserApiKeysModal', () => {
  it('clamps the group selector inside a 320px viewport', async () => {
    getUserApiKeys.mockResolvedValue({ items: [apiKey] })
    getAllGroups.mockResolvedValue([])

    const wrapper = mount(UserApiKeysModal, {
      attachTo: document.body,
      props: {
        show: false,
        user,
      },
      global: {
        stubs: {
          BaseDialog: {
            props: ['show'],
            template: '<div v-if="show"><slot /></div>',
          },
          GroupBadge: true,
          GroupOptionItem: true,
        },
      },
    })
    mountedWrappers.push(wrapper)

    await wrapper.setProps({ show: true })
    await flushPromises()

    const trigger = wrapper.get<HTMLElement>('[data-testid="api-key-group-trigger"]')
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

    const dropdown = document.body.querySelector<HTMLElement>('[data-testid="api-key-group-dropdown"]')
    expect(dropdown).not.toBeNull()
    expect(dropdown!.style.left).toBe('16px')
    expect(dropdown!.style.width).toBe('256px')
    expect(dropdown!.style.top).toBe('128px')
    expect(parseFloat(dropdown!.style.left) + parseFloat(dropdown!.style.width)).toBeLessThanOrEqual(304)
  })
})
