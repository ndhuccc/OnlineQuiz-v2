# E2E 測試（Playwright）

## 前置

1. **後端虛擬環境**（建議路徑 `backend/.venv`）：

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **前端依賴**：

   ```bash
   cd frontend
   npm install
   npx playwright install chromium
   ```

E2E 使用獨立資料庫 `data/e2e-quiz.db`（每次執行時由 `scripts/e2e-backend.bat` 重建並 migrate）。

## 執行

```bash
cd frontend
npm run test:e2e
```

**Windows PowerShell** 若出現「已停用指令碼執行」，請改用：

```cmd
cd frontend
npm.cmd run test:e2e
```

或專案根目錄：`scripts\test-e2e.bat`

互動模式：

```bash
npm run test:e2e:ui
```

## Python 路徑（Windows）

`frontend/e2e/resolve-python.mjs` 會依序嘗試：

1. 環境變數 **`PYTHON`**（完整路徑，最可靠）
2. `backend/.venv/Scripts/python.exe`
3. 專案根 `.venv/Scripts/python.exe`
4. `py -3`（Python Launcher）
5. PATH 上的 `python`

範例：

```powershell
$env:PYTHON = "C:\Users\ccchiang\Projects\OnlineQuiz-v2\backend\.venv\Scripts\python.exe"
cd frontend
npm run test:e2e
```

global-setup 會印出 `[e2e] 使用 Python: ...` 方便確認。

## 涵蓋情境

- 教師首頁、題庫頁載入
- API 建立題庫與場次 → 教師控制 → 學生加入、顯示選項、提交
- 題幹 KaTeX（`$...$`）渲染

## 注意

- `playwright.config.js` 會自動啟動 Django（`:5000`）與 Vite（`:5173`）。
- 非 CI 環境下，若埠已被占用會 **重用** 現有服務（`reuseExistingServer: true`）。
- 請使用 [python.org](https://www.python.org/downloads/) 安裝版，避免 Microsoft Store Python 占位程式。
