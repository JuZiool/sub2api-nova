import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UsageProgressBar from '../UsageProgressBar.vue'

vi.mock('vue-i18n', async () => {
  const actual = await vi.importActual<typeof import('vue-i18n')>('vue-i18n')
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key
    })
  }
})

describe('UsageProgressBar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-17T00:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('showNowWhenIdle=true 且利用率为 0 时显示“现在”', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 0,
        resetsAt: '2026-03-17T02:30:00Z',
        showNowWhenIdle: true,
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('usage.resetNow')
    expect(wrapper.text()).not.toContain('2h 30m')
  })

  it('showNowWhenIdle=true 但利用率大于 0 时显示倒计时', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '7d',
        utilization: 12,
        resetsAt: '2026-03-17T02:30:00Z',
        showNowWhenIdle: true,
        color: 'emerald'
      }
    })

    expect(wrapper.text()).toContain('2h 30m')
    expect(wrapper.text()).not.toContain('usage.resetNow')
    expect(wrapper.text()).not.toContain('usage.resetPending')
  })

  it('showNowWhenIdle=false 时保持原有倒计时行为', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '1d',
        utilization: 0,
        resetsAt: '2026-03-17T02:30:00Z',
        showNowWhenIdle: false,
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('2h 30m')
    expect(wrapper.text()).not.toContain('usage.resetNow')
  })

  it('resetsAt 已过期且利用率大于 0 时显示「待刷新」', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 53,
        // 早于 fake system time 2026-03-17T00:00:00Z
        resetsAt: '2026-03-16T22:00:00Z',
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('usage.resetPending')
    expect(wrapper.text()).not.toContain('usage.resetNow')
  })

  it('resetsAt 已过期且利用率为 0 时仍显示「现在」', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 0,
        resetsAt: '2026-03-16T22:00:00Z',
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('usage.resetNow')
    expect(wrapper.text()).not.toContain('usage.resetPending')
  })

  it('剩余容量模式在 100% 时显示满格绿色', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: 'Req',
        utilization: 100,
        remainingCapacity: true,
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('100%')
    expect(wrapper.get('.h-1\\.5 > div').attributes('style')).toContain('width: 100%')
    expect(wrapper.get('.h-1\\.5 > div').classes()).toContain('bg-green-500')
  })

  it('剩余容量模式在低量和耗尽时缩短并变红', async () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: 'Req',
        utilization: 15,
        remainingCapacity: true,
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('15%')
    expect(wrapper.get('.h-1\\.5 > div').attributes('style')).toContain('width: 15%')
    expect(wrapper.get('.h-1\\.5 > div').classes()).toContain('bg-red-500')

    await wrapper.setProps({ utilization: 0 })

    expect(wrapper.text()).toContain('0%')
    expect(wrapper.get('.h-1\\.5 > div').attributes('style')).toContain('width: 0%')
    expect(wrapper.get('.h-1\\.5 > div').classes()).toContain('bg-red-500')
  })

  it('默认利用率模式仍把超限显示为满格红色', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 120,
        color: 'indigo'
      }
    })

    expect(wrapper.text()).toContain('120%')
    expect(wrapper.get('.h-1\\.5 > div').attributes('style')).toContain('width: 100%')
    expect(wrapper.get('.h-1\\.5 > div').classes()).toContain('bg-red-500')
  })

  it('透支期会显示请求、Token 和账号金额', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 100,
        color: 'indigo',
        overdraftActive: true,
        overdraftRecoverAt: '2026-03-17T02:30:00Z',
        overdraftStats: {
          requests: 12,
          tokens: 3456,
          cost: 1.23
        }
      }
    })

    expect(wrapper.text()).toContain('usage.overdraftActive')
    expect(wrapper.text()).toContain('12 req')
    expect(wrapper.text()).toContain('3.5K')
    expect(wrapper.text()).toContain('$1.23')
  })

  it('合并透支统计时隐藏重复的窗口统计行', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '7d',
        utilization: 100,
        color: 'emerald',
        hideWindowStats: true,
        windowStats: {
          requests: 50,
          tokens: 3_900_000,
          cost: 0.14,
          user_cost: 0.06
        }
      }
    })

    expect(wrapper.find('[data-test="window-stats"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('50 req')
    expect(wrapper.text()).not.toContain('U $0.06')
  })

  it('显示窗口统计中的请求数、Token和账号金额，不显示用户金额', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '5h',
        utilization: 42,
        color: 'indigo',
        windowStats: {
          requests: 12,
          tokens: 3456,
          cost: 1.23,
          user_cost: 0.45
        },
        hideUserCost: true
      }
    })

    const stats = wrapper.get('[data-test="window-stats"]')
    expect(stats.text()).toContain('12 req')
    expect(stats.text()).toContain('3.5K')
    expect(stats.text()).toContain('A $1.23')
    expect(stats.text()).not.toContain('U $0.45')
  })

  it('启用额度汇总时按已用账号费用和利用率估算总额', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '7d',
        utilization: 8,
        color: 'emerald',
        showQuotaSummary: true,
        windowStats: {
          requests: 351,
          tokens: 61_500_000,
          cost: 80.89,
          user_cost: 3.24
        }
      }
    })

    const summary = wrapper.get('[data-test="quota-summary"]')
    expect(summary.text()).toContain('admin.accounts.usageWindow.quotaEstimate')
    expect(summary.text()).toContain('$1011.13')
    expect(summary.text()).toContain('admin.accounts.usageWindow.usedQuota')
    expect(summary.text()).toContain('$80.89')
    expect(summary.text()).not.toContain('Token')
    expect(summary.text()).not.toContain('quotaAvailable')
  })

  it('额度汇总将正常使用和透支费用分开显示', () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '7d',
        utilization: 100,
        color: 'emerald',
        showQuotaSummary: true,
        windowStats: {
          requests: 0,
          tokens: 0,
          cost: 0
        },
        overdraftActive: true,
        overdraftStats: {
          requests: 1,
          tokens: 9_800_000,
          cost: 0.34
        }
      }
    })

    const summary = wrapper.get('[data-test="quota-summary"]')
    const rows = summary.element.children
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('admin.accounts.usageWindow.quotaEstimate：$0.00')
    expect(rows[0].textContent).toContain('admin.accounts.usageWindow.usedQuota：$0.00')
    expect(rows[1].textContent).toContain('admin.accounts.usageWindow.overdraftQuota：$0.34 · 9.8M Token')
    expect(summary.text()).toContain('$0.00')
    expect(summary.text()).toContain('$0.34')
    expect(summary.text()).toContain('admin.accounts.usageWindow.quotaEstimate：$0.00')
    expect(summary.text()).toContain('admin.accounts.usageWindow.usedQuota：$0.00')
    expect(summary.text()).toContain('admin.accounts.usageWindow.overdraftQuota：$0.34 · 9.8M Token')
    expect(summary.text().match(/\$0\.00/g)).toHaveLength(2)
    expect(summary.text().match(/\$0\.34/g)).toHaveLength(1)
  })

  it('额度汇总在利用率或已用费用为零时仍保持显示', async () => {
    const wrapper = mount(UsageProgressBar, {
      props: {
        label: '7d',
        utilization: 0,
        color: 'emerald',
        showQuotaSummary: true,
        windowStats: {
          requests: 1,
          tokens: 100,
          cost: 1
        }
      }
    })

    const summary = wrapper.get('[data-test="quota-summary"]')
    expect(summary.text()).toContain('admin.accounts.usageWindow.quotaEstimate')
    expect(summary.text()).toContain('admin.accounts.usageWindow.usedQuota')
    expect(summary.text()).toContain('$1.00')
    expect(summary.text()).toContain('-')
    expect(summary.text()).not.toContain('Token')

    await wrapper.setProps({
      utilization: 8,
      windowStats: { requests: 1, tokens: 100, cost: 0 }
    })
    expect(wrapper.get('[data-test="quota-summary"]').text()).toContain('$0.00')

    await wrapper.setProps({
      utilization: 8,
      windowStats: null
    })
    expect(wrapper.get('[data-test="quota-summary"]').text()).not.toContain('Token')
  })
})
