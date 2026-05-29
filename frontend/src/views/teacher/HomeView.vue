<script setup>
import { onMounted, ref } from "vue";
import TeacherLayout from "@/components/TeacherLayout.vue";
import { DEV_BACKEND_HINT, parseJsonResponse } from "@/utils/parseJsonResponse";

const health = ref(null);
const devHint = DEV_BACKEND_HINT;

async function checkHealth() {
  try {
    const res = await fetch("/api/health/");
    health.value = await parseJsonResponse(res);
    if (!res.ok) {
      health.value = { error: `HTTP ${res.status}`, detail: health.value, hint: devHint };
    }
  } catch (e) {
    health.value = { error: String(e.message || e), hint: devHint };
  }
}

onMounted(() => {
  checkHealth();
});
</script>

<template>
  <TeacherLayout title="Teacher Home">
    <main class="mx-auto max-w-lg p-6">
      <h1 class="sr-only">Teacher Home</h1>
      <p class="mt-2 text-slate-600">OnlineQuiz-v2 teacher dashboard</p>

      <router-link
        to="/teacher/banks"
        class="mt-4 inline-flex min-h-[44px] items-center rounded-lg bg-indigo-600 px-4 py-2 text-white"
      >
        Open Question Banks
      </router-link>

      <dl class="mt-6 space-y-2 rounded-lg bg-white p-4 shadow">
        <div>
          <dt class="text-sm text-slate-500">API（Flask + HTTP 輪詢）</dt>
          <dd class="font-mono text-sm">{{ health }}</dd>
        </div>
        <div>
          <dt class="text-sm text-slate-500">同步方式</dt>
          <dd class="text-sm text-slate-600">教師端每 10 秒、學生端依階段 2 秒或 10–15 秒向 API 輪詢。</dd>
        </div>
      </dl>
    </main>
  </TeacherLayout>
</template>
