import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import NovaSurface from '../NovaSurface.vue'

describe('NovaSurface', () => {
  it('renders a solid section by default', () => {
    const wrapper = mount(NovaSurface, {
      slots: { default: 'Surface content' }
    })

    expect(wrapper.element.tagName).toBe('SECTION')
    expect(wrapper.classes()).toContain('nova-surface')
    expect(wrapper.classes()).toContain('surface-solid')
    expect(wrapper.attributes('data-surface')).toBe('solid')
    expect(wrapper.text()).toBe('Surface content')
  })

  it.each(['solid', 'glass', 'overlay'] as const)('applies the %s surface variant', variant => {
    const wrapper = mount(NovaSurface, {
      props: { variant }
    })

    expect(wrapper.classes()).toContain(`surface-${variant}`)
    expect(wrapper.attributes('data-surface')).toBe(variant)
  })

  it('supports semantic elements, interactive styling, and external classes', () => {
    const wrapper = mount(NovaSurface, {
      props: {
        as: 'aside',
        variant: 'glass',
        interactive: true
      },
      attrs: {
        class: 'custom-surface',
        'aria-label': 'Account summary'
      }
    })

    expect(wrapper.element.tagName).toBe('ASIDE')
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['nova-surface', 'surface-glass', 'surface-interactive', 'custom-surface'])
    )
    expect(wrapper.attributes('aria-label')).toBe('Account summary')
  })
})
