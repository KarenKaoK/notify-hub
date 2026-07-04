# notify-hub

A reusable notification service that sends Google Sheets budget summaries to Telegram.

Google Forms supplies the source data, Google Sheets calculates the summary, a bound Apps Script detects updates, and a Flask API hosted on PythonAnywhere validates and formats each notification before delivering it through the Telegram Bot API.

## Architecture

```text
Google Form
    ↓ form submission
Google Sheet
    ↓ calculated summary
Bound Apps Script
    ↓ authenticated POST /notify
Flask on PythonAnywhere
    ↓ Telegram Bot API
Telegram
```

## Features

- Handles Google Form submissions, direct Sheet edits, and structural changes.
- Deduplicates unchanged summaries using Apps Script properties.
- Prevents concurrent duplicate sends with an Apps Script lock.
- Retries transient network errors, HTTP 429 responses, and server errors.
- Validates shared-secret authentication and request payloads.
- Calculates monthly and cumulative weekly budget balances.
- Uses `Decimal` with round-half-up currency precision.
- Keeps the Telegram Bot Token and recipient chat ID server-side.
- Provides a lightweight health endpoint for deployment checks.

## Data contract

The bound watcher reads the following cells from the configured sheet:

| Range | Value |
| --- | --- |
| `M2` | Total expenses |
| `N2` | Total income |
| `O2` | Balance |
| `P2:Q7` | Category names and amounts for 交, 食, 日, 保險, 運; `P2:Q2` may be a header row, and missing categories default to 0 |

The current budget policy is fixed in `budget_calculator.py`:

- Monthly budget: EUR 538
- Weekly base allowance: EUR 100
- Budget timezone: `Europe/Berlin`
- Days 22 through the end of the month remain week 4
- Weekly spending includes only the 食 and 日 categories

## API

### Health check

```http
GET /health
```

```json
{"status": "ok"}
```

### Send a notification

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

Successful response:

```json
{"status": "ok", "message_id": 12345}
```

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

export NOTIFY_API_SECRET='replace-with-a-long-random-secret'
export TELEGRAM_BOT_TOKEN='replace-with-bot-token'
export TELEGRAM_CHAT_ID='replace-with-chat-id'

flask --app app run
```

Run the tests:

```bash
pytest
```

Do not commit real credentials. The application reads all secrets from environment variables, while the Apps Script reads the API URL and shared secret from Script Properties.

## Project structure

```text
notify-hub/
├── app.py
├── budget_calculator.py
├── telegram_sender.py
├── requirements.txt
├── requirements-dev.txt
├── sheet-watchers/
│   └── amount-tracker.gs
├── tests/
├── OPERATIONS_GUIDE.zh-TW.md
├── notify-hub-project-guide.md
└── notify-hub-project-guide.html
```

## Documentation

- [Traditional Chinese operations and deployment guide](OPERATIONS_GUIDE.zh-TW.md)
- [Actual deployment configuration notes (Traditional Chinese)](DEPLOYMENT_SETUP_NOTES.zh-TW.md)
- [Complete project record and implementation guide (Markdown)](notify-hub-project-guide.md)
- [Complete project record and implementation guide (HTML)](notify-hub-project-guide.html)

## Security

- Never commit the Telegram Bot Token, chat ID, or shared API secret.
- Keep the recipient chat ID fixed on the server instead of accepting arbitrary request values.
- Rotate both the WSGI environment value and Apps Script property if the shared secret is exposed.
- Revoke and replace the Bot Token through BotFather if it is exposed.

## License

No license has been specified for this project.
