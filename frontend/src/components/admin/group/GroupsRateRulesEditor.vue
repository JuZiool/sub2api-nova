<script setup lang="ts">
import type { ModelRateMultiplierRule } from "@/types";

// Nova 独有：按客户端模型设置分组计费倍率的编辑器卡片。
// 从 GroupsView.vue 弹窗中抽出以缩小与上游页面模板的碰撞面；
// 通过 props/emits 与父级表单状态桥接，行为与原内联实现一致
// （规则数组由父级持有，此处仅做展示与增删操作）。

defineProps<{
  rules: ModelRateMultiplierRule[];
  candidates: string[];
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "add"): void;
  (e: "pick", pattern: string): void;
  (e: "remove", index: number): void;
}>();

const onPick = (event: Event) => {
  const select = event.target as HTMLSelectElement;
  const pattern = select.value;
  if (pattern) emit("pick", pattern);
  select.value = "";
};
</script>

<template>
  <div class="space-y-2 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
    <div class="flex items-center justify-between gap-2">
      <div>
        <label class="input-label">模型专属倍率</label>
        <p class="input-hint">自动获取可用模型，倍率由管理员设置；未配置模型使用默认倍率。</p>
      </div>
      <button type="button" class="btn btn-secondary btn-sm" @click="emit('add')">添加规则</button>
    </div>
    <select class="input w-full" :disabled="loading" @change="onPick">
      <option value="">{{ loading ? "正在获取模型…" : "从自动获取的模型中添加" }}</option>
      <option v-for="model in candidates" :key="model" :value="model">{{ model }}</option>
    </select>
    <div
      v-for="(rule, index) in rules"
      :key="`${rule.pattern}-${index}`"
      class="flex gap-2"
    >
      <input
        v-model.trim="rule.pattern"
        class="input flex-1"
        placeholder="模型名称或前缀，例如 gpt-5.6-*"
      />
      <input
        v-model.number="rule.multiplier"
        class="input w-28"
        type="number"
        min="0"
        max="1000"
        step="any"
      />
      <button type="button" class="btn btn-danger btn-sm" @click="emit('remove', index)">
        删除
      </button>
    </div>
  </div>
</template>
