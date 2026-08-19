import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'

import Toast from '../Toast.vue'

const { appStore } = vi.hoisted(() => ({
  appStore: {
    toasts: [
      {
        id: 'toast-1',
        type: 'success',
        title: 'Saved',
        message: 'The operation completed.',
        duration: 3000,
      },
    ],
    hideToast: vi.fn(),
  },
}))

vi.mock('@/stores/app', () => ({
  useAppStore: () => appStore,
}))

const mountedWrappers: VueWrapper[] = []

afterEach(() => {
  mountedWrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  appStore.hideToast.mockClear()
})

describe('Toast', () => {
  it('uses viewport insets and lets toast items shrink below 320px', () => {
    const wrapper = mount(Toast, {
      attachTo: document.body,
      global: {
        stubs: {
          Icon: true,
        },
      },
    })
    mountedWrappers.push(wrapper)

    const region = document.body.querySelector<HTMLElement>('[data-testid="toast-region"]')
    const item = document.body.querySelector<HTMLElement>('[data-testid="toast-item"]')

    expect(region).not.toBeNull()
    expect(region!.classList).toContain('inset-x-4')
    expect(region!.classList).toContain('items-end')
    expect(region!.classList).toContain('sm:left-auto')
    expect(item).not.toBeNull()
    expect(item!.classList).toContain('w-full')
    expect(item!.classList).toContain('min-w-0')
    expect(item!.classList).not.toContain('min-w-[320px]')
    expect(item!.classList).toContain('sm:min-w-[320px]')
  })
})
