# notify-hub

將 Google Sheet 的財務摘要送到 Telegram。Apps Script 負責偵測與去重，部署在 PythonAnywhere 的 Flask API 負責驗證、預算計算、訊息格式化及 Telegram 發送。

## 資料來源

綁定的 Apps Script 會從 gid `543845934` 讀取：

| 範圍 | 內容 |
| --- | --- |
| `M2` | 總支出 |
| `N2` | 總收入 |
| `O2` | 結餘 |
| `P2:Q6` | 依序為交、食、日、保險、運及其金額 |

月預算固定為 €538，每週額度固定為 €100。第 22 日至月底一律視為第 4 週；週預算只扣除「日＋食」。

## 本機執行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export NOTIFY_API_SECRET='replace-with-a-long-random-secret'
export TELEGRAM_BOT_TOKEN='replace-with-bot-token'
export TELEGRAM_CHAT_ID='replace-with-chat-id'
flask --app app run
```

執行測試：

```bash
pytest
```

健康檢查：`GET /health`

通知 API：

```http
POST /notify
Content-Type: application/json
X-Notify-Secret: <shared-secret>

{
  "type": "budget_summary",
  "total_expense": -736.42,
  "total_income": 0,
  "balance": -736.42,
  "categories": {
    "交": 126,
    "食": 372.14,
    "日": 167.51,
    "保險": 5.8,
    "運": 64.97
  }
}
```

## Telegram 設定

1. 在 Telegram 對 `@BotFather` 傳送 `/newbot`，完成後保存 Bot Token。
2. 使用預定接收通知的帳號開啟新 Bot 並傳送任意訊息。
3. 開啟 `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`，從回應的 `message.chat.id` 取得 chat ID。
4. 不要將 Bot Token、chat ID 或 shared secret commit 到 repository。

## PythonAnywhere 部署

1. 建立免費帳號及新的 Flask Web App，將本專案上傳至 home directory。
2. 建立 virtualenv，執行 `pip install -r requirements.txt`，並在 Web 頁面指定該 virtualenv。
3. 在 Web App 的 WSGI configuration file 中，必須先設定環境變數，再 import app：

```python
import os
import sys

project_home = '/home/<username>/notify-hub'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['NOTIFY_API_SECRET'] = '<long-random-secret>'
os.environ['TELEGRAM_BOT_TOKEN'] = '<bot-token>'
os.environ['TELEGRAM_CHAT_ID'] = '<chat-id>'

from app import app as application
```

4. Reload Web App，先確認 `https://<username>.pythonanywhere.com/health` 回傳 `{"status":"ok"}`。
5. WSGI configuration file 含有機密資料，不應加入 repository 或貼到公開位置。

## Apps Script 安裝

1. 在目標 Sheet 選擇「擴充功能 → Apps Script」。
2. 將 `sheet-watchers/amount-tracker.gs` 貼入綁定專案。
3. 在「專案設定 → 指令碼屬性」加入：
   - `NOTIFY_API_URL`：`https://<username>.pythonanywhere.com/notify`
   - `NOTIFY_API_SECRET`：與 PythonAnywhere 相同的 shared secret
4. 儲存並重新整理 Sheet。
5. 從「Notify Hub」選單執行「安裝觸發器並立即推播」，完成 Google 授權。
6. 確認 Telegram 收到首次通知。之後相同的摘要不會重複發送。

Apps Script 的 installable edit trigger 處理人工輸入，change trigger補充工作表結構變更。API 只有在成功送出 Telegram 後，watcher 才會保存去重狀態。
