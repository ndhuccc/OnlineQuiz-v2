export const DEV_BACKEND_HINT =
  "若用 scripts\\start.bat（:3080），請開 http://localhost:3080，或重啟 npm run dev（已代理到 :3080）。開發雙服務請執行 scripts\\restart-dev.bat（:5000 + :5173）。";

export async function parseJsonResponse(res) {
  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const preview = (await res.text()).replace(/\s+/g, " ").slice(0, 100);
    if (res.status === 500 && preview.includes("<!doctype")) {
      throw new Error(
        `API 代理失敗（HTTP 500）：前端 :5173 連不到後端。${DEV_BACKEND_HINT} 回應：${preview}`,
      );
    }
    throw new Error(
      `API 回傳 HTML 而非 JSON（HTTP ${res.status}）。${DEV_BACKEND_HINT} 回應：${preview}`,
    );
  }
  return res.json();
}
