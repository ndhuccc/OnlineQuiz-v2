<script setup>
import { onMounted, ref } from "vue";
import MathText from "@/components/MathText.vue";
import StudentLayout from "@/components/StudentLayout.vue";
import { authHeaders, getClientToken } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const review = ref(null);
const error = ref("");
const loading = ref(true);

onMounted(async () => {
  const token = getClientToken();
  if (!token) {
    error.value = "請先加入測驗";
    loading.value = false;
    return;
  }
  try {
    const res = await fetch("/api/participants/me/review/", {
      headers: authHeaders(token),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) {
      error.value = data.detail || "無法載入複習";
      return;
    }
    review.value = data;
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <StudentLayout title="我的成績">
    <main class="mx-auto max-w-lg space-y-4 px-4 pb-8 pt-4">
      <p v-if="loading" class="text-center text-slate-500">載入中…</p>
      <p v-else-if="error" class="card text-red-700">{{ error }}</p>

      <section v-if="review" class="card">
        <p class="mb-4 text-slate-600">
          {{ review.display_name }}（{{ review.student_no }}）
          <span class="mx-1">·</span>
          總分
          <strong class="text-lg text-indigo-700">{{ review.total_score }}</strong>
          / {{ review.max_total_score }}
        </p>

        <article
          v-for="q in review.questions"
          :key="q.question_index"
          class="mb-6 border-b border-slate-100 pb-6 last:mb-0 last:border-0 last:pb-0"
        >
          <p class="mb-2 text-sm font-medium">
            <span class="text-indigo-600">第 {{ q.question_index + 1 }} 題</span>
            <span
              class="ml-2 rounded-full px-2 py-0.5 text-xs"
              :class="q.is_full_score ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'"
            >
              {{ q.is_full_score ? "滿分" : `得分 ${q.score}` }}
            </span>
          </p>
          <div class="mb-3 rounded-lg bg-slate-50 p-3">
            <MathText :content="q.stem_text" block />
          </div>
          <p class="text-sm">
            你的答案：<strong>{{ q.your_answer || "（未答）" }}</strong>
          </p>
          <p class="mt-1 text-sm text-green-700">
            正確答案：<MathText :content="q.correct_answer" class="inline" />
          </p>
          <details v-if="q.explanation_text" class="mt-3">
            <summary class="cursor-pointer text-sm font-medium text-indigo-600">解析</summary>
            <div class="mt-2 rounded-lg bg-indigo-50/50 p-3">
              <MathText :content="q.explanation_text" />
            </div>
          </details>
        </article>
      </section>

      <router-link to="/student/quiz" class="btn-secondary inline-flex w-full justify-center">
        返回測驗頁
      </router-link>
    </main>
  </StudentLayout>
</template>
