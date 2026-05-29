/** @typedef {import('@playwright/test').APIRequestContext} APIRequestContext */

const API = "http://127.0.0.1:5000";

export const SAMPLE_BANK = {
  name: "E2E 題庫",
  default_points: 1,
  default_timer_seconds: 60,
  questions: [
    {
      node: "測試",
      format: "Single Choice",
      question: "若 $x=2$，則 $x^2$ 為何？",
      options: ["A. 2", "B. 4", "C. 6"],
      correct_answer: "B",
      explanation: "因為 $2^2=4$。",
    },
  ],
};

/**
 * @param {APIRequestContext} request
 */
export async function seedBank(request) {
  const res = await request.post(`${API}/api/question-banks/`, {
    data: SAMPLE_BANK,
  });
  if (!res.ok()) throw new Error(`seed bank failed: ${await res.text()}`);
  const body = await res.json();
  return body.id;
}

/**
 * @param {APIRequestContext} request
 * @param {number} bankId
 */
export async function createSession(request, bankId) {
  const res = await request.post(`${API}/api/sessions/`, {
    data: { bank_id: bankId },
  });
  if (!res.ok()) throw new Error(`create session failed: ${await res.text()}`);
  return res.json();
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {number} sessionId
 * @param {string} hostToken
 */
export async function setHostToken(page, sessionId, hostToken) {
  await page.goto("/teacher");
  await page.evaluate(
    ({ sessionId, hostToken }) => {
      const data = {};
      data[sessionId] = hostToken;
      localStorage.setItem("onlinequiz_host", JSON.stringify(data));
    },
    { sessionId, hostToken },
  );
}

/**
 * @param {APIRequestContext} request
 * @param {string} hostToken
 * @param {number} sessionId
 * @param {string} phase
 * @param {object} [extra]
 */
/**
 * @param {APIRequestContext} request
 * @param {string} joinCode
 * @param {string} studentNo
 */
export async function joinStudent(request, joinCode, studentNo = "E2001") {
  const res = await request.post(`${API}/api/sessions/join/`, {
    data: { join_code: joinCode, student_no: studentNo, display_name: "測試生" },
  });
  if (!res.ok()) throw new Error(`join failed: ${await res.text()}`);
  return res.json();
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {string} clientToken
 */
export async function setClientToken(page, clientToken) {
  await page.goto("/student/quiz");
  await page.evaluate((token) => {
    localStorage.setItem("onlinequiz_client_token", token);
  }, clientToken);
  await page.goto("/student/quiz", { waitUntil: "domcontentloaded" });
}

export async function setPhase(request, hostToken, sessionId, phase, extra = {}) {
  const res = await request.post(`${API}/api/sessions/${sessionId}/phase/`, {
    headers: { Authorization: `Bearer ${hostToken}` },
    data: { phase, ...extra },
    timeout: 60_000,
  });
  if (!res.ok()) throw new Error(`phase ${phase} failed: ${await res.text()}`);
}
