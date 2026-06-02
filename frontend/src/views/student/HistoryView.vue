<script setup>
import { onMounted, ref } from "vue";
import MathText from "@/components/MathText.vue";
import StudentLayout from "@/components/StudentLayout.vue";
import { authHeaders, getLoginSession } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const historyData = ref(null);
const currentPage = ref(1);
const error = ref("");
const loading = ref(false);

const selectedDetail = ref(null);
const loadingDetail = ref(false);

async function fetchHistory(page = 1) {
  const session = getLoginSession();
  const token = session?.token;
  if (!token) {
    error.value = "請重新登入學生帳號";
    return;
  }

  loading.value = true;
  error.value = "";
  try {
    const res = await fetch(`/api/students/history/?page=${page}`, {
      headers: authHeaders(token),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.detail || "無法載入測驗紀錄");
    }
    historyData.value = data;
    currentPage.value = data.page;
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    loading.value = false;
  }
}

async function viewDetail(participantId) {
  const session = getLoginSession();
  const token = session?.token;
  if (!token) {
    error.value = "請重新登入學生帳號";
    return;
  }

  selectedDetail.value = null;
  loadingDetail.value = true;
  try {
    const res = await fetch(`/api/students/history/${participantId}/`, {
      headers: authHeaders(token),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) {
      throw new Error(data.detail || "無法載入答題細節");
    }
    selectedDetail.value = data;
  } catch (e) {
    alert(e.message || e);
  } finally {
    loadingDetail.value = false;
  }
}

function formatDate(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  return date.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getStatusLabel(status) {
  switch (status) {
    case "lobby": return "大廳中";
    case "running": return "進行中";
    case "summary": return "總結期";
    case "review": return "複習中";
    case "closed": return "已關閉";
    default: return status;
  }
}

onMounted(() => {
  fetchHistory(1);
});
</script>

<template>
  <StudentLayout title="個人測驗紀錄區">
    <main class="mx-auto max-w-4xl px-4 py-8 space-y-6">
      <div class="flex items-center justify-between pb-4 border-b border-slate-200">
        <h2 class="text-2xl font-black text-slate-900">歷史測驗紀錄</h2>
        <span class="text-sm font-medium text-slate-500">
          共 {{ historyData?.total_count || 0 }} 筆記錄
        </span>
      </div>

      <p v-if="loading && !historyData" class="text-center text-slate-500 py-8">載入中…</p>
      <p v-else-if="error" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ error }}</p>

      <!-- History List -->
      <section v-else-if="historyData" class="space-y-4">
        <div v-if="historyData.items.length === 0" class="text-center py-12 bg-white rounded-3xl border border-slate-200 shadow-sm text-slate-500">
          目前尚無任何測驗紀錄。
        </div>

        <div v-else class="overflow-hidden bg-white border border-slate-200 shadow-sm rounded-3xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse text-sm">
              <thead>
                <tr class="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-xs">
                  <th class="px-6 py-4">題庫名稱</th>
                  <th class="px-6 py-4">加入代碼</th>
                  <th class="px-6 py-4">測驗時間</th>
                  <th class="px-6 py-4">狀態</th>
                  <th class="px-6 py-4">我的得分</th>
                  <th class="px-6 py-4 text-center">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 text-slate-700">
                <tr v-for="item in historyData.items" :key="item.participant_id" class="hover:bg-slate-50/50 transition">
                  <td class="px-6 py-4 font-semibold text-slate-900">{{ item.bank_name }}</td>
                  <td class="px-6 py-4 font-mono">{{ item.join_code }}</td>
                  <td class="px-6 py-4 text-slate-500">{{ formatDate(item.joined_at) }}</td>
                  <td class="px-6 py-4">
                    <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold"
                          :class="item.session_status === 'review' || item.session_status === 'closed' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-amber-50 text-amber-700 border border-amber-200'">
                      {{ getStatusLabel(item.session_status) }}
                    </span>
                  </td>
                  <td class="px-6 py-4 font-bold text-indigo-600">
                    {{ item.actual_score }} <span class="text-slate-400 font-normal">/ {{ item.max_score }}</span>
                  </td>
                  <td class="px-6 py-4 text-center">
                    <button type="button" @click="viewDetail(item.participant_id)"
                            class="inline-flex items-center justify-center rounded-xl bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 text-xs font-semibold text-indigo-700 transition">
                      查看細節
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Controls -->
          <div v-if="historyData.total_pages > 1" class="flex items-center justify-between border-t border-slate-200 px-6 py-4 bg-slate-50/50">
            <button type="button" :disabled="currentPage <= 1 || loading" @click="fetchHistory(currentPage - 1)"
                    class="rounded-xl border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50 px-3 py-1.5 text-xs font-semibold text-slate-600 transition">
              上一頁
            </button>
            <span class="text-xs text-slate-500 font-medium">
              第 {{ currentPage }} 頁 / 共 {{ historyData.total_pages }} 頁
            </span>
            <button type="button" :disabled="currentPage >= historyData.total_pages || loading" @click="fetchHistory(currentPage + 1)"
                    class="rounded-xl border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50 px-3 py-1.5 text-xs font-semibold text-slate-600 transition">
              下一頁
            </button>
          </div>
        </div>
      </section>

      <!-- Details View Overlay / Section -->
      <section v-if="loadingDetail" class="text-center py-8 text-slate-500">
        正在載入測驗答題細節與解析…
      </section>

      <section v-else-if="selectedDetail" class="bg-white border border-slate-200 shadow-sm rounded-3xl p-6 space-y-6">
        <div class="flex items-center justify-between pb-4 border-b border-slate-200">
          <div>
            <h3 class="text-xl font-bold text-slate-900">{{ selectedDetail.bank_name }}</h3>
            <p class="text-xs text-slate-500 mt-1">
              學生：{{ selectedDetail.display_name }}（{{ selectedDetail.student_no }}）
            </p>
          </div>
          <div class="text-right">
            <span class="text-sm font-semibold text-slate-500 block">該次獲得分數</span>
            <span class="text-2xl font-black text-indigo-600">
              {{ selectedDetail.total_score }} <span class="text-sm font-normal text-slate-400">/ {{ selectedDetail.max_total_score }}</span>
            </span>
          </div>
        </div>

        <div class="space-y-6">
          <article v-for="q in selectedDetail.questions" :key="q.question_index" class="border border-slate-100 rounded-3xl p-5 space-y-3 shadow-sm bg-slate-50/20">
            <div class="flex items-center justify-between">
              <span class="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-bold text-indigo-700">
                第 {{ q.question_index + 1 }} 題
              </span>
              <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
                    :class="q.is_full_score ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-amber-50 text-amber-700 border border-amber-200'">
                {{ q.is_full_score ? '滿分' : `得分: ${q.score}` }}（總分：{{ q.points }}）
              </span>
            </div>

            <!-- Stem -->
            <div class="p-3 bg-white border border-slate-100 rounded-2xl">
              <MathText :content="q.stem_text" block />
            </div>

            <!-- Options -->
            <div class="grid gap-2 text-sm pl-1">
              <div v-for="opt in q.options" :key="opt.letter" class="flex items-start gap-2">
                <span class="font-bold text-slate-600">{{ opt.letter }}.</span>
                <MathText :content="opt.label_text" class="text-slate-700" />
              </div>
            </div>

            <!-- Answers Comparison -->
            <div class="flex flex-wrap items-center gap-4 text-xs font-medium text-slate-500 border-t border-slate-100 pt-3">
              <div>
                你的回答：
                <span v-if="q.your_answer" class="rounded-md bg-slate-100 px-2 py-1 font-bold text-slate-800">
                  {{ q.your_answer }}
                </span>
                <span v-else class="text-slate-400 font-normal italic">（未答）</span>
              </div>
              <div>
                正確答案：
                <span class="rounded-md bg-emerald-50 border border-emerald-100 px-2 py-1 font-bold text-emerald-800">
                  {{ q.correct_answer }}
                </span>
              </div>
            </div>

            <!-- Explanation -->
            <div v-if="q.explanation_text" class="rounded-2xl bg-indigo-50/50 p-4 border border-indigo-100/50 mt-3 space-y-1">
              <h4 class="text-xs font-bold text-indigo-800 uppercase tracking-widest">題目解析</h4>
              <MathText :content="q.explanation_text" class="text-slate-700 text-sm" />
            </div>
          </article>
        </div>

        <div class="flex justify-end pt-4 border-t border-slate-200">
          <button type="button" @click="selectedDetail = null"
                  class="rounded-xl border border-slate-300 bg-white hover:bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700 transition shadow-sm">
            關閉非凡細節
          </button>
        </div>
      </section>
    </main>
  </StudentLayout>
</template>
