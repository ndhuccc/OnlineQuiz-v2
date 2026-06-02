# 題庫 JSON 匯入格式規格

| 項目 | 內容 |
|------|------|
| 版本 | v1.0 |
| 範例檔 | 專案根目錄 `questions.json` |

---

## 1. 檔案結構

匯入格式有**兩種**（皆可從「題庫管理」上傳）：

### 格式 A：完整物件（推薦，含題庫名稱與預設值）

```json
{
  "name": "線性代數題庫 A",
  "description": "期中考前複習題",
  "default_points": 1,
  "default_timer_seconds": 60,
  "questions": [
    {
      "node": "向量空間",
      "question_type": "Calculation",
      "format": "Single Choice",
      "question": "向量 $\\vec{v} = (3, 4)$ 的長度是？",
      "options": [
        "A. 5",
        "B. 7",
        "C. $\\sqrt{12}$",
        "D. 12"
      ],
      "correct_answer": "A",
      "explanation": "$\\|\\vec{v}\\| = \\sqrt{3^2+4^2} = \\sqrt{25} = 5$"
    }
  ]
}
```

`description`、`default_points`、`default_timer_seconds` 可省略，省略時採系統預設（`""`、`1.0`、`90`）。

### 格式 B：純題目陣列

```json
[
  {
    "node": "章節或知識點名稱",
    "question_type": "Calculation | Analysis | ...",
    "format": "Single Choice | Multiple Choice",
    "question": "題幹文字（可含 LaTeX，如 $x^2$）",
    "options": [
      "A. 選項 A 內容",
      "B. 選項 B 內容"
    ],
    "correct_answer": "B",
    "explanation": "解析文字（可含 LaTeX）"
  }
]
```

使用純陣列時，題庫名稱自動命名為「匯入題庫」，預設配分 1.0 分、計時 90 秒。可在「題庫管理」上傳前先用「Question bank name」欄位覆蓋名稱。

> 範例檔：[docs/sample-bank.json](sample-bank.json)（完整物件版，含 1 單選 + 1 多選示範）。

---

## 2. 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `node` | string | 是 | 題目所屬節點／章節，匯入後存為 `category` |
| `question_type` | string | 否 | 題目分類標籤（如 Calculation），供篩選統計 |
| `format` | string | 是 | `Single Choice` → 單選；`Multiple Choice` → 多選 |
| `question` | string | 是 | 題幹；支援 `$...$`、`$$...$$` LaTeX |
| `options` | string[] | 是 | 選項列表；**必須**以 `A.`、`B.` … 開頭（2–10 個） |
| `correct_answer` | string | 是 | 正確選項字母，如 `B` 或 `ABC`（順序不拘） |
| `explanation` | string | 否 | 解析；**純自動模式**只在複習階段顯示；**評量講解模式**每題關閉選項後立即顯示 |

### 1.1 題庫層級欄位（僅格式 A）

| 欄位 | 類型 | 預設 | 說明 |
|------|------|------|------|
| `name` | string | — | 題庫顯示名稱（1–255 字） |
| `description` | string | `""` | 題庫描述，純文字 |
| `default_points` | number | `1.0` | 每題預設配分（> 0） |
| `default_timer_seconds` | int | `90` | 每題預設計時秒數（5–3600） |

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

1. 教師從「題庫管理」上傳 JSON 檔案（必填，**不接受貼上內容**）。
2. 後端以 Pydantic 驗證結構 → 逐題解析 → 寫入 `question_banks` + `questions` + `options`。
3. 任何一題解析失敗：跳過該題（不擋整批），並在 `import_report.errors[]` 列出 `index` 與 `message`。
4. 全部題目都失敗 → 整個題庫刪除，匯入回傳 400。
5. **測驗時**：教師選擇已建好的題庫 → 選模式（純自動 / 評量講解）→ Start → 系統自 DB 載入該庫全部題目（依匯入順序）。

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
