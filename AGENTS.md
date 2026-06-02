# OnlineQuiz-v2 — Project Notes

## Backend architecture: 兩套 API handler（必讀）

**坑點**：這個專案的 `/api/sessions/`（以及所有 `/api/...` 路由）有**兩套實作**，瀏覽器只會打到其中一套。

- **DRF view** — `backend/quiz/api/session_views.py`（掛在 `config/urls.py`，由 `manage.py runserver` port 8000 服務）。**只給 pytest 用**。
- **Flask handler** — `backend/run_flask.py`（port 5000，Vite 把 `/api/*` proxy 過來）。**這才是瀏覽器實際打到的**。

修任何 session 端點時，**兩個檔案都要改**。我之前只改 DRF，Flask 端 session_create 還是用舊的 `bank_id` 邏輯，silently 忽略 `mode` 欄位，前端選「評量講解」永遠被降成 AUTO。

驗證方法：直接打 port 5000 的 `POST /api/sessions/`，看 response 有沒有新欄位。

## Flask 沒開 auto-reload

`run_flask.py:825` 用 `app.run(host=..., port=..., threaded=True)`，**沒 `debug=True` 也沒 `use_reloader=True`**。改後端程式碼後**必須手動重啟 Flask**：

```powershell
# 找到占用 5000 的 PID 並殺掉
netstat -ano | Select-String ":5000.*LISTENING" | ForEach-Object {
    ($_ -replace ".*\s+(\d+)$", '$1')
} | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force }

# 重啟
cd backend
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "run_flask.py" `
  -RedirectStandardOutput "flask.log" -RedirectStandardError "flask.err" `
  -WindowStyle Hidden
```

（不建議在 dev 開 auto-reload：multi-process 會跟 pytest 搶 DB state。）

## Product Modes (重要)

這個專案規劃有兩種測驗模式，**目前只有「純自動模式」實作**，「評量與講解模式」是未來 roadmap。

### 1. 純自動模式（current, 唯一實作）
- 老師啟動測驗後**全自動跑完**：第一題 → 計時 → 收尾 → 下一題 → ... → 最後一題 → 自動開複習
- 老師**不介入**測驗過程（不講解、不按下一題）
- 學生交卷後看到的是「請等待」狀態，不需要任何老師決策
- 收尾觸發：計時逾時 OR 全員提交（任一成立就收）
- 進入下一題的決策**應該在 server**——老師的瀏覽器不該是必要條件

### 2. 評量與講解模式（manual, 已實作 2026-06-02）

老師逐題控制流程：每題 STEM → OPTIONS → CLOSED → 講解 → 下一題。

**Server FSM 行為**：
- `start_session()` 在 MANUAL 模式停在 STEM（不自動開 options），老師必須按「開放選項」
- `next_question()` 在 MANUAL 模式保持新題的 STEM（不自動開 options）
- `_close_options_phase()` 在 MANUAL 模式不排程 auto-advance
- `set_phase("closed", ...)` 走 `_set_phase_locked` 在 MANUAL 也不排程

**API 契約**：
- Submit response 仍回 `is_full_score` + `score`（**立即評分**）
- 新端點 `GET /api/participants/me/question_result/`
  - STEM / OPTIONS 階段回 403「本題尚未結束」（避免洩題）
  - CLOSED / REVIEW 回傳正解 + your_answer + 分數 + 解析
- `start_session()` 在 MANUAL 設 `current_phase=STEM`（AUTO 直接 OPTIONS）

**前端契約**：
- QuizView：phase 變 CLOSED 時自動 fetch `/question_result/` 顯示在卡片
  - 顯示「答對/答錯」徽章、your_answer、correct_answer（錯才顯示正解）、解釋（KaTeX）
- SessionView：sticky header 有 mode 徽章（純自動/評量講解），投影文字依 mode 變化
  - MANUAL + STEM: 「題幹階段，準備好請按『開放選項』」
  - MANUAL + CLOSED: 「本題已結束，學生可看結果。講解完畢請按『下一題』」
- 「開放選項 & 開始計時」按鈕在 MANUAL 模式是**必按**（不是選用）

**測試**：`test_manual_mode.py` 8 個案例（DRF test client，含 STEM/OPTIONS 403 gate、CLOSE 後可看、錯答、下一題仍 STEM、解析文字）。`test_session_mode.py` 3 個 mode 欄位測試。`test_auto_advance.py` 已涵蓋 MANUAL 不 auto-advance。

## 架構特性

- **Backend**: Flask (run_flask.py, 單埠) + Django ORM (models/migrations) + SQLite
- **DRF view layer (`quiz/api/views.py` + `quiz/api/urls.py`) 是 dead code**——run_flask.py 用原生 Flask route 全部重寫，只借用 DRF Serializer 做 input validation
- **WebSocket 模組是 dead code**（`consumers.py` + `routing.py`）——`services/broadcast.py` 是空殼
- **同步策略**: HTTP 輪詢（教師 3-10s, 學生 2-15s），不是 WebSocket
- **計時**: 後端有 `phase_ends_at` 在 DB，背景 thread 每秒掃逾時
- **倒數顯示**: 前端用 `usePhaseCountdown` composable，後端 phase_remaining_seconds 為錨，本地每秒 tick

## 已知 dead code / 待清理 backlog

- `Participant.rejoin_allowed` 欄位：寫了但 join_session() 從未檢查
- `rescue_participant` 服務 + `/api/sessions/{id}/rescue/` API + SessionView 救援按鈕：被 auto-rejoin 取代，純死碼
- `Participant.rejoin_used`：限制一生只能 rejoin 一次，但實際上沒人檢查這個限制在 lobby 階段的意義——只在 session 內有效。配合上面的「auto-rejoin 取代 rescue」，這個欄位也該拿掉
- 計時跑完的 auto-close 沒呼叫 `next_question()`：FSM 收尾後停在 `closed` 等老師前端 watch。但純自動模式不該依賴老師前端存活

## 學生 rejoin / multi-tab 設計決策（2026-06-02）

使用者明確決定：
- ❌ 拿掉「一生只能 rejoin 一次」限制（`rejoin_used` 死碼）
- ❌ 拿掉 rescue 機制（老師同意才能 rejoin 的設計）
- ✅ **必須**防止學生用多個瀏覽器分頁進入同一場測驗
  - 現有隱式保護：每次 rejoin 重生 `client_token`，舊 token 立刻失效 → 401
  - 但 UX 不夠明確（舊分頁只是莫名其妙被登出）
  - 建議改成顯式契約：例如 `last_seen_at` + 409 Conflict 提示「其他分頁正在使用」

## join_session() 的 rejoin 契約（2026-06-02 修補）

`join_session()` 對**既有** participant 一律允許 rejoin（不管 lobby 還是 running）：

- **lobby rejoin**：client_token 掉了（關分頁、清 localStorage）的學生能重新取得 token。`start_question_index` 保持 0，`joined_at` 保留不重設。
- **mid-quiz rejoin**：`start_question_index` 設為當前題，避免看到/補交之前的題。
- **新學號 mid-quiz**：仍拒絕（"測驗進行中，無法新加入"）。

**重要**：原本 `if existing: raise "此學號已加入本場次"` 這個寫法是**錯誤的**——它把 lobby 階段的 rejoin 也擋掉了。Rescue 機制原本只補 mid-quiz 缺口，沒覆蓋 lobby。**拿掉 rescue 後一定要把 lobby rejoin 也打開**，否則使用者會卡死（手動驗證時親身踩到）。

## FSM auto-advance 設計洞（2026-06-02）

純自動模式下，server 才是 timer 唯一真理來源，但目前 `next_question()` 由老師前端的 `maybeAutoAdvanceQuestion()` 觸發——意思是老師瀏覽器關掉就卡住。

修正方向（影響核心 FSM，**須先寫測試**）：
- 將 auto-advance 決定權搬回 server
- `_close_options_phase()` 改成可傳 `auto_advance: bool`：
  - `recover_expired_timers()` 逾時 → `auto_advance=True`（給 grace 3-5s）
  - `try_close_options_if_all_answered()` 全員提交 → `auto_advance=True`
- 加 `session.mode` 欄位區分 `auto` / `manual`，為未來「評量與講解模式」預留
- 純自動模式不需要「Hold」按鈕
