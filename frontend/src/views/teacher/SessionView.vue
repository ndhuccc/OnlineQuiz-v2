<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import JoinCodeCard from "@/components/JoinCodeCard.vue";
import MathText from "@/components/MathText.vue";
import ScorePieChart from "@/components/ScorePieChart.vue";
import TeacherLayout from "@/components/TeacherLayout.vue";
import TimerBar from "@/components/TimerBar.vue";
import { usePhaseCountdown } from "@/composables/usePhaseCountdown";
import { authHeaders, getHostToken } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const route = useRoute();
const sessionId = Number(route.params.sessionId);

const state = ref(null);
const participants = ref([]);
const submittedCount = ref(0);
const questionStats = ref(null);
const summary = ref(null);
const message = ref("");
const error = ref("");
const actionBusy = ref(false);
const timerInput = ref(90);
const activeTimerTotal = ref(90);
const lastQuestionId = ref(null);
const rescueStudentNo = ref("");
const projectionOpen = ref(true);

const TEACHER_POLL_MS = 10_000;

let pollTimer = null;
let closedSyncTimer = null;

const { remainingSec, syncClock, stopClock } = usePhaseCountdown(
  () => state.value,
  () => isAnswering.value,
);

const hostToken = computed(() => getHostToken(sessionId));
const isSummary = computed(() => state.value?.status === "summary");
const isReview = computed(() => state.value?.status === "review");
const isLobby = computed(() => state.value?.status === "lobby");
const isQuizRunning = computed(() => state.value?.status === "running");
const isStem = computed(() => state.value?.current_phase === "stem");
const isAnswering = computed(() => state.value?.current_phase === "options");
const isClosed = computed(() => state.value?.current_phase === "closed");
const showQuestionBoard = computed(
  () => state.value && !isLobby.value && !isSummary.value && !isReview.value,
);
const joinUrl = computed(
  () =>
    state.value?.join_url ||
    `${location.origin}/student/quiz?code=${state.value?.join_code || ""}`,
);
const questionNumber = computed(() => (state.value?.current_question_index ?? 0) + 1);
const canAdvance = computed(
  () => state.value?.status === "running" && state.value?.current_phase === "closed",
);
const isLastQuestion = computed(
  () => questionNumber.value === (state.value?.total_questions ?? 0),
);

const joinCodeCopied = ref(false);

const phaseHintProjection = computed(() => {
  if (isClosed.value) return "本題已結束，請在控制面板查看統計並繼續。";
  if (isStem.value) return "題幹階段：請在下方按鈕開放選項並開始計時。";
  if (isAnswering.value) return "作答進行中";
  return "";
});

function closeProjection() {
  projectionOpen.value = false;
}

function openProjection() {
  projectionOpen.value = true;
}

function onProjectionKeydown(e) {
  if (e.key === "Escape" && projectionOpen.value) {
    closeProjection();
  }
}

async function copyJoinCode() {
  if (!state.value?.join_code) return;
  await navigator.clipboard.writeText(state.value.join_code);
  joinCodeCopied.value = true;
  setTimeout(() => {
    joinCodeCopied.value = false;
  }, 2000);
}

function applySessionData(data) {
  if (!data) return;
  state.value = data;
  participants.value = data.participants || participants.value;
  submittedCount.value = data.submitted_count ?? submittedCount.value;
  syncQuestionTimer(data);
  syncClock();
}

function setMessage(text) {
  message.value = text;
  error.value = "";
}

function syncQuestionTimer(data) {
  if (!data?.current_question_id || !data?.stem?.timer_seconds) return;
  if (lastQuestionId.value !== data.current_question_id) {
    lastQuestionId.value = data.current_question_id;
    timerInput.value = data.stem.timer_seconds;
    activeTimerTotal.value = data.stem.timer_seconds;
  }
  if (isAnswering.value && data.phase_timer_seconds != null) {
    activeTimerTotal.value = data.phase_timer_seconds;
  }
}

async function api(path, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`/api/sessions/${sessionId}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(hostToken.value),
        ...options.headers,
      },
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    return data;
  } catch (e) {
    if (e.name === "AbortError") {
      throw new Error("請求逾時，後端可能卡住。請重啟後端後再試。");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function refresh() {
  const data = await api("/");
  applySessionData(data);

  if (isSummary.value || isReview.value) {
    summary.value = await api("/stats/summary/");
  }
}

async function loadCurrentStats() {
  try {
    questionStats.value = await api("/stats/current/");
  } catch {
    questionStats.value = null;
  }
}

function stopClosedSync() {
  if (closedSyncTimer) {
    clearInterval(closedSyncTimer);
    closedSyncTimer = null;
  }
}

function startClosedSync() {
  if (closedSyncTimer) return;
  const syncClosed = () => {
    refresh()
      .then(() => loadCurrentStats())
      .catch(() => {});
  };
  syncClosed();
  closedSyncTimer = setInterval(syncClosed, TEACHER_POLL_MS);
}

watch(remainingSec, (sec) => {
  if (sec === 0 && isAnswering.value) {
    startClosedSync();
  } else if (isClosed.value) {
    stopClosedSync();
  }
});

watch(
  () => state.value?.current_phase,
  (phase) => {
    syncClock();
    if (phase === "closed") {
      stopClosedSync();
      loadCurrentStats().catch(() => {});
    }
  },
);

watch(
  () => state.value?.current_question_index,
  () => {
    if (showQuestionBoard.value) {
      projectionOpen.value = true;
    }
  },
);
async function startQuizFromLobby() {
  if (actionBusy.value) return;
  actionBusy.value = true;
  error.value = "";
  try {
    await api("/start/", { method: "POST" });
    await refresh();
    setMessage(`第 ${questionNumber.value} 題題幹已顯示（僅投影幕），學生端不會看到題幹。`);
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    actionBusy.value = false;
  }
}

async function openOptions() {
  if (actionBusy.value) return;
  actionBusy.value = true;
  error.value = "";
  const seconds = Number(timerInput.value);
  if (!Number.isFinite(seconds) || seconds < 5) {
    error.value = "計時至少 5 秒。";
    actionBusy.value = false;
    return;
  }
  try {
    activeTimerTotal.value = seconds;
    const data = await api("/phase/", {
      method: "POST",
      body: JSON.stringify({ phase: "options", timer_seconds: seconds }),
    });
    applySessionData({
      ...state.value,
      ...data,
      participants: state.value?.participants ?? participants.value,
      submitted_count: state.value?.submitted_count ?? submittedCount.value,
    });
    if (data.phase_remaining_seconds != null) {
      timerInput.value = 30;
    }
    syncClock();
    loadCurrentStats().catch(() => {});
    setMessage(`第 ${questionNumber.value} 題已開放作答，倒數 ${seconds} 秒。`);
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    actionBusy.value = false;
  }
}

async function adjustTimer() {
  if (actionBusy.value) return;
  error.value = "";
  const seconds = Number(timerInput.value);
  if (!Number.isFinite(seconds) || seconds < 5) {
    error.value = "至少增加 5 秒。";
    return;
  }
  actionBusy.value = true;
  try {
    const data = await api("/timer/", {
      method: "PATCH",
      body: JSON.stringify({ timer_seconds: seconds }),
    });
    applySessionData({
      ...state.value,
      ...data,
      participants: state.value?.participants ?? participants.value,
      submitted_count: state.value?.submitted_count ?? submittedCount.value,
    });
    if (data.phase_timer_seconds != null) {
      activeTimerTotal.value = data.phase_timer_seconds;
    }
    setMessage(
      `已增加 ${seconds} 秒，剩餘 ${data.phase_remaining_seconds ?? "?"} 秒。`,
    );
  } catch (e) {
    error.value = String(e);
  } finally {
    actionBusy.value = false;
  }
}

async function rescueStudent() {
  if (actionBusy.value) return;
  error.value = "";
  const studentNo = rescueStudentNo.value.trim();
  if (!studentNo) {
    error.value = "請輸入學號。";
    return;
  }
  actionBusy.value = true;
  try {
    const data = await api("/rescue/", {
      method: "POST",
      body: JSON.stringify({ student_no: studentNo }),
    });
    setMessage(
      `${data.message || "已開放搶救"}。請該生以相同學號在學生端重新加入。`,
    );
    await refresh();
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    actionBusy.value = false;
  }
}

async function nextQuestion() {
  if (actionBusy.value) return;
  actionBusy.value = true;
  error.value = "";
  try {
    const data = await api("/next/", { method: "POST" });
    questionStats.value = null;
    if (data.status === "running") {
      await refresh();
      actionBusy.value = false;
      await openOptions();
    } else {
      setMessage("測驗已結束，可查看總結。");
      await refresh();
    }
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    actionBusy.value = false;
  }
}

async function openReview() {
  await api("/open-review/", { method: "POST" });
  setMessage("Review is now open for students.");
  await refresh();
}

onMounted(async () => {
  if (!hostToken.value) {
    error.value = "Missing host token. Open the session from the teacher banks page first.";
    return;
  }

  try {
    await refresh();
    await loadCurrentStats();
    syncClock();
    window.addEventListener("keydown", onProjectionKeydown);
    pollTimer = setInterval(() => {
      refresh()
        .then(() => {
          if (isClosed.value || isAnswering.value) {
            loadCurrentStats().catch(() => {});
          }
        })
        .catch(() => {});
    }, TEACHER_POLL_MS);
  } catch (e) {
    error.value = String(e);
  }
});

onUnmounted(() => {
  window.removeEventListener("keydown", onProjectionKeydown);
  if (pollTimer) clearInterval(pollTimer);
  stopClock();
  stopClosedSync();
});
</script>

<template>
  <TeacherLayout title="Session Control">
    <main class="mx-auto max-w-6xl px-4 pb-10 pt-4">
      <div
        v-if="state?.join_code"
        class="sticky top-0 z-10 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 shadow-sm"
      >
        <div>
          <p class="text-xs font-medium text-slate-600">本場測驗邀請碼</p>
          <p class="text-2xl font-bold tracking-[0.25em] text-indigo-700">{{ state.join_code }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button type="button" class="btn-secondary text-sm" @click="copyJoinCode">
            {{ joinCodeCopied ? "已複製" : "複製邀請碼" }}
          </button>
          <a
            :href="joinUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="text-sm text-indigo-600 underline"
          >
            學生加入連結
          </a>
        </div>
      </div>

      <p v-if="error" class="card mb-4 bg-red-50 text-red-800">{{ error }}</p>
      <p v-if="message" class="card mb-4 bg-green-50 text-green-800">{{ message }}</p>

      <section
        v-if="state && isLobby"
        class="mb-6 grid min-h-[72vh] gap-6 rounded-2xl bg-slate-950 px-6 py-8 text-white lg:grid-cols-[1.25fr_0.75fr]"
      >
        <div class="flex flex-col justify-between gap-6">
          <div class="space-y-4">
            <p class="text-sm uppercase tracking-[0.3em] text-indigo-200">Lobby</p>
            <h2 class="text-4xl font-semibold">Scan to join this quiz</h2>
            <p class="max-w-2xl text-lg text-slate-300">
              Let students join first, then begin the quiz to show the question stem.
            </p>
          </div>

          <div class="grid gap-4 sm:grid-cols-2">
            <div class="rounded-2xl bg-white/10 p-5">
              <p class="text-sm text-slate-300">Joined students</p>
              <p class="mt-2 text-4xl font-semibold">{{ participants.length }}</p>
            </div>
            <div class="rounded-2xl bg-white/10 p-5">
              <p class="text-sm text-slate-300">Questions</p>
              <p class="mt-2 text-4xl font-semibold">{{ state.total_questions }}</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <button type="button" class="btn-primary" @click="startQuizFromLobby">Begin Quiz</button>
          </div>
        </div>

        <div class="flex items-center justify-center">
          <div class="w-full max-w-md rounded-3xl bg-white p-6 text-slate-900 shadow-2xl">
            <JoinCodeCard :join-code="state.join_code" :join-url="joinUrl" />
          </div>
        </div>
      </section>

      <section v-if="summary && (isSummary || isReview)" class="card mb-6 space-y-4">
        <h2 class="text-lg font-semibold">Session Summary</h2>
        <div class="grid gap-4 md:grid-cols-4">
          <div class="rounded-xl bg-slate-50 p-4">
            <p class="text-sm text-slate-500">Participants</p>
            <p class="mt-1 text-2xl font-semibold">{{ summary.participant_count }}</p>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <p class="text-sm text-slate-500">Average Score</p>
            <p class="mt-1 text-2xl font-semibold">
              {{ summary.average_score }} / {{ summary.max_total_score }}
            </p>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <p class="text-sm text-slate-500">Average Rate</p>
            <p class="mt-1 text-2xl font-semibold">{{ summary.average_percentage }}%</p>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <p class="text-sm text-slate-500">Std. Dev.</p>
            <p class="mt-1 text-2xl font-semibold">{{ summary.score_stddev }}</p>
          </div>
        </div>

        <ScorePieChart
          v-if="summary.total_score_pie"
          title="Total Score Distribution"
          :labels="summary.total_score_pie.labels"
          :counts="summary.total_score_pie.counts"
          :colors="summary.total_score_pie.colors"
        />

        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b">
                <th class="py-2">Question</th>
                <th>Category</th>
                <th>Answer Rate</th>
                <th>Full Score</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in summary.question_rates || []"
                :key="item.question_id"
                class="border-b"
              >
                <td class="py-2">Q{{ item.question_index + 1 }}</td>
                <td class="max-w-xs truncate">{{ item.category }}</td>
                <td>{{ ((item.answer_rate || 0) * 100).toFixed(0) }}%</td>
                <td>{{ item.full_score_count }} / {{ item.submitted_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <button v-if="isSummary" class="btn-primary" @click="openReview">Open Review</button>
      </section>

      <section v-if="showQuestionBoard && state" class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px] xl:grid-cols-[minmax(0,1fr)_200px]">
        <div class="space-y-6">
          <section class="card space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-sm uppercase tracking-[0.2em] text-slate-500">Question</p>
                <h2 class="text-xl font-semibold">
                  第 {{ questionNumber }} 題 / {{ state.total_questions }}
                </h2>
                <p class="mt-1 text-sm text-slate-600">
                  {{ state.stem?.category || "Uncategorized" }} | {{ state.stem?.points }} 分
                </p>
              </div>
              <button
                v-if="!projectionOpen"
                type="button"
                class="btn-primary text-sm"
                @click="openProjection"
              >
                開啟投影視窗
              </button>
            </div>

            <p v-if="!projectionOpen" class="text-sm text-slate-500">
              題幹與計時器請使用投影視窗顯示；按上方按鈕或 Esc 收合後可在此操作。
            </p>

            <div v-if="isStem && !projectionOpen" class="flex justify-end">
              <button type="button" class="btn-primary" :disabled="actionBusy" @click="openOptions">
                {{ actionBusy ? "處理中…" : "Open Options & Start Timer" }}
              </button>
            </div>
          </section>

          <section v-if="isClosed" class="card space-y-4">
            <template v-if="questionStats">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <h3 class="text-lg font-semibold">Answer Distribution</h3>
                  <p class="text-sm text-slate-600">
                    {{ submittedCount }} / {{ questionStats.total_participants }} students submitted
                  </p>
                </div>
                <div class="text-right">
                  <p class="text-sm text-slate-500">Full score rate</p>
                  <p class="text-2xl font-semibold text-slate-900">
                    {{ ((questionStats.answer_rate || 0) * 100).toFixed(0) }}%
                  </p>
                </div>
              </div>

              <div class="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
                <ScorePieChart
                  v-if="questionStats.pie"
                  title="Current Question"
                  :labels="questionStats.pie.labels"
                  :counts="questionStats.pie.counts"
                  :colors="questionStats.pie.colors"
                />
                <div class="grid gap-3 sm:grid-cols-3">
                  <div class="rounded-xl bg-emerald-50 p-4 text-emerald-900">
                    <p class="text-sm">Full Score</p>
                    <p class="mt-1 text-2xl font-semibold">{{ questionStats.full_score_count }}</p>
                  </div>
                  <div class="rounded-xl bg-amber-50 p-4 text-amber-900">
                    <p class="text-sm">Submitted</p>
                    <p class="mt-1 text-2xl font-semibold">{{ submittedCount }}</p>
                  </div>
                  <div class="rounded-xl bg-slate-50 p-4 text-slate-900">
                    <p class="text-sm">Participants</p>
                    <p class="mt-1 text-2xl font-semibold">{{ questionStats.total_participants }}</p>
                  </div>
                </div>
              </div>
            </template>
            <p v-else class="text-sm text-slate-600">Loading answer statistics...</p>

            <div class="flex justify-end">
              <button
                v-if="canAdvance"
                type="button"
                class="btn-primary"
                @click="nextQuestion"
              >
                {{ isLastQuestion ? "Finish Quiz" : "Next Question" }}
              </button>
            </div>
          </section>
        </div>

        <aside class="teacher-sidebar w-full min-w-0 space-y-2 text-[11px] text-slate-600">
          <section class="rounded-lg border border-slate-200/80 bg-white p-2 shadow-sm space-y-1.5">
            <h3 class="text-xs font-semibold text-slate-900">Controls</h3>
            <p>
              Phase:
              <span class="font-medium text-slate-800">{{ state?.current_phase || "unknown" }}</span>
            </p>
            <div class="space-y-2">
              <label class="block text-slate-600">
                {{ isAnswering ? "增加秒數" : "計時（秒）" }}
              </label>
              <div class="flex flex-col gap-1.5">
                <input
                  v-model.number="timerInput"
                  type="number"
                  min="5"
                  class="teacher-sidebar-input w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                  @keyup.enter="isAnswering ? adjustTimer() : openOptions()"
                />
                <button
                  v-if="isStem"
                  type="button"
                  class="teacher-sidebar-btn btn-primary w-full"
                  :disabled="actionBusy"
                  @click="openOptions"
                >
                  {{ actionBusy ? "…" : "Open Options" }}
                </button>
                <button
                  v-else
                  type="button"
                  class="teacher-sidebar-btn btn-secondary w-full"
                  :disabled="!isAnswering || actionBusy"
                  @click="adjustTimer"
                >
                  {{ actionBusy ? "…" : "+ 時間" }}
                </button>
              </div>
              <p class="text-[10px] leading-snug text-slate-500">
                {{
                  isStem
                    ? "設定本題作答秒數，再開放選項開始倒數。"
                    : "將輸入的秒數加至目前剩餘時間，學生端下次輪詢會同步。"
                }}
              </p>
            </div>

            <div class="rounded-md bg-slate-50 px-2 py-1.5 text-[10px] leading-snug text-slate-600">
              測驗開始後無法中途加入；搶救僅限一次。
            </div>

            <div v-if="isQuizRunning" class="space-y-1.5 border-t border-slate-100 pt-1.5">
              <label class="block text-slate-600">搶救學號</label>
              <div class="flex flex-col gap-1.5">
                <input
                  v-model="rescueStudentNo"
                  placeholder="學號"
                  class="teacher-sidebar-input w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                  autocomplete="off"
                  @keyup.enter="rescueStudent()"
                />
                <button
                  type="button"
                  class="teacher-sidebar-btn btn-secondary w-full"
                  :disabled="actionBusy || !rescueStudentNo.trim()"
                  @click="rescueStudent"
                >
                  開放加入
                </button>
              </div>
            </div>
          </section>

          <section class="rounded-lg border border-slate-200/80 bg-white p-2 shadow-sm space-y-1.5">
            <div class="flex items-center justify-between gap-1">
              <h3 class="text-xs font-semibold text-slate-900">Students</h3>
              <span class="shrink-0 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-700">
                {{ participants.length }}
              </span>
            </div>

            <div class="max-h-36 space-y-1 overflow-auto">
              <div
                v-for="participant in participants"
                :key="participant.id"
                class="rounded-md border border-slate-200 px-1.5 py-1"
              >
                <p class="truncate font-medium text-slate-900">{{ participant.display_name }}</p>
                <p class="truncate text-slate-500">{{ participant.student_no }}</p>
                <p v-if="participant.rejoin_used" class="mt-0.5 text-[9px] text-amber-600">
                  已搶救
                </p>
              </div>
            </div>
          </section>
        </aside>
      </section>
    </main>

    <Teleport to="body">
      <div
        v-if="projectionOpen && showQuestionBoard && state"
        class="teacher-projection fixed inset-0 z-[200] flex flex-col bg-slate-950 text-white"
        role="dialog"
        aria-modal="true"
        aria-label="題幹投影"
      >
        <header class="flex shrink-0 flex-wrap items-start justify-between gap-4 border-b border-white/10 px-6 py-4 lg:px-10 lg:py-6">
          <div>
            <p class="text-sm uppercase tracking-[0.25em] text-indigo-300">Question</p>
            <h2 class="text-3xl font-semibold lg:text-4xl">
              第 {{ questionNumber }} 題 / {{ state.total_questions }}
            </h2>
            <p class="mt-1 text-base text-slate-300 lg:text-lg">
              {{ state.stem?.category || "Uncategorized" }} · {{ state.stem?.points }} 分
            </p>
          </div>
          <div class="min-w-[280px] flex-1 max-w-xl">
            <TimerBar
              v-if="isAnswering"
              large
              :remaining-sec="remainingSec"
              :total-sec="activeTimerTotal"
            />
            <p v-else class="text-lg text-slate-300 lg:text-xl">{{ phaseHintProjection }}</p>
          </div>
          <button
            type="button"
            class="rounded-lg border border-white/20 px-4 py-2 text-sm text-slate-200 hover:bg-white/10"
            @click="closeProjection"
          >
            收合 (Esc)
          </button>
        </header>

        <main class="flex min-h-0 flex-1 items-center justify-center overflow-auto px-6 py-8 lg:px-12 lg:py-10">
          <div class="teacher-stem-projection w-full max-w-6xl">
            <MathText
              v-if="state.stem"
              :content="state.stem.stem_text"
              block
              text-class="text-3xl lg:text-5xl xl:text-6xl leading-relaxed text-white"
            />
          </div>
        </main>

        <footer
          v-if="isStem || isClosed"
          class="flex shrink-0 flex-wrap items-center justify-center gap-3 border-t border-white/10 px-6 py-4"
        >
          <button
            v-if="isStem"
            type="button"
            class="btn-primary min-w-[240px]"
            :disabled="actionBusy"
            @click="openOptions"
          >
            {{ actionBusy ? "處理中…" : "Open Options & Start Timer" }}
          </button>
          <p v-if="isClosed" class="text-lg text-slate-300">計時已結束，請收合視窗查看統計。</p>
        </footer>
      </div>
    </Teleport>
  </TeacherLayout>
</template>

<style scoped>
.teacher-stem :deep(.katex) {
  font-size: 1.05em;
}

.teacher-stem :deep(.katex-display) {
  margin: 0.6em 0;
}

.teacher-stem-projection :deep(.katex) {
  font-size: 1.08em;
  color: #fff;
}

.teacher-stem-projection :deep(.katex-display) {
  margin: 0.75em 0;
}

.teacher-sidebar-btn {
  min-height: 1.75rem;
  padding: 0.25rem 0.5rem;
  font-size: 0.6875rem;
  line-height: 1rem;
  border-radius: 0.375rem;
}
</style>
