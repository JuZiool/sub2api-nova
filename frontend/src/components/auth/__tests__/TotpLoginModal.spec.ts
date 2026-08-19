import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import TotpLoginModal from '@/components/auth/TotpLoginModal.vue'

const totpStepUpSource = readFileSync(
  resolve(process.cwd(), 'src/components/auth/TotpStepUpDialog.vue'),
  'utf8',
)
const totpSetupSource = readFileSync(
  resolve(process.cwd(), 'src/components/user/profile/TotpSetupModal.vue'),
  'utf8',
)

const { showErrorMock } = vi.hoisted(() => ({
  showErrorMock: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/stores', () => ({
  useAppStore: () => ({
    showError: (...args: any[]) => showErrorMock(...args),
  }),
}))

describe('TotpLoginModal', () => {
  beforeEach(() => {
    showErrorMock.mockReset()
  })

  it('fits all six code inputs in a bounded responsive grid', () => {
    const wrapper = mount(TotpLoginModal, {
      props: {
        tempToken: 'temp-token',
        userEmailMasked: 'u***@example.com',
      },
    })

    const inputs = wrapper.findAll('input[maxlength="1"]')
    expect(inputs).toHaveLength(6)
    expect(inputs[0].element.parentElement?.className).toContain(
      'max-w-[280px] grid-cols-6 gap-1 sm:gap-2',
    )
    for (const input of inputs) {
      expect(input.classes()).toEqual(expect.arrayContaining(['w-full', 'min-w-0']))
      expect(input.classes()).not.toContain('w-10')
    }
  })

  it('uses the same bounded code grid in step-up and setup dialogs', () => {
    for (const source of [totpStepUpSource, totpSetupSource]) {
      expect(source).toContain('mx-auto grid max-w-[280px] grid-cols-6 gap-1 sm:gap-2')
      expect(source).toContain('class="h-12 w-full min-w-0 rounded-lg')
      expect(source).not.toContain('class="h-12 w-10 rounded-lg')
    }
  })

  it('sends verification errors to toast and does not render inline red text', async () => {
    const wrapper = mount(TotpLoginModal, {
      props: {
        tempToken: 'temp-token',
        userEmailMasked: 'u***@example.com',
      },
    })

    ;(wrapper.vm as unknown as { setError: (message: string) => void }).setError('Invalid code')
    await wrapper.vm.$nextTick()

    expect(showErrorMock).toHaveBeenCalledWith('Invalid code')
    expect(wrapper.text()).not.toContain('Invalid code')
    expect(wrapper.find('.bg-red-50').exists()).toBe(false)
  })
})
