# OnlineQuiz-v2 — Project Notes

## Product Modes (重要)

這個專案規劃有兩種測驗模式，**目前只有「純自動模式」實作**，「評量與講解模式」是未來 roadmap。

### 1. 純自動模式（current, 唯一實作）
- 老師啟動測驗後**全自動跑完**：第一題 → 計時 → 收尾 → 下一題 → ... → 最後一題 → 自動開複習
- 老師**不介入**測驗過程（不講解、不按下一題）
- 學生交卷後看到的是「請等待」狀態，不需要任何老師決策
- 收尾觸發：計時逾時 OR 全員提交（任一成立就收）
- 進入下一題的決策**應該在 server**——老師的瀏覽器不該是必要條件

### 2. 評量與講解模式（future, 未實作）
- 老師逐題開放
- 學生提交 → 立即評分（學生端可看對錯）
- 老師講解
- 老師按「下一題」繼續
- 需要手動 pacing，需要 session mode flag 區分

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

## FSM auto-advance 設計洞（2026-06-02）

純自動模式下，server 才是 timer 唯一真理來源，但目前 `next_question()` 由老師前端的 `maybeAutoAdvanceQuestion()` 觸發——意思是老師瀏覽器關掉就卡住。

修正方向（影響核心 FSM，**須先寫測試**）：
- 將 auto-advance 決定權搬回 server
- `_close_options_phase()` 改成可傳 `auto_advance: bool`：
  - `recover_expired_timers()` 逾時 → `auto_advance=True`（給 grace 3-5s）
  - `try_close_options_if_all_answered()` 全員提交 → `auto_advance=True`
- 加 `session.mode` 欄位區分 `auto` / `manual`，為未來「評量與講解模式」預留
- 純自動模式不需要「Hold」按鈕
