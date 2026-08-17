<template>
  <component
    :is="props.as"
    :class="surfaceClasses"
    :data-surface="props.variant"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'

type SurfaceVariant = 'solid' | 'glass' | 'overlay'

const props = withDefaults(
  defineProps<{
    as?: string | Component
    variant?: SurfaceVariant
    interactive?: boolean
  }>(),
  {
    as: 'section',
    variant: 'solid',
    interactive: false
  }
)

const surfaceClasses = computed(() => [
  'nova-surface',
  `surface-${props.variant}`,
  props.interactive && 'surface-interactive'
])
</script>
