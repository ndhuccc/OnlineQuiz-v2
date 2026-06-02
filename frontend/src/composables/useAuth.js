const HOST_KEY = "onlinequiz_host";
const CLIENT_KEY = "onlinequiz_client_token";
const LOGIN_KEY = "onlinequiz_login";

export function saveHostSession(sessionId, hostToken) {
  const data = JSON.parse(localStorage.getItem(HOST_KEY) || "{}");
  data[sessionId] = hostToken;
  localStorage.setItem(HOST_KEY, JSON.stringify(data));
}

export function getHostToken(sessionId) {
  const data = JSON.parse(localStorage.getItem(HOST_KEY) || "{}");
  return data[sessionId] || null;
}

export function saveClientToken(token) {
  localStorage.setItem(CLIENT_KEY, token);
}

export function clearClientToken() {
  localStorage.removeItem(CLIENT_KEY);
}

export function getClientToken() {
  return localStorage.getItem(CLIENT_KEY);
}

export function authHeaders(hostOrClient) {
  if (hostOrClient) {
    return { Authorization: `Bearer ${hostOrClient}` };
  }
  return {};
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
