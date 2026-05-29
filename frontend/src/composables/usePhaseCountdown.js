import { computed, onUnmounted, ref } from "vue";

/** 依 phase_remaining_seconds 或 phase_started_at + phase_timer_seconds 計算剩餘秒數 */
export function computePhaseRemainingSeconds(session, nowMs = Date.now()) {
  if (session?.phase_remaining_seconds != null) {
    return session.phase_remaining_seconds;
  }
  if (!session?.phase_started_at || session.phase_timer_seconds == null) {
    return null;
  }
  const startedAt = new Date(session.phase_started_at).getTime();
  if (Number.isNaN(startedAt)) {
    return null;
  }
  const elapsed = Math.floor((nowMs - startedAt) / 1000);
  return Math.max(0, session.phase_timer_seconds - elapsed);
}

/**
 * 輪詢時以後端 phase_remaining_seconds 校正錨點；
 * 兩次輪詢之間以本地每秒遞減顯示。
 */
export function usePhaseCountdown(getSession, getIsActive) {
  const anchorRemaining = ref(null);
  const anchorMs = ref(0);
  const totalSec = ref(90);
  const nowMs = ref(Date.now());
  let clockTimer = null;

  function stopClock() {
    if (clockTimer) {
      clearInterval(clockTimer);
      clockTimer = null;
    }
    anchorRemaining.value = null;
  }

  function syncClock() {
    const active = getIsActive();
    const session = getSession();
    if (!active || !session) {
      stopClock();
      return;
    }

    const remaining = computePhaseRemainingSeconds(session, Date.now());
    if (remaining == null) {
      stopClock();
      return;
    }

    anchorRemaining.value = remaining;
    anchorMs.value = Date.now();
    if (session.phase_timer_seconds != null) {
      totalSec.value = session.phase_timer_seconds;
    }

    if (!clockTimer) {
      nowMs.value = Date.now();
      clockTimer = setInterval(() => {
        nowMs.value = Date.now();
      }, 1000);
    }
  }

  const remainingSec = computed(() => {
    if (!getIsActive() || anchorRemaining.value == null) {
      return null;
    }
    void nowMs.value;
    const elapsed = Math.floor((nowMs.value - anchorMs.value) / 1000);
    return Math.max(0, anchorRemaining.value - elapsed);
  });

  onUnmounted(stopClock);

  return { remainingSec, totalSec, syncClock, stopClock };
}

/** 合併計時相關欄位（phase_changed / timer_adjusted / refresh） */
export function mergeTimerFields(state, data) {
  if (!data) return state;
  return {
    ...state,
    phase_started_at: data.phase_started_at ?? state?.phase_started_at,
    phase_timer_seconds:
      data.phase_timer_seconds != null ? data.phase_timer_seconds : state?.phase_timer_seconds,
    phase_remaining_seconds:
      data.phase_remaining_seconds != null
        ? data.phase_remaining_seconds
        : state?.phase_remaining_seconds,
  };
}

/** 學生端大廳等候輪詢間隔（偵測教師是否開始測驗） */
export function studentLobbyPollIntervalMs() {
  return 2_000;
}

/** 學生端計時同步輪詢間隔（僅在作答中且已取得選項、尚未提交時使用） */
export function studentPollIntervalMs() {
  return 10_000 + Math.floor(Math.random() * 5_001);
}
