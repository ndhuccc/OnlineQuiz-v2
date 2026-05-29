# OnlineQuiz-v2 實作計畫書

| 項目 | 內容 |
|------|------|
| 版本 | **v0.6**（**Django** 後端，已開工） |
| 日期 | 2026-05-29 |
| 預估總工期 | 約 **7–8 週**（1 人全職） |
| 前置文件 | [系統設計書 v0.6](./SYSTEM_DESIGN.md)、[題庫 JSON 格式](./QUESTION_BANK_JSON.md) |

---

## 後端定案

**Django 5** + DRF + Channels（InMemoryChannelLayer）+ SQLite + Daphne + WhiteNoise

---

## Phase 0 狀態

| 項目 | 狀態 |
|------|------|
| Django 專案 `backend/config`、`quiz` | ✅ |
| `GET /api/health/` | ✅ |
| WebSocket `/ws/quiz/` echo / ping | ✅ |
| `quiz/services/grading.py` + pytest | ✅ |
| Vue 3 前端骨架（教師/學生路由） | ✅ |
| `scripts/start.bat`、`.env.example` | ✅ |

## Phase 1 狀態

| 項目 | 狀態 |
|------|------|
| Models：`QuestionBank`、`Question`、`Option` | ✅ |
| Pydantic 驗證 + `import_json.py` | ✅ |
| `POST/GET/DELETE /api/question-banks/` | ✅ |
| API 不回傳 `is_correct` | ✅ |
| `manage.py import_questions` | ✅ |
| 教師端 `/teacher/banks` 匯入頁 | ✅ |
| pytest（匯入 + API） | ✅ |

---

## Phase 2 + 2b 狀態

| 項目 | 狀態 |
|------|------|
| Models：Session、Participant、Answer、OptionShuffle | ✅ |
| 場次 API（建立、加入、start/phase/next/timer） | ✅ |
| WebSocket `/ws/session/:id/` | ✅ |
| 選項亂序、提交批閱 | ✅ |
| 程序內計時、逾時自動提交 | ✅ |
| 教師控制頁、學生作答頁（基礎） | ✅ |
| pytest 場次流程 | ✅ |

## Phase 5 + 6 狀態

| 項目 | 狀態 |
|------|------|
| 單題得分圓餅圖（滿分/部分/零分） | ✅ |
| WS `session:question_stats` | ✅ |
| 測驗總結（總分分布、各題答對率） | ✅ |
| 開放複習 API | ✅ |
| 學生複習頁 | ✅ |
| Chart.js 教師端圖表 | ✅ |

## 後續優化（已完成）

| 項目 | 狀態 |
|------|------|
| KaTeX 題幹／選項／解析渲染（`MathText.vue`） | ✅ |
| Playwright E2E（`frontend/e2e/`） | ✅ |
| UI：版面、QR、計時條、觸控按鈕 | ✅ |
| E2E 說明 | `docs/E2E.md` |

詳見先前各 Phase 任務說明；實作路徑僅保留 **Django** 分支。

---

## 專案結構

```
OnlineQuiz-v2/
├── backend/          # Django
├── frontend/         # Vue 3
├── data/             # quiz.db
├── scripts/
└── docs/
```

---

## 下一步

執行 **Phase 1**：題庫 models + `questions.json` 匯入。
