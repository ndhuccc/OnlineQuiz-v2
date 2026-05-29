/**
 * 解析 E2E / Playwright 使用的 Python 直譯器。
 * 優先順序：PYTHON 環境變數 → backend/.venv → 專案根 .venv → py -3 → PATH 上的 python
 */
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * @param {string} projectRoot OnlineQuiz-v2 專案根目錄
 * @returns {string} 可執行的 python 路徑或指令名稱
 */
export function resolvePython(projectRoot) {
  const candidates = [];

  if (process.env.PYTHON?.trim()) {
    candidates.push(process.env.PYTHON.trim());
  }

  if (process.platform === "win32") {
    candidates.push(
      path.join(projectRoot, "backend", ".venv", "Scripts", "python.exe"),
      path.join(projectRoot, ".venv", "Scripts", "python.exe"),
    );
    try {
      const py = execSync('py -3 -c "import sys; print(sys.executable)"', {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
      if (py && fs.existsSync(py)) candidates.push(py);
    } catch {
      /* py launcher 不可用 */
    }
    candidates.push("python");
  } else {
    candidates.push(
      path.join(projectRoot, "backend", ".venv", "bin", "python"),
      path.join(projectRoot, ".venv", "bin", "python"),
      "python3",
      "python",
    );
  }

  for (const c of candidates) {
    if (c === "python" || c === "python3") {
      try {
        execSync(`"${c}" -c "import sys"`, { stdio: "ignore" });
        return c;
      } catch {
        continue;
      }
    }
    if (fs.existsSync(c)) return c;
  }

  throw new Error(
    [
      "找不到可用的 Python。請先建立後端虛擬環境：",
      "  cd backend",
      "  python -m venv .venv",
      "  .venv\\Scripts\\activate    # Windows",
      "  pip install -r requirements.txt",
      "",
      "或設定環境變數 PYTHON 指向 python.exe 完整路徑。",
      "Windows 請使用 python.org 安裝版，並勾選 Add to PATH（勿用 Microsoft Store 占位程式）。",
    ].join("\n"),
  );
}
