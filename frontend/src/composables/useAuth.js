const HOST_KEY = "onlinequiz_host";
const CLIENT_KEY = "onlinequiz_client_token";
const PARTICIPANT_ID_KEY = "onlinequiz_participant_id";
const LOGIN_KEY = "onlinequiz_login";
const TAB_KEY = "onlinequiz_tab_id";

/** 為每個瀏覽器分頁產生固定 UUID；存在 sessionStorage，分頁關閉即消失。 */
function getOrCreateTabId() {
  if (typeof sessionStorage === "undefined") return null;
  let tid = sessionStorage.getItem(TAB_KEY);
  if (!tid) {
    tid =
      (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
    sessionStorage.setItem(TAB_KEY, tid);
  }
  return tid;
}

export function getTabId() {
  return getOrCreateTabId();
}

export function saveHostSession(sessionId, hostToken) {
  const data = JSON.parse(localStorage.getItem(HOST_KEY) || "{}");
  data[sessionId] = hostToken;
  localStorage.setItem(HOST_KEY, JSON.stringify(data));
}

export function getHostToken(sessionId) {
  const data = JSON.parse(localStorage.getItem(HOST_KEY) || "{}");
  return data[sessionId] || null;
}

export function saveClientToken(token, participantId) {
  localStorage.setItem(CLIENT_KEY, token);
  if (participantId != null) {
    localStorage.setItem(PARTICIPANT_ID_KEY, String(participantId));
  }
}

export function clearClientToken() {
  localStorage.removeItem(CLIENT_KEY);
  localStorage.removeItem(PARTICIPANT_ID_KEY);
}

export function getClientToken() {
  return localStorage.getItem(CLIENT_KEY);
}

export function getParticipantId() {
  return localStorage.getItem(PARTICIPANT_ID_KEY);
}

/** 每次 request 帶上 client_token + tab_id + participant_id 給 server 驗證多分頁狀態。 */
export function authHeaders(hostOrClient) {
  const headers = {};
  if (hostOrClient) {
    headers.Authorization = `Bearer ${hostOrClient}`;
  }
  const tid = getOrCreateTabId();
  if (tid) {
    headers["X-Tab-Id"] = tid;
  }
  const pid = getParticipantId();
  if (pid) {
    headers["X-Participant-Id"] = pid;
  }
  return headers;
}

export function saveLoginSession(session) {
  localStorage.setItem(LOGIN_KEY, JSON.stringify(session));
}

export function getLoginSession() {
  try {
    return JSON.parse(localStorage.getItem(LOGIN_KEY) || "null");
  } catch {
    return null;
  }
}

export function clearLoginSession() {
  localStorage.removeItem(LOGIN_KEY);
}
