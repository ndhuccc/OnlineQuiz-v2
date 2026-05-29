<script setup>
import { computed } from "vue";

const props = defineProps({
  remainingSec: { type: Number, default: null },
  totalSec: { type: Number, default: 90 },
  large: { type: Boolean, default: false },
});

const pct = computed(() => {
  if (props.remainingSec == null || !props.totalSec) return 0;
  return Math.min(100, Math.max(0, (props.remainingSec / props.totalSec) * 100));
});

const urgent = computed(() => props.remainingSec != null && props.remainingSec <= 10);
</script>

<template>
  <div v-if="remainingSec != null" class="w-full">
    <div class="mb-1 flex justify-between" :class="large ? 'text-2xl lg:text-3xl' : 'text-sm'">
      <span>{{ large ? "剩餘時間" : "Time Remaining" }}</span>
      <span :class="urgent ? 'font-bold text-red-400' : large ? 'text-white' : 'text-slate-700'">
        {{ remainingSec }} 秒
      </span>
    </div>
    <div
      class="overflow-hidden rounded-full bg-slate-200/30"
      :class="large ? 'h-4 lg:h-6' : 'h-2'"
    >
      <div
        class="h-full transition-all duration-500"
        :class="urgent ? 'bg-red-500' : large ? 'bg-indigo-400' : 'bg-indigo-500'"
        :style="{ width: `${pct}%` }"
      />
    </div>
  </div>
</template>
