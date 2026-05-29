# 題庫 JSON 匯入格式規格

| 項目 | 內容 |
|------|------|
| 版本 | v1.0 |
| 範例檔 | 專案根目錄 `questions.json` |

---

## 1. 檔案結構

檔案為 **JSON 陣列**，每個元素代表一題：

```json
[
  {
    "node": "章節或知識點名稱",
    "question_type": "Calculation | Analysis | ...",
    "format": "Multiple Choice | Single Choice",
    "question": "題幹文字（可含 LaTeX，如 $x^2$）",
    "options": [
      "A. 選項 A 內容",
      "B. 選項 B 內容"
    ],
    "correct_answer": "ABC",
    "explanation": "解析文字（可含 LaTeX）"
  }
]
```

---

## 2. 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `node` | string | 是 | 題目所屬節點／章節，匯入後存為 `category` |
| `question_type` | string | 否 | 題目分類標籤（如 Calculation），供篩選統計 |
| `format` | string | 是 | `Single Choice` → 單選；`Multiple Choice` → 多選 |
| `question` | string | 是 | 題幹；支援 `$...$`、`$$...$$` LaTeX |
| `options` | string[] | 是 | 選項列表；**必須**以 `A.`、`B.` … 開頭 |
| `correct_answer` | string | 是 | 正確選項字母，如 `B` 或 `ABC`（順序不拘） |
| `explanation` | string | 否 | 解析；測驗結束複習階段才對學生顯示 |

### 2.1 選項字母規則

- 前綴格式：`/^[A-Z]\.\s*/`（A–Z，匯入時解析字母與內文）
- 同一題內字母不可重複
- 建議 2–8 個選項（系統上限可設為 10）

### 2.2 題型對應

| `format` | 系統 `type` | `correct_answer` |
|----------|-------------|------------------|
| `Single Choice` | `single` | 單一字元，如 `B` |
| `Multiple Choice` | `multiple` | 多字元，如 `ABC` |

---

## 3. 匯入流程（系統行為）

1. 教師上傳 JSON 檔（或貼上內容）至「題庫管理」。
2. 後端以 Zod 驗證結構 → 逐題解析 → 寫入 `question_banks` + `questions` + `options`。
3. 可設定題庫層級預設：
   - `default_points`（預設配分，如 1 分）
   - `default_timer_seconds`（預設作答秒數，如 90）
4. 匯入報告：成功題數、跳過題數、錯誤列號與原因。
5. **測驗時**：教師選擇已建好的題庫 → 建立場次 → 系統自 DB 載入該庫全部題目（依匯入順序）。

---

## 4. LaTeX 處理

- 題幹、選項、解析**原樣儲存**於 DB。
- 前端以 **KaTeX** 渲染（`$...$` 行內、`$$...$$` 區塊）。
- 匯入時不將 LaTeX 轉 HTML；僅對非 LaTeX 的 HTML 標籤做消毒（若未來允許 HTML 混排）。

---

## 5. 驗證錯誤範例

| 情況 | 處理 |
|------|------|
| `correct_answer` 含不在 options 的字母 | 該題匯入失敗，列入錯誤報告 |
| `format` 不認得 | 匯入失敗 |
| 選項少於 2 個 | 匯入失敗 |
| 重複題庫名稱 | 提示覆蓋或重新命名 |
