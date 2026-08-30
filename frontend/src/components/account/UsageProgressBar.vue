<template>
  <div>
    <!-- Window stats row (above progress bar) -->
    <div
      v-if="!hideWindowStats && windowStats && (windowStats.requests > 0 || windowStats.tokens > 0)"
      data-test="window-stats"
      class="mb-0.5 flex items-center"
    >
      <div class="flex items-center gap-1.5 text-[9px] text-gray-500 dark:text-gray-400">
        <span class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800">
          {{ formatRequests }} req
        </span>
        <span class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800">
          {{ formatTokens }}
        </span>
        <span class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800" :title="t('usage.accountBilled')">
          A ${{ formatAccountCost }}
        </span>
        <span
          v-if="!hideUserCost && windowStats?.user_cost != null"
          class="rounded bg-gray-100 px-1.5 py-0.5 dark:bg-gray-800"
          :title="t('usage.userBilled')"
        >
          U ${{ formatUserCost }}
        </span>
      </div>
    </div>

    <CodexOverdraftStats
      v-if="!hideOverdraftStats"
      :active="overdraftActive"
      :stats="overdraftStats"
      :started-at="overdraftStartedAt"
      :recover-at="overdraftRecoverAt"
    />

    <!-- Progress bar row -->
    <div class="flex items-center gap-1">
      <!-- Label badge (fixed width for alignment) -->
      <span
        :class="['w-[32px] shrink-0 rounded px-1 text-center text-[10px] font-medium', labelClass]"
      >
        {{ label }}
      </span>

      <!-- Progress bar container -->
      <div class="h-1.5 w-8 shrink-0 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          :class="['h-full transition-all duration-300', barClass]"
          :style="{ width: barWidth }"
        ></div>
      </div>

      <!-- Percentage -->
      <span :class="['w-[32px] shrink-0 text-right text-[10px] font-medium', textClass]">
        {{ displayPercent }}
      </span>

      <!-- Reset time -->
      <span v-if="shouldShowResetTime" class="shrink-0 text-[10px] text-gray-400">
        {{ formatResetTime }}
      </span>
    </div>

    <!-- Optional quota estimate for native 7d windows. -->
    <div
      v-if="showQuotaSummary"
      data-test="quota-summary"
      class="mt-0.5 space-y-0.5 text-[10px] text-gray-500 dark:text-gray-400"
      :title="t('admin.accounts.usageWindow.quotaEstimateHint')"
    >
      <div class="flex items-center gap-2 whitespace-nowrap">
        <span class="font-semibold text-emerald-700 dark:text-emerald-300">
          {{ t('admin.accounts.usageWindow.quotaEstimate') }}：{{ formatQuotaCost(quotaSummary?.estimatedTotalCost) }}
        </span>
        <span class="font-medium text-gray-700 dark:text-gray-300">
          {{ t('admin.accounts.usageWindow.usedQuota') }}：{{ formatQuotaCost(quotaSummary?.usedCost) }}
        </span>
      </div>
      <div
        v-if="quotaSummary?.overdraftCost != null"
        class="whitespace-nowrap font-medium text-red-600 dark:text-red-400"
      >
        {{ t('admin.accounts.usageWindow.overdraftQuota') }}：{{ formatQuotaCost(quotaSummary.overdraftCost) }} ·
        {{ formatQuotaTokens(quotaSummary.overdraftTokens) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { useI18n } from 'vue-i18n'
import type { WindowStats } from '@/types'
import { formatCompactNumber } from '@/utils/format'
import CodexOverdraftStats from './CodexOverdraftStats.vue'

const props = defineProps<{
  label: string
  utilization: number // Percentage (0-100+)
  resetsAt?: string | null
  color: 'indigo' | 'emerald' | 'purple' | 'amber'
  windowStats?: WindowStats | null
  showQuotaSummary?: boolean
  showNowWhenIdle?: boolean
  remainingCapacity?: boolean
  overdraftActive?: boolean
  overdraftStats?: WindowStats | null
  overdraftStartedAt?: string | null
  overdraftRecoverAt?: string | null
  hideOverdraftStats?: boolean
  hideWindowStats?: boolean
  hideUserCost?: boolean
}>()

const { t } = useI18n()

// Reactive clock for countdown — only runs when a reset time is shown,
// to avoid creating many idle timers across large account lists.
const now = ref(new Date())
const { pause: pauseClock, resume: resumeClock } = useIntervalFn(
  () => {
    now.value = new Date()
  },
  60_000,
  { immediate: false },
)
if (props.resetsAt) resumeClock()
watch(
  () => props.resetsAt,
  (val) => {
    if (val) {
      now.value = new Date()
      resumeClock()
    } else {
      pauseClock()
    }
  },
)

// Label background colors
const labelClass = computed(() => {
  const colors = {
    indigo: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
    emerald: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
  }
  return colors[props.color]
})

// Progress bar color based on utilization
const barClass = computed(() => {
  if (props.remainingCapacity) {
    if (props.utilization <= 20) {
      return 'bg-red-500'
    } else if (props.utilization <= 50) {
      return 'bg-amber-500'
    }
    return 'bg-green-500'
  }
  if (props.utilization >= 100) {
    return 'bg-red-500'
  } else if (props.utilization >= 80) {
    return 'bg-amber-500'
  } else {
    return 'bg-green-500'
  }
})

// Text color based on utilization
const textClass = computed(() => {
  if (props.remainingCapacity) {
    if (props.utilization <= 20) {
      return 'text-red-600 dark:text-red-400'
    } else if (props.utilization <= 50) {
      return 'text-amber-600 dark:text-amber-400'
    }
    return 'text-gray-600 dark:text-gray-400'
  }
  if (props.utilization >= 100) {
    return 'text-red-600 dark:text-red-400'
  } else if (props.utilization >= 80) {
    return 'text-amber-600 dark:text-amber-400'
  } else {
    return 'text-gray-600 dark:text-gray-400'
  }
})

// Bar width (capped at 100%)
const barWidth = computed(() => {
  return `${Math.min(Math.max(props.utilization, 0), 100)}%`
})

// Display percentage (cap at 999% for readability)
const displayPercent = computed(() => {
  const percent = Math.round(
    props.remainingCapacity
      ? Math.min(Math.max(props.utilization, 0), 100)
      : props.utilization
  )
  return percent > 999 ? '>999%' : `${percent}%`
})

const shouldShowResetTime = computed(() => {
  if (props.resetsAt) return true
  return Boolean(props.showNowWhenIdle && props.utilization <= 0)
})

// Format reset time
const formatResetTime = computed(() => {
  // For rolling windows, when utilization is 0%, treat as immediately available.
  if (props.showNowWhenIdle && props.utilization <= 0) {
    return t('usage.resetNow')
  }

  if (!props.resetsAt) return '-'

  const date = new Date(props.resetsAt)
  const diffMs = date.getTime() - now.value.getTime()

  // resetsAt 已过期：utilization>0 说明后端窗口数据还没刷新（active poll 没回写），
  // 显示「待刷新」以区别于真正可用的「现在」。
  if (diffMs <= 0) {
    return props.utilization > 0 ? t('usage.resetPending') : t('usage.resetNow')
  }

  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))

  if (diffHours >= 24) {
    const days = Math.floor(diffHours / 24)
    return `${days}d ${diffHours % 24}h`
  } else if (diffHours > 0) {
    return `${diffHours}h ${diffMins}m`
  } else {
    return `${diffMins}m`
  }
})

// Window stats formatters
const formatRequests = computed(() => {
  if (!props.windowStats) return ''
  return formatCompactNumber(props.windowStats.requests, { allowBillions: false })
})

const formatTokens = computed(() => {
  if (!props.windowStats) return ''
  return formatCompactNumber(props.windowStats.tokens)
})

const formatAccountCost = computed(() => {
  if (!props.windowStats) return '0.00'
  return props.windowStats.cost.toFixed(2)
})

const formatUserCost = computed(() => {
  if (!props.windowStats || props.windowStats.user_cost == null) return '0.00'
  return props.windowStats.user_cost.toFixed(2)
})

// Estimate the account's native quota from the observed 7d utilization.
// Overdraft usage is returned separately from the regular window stats. Keep it
// separate in the summary so the native usage and overdraft usage are visible
// independently, while the estimate still represents the native window only.
// Keep the summary object present whenever the feature is enabled so the UI
// remains visible even while the API has returned zero or incomplete values.
const quotaSummary = computed(() => {
  if (!props.showQuotaSummary) return null

  const regularCost = props.windowStats ? Number(props.windowStats.cost) : Number.NaN
  const validRegularCost = Number.isFinite(regularCost) && regularCost >= 0 ? regularCost : null
  const overdraftCost =
    props.overdraftStats && props.overdraftActive !== false
      ? Number(props.overdraftStats.cost)
      : Number.NaN
  const overdraftTokens =
    props.overdraftStats && props.overdraftActive !== false
      ? Number(props.overdraftStats.tokens)
      : Number.NaN
  const validOverdraftCost = Number.isFinite(overdraftCost) && overdraftCost >= 0 ? overdraftCost : null
  const validOverdraftTokens =
    Number.isFinite(overdraftTokens) && overdraftTokens >= 0 ? overdraftTokens : null
  const usedCost = validRegularCost
  const utilization = Number(props.utilization)

  let estimatedTotalCost: number | null = null
  if (validRegularCost !== null && Number.isFinite(utilization) && utilization > 0) {
    const ratio = utilization / 100
    const estimate = validRegularCost / ratio
    if (Number.isFinite(estimate) && estimate >= 0) {
      estimatedTotalCost = estimate
    }
  }

  return {
    usedCost,
    overdraftCost: validOverdraftCost,
    overdraftTokens: validOverdraftTokens,
    estimatedTotalCost
  }
})

const formatQuotaCost = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value)) return '-'
  return `$${value.toFixed(2)}`
}

const formatQuotaTokens = (value: number | null | undefined): string => {
  if (value == null || !Number.isFinite(value)) return '- Token'
  return `${formatCompactNumber(value)} Token`
}

</script>
