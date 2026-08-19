import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (path: string) => readFileSync(resolve(process.cwd(), path), 'utf8')

const monitorFormSource = readSource('src/components/admin/monitor/MonitorFormDialog.vue')
const monitorAdvancedSource = readSource(
  'src/components/admin/monitor/MonitorAdvancedRequestConfig.vue',
)
const rpmOverridesSource = readSource(
  'src/components/admin/group/GroupRPMOverridesModal.vue',
)
const rateMultipliersSource = readSource(
  'src/components/admin/group/GroupRateMultipliersModal.vue',
)
const tlsProfilesSource = readSource('src/components/admin/TLSFingerprintProfilesModal.vue')
const errorRulesSource = readSource('src/components/admin/ErrorPassthroughRulesModal.vue')

describe('admin form mobile layouts', () => {
  it('stacks monitor endpoint and API-key actions below the sm breakpoint', () => {
    expect(monitorFormSource.match(/class="flex flex-col gap-2 sm:flex-row"/g)).toHaveLength(2)
    expect(monitorFormSource.match(/class="input min-w-0 flex-1"/g)).toHaveLength(2)
    expect(monitorFormSource.match(/w-full whitespace-nowrap sm:w-auto/g)).toHaveLength(2)
  })

  it('stacks advanced monitor header fields and body modes on mobile', () => {
    expect(monitorAdvancedSource).toContain(
      'class="flex flex-col gap-2 sm:flex-row sm:items-center"',
    )
    expect(monitorAdvancedSource).toContain('class="input w-full font-mono text-xs sm:w-52 sm:flex-none"')
    expect(monitorAdvancedSource).toContain('class="grid grid-cols-1 gap-3 sm:grid-cols-3"')
  })

  it('stacks group override controls and restores rows at sm', () => {
    expect(rpmOverridesSource).toContain(
      'class="flex flex-col gap-2 sm:flex-row sm:items-end"',
    )
    expect(rpmOverridesSource).toContain('class="relative min-w-0 flex-1"')
    expect(rpmOverridesSource).toContain('class="w-full sm:w-24"')

    expect(rateMultipliersSource).toContain(
      'class="flex flex-col gap-2 sm:flex-row sm:items-end"',
    )
    expect(rateMultipliersSource).toContain('sm:flex-row sm:items-center')
    expect(rateMultipliersSource).toContain('class="flex w-full min-w-0 items-center gap-1.5 sm:w-auto"')
  })

  it('uses single-column TLS and error-rule forms until sm', () => {
    expect(tlsProfilesSource.match(/grid grid-cols-1 gap-4 sm:grid-cols-2/g)).toHaveLength(2)
    expect(errorRulesSource).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2')
    expect(errorRulesSource.match(/grid grid-cols-1 gap-3 sm:grid-cols-2/g)).toHaveLength(2)
  })
})
