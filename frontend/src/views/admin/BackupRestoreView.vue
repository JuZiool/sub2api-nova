<template>
  <AppLayout>
    <main class="mx-auto max-w-6xl space-y-6" aria-labelledby="backup-restore-title">
      <header>
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-300">
            <Icon name="database" size="md" />
          </div>
          <div>
            <h1 id="backup-restore-title" class="text-xl font-semibold text-gray-900 dark:text-white">
              {{ t('admin.backup.title') }}
            </h1>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {{ t('admin.backup.description') }}
            </p>
          </div>
        </div>
      </header>

      <BackupView />
    </main>
  </AppLayout>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/icons/Icon.vue'
import BackupView from '@/views/admin/BackupView.vue'

const { t } = useI18n()
</script>
