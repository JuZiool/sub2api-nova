import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ProfileBalanceNotifyCard from '../ProfileBalanceNotifyCard.vue'

const mocks = vi.hoisted(() => ({
  sendNotifyEmailCode: vi.fn(),
  showSuccess: vi.fn(),
  showError: vi.fn(),
  authStore: { user: null },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mocks.authStore,
}))

vi.mock('@/stores/app', () => ({
  useAppStore: () => ({
    showSuccess: mocks.showSuccess,
    showError: mocks.showError,
  }),
}))

vi.mock('@/api', () => ({
  userAPI: {
    sendNotifyEmailCode: mocks.sendNotifyEmailCode,
  },
}))

vi.mock('@/utils/apiError', () => ({
  extractApiErrorMessage: () => 'request failed',
}))

describe('ProfileBalanceNotifyCard responsive layout', () => {
  it('stacks email rows and wraps verification controls on narrow screens', async () => {
    mocks.sendNotifyEmailCode.mockResolvedValue(undefined)

    const wrapper = mount(ProfileBalanceNotifyCard, {
      props: {
        enabled: true,
        threshold: null,
        extraEmails: [
          {
            email: 'saved-address-with-a-long-name@example.com',
            disabled: false,
            verified: false,
          },
        ],
        systemDefaultThreshold: 5,
        userEmail: 'owner@example.com',
      },
    })

    expect(wrapper.get('[data-testid="saved-email-row"]').classes()).toEqual(
      expect.arrayContaining(['flex-col', 'items-stretch', 'sm:flex-row', 'sm:items-center']),
    )
    expect(wrapper.get('[data-testid="saved-email-actions"]').classes()).toEqual(
      expect.arrayContaining(['w-full', 'flex-wrap', 'sm:w-auto']),
    )

    const addControls = wrapper.get('[data-testid="add-email-controls"]')
    expect(addControls.classes()).toEqual(expect.arrayContaining(['flex-col', 'sm:flex-row']))
    expect(addControls.get('input[type="email"]').classes()).toEqual(
      expect.arrayContaining(['min-w-0', 'flex-1']),
    )
    expect(addControls.get('button').classes()).toEqual(expect.arrayContaining(['w-full', 'sm:w-auto']))

    await addControls.get('input[type="email"]').setValue('pending-address-with-a-long-name@example.com')
    await addControls.get('button').trigger('click')

    expect(wrapper.get('[data-testid="pending-email-row"]').classes()).toEqual(
      expect.arrayContaining(['flex-col', 'items-stretch', 'sm:flex-row', 'sm:items-center']),
    )
    expect(wrapper.get('[data-testid="pending-email-row"] > span').classes()).toContain('break-all')
    expect(wrapper.get('[data-testid="pending-email-actions"]').classes()).toEqual(
      expect.arrayContaining(['w-full', 'flex-wrap', 'sm:w-auto']),
    )

    await wrapper.get('[data-testid="pending-email-actions"] button').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="pending-email-actions"] input[type="text"]').classes()).toContain('w-20')
    expect(wrapper.get('[data-testid="pending-email-actions"]').classes()).toContain('flex-wrap')

    wrapper.unmount()
  })
})
