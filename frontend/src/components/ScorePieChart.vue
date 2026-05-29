<script setup>
import { Chart, DoughnutController, ArcElement, Tooltip, Legend } from "chart.js";
import { onMounted, onUnmounted, ref, watch } from "vue";

Chart.register(DoughnutController, ArcElement, Tooltip, Legend);

const props = defineProps({
  labels: { type: Array, default: () => [] },
  counts: { type: Array, default: () => [] },
  colors: { type: Array, default: () => [] },
  title: { type: String, default: "" },
});

const canvasRef = ref(null);
let chart = null;

function render() {
  if (!canvasRef.value) return;
  if (chart) chart.destroy();
  const total = props.counts.reduce((a, b) => a + b, 0);
  if (total === 0) return;

  chart = new Chart(canvasRef.value, {
    type: "doughnut",
    data: {
      labels: props.labels,
      datasets: [
        {
          data: props.counts,
          backgroundColor: props.colors.length ? props.colors : undefined,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        title: { display: !!props.title, text: props.title },
        legend: { position: "bottom" },
      },
    },
  });
}

watch(() => [props.labels, props.counts], render, { deep: true });
onMounted(render);
onUnmounted(() => chart?.destroy());
</script>

<template>
  <div class="mx-auto w-full max-w-xs">
    <canvas ref="canvasRef" />
    <p v-if="!counts.some((c) => c > 0)" class="mt-2 text-center text-sm text-slate-500">
      No data yet.
    </p>
  </div>
</template>
