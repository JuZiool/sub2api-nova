<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useTemplateRef, nextTick } from 'vue'

const props = withDefaults(defineProps<{
  content?: string
  trigger?: 'hover' | 'click'
  widthClass?: string
}>(), {
  trigger: 'hover',
  widthClass: 'w-64',
})

const show = ref(false)
const triggerRef = useTemplateRef<HTMLElement>('trigger')
const tooltipRef = useTemplateRef<HTMLElement>('tooltip')
const tooltipPlacement = ref<'top' | 'bottom'>('top')
const tooltipArrowLeft = ref('50%')
const tooltipStyle = ref({
  top: '0px',
  left: '16px',
  maxWidth: 'calc(100vw - 2rem)',
})
const viewportPadding = 16
const tooltipGap = 8

function openTooltip() {
  show.value = true
  nextTick(updatePosition)
}

function closeTooltip() {
  show.value = false
}

function onEnter() {
  if (props.trigger !== 'hover') return
  openTooltip()
}

function onLeave() {
  if (props.trigger !== 'hover') return
  closeTooltip()
}

function onClick(event: MouseEvent) {
  if (props.trigger !== 'click') return
  event.stopPropagation()
  if (show.value) {
    closeTooltip()
    return
  }
  openTooltip()
}

function onDocumentClick(event: MouseEvent) {
  if (props.trigger !== 'click' || !show.value) return
  const target = event.target as Node | null
  if (!target) return
  if (triggerRef.value?.contains(target) || tooltipRef.value?.contains(target)) return
  closeTooltip()
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (props.trigger !== 'click') return
  if (event.key === 'Escape') {
    closeTooltip()
  }
}

function onViewportChange() {
  if (!show.value) return
  updatePosition()
}

function updatePosition() {
  const trigger = triggerRef.value
  const tooltip = tooltipRef.value
  if (!trigger || !tooltip) return

  const rect = trigger.getBoundingClientRect()
  const viewportWidth = document.documentElement.clientWidth || window.innerWidth
  const viewportHeight = window.innerHeight
  const availableWidth = Math.max(0, viewportWidth - viewportPadding * 2)
  const tooltipWidth = Math.min(tooltip.offsetWidth, availableWidth)
  const tooltipHeight = tooltip.offsetHeight
  const triggerCenter = rect.left + rect.width / 2
  const maxLeft = Math.max(viewportPadding, viewportWidth - tooltipWidth - viewportPadding)
  const left = Math.max(
    viewportPadding,
    Math.min(triggerCenter - tooltipWidth / 2, maxLeft),
  )
  const spaceAbove = rect.top - tooltipGap - viewportPadding
  const spaceBelow = viewportHeight - rect.bottom - tooltipGap - viewportPadding
  const openAbove = spaceAbove >= tooltipHeight || spaceAbove >= spaceBelow
  const preferredTop = openAbove
    ? rect.top - tooltipGap - tooltipHeight
    : rect.bottom + tooltipGap
  const maxTop = Math.max(viewportPadding, viewportHeight - tooltipHeight - viewportPadding)
  const top = Math.max(viewportPadding, Math.min(preferredTop, maxTop))

  tooltipPlacement.value = openAbove ? 'top' : 'bottom'
  tooltipArrowLeft.value = `${Math.max(12, Math.min(triggerCenter - left, tooltipWidth - 12))}px`
  tooltipStyle.value = {
    top: `${top}px`,
    left: `${left}px`,
    maxWidth: 'calc(100vw - 2rem)',
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  document.addEventListener('keydown', onDocumentKeydown)
  window.addEventListener('resize', onViewportChange)
  window.addEventListener('scroll', onViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, true)
  document.removeEventListener('keydown', onDocumentKeydown)
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})
</script>

<template>
  <div
    ref="trigger"
    class="group relative ml-1 inline-flex items-center align-middle"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
    @click="onClick"
  >
    <!-- Trigger Icon -->
    <slot name="trigger">
      <svg
        class="h-4 w-4 cursor-help text-gray-400 transition-colors hover:text-primary-600 dark:text-gray-500 dark:hover:text-primary-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="2"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    </slot>

    <!-- Teleport to body to escape modal overflow clipping -->
    <Teleport to="body">
      <div
        ref="tooltip"
        v-show="show"
        role="tooltip"
        :class="[
          'fixed z-[99999] text-xs leading-relaxed text-white',
          props.widthClass,
        ]"
        :style="tooltipStyle"
      >
        <div class="relative max-h-[calc(100vh-2rem)] overflow-y-auto rounded-lg bg-gray-900 p-3 shadow-xl ring-1 ring-white/10 dark:bg-gray-800">
          <button
            v-if="props.trigger === 'click'"
            type="button"
            class="absolute right-1.5 top-1.5 rounded p-1 text-gray-300 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Close"
            @click.stop="closeTooltip"
          >
            <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <slot>{{ content }}</slot>
        </div>
        <div
          :class="[
            'absolute h-2 w-2 -translate-x-1/2 rotate-45 bg-gray-900 dark:bg-gray-800',
            tooltipPlacement === 'top' ? '-bottom-1' : '-top-1',
          ]"
          :style="{ left: tooltipArrowLeft }"
        ></div>
      </div>
    </Teleport>
  </div>
</template>
