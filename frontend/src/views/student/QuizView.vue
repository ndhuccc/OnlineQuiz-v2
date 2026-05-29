<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import MathText from "@/components/MathText.vue";
import StudentLayout from "@/components/StudentLayout.vue";
import TimerBar from "@/components/TimerBar.vue";
import { mergeTimerFields, studentPollIntervalMs, usePhaseCountdown } from "@/composables/usePhaseCountdown";
import { authHeaders, clearClientToken, getClientToken, saveClientToken } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const phase = ref("join");
const joinCode = ref("");
const studentNo = ref("");
const displayName = ref("");
const state = ref(null);
const questionType = ref("single");
const options = ref([]);
const optionsRevealed = ref(false);
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

function currentPollIntervalMs() {
  return studentPollIntervalMs({
    isAnswering: isAnswering.value,
    optionsRevealed: optionsRevealed.value,
    submitted: submitted.value,
  });
}

const { remainingSec, syncClock, stopClock } = usePhaseCountdown(
  () => state.value,
  () => isAnswering.value,
);

const isRunning = computed(() => state.value?.status === "running");
const isLobbyWaiting = computed(() => state.value?.status === "lobby");
const isMultiple = computed(() => questionType.value === "multiple");
const isAnswering = computed(() => state.value?.current_phase === "options");
const isStem = computed(() => state.value?.current_phase === "stem");
const isClosed = computed(() => state.value?.current_phase === "closed");
const showActionPanel = computed(
  () =>
    Boolean(state.value) &&
    !submitted.value &&
    !isClosed.value &&
    (isLobbyWaiting.value || isRunning.value),
);
const canRevealOptions = computed(
  () => isAnswering.value && !optionsRevealed.value && !loadingOptions.value,
);
const canSubmit = computed(
  () => isAnswering.value && optionsRevealed.value && selectedIds.value.length > 0,
);
const questionNumber = computed(() => (state.value?.current_question_index ?? 0) + 1);

const statusHint = computed(() => {
  if (state.value?.status === "lobby") {
    return "測驗尚未開始，請等待教師指示。";
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
  if (phase.value !== "quiz" || !clientToken) return;
  pollTimer = setTimeout(async () => {
    await me().catch(() => {});
    scheduleNextPoll();
  }, currentPollIntervalMs());
}

function startPolling() {
  scheduleNextPoll();
}

function onVisibilityChange() {
  if (document.visibilityState === "visible" && phase.value === "quiz" && clientToken) {
    me().catch(() => {});
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
  startPolling();
  me().catch(() => {});
}

function resetQuestionUi() {
  optionsRevealed.value = false;
  options.value = [];
  selectedIds.value = [];
  submitted.value = false;
  message.value = "";
}

watch(
  () => [state.value?.current_phase, optionsRevealed.value, submitted.value],
  () => {
    if (phase.value === "quiz" && clientToken) {
      scheduleNextPoll();
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
  },
);

function leaveAndRejoin() {
  stopPolling();
  clearClientToken();
  clientToken = null;
  state.value = null;
  phase.value = "join";
  error.value = "";
  studentNo.value = "";
  displayName.value = "";
}

async function join() {
  error.value = "";
  joining.value = true;
  try {
    const res = await fetch("/api/sessions/join/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        join_code: joinCode.value.trim().toUpperCase(),
        student_no: studentNo.value.trim(),
        display_name: displayName.value.trim(),
      }),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "加入場次失敗。");
    clientToken = data.client_token;
    saveClientToken(clientToken);
    applyParticipantState({ ...data.session, has_answered: false });
    enterQuizPhase();
  } catch (e) {
    error.value = String(e.message || e);
  } finally {
    joining.value = false;
  }
}

async function me() {
  if (!clientToken) return;
  const seq = ++pollSeq;
  syncing.value = true;
  try {
    const res = await fetch("/api/participants/me/", {
      headers: authHeaders(clientToken),
    });
    if (seq !== pollSeq) return;
    if (res.status === 401 || res.status === 403) {
      clientToken = null;
      clearClientToken();
      stopPolling();
      phase.value = "join";
      state.value = null;
      error.value = "登入已失效，請重新輸入學號與姓名加入場次。";
      return;
    }
    const data = await parseJsonResponse(res).catch(() => null);
    if (seq !== pollSeq) return;
    if (!res.ok || !data) {
      error.value = data?.detail || "無法同步場次狀態，請稍後再試。";
      return;
    }
    error.value = "";
    const prevIndex = state.value?.current_question_index;
    applyParticipantState(data);
    if (data.current_question_index !== prevIndex) {
      resetQuestionUi();
      submitted.value = Boolean(data.has_answered);
    } else {
      submitted.value = Boolean(data.has_answered);
    }
  } finally {
    if (seq === pollSeq) syncing.value = false;
  }
}

async function revealOptions() {
  if (submitted.value || optionsRevealed.value || loadingOptions.value) return;
  if (!isAnswering.value) {
    error.value = "教師尚未開放選項，請稍候或按下方重新整理。";
    await me().catch(() => {});
    return;
  }
  error.value = "";
  loadingOptions.value = true;
  try {
    const res = await fetch("/api/participants/me/options/", {
      method: "POST",
      headers: authHeaders(clientToken),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "無法取得答案選項。");
    options.value = data.options;
    questionType.value = data.type;
    optionsRevealed.value = true;
    if (data.phase_timer_seconds != null) {
      activeTimerTotal.value = data.phase_timer_seconds;
      state.value = mergeTimerFields(state.value, data);
    }
    syncClock();
  } catch (e) {
    error.value = String(e);
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
  } catch (e) {
    error.value = String(e.message || e);
  }
}

onMounted(async () => {
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

  if (clientToken) {
    const resumed = await tryResumeSession();
    if (resumed) {
      enterQuizPhase();
      return;
    }
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
        <p class="text-sm text-slate-600">請輸入加入代碼、學號與姓名以加入本場測驗。</p>
        <input
          v-model="joinCode"
          placeholder="加入代碼"
          class="input-field uppercase tracking-widest"
          autocomplete="off"
        />
        <input
          v-model="studentNo"
          placeholder="學號"
          class="input-field"
          inputmode="numeric"
          autocomplete="username"
        />
        <input
          v-model="displayName"
          placeholder="姓名"
          class="input-field"
          autocomplete="name"
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

        <div v-if="showActionPanel" class="card space-y-3">
          <button
            type="button"
            class="btn-primary w-full min-h-[52px] text-base"
            :disabled="!canRevealOptions"
            @click="revealOptions().catch((e) => (error = String(e)))"
          >
            {{ loadingOptions ? "載入中..." : "取得答案選項" }}
          </button>
          <p v-if="isLobbyWaiting" class="text-center text-xs text-slate-500">
            測驗尚未開始，請等待教師按 Begin Quiz。
          </p>
          <p v-else-if="isStem" class="text-center text-xs text-slate-500">
            教師尚未開放選項，請先看投影幕上的題幹。
          </p>

          <div v-if="optionsRevealed && options.length" class="space-y-2">
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
          <p v-if="optionsRevealed && !selectedIds.length" class="text-center text-xs text-slate-500">
            請先選擇至少一個選項。
          </p>
        </div>

        <p v-if="submitted" class="card bg-green-50 text-green-800">{{ message }}</p>

        <router-link
          v-if="state?.status === 'review'"
          to="/student/review"
          class="btn-primary flex w-full items-center justify-center"
        >
          查看複習
        </router-link>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <button type="button" class="btn-secondary w-full text-sm" @click="leaveAndRejoin">
          重新加入（更換學號／姓名）
        </button>
      </section>
    </main>
  </StudentLayout>
</template>
