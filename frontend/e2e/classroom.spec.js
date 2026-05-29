import { expect, test } from "@playwright/test";
import {
  createSession,
  joinStudent,
  SAMPLE_BANK,
  seedBank,
  setClientToken,
  setHostToken,
  setPhase,
} from "./helpers.js";

test.describe.configure({ mode: "serial" });

test.describe("課堂測驗流程", () => {
  test("健康檢查與題庫頁", async ({ page }) => {
    await page.goto("/teacher");
    await expect(page.getByRole("heading", { name: "教師首頁" })).toBeVisible();
    await page.goto("/teacher/banks");
    await expect(page.getByRole("heading", { name: "題庫管理" })).toBeVisible();
  });

  test("完整流程：開場 → 學生作答 → 教師控制", async ({ page, request }) => {
    test.setTimeout(120_000);

    const bankId = await seedBank(request);
    const session = await createSession(request, bankId);
    const { id: sessionId, join_code: joinCode, host_token: hostToken } = session;

    const startRes = await request.post(`http://127.0.0.1:5000/api/sessions/${sessionId}/start/`, {
      headers: { Authorization: `Bearer ${hostToken}` },
    });
    expect(startRes.ok()).toBeTruthy();

    const joinData = await joinStudent(request, joinCode, `E${Date.now()}`);
    await setPhase(request, hostToken, sessionId, "options", { timer_seconds: 60 });

    const student = await page.context().newPage();
    await setClientToken(student, joinData.client_token);
    await expect(student.getByText(/第\s*1\s*題/)).toBeVisible({ timeout: 15_000 });
    await expect(student.getByRole("button", { name: "顯示答案選項" })).toBeVisible({
      timeout: 15_000,
    });
    await student.getByRole("button", { name: "顯示答案選項" }).click();
    await student.locator("button").filter({ hasText: /^[A-D]\./ }).first().click();
    await student.getByRole("button", { name: "提交答案" }).click();
    await expect(student.getByText("已送出")).toBeVisible();

    await setPhase(request, hostToken, sessionId, "closed");
    await student.close();

    await setHostToken(page, sessionId, hostToken);
    await page.goto(`/teacher/session/${sessionId}`);
    await expect(page.locator(".text-4xl").filter({ hasText: joinCode })).toBeVisible();
    await page.getByRole("button", { name: "載入本題統計" }).click();
    await expect(page.getByText("得分分布")).toBeVisible({ timeout: 10_000 });
  });

  test("KaTeX 渲染題幹", async ({ page, request }) => {
    const bankId = await seedBank(request);
    const session = await createSession(request, bankId);

    await request.post(`http://127.0.0.1:5000/api/sessions/${session.id}/start/`, {
      headers: { Authorization: `Bearer ${session.host_token}` },
    });
    await setPhase(request, session.host_token, session.id, "stem");

    await setHostToken(page, session.id, session.host_token);
    await page.goto(`/teacher/session/${session.id}`);
    await expect(page.locator(".katex").first()).toBeVisible({ timeout: 10_000 });
    expect(SAMPLE_BANK.questions[0].question).toContain("$");
  });
});
