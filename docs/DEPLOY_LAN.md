# 校園區網部署指南（精簡版）

適用於 OnlineQuiz-v2 v0.6：**Django** + SQLite + Daphne，無 Redis／Nginx。

---

## 1. 需求

| 項目 | 建議 |
|------|------|
| 主機 | Windows 10/11 或 Linux 筆電／迷你 PC |
| Python | **3.11+**（安裝時勾選「Add to PATH」） |
| Node.js | 20 LTS（僅**建置前端**時需要；上課主機可只跑已 build 的 `dist`） |
| 網路 | 與學生同一教室 Wi-Fi；主機建議固定 IP |
| 規模 | 單場 ≤100 人 |

---

## 2. 安裝（首次）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt

python manage.py migrate

cd ../frontend
npm install
npm run build
```

於專案根目錄建立 `.env`：

```env
HOST=0.0.0.0
PORT=3080
LAN_BASE_URL=http://192.168.1.50:3080
DATABASE_URL=sqlite:///data/quiz.db
```

將 `192.168.1.50` 改為本機區網 IP。

---

## 3. 每次上課啟動

**Windows**：雙擊 `scripts/start.bat`

```bash
cd backend && .venv\Scripts\activate
python manage.py collectstatic --noinput
daphne -b 0.0.0.0 -p 3080 config.asgi:application
```

教師瀏覽器：`http://localhost:3080/teacher`  
學生同一 Wi-Fi 掃描 QR（`LAN_BASE_URL`）。

---

## 4. Windows 防火牆

允許 **Python** 或 **Waitress** 私人網路連線，或開放 **TCP 3080**。

---

## 5. 開發模式（非上課）

```bash
cd backend && python manage.py runserver 0.0.0.0:5000
```

另開終端：`cd frontend && npm run dev`（Vite 代理 `/api`、`/ws`）。

---

## 6. 備份

關閉服務後複製 `data/quiz.db`。

---

## 7. 常見問題

| 現象 | 處理 |
|------|------|
| 找不到模組 | 確認已 `activate` 虛擬環境並 `pip install -r requirements.txt` |
| 靜態頁 404 | 確認已 `npm run build`，且 Flask 指向 `frontend/dist` |
| WebSocket 失敗 | 使用 Daphne（勿用純 `runserver` 上正式課堂）；Channels 為 InMemoryLayer |
