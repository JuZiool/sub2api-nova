import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, ref } from 'vue'

import DateRangePicker from '../DateRangePicker.vue'

const messages: Record<string, string> = {
  'dates.today': 'Today',
  'dates.yesterday': 'Yesterday',
  'dates.last24Hours': 'Last 24 Hours',
  'dates.last7Days': 'Last 7 Days',
  'dates.last14Days': 'Last 14 Days',
  'dates.last30Days': 'Last 30 Days',
  'dates.thisMonth': 'This Month',
  'dates.lastMonth': 'Last Month',
  'dates.startDate': 'Start Date',
  'dates.endDate': 'End Date',
  'dates.apply': 'Apply',
  'dates.selectDateRange': 'Select date range'
}

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => messages[key] ?? key,
    locale: ref('en')
  })
}))

const formatLocalDate = (date: Date): string => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const mountedWrappers: VueWrapper[] = []
const originalInnerHeight = window.innerHeight

const mountPicker = (startDate: string, endDate: string) => {
  const wrapper = mount(DateRangePicker, {
    attachTo: document.body,
    props: { startDate, endDate },
    global: {
      stubs: {
        Icon: true
      }
    }
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  document.body.innerHTML = ''
  Object.defineProperty(window, 'innerHeight', {
    configurable: true,
    value: originalInnerHeight
  })
  vi.restoreAllMocks()
})

describe('DateRangePicker', () => {
  it('uses today as the default recognized preset', () => {
    const now = new Date()
    const today = formatLocalDate(now)

    const wrapper = mountPicker(today, today)

    expect(wrapper.text()).toContain('Today')
  })

  it('emits range updates with last24Hours preset when applied', async () => {
    const now = new Date()
    const today = formatLocalDate(now)

    const wrapper = mountPicker(today, today)

    await wrapper.find('.date-picker-trigger').trigger('click')
    const presetButton = Array.from(
      document.body.querySelectorAll<HTMLButtonElement>('.date-picker-preset')
    ).find((node) =>
      node.textContent?.includes('Last 24 Hours')
    )
    expect(presetButton).toBeDefined()

    presetButton!.click()
    await nextTick()
    document.body.querySelector<HTMLButtonElement>('.date-picker-apply')!.click()
    await nextTick()

    const nowAfterClick = new Date()
    const yesterdayAfterClick = new Date(nowAfterClick.getTime() - 24 * 60 * 60 * 1000)
    const expectedStart = formatLocalDate(yesterdayAfterClick)
    const expectedEnd = formatLocalDate(nowAfterClick)

    expect(wrapper.emitted('update:startDate')?.[0]).toEqual([expectedStart])
    expect(wrapper.emitted('update:endDate')?.[0]).toEqual([expectedEnd])
    expect(wrapper.emitted('change')?.[0]).toEqual([
      {
        startDate: expectedStart,
        endDate: expectedEnd,
        preset: 'last24Hours'
      }
    ])
  })

  it('clamps the teleported dropdown inside a 320px viewport', async () => {
    const today = formatLocalDate(new Date())
    const wrapper = mountPicker(today, today)
    const trigger = wrapper.get<HTMLButtonElement>('.date-picker-trigger')

    vi.spyOn(document.documentElement, 'clientWidth', 'get').mockReturnValue(320)
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      value: 568
    })
    vi.spyOn(trigger.element, 'getBoundingClientRect').mockReturnValue({
      x: 120,
      y: 80,
      top: 80,
      right: 260,
      bottom: 120,
      left: 120,
      width: 140,
      height: 40,
      toJSON: () => ({})
    })

    await trigger.trigger('click')
    await nextTick()

    const dropdown = document.body.querySelector<HTMLElement>('.date-picker-dropdown')
    expect(dropdown).not.toBeNull()
    expect(dropdown!.style.left).toBe('16px')
    expect(dropdown!.style.width).toBe('288px')
    expect(dropdown!.style.top).toBe('128px')
    expect(parseFloat(dropdown!.style.left) + parseFloat(dropdown!.style.width)).toBeLessThanOrEqual(304)
  })
})
