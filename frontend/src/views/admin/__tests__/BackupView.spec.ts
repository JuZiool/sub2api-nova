import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import BackupView from '../BackupView.vue'

const {
  getS3Config,
  getImageStorageConfig,
  getSchedule,
  listBackups,
  getDownloadURL,
  downloadLocalBackup,
  importLocalBackup,
} = vi.hoisted(() => ({
  getS3Config: vi.fn(),
  getImageStorageConfig: vi.fn(),
  getSchedule: vi.fn(),
  listBackups: vi.fn(),
  getDownloadURL: vi.fn(),
  downloadLocalBackup: vi.fn(),
  importLocalBackup: vi.fn(),
}))

vi.mock('@/api', () => ({
  adminAPI: {
    backup: {
      getS3Config,
      updateS3Config: vi.fn(),
      testS3Connection: vi.fn(),
      getImageStorageConfig,
      updateImageStorageConfig: vi.fn(),
      testImageStorageConnection: vi.fn(),
      getSchedule,
      updateSchedule: vi.fn(),
      createBackup: vi.fn(),
      importLocalBackup,
      listBackups,
      getBackup: vi.fn(),
      deleteBackup: vi.fn(),
      getDownloadURL,
      downloadLocalBackup,
      restoreBackup: vi.fn(),
    },
  },
}))

vi.mock('@/stores', () => ({
  useAppStore: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
    showWarning: vi.fn(),
  }),
}))

vi.mock('@/composables/useStepUp', () => ({
  useStepUp: () => ({ run: (fn: () => unknown) => fn() }),
  isStepUpBlocked: () => false,
  isStepUpCancelled: () => false,
  stepUpBlockReason: () => '',
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params?.index === undefined ? key : `${key}:${params.index}`,
  }),
}))

vi.mock('file-saver', () => ({
  saveAs: vi.fn(),
}))

const baseRecord = (id: string, parts?: unknown[]) => ({
  id,
  status: 'completed',
  backup_type: 'postgres',
  file_name: `${id}.sql.gz`,
  s3_key: `backups/${id}.sql.gz`,
  parts,
  size_bytes: 10,
  triggered_by: 'manual',
  started_at: '2026-08-09T00:00:00Z',
})

function mountBackupView() {
  return mount(BackupView, {
    global: {
      stubs: {
        TotpStepUpDialog: true,
      },
    },
  })
}

describe('admin BackupView 分卷备份', () => {
  beforeEach(() => {
    getS3Config.mockResolvedValue({})
    getImageStorageConfig.mockResolvedValue({ config: {}, secret_configured: false })
    getSchedule.mockResolvedValue({ enabled: false, cron_expr: '', retain_days: 14, retain_count: 10 })
    getDownloadURL.mockReset()
    downloadLocalBackup.mockReset()
    importLocalBackup.mockReset()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('显示分卷数并在下载时列出每个分卷链接', async () => {
    listBackups.mockResolvedValue({
      items: [baseRecord('split', [{ index: 1 }, { index: 2 }, { index: 3 }])],
    })
    getDownloadURL.mockResolvedValue({
      parts: [
        { index: 1, size_bytes: 5, url: 'https://example.test/part-1' },
        { index: 2, size_bytes: 6, url: 'https://example.test/part-2' },
        { index: 3, size_bytes: 7, url: 'https://example.test/part-3' },
      ],
    })

    const wrapper = mountBackupView()
    await flushPromises()

    expect(wrapper.text()).toContain('3')
    const downloadButton = wrapper.findAll('button').find(button =>
      button.text().includes('admin.backup.actions.download'),
    )
    expect(downloadButton).toBeDefined()
    await downloadButton!.trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('admin.backup.actions.partLabel:1')
    expect(document.body.textContent).toContain('admin.backup.actions.partLabel:3')
    expect(document.body.querySelector('a[href="https://example.test/part-2"]')).not.toBeNull()
  })

  it('旧单文件记录仍使用单个下载地址', async () => {
    listBackups.mockResolvedValue({ items: [baseRecord('legacy')] })
    getDownloadURL.mockResolvedValue({ url: 'https://example.test/legacy.sql.gz' })

    const wrapper = mountBackupView()
    await flushPromises()
    const downloadButton = wrapper.findAll('button').find(button =>
      button.text().includes('admin.backup.actions.download'),
    )
    await downloadButton!.trigger('click')
    await flushPromises()

    expect(getDownloadURL).toHaveBeenCalledWith('legacy')
    expect(document.body.textContent).not.toContain('admin.backup.actions.downloadParts')
  })

  it('本地备份通过受保护的下载接口获取文件', async () => {
    listBackups.mockResolvedValue({ items: [{ ...baseRecord('local'), storage_type: 'local' }] })
    getDownloadURL.mockResolvedValue({ local: true })
    downloadLocalBackup.mockResolvedValue(new Blob(['backup']))

    const wrapper = mountBackupView()
    await flushPromises()
    const downloadButton = wrapper.findAll('button').find(button =>
      button.text().includes('admin.backup.actions.download'),
    )
    await downloadButton!.trigger('click')
    await flushPromises()

    expect(downloadLocalBackup).toHaveBeenCalledWith('local', undefined)
  })

  it('上传 .sql.gz 文件后将导入记录加入列表', async () => {
    listBackups.mockResolvedValue({ items: [] })
    importLocalBackup.mockResolvedValue({ ...baseRecord('imported'), storage_type: 'local', triggered_by: 'imported' })

    const wrapper = mountBackupView()
    await flushPromises()
    const fileInput = wrapper.find('#backup-import-file')
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [new File(['backup'], 'migration.sql.gz', { type: 'application/gzip' })],
    })
    await fileInput.trigger('change')

    const importButton = wrapper.findAll('button').find(button =>
      button.text().includes('admin.backup.operations.importBackup'),
    )
    expect(importButton).toBeDefined()
    await importButton!.trigger('click')
    await flushPromises()

    expect(importLocalBackup).toHaveBeenCalledWith(expect.objectContaining({ name: 'migration.sql.gz' }))
    expect(wrapper.text()).toContain('imported.sql.gz')
    expect(wrapper.text()).toContain('admin.backup.trigger.imported')
  })

  it('运行中的备份不显示删除入口', async () => {
    listBackups.mockResolvedValue({
      items: [{ ...baseRecord('running'), status: 'running', progress: 'uploading' }],
    })

    const wrapper = mountBackupView()
    await flushPromises()

    expect(wrapper.find('tbody tr td:nth-child(5)').text()).toBe('-')
    expect(wrapper.findAll('button').some(button => button.text() === 'common.delete')).toBe(false)
  })

  it('R2 配置指南在窄屏内断行 endpoint 并独立滚动配置表', async () => {
    listBackups.mockResolvedValue({ items: [] })

    const wrapper = mountBackupView()
    await flushPromises()
    const guideButton = wrapper.findAll('button').find(button => button.text() === 'Cloudflare R2')
    expect(guideButton).toBeDefined()
    await guideButton!.trigger('click')

    const endpoint = document.body.querySelector('[data-testid="r2-endpoint-example"]')
    const tableScroll = document.body.querySelector('[data-testid="r2-config-table-scroll"]')
    const table = tableScroll?.querySelector('table')

    expect(endpoint?.classList.contains('break-all')).toBe(true)
    expect(endpoint?.classList.contains('sm:ml-8')).toBe(true)
    expect(tableScroll?.classList.contains('overflow-x-auto')).toBe(true)
    expect(tableScroll?.classList.contains('overflow-hidden')).toBe(false)
    expect(table?.classList.contains('min-w-[480px]')).toBe(true)
  })
})
