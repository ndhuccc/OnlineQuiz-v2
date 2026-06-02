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
LAN_BASE_URL=http://134.208.64.172:3080
DATABASE_URL=sqlite:///data/quiz.db
```

將 `134.208.64.172` 改為你實際對外可達的 IP 或網域名稱。

---

## 3. 每次上課啟動

**Windows**：雙擊 `scripts/start.bat`

```bash
cd backend && .venv\Scripts\activate
python manage.py collectstatic --noinput
daphne -b 0.0.0.0 -p 3080 config.asgi:application
```

教師瀏覽器：`http://134.208.64.172:3080/teacher`  
學生掃描 QR 或直接開 `LAN_BASE_URL`。

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

---

## 8. 外網存取（可選）

如果你要讓**不在同一個區網**的裝置也能連線，這套系統可以用下面兩種方式：

### 8.1 最簡單：Tailscale / ZeroTier

1. 在主機安裝 Tailscale（或 ZeroTier），並讓主機與外部裝置加入同一個虛擬網路。
2. 用虛擬網路分配的 IP 存取服務：
	- 前端 / Teacher / Student / Login：`http://134.208.64.172:3080`
	- Django Admin：`http://134.208.64.172:8000/admin/`
3. 將 `.env` 的 `LAN_BASE_URL` 改成對外可達的位址，例如：

```env
LAN_BASE_URL=http://134.208.64.172:3080
PUBLIC_BASE_URL=http://134.208.64.172:3080
```

這種方式不需要路由器做埠轉發，適合臨時遠端測試或教學。

### 8.2 公網直連：路由器埠轉發

1. 在路由器上把 `3080`、`8000` 轉發到主機。
2. Windows 防火牆允許對應埠的 TCP 連線。
3. 將 `.env` 的 `LAN_BASE_URL` 設成公網可達的 URL，例如：

```env
LAN_BASE_URL=http://134.208.64.172:3080
PUBLIC_BASE_URL=http://134.208.64.172:3080
```

4. 注意：如果前端、API、Admin 都要從外網使用，請確認所有入口都改成公網位址，不要再使用 `localhost` 或 `127.0.0.1`。

### 8.3 補充

- `PUBLIC_BASE_URL` 主要影響學生加入連結與 QR Code。
- 目前的開發模式仍以本機 / 區網為主；若要正式對外提供服務，建議改用穩定的主機、TLS、強密碼與防火牆規則。
