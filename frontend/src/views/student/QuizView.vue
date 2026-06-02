<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import MathText from "@/components/MathText.vue";
import StudentLayout from "@/components/StudentLayout.vue";
import TimerBar from "@/components/TimerBar.vue";
import { mergeTimerFields, studentLobbyPollIntervalMs, studentPollIntervalMs, usePhaseCountdown } from "@/composables/usePhaseCountdown";
import { authHeaders, clearClientToken, getClientToken, getTabId, saveClientToken, getLoginSession } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const router = useRouter();
const phase = ref("join");
const joinCode = ref("");
const studentNo = ref("");
const displayName = ref("");
const state = ref(null);

const isLoggedInStudent = computed(() => {
  const session = getLoginSession();
  return session && session.role === "student";
});
const questionResult = ref(null);  // { correct_answer, your_answer, score, is_full_score, explanation_text, ... }
const questionType = ref("single");
const options = ref([]);
const optionsRevealed = ref(false);
const revealedQuestionId = ref(null);
const selectedIds = ref([]);
const message = ref("");
const error = ref("");
const submitted = ref(false);
const joining = ref(false);
const loadingOptions = ref(false);
const activeTimerTotal = ref(90);
const syncing = ref(false);

let clientToken = getClientToken();
let pollTimer = null;
let pollSeq = 0;

function isLobbyPolling() {
  return phase.value === "quiz" && Boolean(clientToken) && isLobbyWaiting.value;
}

function isTimerPolling() {
  return (
    phase.value === "quiz" &&
    Boolean(clientToken) &&
    isAnswering.value &&
    optionsRevealed.value &&
    !submitted.value
  );
}

function shouldPoll() {
  return isLobbyPolling() || isTimerPolling();
}

function currentPollIntervalMs() {
  if (isLobbyPolling()) return studentLobbyPollIntervalMs();
  return studentPollIntervalMs();
}

const { remainingSec, syncClock, stopClock } = usePhaseCountdown(
  () => state.value,
  () => isAnswering.value && optionsRevealed.value && !submitted.value,
);

const isRunning = computed(() => state.value?.status === "running");
const isLobbyWaiting = computed(() => state.value?.status === "lobby");
const isSummary = computed(() => state.value?.status === "summary");
const isReviewOpen = computed(() => state.value?.status === "review");
const isMultiple = computed(() => questionType.value === "multiple");
const isAnswering = computed(() => state.value?.current_phase === "options");
const isStem = computed(() => state.value?.current_phase === "stem");
const isClosed = computed(() => state.value?.current_phase === "closed");
const isBeforeStart = computed(
  () =>
    state.value &&
    state.value.current_question_index != null &&
    state.value.start_question_index != null &&
    state.value.current_question_index < state.value.start_question_index,
);
const showRevealButton = computed(
  () =>
    Boolean(state.value) &&
    !isReviewOpen.value &&
    !isBeforeStart.value &&
    ((isRunning.value && !isLobbyWaiting.value) || isSummary.value),
);
const showAnswerPanel = computed(
  () => Boolean(state.value) && isRunning.value && !isLobbyWaiting.value && optionsRevealed.value,
);
const canSubmit = computed(
  () =>
    isAnswering.value &&
    optionsRevealed.value &&
    !submitted.value &&
    selectedIds.value.length > 0,
);
const questionNumber = computed(() => (state.value?.current_question_index ?? 0) + 1);

const statusHint = computed(() => {
  if (state.value?.status === "lobby") {
    return "測驗尚未開始，請等待教師指示。";
  }
  if (isBeforeStart.value) {
    return "此題已於您加入前結束，無法作答。請等待目前開放的題目。";
  }
  if (isReviewOpen.value) {
    return "測驗已結束，複習已自動開放。請按下 Open Review 查看成績與解析。";
  }
  if (isSummary.value) {
    return "測驗已結束，複習即將自動開放。";
  }
  if (isStem.value) {
    return "請看投影幕上的題目，題幹不會顯示在此裝置。";
  }
  if (isAnswering.value && !optionsRevealed.value && !submitted.value) {
    return "作答時間開始！請先按下「取得答案選項」。";
  }
  if (isAnswering.value && optionsRevealed.value && !submitted.value) {
    return "選擇答案後按下「提交答案」。";
  }
  if (submitted.value) {
    return "已提交答案，請等待教師繼續。";
  }
  if (isClosed.value) {
    return "本題已結束，請等待教師進入下一題。";
  }
  return "請跟隨教師進度。";
});

function applyParticipantState(data) {
  if (!data) return;
  state.value = mergeTimerFields(
    {
      ...data,
      session_id: data.session_id ?? data.session?.session_id,
    },
    data,
  );
  if (data.question?.type) {
    questionType.value = data.question.type;
  }
  if (data.question?.timer_seconds) {
    activeTimerTotal.value = data.question.timer_seconds;
  }
  if (isAnswering.value && data.phase_timer_seconds != null) {
    activeTimerTotal.value = data.phase_timer_seconds;
  }
  submitted.value = Boolean(data.has_answered);
  syncClock();
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function scheduleNextPoll() {
  stopPolling();
  if (!shouldPoll()) return;
  pollTimer = setTimeout(async () => {
    if (!shouldPoll()) return;
    await pollFromServer().catch(() => {});
    scheduleNextPoll();
  }, currentPollIntervalMs());
}

function startPolling() {
  scheduleNextPoll();
}

function onVisibilityChange() {
  if (document.visibilityState === "visible" && shouldPoll()) {
    pollFromServer().catch(() => {});
  }
}

async function tryResumeSession(expectedJoinCode = "") {
  if (!clientToken) return false;
  syncing.value = true;
  try {
    const res = await fetch("/api/participants/me/", {
      headers: authHeaders(clientToken),
    });
    if (res.status === 401 || res.status === 403) return false;
    const data = await parseJsonResponse(res).catch(() => null);
    if (!res.ok || !data) return false;
    if (expectedJoinCode && data.join_code?.toUpperCase() !== expectedJoinCode.toUpperCase()) {
      return false;
    }
    applyParticipantState(data);
    return true;
  } finally {
    syncing.value = false;
  }
}

function enterQuizPhase() {
  phase.value = "quiz";
  me()
    .catch(() => {})
    .finally(() => {
      if (shouldPoll()) startPolling();
    });
}

function resetQuestionUi() {
  optionsRevealed.value = false;
  revealedQuestionId.value = null;
  options.value = [];
  selectedIds.value = [];
  submitted.value = false;
  message.value = "";
  questionResult.value = null;
}

async function fetchQuestionResult() {
  if (!clientToken) return;
  try {
    const res = await fetch("/api/participants/me/question_result/", {
      headers: authHeaders(clientToken),
    });
    if (res.status === 403) {
      // 還沒到 closed 階段，不算 error
      questionResult.value = null;
      return;
    }
    if (!res.ok) {
      return;
    }
    const data = await parseJsonResponse(res);
    questionResult.value = data.question;
  } catch (e) {
    // 網路問題不擋流程
  }
}

function isSameOptionSet(previous, next) {
  if (!previous?.length || !next?.length) return false;
  if (previous.length !== next.length) return false;
  return previous.every((opt, index) => opt.id === next[index]?.id);
}

watch(
  () => [isLobbyWaiting.value, isAnswering.value, optionsRevealed.value, submitted.value],
  () => {
    if (shouldPoll()) {
      startPolling();
    } else {
      stopPolling();
    }
  },
);

watch(
  () => state.value?.current_phase,
  (currentPhase, prevPhase) => {
    if (currentPhase !== prevPhase) {
      resetQuestionUi();
    }
    syncClock();
    // MANUAL 模式：closed 後自動拿本題結果顯示
    if (currentPhase === "closed") {
      fetchQuestionResult();
    }
  },
);

watch(
  () => state.value?.current_question_index,
  (newIdx, oldIdx) => {
    // 換題時清掉結果
    if (newIdx !== oldIdx) {
      questionResult.value = null;
    }
  },
);

function leaveAndRejoin() {
  stopPolling();
  clearClientToken();
  clientToken = null;
  state.value = null;
  phase.value = "join";
  error.value = "";
  joinCode.value = "";
  // Re-populate student info from login session for logged-in students
  const session = getLoginSession();
  if (session && session.role === "student") {
    studentNo.value = session.identifier || "";
    displayName.value = session.display_name || "";
  } else {
    studentNo.value = "";
    displayName.value = "";
  }
}

// Expose helper for resetters in template
defineExpose({ leaveAndRejoin });

async function join() {
  error.value = "";
  joining.value = true;
  try {
    const session = getLoginSession();
    const headers = { "Content-Type": "application/json" };
    if (session && session.token) {
      headers["Authorization"] = `Bearer ${session.token}`;
    }
    const res = await fetch("/api/sessions/join/", {
      method: "POST",
      headers,
      body: JSON.stringify({
        join_code: joinCode.value.trim().toUpperCase(),
        student_no: studentNo.value.trim(),
        display_name: displayName.value.trim(),
        tab_id: getTabId() || "",
      }),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "加入場次失敗。");
    clientToken = data.client_token;
    const participantId = data.participant?.id;
    saveClientToken(clientToken, participantId);
    applyParticipantState({ ...data.session, has_answered: false });
    enterQuizPhase();
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    joining.value = false;
  }
}

async function fetchParticipantState({ showSyncing = true } = {}) {
  if (!clientToken) return null;
  const seq = ++pollSeq;
  if (showSyncing) syncing.value = true;
  try {
    const res = await fetch("/api/participants/me/", {
      headers: authHeaders(clientToken),
    });
    if (seq !== pollSeq) return null;
    if (res.status === 401 || res.status === 403) {
      clientToken = null;
      clearClientToken();
      stopPolling();
      phase.value = "join";
      state.value = null;
      error.value = "登入已失效，請重新輸入學號與姓名加入場次。";
      return null;
    }
    if (res.status === 409) {
      // 另一個分頁已接管此測驗
      clientToken = null;
      clearClientToken();
      stopPolling();
      phase.value = "join";
      state.value = null;
      error.value = "另一個分頁已接管此測驗，請重新加入。";
      return null;
    }
    const data = await parseJsonResponse(res).catch(() => null);
    if (seq !== pollSeq) return null;
    if (!res.ok || !data) {
      if (showSyncing) {
        error.value = data?.detail || "無法同步場次狀態，請稍後再試。";
      }
      return null;
    }
    if (showSyncing) error.value = "";
    return data;
  } finally {
    if (seq === pollSeq && showSyncing) syncing.value = false;
  }
}

function applyParticipantAnswerState(data) {
  const prevIndex = state.value?.current_question_index;
  applyParticipantState(data);
  if (data.current_question_index !== prevIndex) {
    resetQuestionUi();
  }
  submitted.value = Boolean(data.has_answered);
}

async function me() {
  const data = await fetchParticipantState({ showSyncing: true });
  if (!data) return;
  applyParticipantAnswerState(data);
}

async function pollFromServer() {
  const data = await fetchParticipantState({ showSyncing: false });
  if (!data) return;
  if (isLobbyPolling() || data.status !== state.value?.status) {
    applyParticipantAnswerState(data);
    return;
  }
  const prevIndex = state.value?.current_question_index;
  const prevPhase = state.value?.current_phase;
  if (data.current_question_index !== prevIndex || data.current_phase !== prevPhase) {
    applyParticipantAnswerState(data);
    return;
  }
  state.value = mergeTimerFields(state.value, data);
  submitted.value = Boolean(data.has_answered);
  syncClock();
}

async function revealOptions() {
  if (loadingOptions.value) return;
  if (!clientToken) return;
  error.value = "";
  loadingOptions.value = true;
  const previousOptions = options.value;
  const wasSubmitted = submitted.value;
  try {
    const meData = await fetchParticipantState({ showSyncing: false });
    if (!meData) return;
    applyParticipantAnswerState(meData);

    if (meData.status === "review") {
      message.value = "教師已開放複習，請查看成績與解析。";
      stopPolling();
      return;
    }

    if (meData.current_phase !== "options") {
      message.value = isSummary.value
        ? "測驗已結束，教師尚未開放複習，請稍候再試。"
        : isClosed.value
          ? "本題已結束，請等待教師進入下一題。"
          : "教師尚未開放選項，請稍候。";
      return;
    }

    const res = await fetch("/api/participants/me/options/", {
      method: "POST",
      headers: authHeaders(clientToken),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) {
      if (res.status === 403) {
        message.value = data.detail || "此題已結束，無法取回選項。";
        return;
      }
      throw new Error(data.detail || "無法取得答案選項。");
    }
    const newOptions = data.options ?? [];
    const isStillSameQuestion =
      isSameOptionSet(previousOptions, newOptions) ||
      (revealedQuestionId.value != null &&
        data.question_id != null &&
        revealedQuestionId.value === data.question_id);

    options.value = newOptions;
    questionType.value = data.type;
    optionsRevealed.value = true;
    revealedQuestionId.value = data.question_id ?? null;
    selectedIds.value = [];

    if (isStillSameQuestion && wasSubmitted) {
      submitted.value = true;
      stopPolling();
    } else {
      submitted.value = false;
      message.value = "";
      startPolling();
    }

    if (data.phase_timer_seconds != null) {
      activeTimerTotal.value = data.phase_timer_seconds;
      state.value = mergeTimerFields(state.value, data);
    }
    syncClock();
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    loadingOptions.value = false;
  }
}

function toggleOption(id) {
  if (submitted.value) return;
  if (isMultiple.value) {
    const index = selectedIds.value.indexOf(id);
    if (index >= 0) selectedIds.value.splice(index, 1);
    else selectedIds.value.push(id);
  } else {
    selectedIds.value = [id];
  }
}

async function submit() {
  if (!optionsRevealed.value || submitted.value) return;
  error.value = "";
  try {
    const res = await fetch("/api/participants/me/answers/", {
      method: "POST",
      headers: { ...authHeaders(clientToken), "Content-Type": "application/json" },
      body: JSON.stringify({ option_ids: selectedIds.value }),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "提交失敗。");
    submitted.value = true;
    message.value = "已送出答案，請等待教師繼續。";
    stopPolling();
  } catch (e) {
    error.value = String(e.message || e);
  }
}

onMounted(async () => {
  const session = getLoginSession();
  if (session && session.role === "student") {
    studentNo.value = session.identifier || "";
    displayName.value = session.display_name || "";
  } else {
    router.replace("/login?next=" + encodeURIComponent(location.pathname + location.search));
    return;
  }

  const params = new URLSearchParams(location.search);
  const urlCode = params.get("code")?.trim().toUpperCase() || "";
  if (urlCode) joinCode.value = urlCode;

  document.addEventListener("visibilitychange", onVisibilityChange);

  clientToken = getClientToken();
  if (urlCode) {
    if (clientToken) {
      const resumed = await tryResumeSession(urlCode);
      if (resumed) {
        enterQuizPhase();
        return;
      }
      clearClientToken();
      clientToken = null;
    }
    phase.value = "join";
    return;
  }

  // No join code in URL — always require student to enter the code
  // even if they have a previous clientToken (ensures correct session)
  if (clientToken) {
    clearClientToken();
    clientToken = null;
  }
  phase.value = "join";
});

onUnmounted(() => {
  document.removeEventListener("visibilitychange", onVisibilityChange);
  stopPolling();
  stopClock();
});
</script>

<template>
  <StudentLayout :title="phase === 'join' ? '加入測驗' : '作答'">
    <main class="mx-auto max-w-lg px-4 pb-8 pt-4">
      <section v-if="phase === 'join'" class="card space-y-4">
        <p class="text-sm text-slate-600">
          {{ isLoggedInStudent ? "請輸入加入代碼，系統已自動為您填寫學號與姓名。" : "請輸入加入代碼、學號與姓名以加入本場測驗。" }}
        </p>
        <input
          v-model="joinCode"
          placeholder="加入代碼"
          class="input-field uppercase tracking-widest"
          autocomplete="off"
        />
        <input
          v-model="studentNo"
          placeholder="學號"
          class="input-field disabled:bg-slate-100 disabled:text-slate-500 disabled:cursor-not-allowed"
          inputmode="numeric"
          autocomplete="username"
          :disabled="isLoggedInStudent"
        />
        <input
          v-model="displayName"
          placeholder="姓名"
          class="input-field disabled:bg-slate-100 disabled:text-slate-500 disabled:cursor-not-allowed"
          autocomplete="name"
          :disabled="isLoggedInStudent"
        />
        <button
          class="btn-primary w-full"
          :disabled="joining || !joinCode.trim() || !studentNo.trim() || !displayName.trim()"
          @click="join().catch((e) => (error = String(e)))"
        >
          {{ joining ? "加入中..." : "加入測驗" }}
        </button>
        <p v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
      </section>

      <section v-else-if="!state" class="card space-y-3 text-center text-slate-600">
        <p>{{ syncing ? "正在同步場次狀態…" : "正在連線…" }}</p>
        <button type="button" class="btn-secondary w-full" @click="me().catch(() => {})">立即重新整理</button>
      </section>

      <section v-else class="space-y-4">
        <div class="card space-y-3">
          <p class="text-sm text-slate-600">
            第 {{ questionNumber }} 題
            <span v-if="state?.total_questions">/ {{ state.total_questions }}</span>
            <span class="mx-1">|</span>
            <span class="font-medium text-indigo-700">
              {{
                isLobbyWaiting
                  ? "大廳等候"
                  : isReviewOpen
                    ? "複習開放"
                    : isSummary
                      ? "測驗結束"
                      : isStem
                        ? "題幹階段"
                        : isAnswering
                          ? "作答中"
                          : isClosed
                            ? "本題結束"
                            : state?.status
              }}
            </span>
          </p>
          <TimerBar
            v-if="isAnswering"
            :remaining-sec="remainingSec"
            :total-sec="activeTimerTotal"
          />
          <p class="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            {{ statusHint }}
          </p>
        </div>

        <div v-if="isLobbyWaiting" class="card text-center text-sm text-slate-600">
          已成功加入，請等待教師開始測驗。
        </div>

        <div v-if="isSummary && !isReviewOpen" class="card text-center text-sm text-slate-600">
          測驗已全部結束，複習即將自動開放…
        </div>

        <div v-if="showRevealButton" class="card space-y-3">
          <button
            type="button"
            class="btn-primary w-full min-h-[52px] text-base"
            :disabled="loadingOptions"
            @click="revealOptions().catch((e) => (error = String(e)))"
          >
            {{ loadingOptions ? "載入中..." : "取得答案選項" }}
          </button>
          <p v-if="isStem" class="text-center text-xs text-slate-500">
            教師尚未開放選項，請先看投影幕上的題幹。
          </p>
        </div>

        <div v-if="showAnswerPanel && !submitted" class="card space-y-3">
          <div v-if="options.length" class="space-y-2">
            <button
              v-for="opt in options"
              :key="opt.id"
              type="button"
              class="min-h-[52px] w-full rounded-xl border-2 px-4 py-3 text-left transition active:scale-[0.99]"
              :class="
                selectedIds.includes(opt.id)
                  ? 'border-indigo-600 bg-indigo-50 shadow-sm'
                  : 'border-slate-200 bg-white'
              "
              @click="toggleOption(opt.id)"
            >
              <span
                class="mr-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 font-bold text-indigo-700"
              >
                {{ opt.display_letter }}
              </span>
              <MathText :content="opt.label_text" class="inline" />
            </button>
          </div>

          <button
            type="button"
            class="btn-primary w-full min-h-[52px] text-base"
            :disabled="!canSubmit"
            @click="submit().catch((e) => (error = String(e)))"
          >
            提交答案
          </button>
          <p v-if="!selectedIds.length" class="text-center text-xs text-slate-500">
            請先選擇至少一個選項。
          </p>
        </div>

        <p v-if="submitted" class="card bg-green-50 text-green-800">{{ message }}</p>

        <section v-if="questionResult" class="card space-y-3 border-2 border-indigo-200">
          <div class="flex items-center justify-between">
            <h3 class="text-base font-semibold text-slate-900">本題結果</h3>
            <span
              class="rounded-full px-3 py-1 text-sm font-bold"
              :class="questionResult.is_full_score ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'"
            >
              {{ questionResult.is_full_score ? '✓ 答對' : '✗ 答錯' }} ·
              {{ questionResult.score }} / {{ questionResult.points }} 分
            </span>
          </div>

          <div v-if="questionResult.stem_text" class="rounded-lg bg-slate-50 p-3 text-sm text-slate-800">
            <MathText :content="questionResult.stem_text" />
          </div>

          <ul v-if="questionResult.options && questionResult.options.length" class="space-y-1 text-sm">
            <li
              v-for="opt in questionResult.options"
              :key="opt.id"
              class="flex items-start gap-2 rounded border px-2 py-1"
              :class="opt.is_your_answer && opt.is_correct
                ? 'border-green-300 bg-green-50'
                : opt.is_your_answer
                  ? 'border-red-300 bg-red-50'
                  : opt.is_correct
                    ? 'border-green-300 bg-green-50/50'
                    : 'border-slate-200'"
            >
              <span class="font-mono font-bold">{{ opt.letter }}.</span>
              <span class="flex-1">
                <MathText :content="opt.label_text" />
              </span>
              <span v-if="opt.is_your_answer" class="text-xs text-slate-600">（你的）</span>
              <span v-if="opt.is_correct" class="text-xs font-semibold text-green-700">正解</span>
            </li>
          </ul>

          <div v-if="questionResult.your_answer" class="text-sm">
            <span class="text-slate-500">你的答案：</span>
            <span
              class="ml-1 font-mono font-bold"
              :class="questionResult.is_full_score ? 'text-green-700' : 'text-red-700'"
            >
              {{ questionResult.your_answer }}
            </span>
            <span v-if="!questionResult.is_full_score" class="ml-3 text-slate-500">
              正解：<span class="font-mono font-bold text-green-700">{{ questionResult.correct_answer }}</span>
            </span>
          </div>
          <div v-else class="text-sm text-slate-500">（未作答 / 逾時自動交卷）</div>

          <details v-if="questionResult.explanation_text" class="rounded-lg bg-slate-50 p-3 text-sm">
            <summary class="cursor-pointer text-slate-700 font-medium">解析</summary>
            <div class="mt-2 text-slate-700">
              <MathText :content="questionResult.explanation_text" />
            </div>
          </details>
        </section>

        <router-link
          v-if="isReviewOpen"
          to="/student/review"
          class="btn-primary flex w-full min-h-[52px] items-center justify-center text-base"
        >
          Open Review
        </router-link>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="button" class="btn-secondary w-full text-sm" @click="leaveAndRejoin">
          重新加入（更換學號／姓名）
        </button>
      </section>
    </main>
  </StudentLayout>
</template>
