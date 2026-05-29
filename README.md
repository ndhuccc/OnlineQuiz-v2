# OnlineQuiz-v2

教室區網線上測驗系統（Django + Vue 3）。教師控場、學生手機作答、即時統計與複習。

## 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Flask、Django ORM、DRF serializers、SQLite、Waitress |
| 前端 | Vue 3、Vite、Tailwind、KaTeX、Chart.js |
| 同步 | HTTP 輪詢（教師／學生端每 2 秒），**不使用 WebSocket** |
| 部署 | 校園區網單機（見 [docs/DEPLOY_LAN.md](docs/DEPLOY_LAN.md)） |

## 環境需求

- **Python 3.11+**（[python.org](https://www.python.org/downloads/) 安裝，勾選 **Add python.exe to PATH**）
- **Node.js 20 LTS**（前端開發與建置）
- Windows 使用者請勿使用 Microsoft Store 的 Python 占位程式；若 `python` 無法執行，可改用 `py -3`

---

## 快速開始（開發）

### 1. 後端

**PowerShell（Windows）：**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python run_flask.py
```

**macOS / Linux：**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python run_flask.py
```

> 虛擬環境建議放在 `backend/.venv`（與 `scripts/start.bat` 一致）。

### 2. 前端（另開終端）

```bash
cd frontend
npm install
npm run dev
```

### 3. 開啟瀏覽器

| 角色 | 網址 |
|------|------|
| 教師首頁 | http://localhost:5173/teacher |
| 題庫管理 | http://localhost:5173/teacher/banks |
| 學生加入 | http://localhost:5173/student/quiz |
| API 健康檢查 | http://127.0.0.1:5000/api/health/ |

Vite 會將 `/api` 代理到後端 `:5000`。

---

## 匯入範例題庫

專案根目錄的 `questions.json` 含 LaTeX 公式（`$...$`）。

**指令匯入：**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py import_questions ..\questions.json --name "線性代數題庫"
```

**網頁匯入：** 教師端 → [題庫管理](http://localhost:5173/teacher/banks) → 上傳 JSON。

格式說明見 [docs/QUESTION_BANK_JSON.md](docs/QUESTION_BANK_JSON.md)。

---

## 課堂測驗流程（開發環境）

1. **題庫** → 匯入或選擇題庫 → **開場**
2. **教師控制頁** → 投影 QR／加入代碼 → 等待學生加入 → **開始測驗**
3. 每題：**題幹** → **開放選項**（可調計時）→ 學生「顯示答案選項」→ 作答提交 → **結束本題** → 查看統計 → **下一題**
4. 全部結束後 → **開放學生複習** → 學生端檢視成績與解析（含 KaTeX）

---

## 測試

### 後端單元測試（pytest）

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

### 前端 E2E（Playwright）

需先完成後端虛擬環境與 `frontend` 的 `npm install`。

```powershell
cd frontend
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

**PowerShell 若出現「已停用指令碼執行」**：請用 `npm.cmd` / `npx.cmd`，不要直接打 `npm`（會載入 `npm.ps1`）。或從專案根目錄：

```cmd
scripts\test-e2e.bat
```

Playwright 會自動：

- 使用 `data/e2e-quiz.db`（獨立測試資料庫）
- 啟動 Flask（`:5000`）與 Vite（`:5173`）

互動除錯：`npm run test:e2e:ui`

詳見 [docs/E2E.md](docs/E2E.md)。

#### Windows：指定 Python 路徑

若自動偵測失敗，可設定環境變數後再跑 E2E：

```powershell
$env:PYTHON = "C:\Users\你\backend\.venv\Scripts\python.exe"
cd frontend
npm run test:e2e
```

解析順序：`PYTHON` → `backend/.venv` → 專案根 `.venv` → `py -3` → PATH 上的 `python`。

---

## 區網正式上課

建置前端並以 Waitress + Flask 單埠服務：

```powershell
cd frontend
npm install
npm run build

cd ..\backend
.\.venv\Scripts\Activate.ps1
python manage.py collectstatic --noinput
waitress-serve --host=0.0.0.0 --port=3080 run_flask:app
```

或使用 `scripts\start.bat`。完整步驟見 [docs/DEPLOY_LAN.md](docs/DEPLOY_LAN.md)。

於專案根目錄 `.env` 設定區網 IP，供 QR Code 使用：

```env
LAN_BASE_URL=http://192.168.1.50:3080
```

---

## 常見問題（Windows）

| 問題 | 處理方式 |
|------|----------|
| `python` 開啟 Microsoft Store | 安裝 [python.org](https://www.python.org/downloads/) 並勾選 PATH；或改用 `py -3` |
| 無法執行 `Activate.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `npm` 提示已停用指令碼執行 | 改用 **`npm.cmd run test:e2e`**，或執行 **`scripts\test-e2e.bat`**（見下方） |
| E2E 找不到 Python | 確認 `backend\.venv\Scripts\python.exe` 存在，或設定 `$env:PYTHON` |
| 學生無法連線 | 確認同一 Wi-Fi；防火牆允許 Python / 埠 3080 |
| 公式未顯示 | 題庫文字需含 `$...$` 或 `$$...$$`；重新整理頁面 |

---

## 文件

| 文件 | 說明 |
|------|------|
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | 系統設計書 |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | 實作計畫與進度 |
| [docs/QUESTION_BANK_JSON.md](docs/QUESTION_BANK_JSON.md) | 題庫 JSON 格式 |
| [docs/DEPLOY_LAN.md](docs/DEPLOY_LAN.md) | 校園區網部署 |
| [docs/E2E.md](docs/E2E.md) | Playwright E2E |

## 授權

依專案維護者設定為準。
