# EqWell

EqWell is a role-based student wellbeing platform built with Flask + FastAPI + a Chrome Extension. It provides:

- Student mood, quiz, profile, counselling, and task workflows.
- Institutional dashboards for warden, counsellor, developer, parent, and proctor roles.
- Consent-first browser signal collection through a Chrome Manifest V3 extension.
- Stress/risk signal analysis using Hugging Face emotion inference and Groq refinement.
- Optional Google Fit integration for step/sleep context in student risk scoring.

## 1. Architecture overview

At runtime on Vercel:

1. All standard web routes are served by Flask (`application/app.py`) through `api/index.py`.
2. Stress-analysis API routes (`/extension-analyze`, `/health`) are served by FastAPI (`application/stress_api.py`) through `api/stress_api.py`.
3. Chrome extension calls authenticated Flask endpoints under `/api/extension/student/*`.
4. Server stores state/events in SQLite (`eqwell_scores.db`, `/tmp/eqwell_scores.db` on Vercel).

## 2. Repository structure

```text
EqWell/
  api/
    index.py                 # Vercel entrypoint -> Flask app
    stress_api.py            # Vercel entrypoint -> FastAPI app

  application/
    app.py                   # Main Flask app (web + extension APIs + integrations)
    stress_api.py            # Dedicated FastAPI service
    templates/               # Jinja templates
    static/                  # CSS and static assets
    sql/                     # SQL assets/migrations
    .env.example             # Environment variable template
    requirements.txt
    render.yaml
    Procfile
    wsgi.py

  extension/
    manifest.json            # Chrome MV3 manifest
    background.js            # Service worker, alarms, event collection
    content.js               # Page snippet extraction + portal proof flow
    popup.html
    popup.js                 # Login/consent/control UI
    config.js                # Base URL and endpoint config

  vercel.json                # Routing between Flask and FastAPI on Vercel
  requirements.txt           # Root deployment requirements
```

## 3. Tech stack

### Backend

- Python 3.x
- Flask 3.1.0
- FastAPI 0.115.0
- Uvicorn 0.30.6
- Gunicorn 23.0.0
- PyJWT 2.9.0
- Requests 2.32.3
- python-dotenv 1.0.1
- Twilio 9.3.2
- SQLite (built-in `sqlite3`)

### Frontend web app

- Server-side rendered Jinja templates
- Plain JavaScript
- CSS (custom styles)
- Tailwind CDN usage in selected templates
- Google Fonts + Material Symbols
- `ismobilejs` client-side guard via CDN

### Browser extension

- Chrome Extension Manifest V3
- JavaScript modules
- Chrome extension APIs:
  - `chrome.storage`
  - `chrome.alarms`
  - `chrome.tabs`
  - `chrome.runtime`
  - `chrome.action`
  - `chrome.scripting`

### Extension permissions and browser APIs

- Manifest permissions: `storage`, `alarms`, `tabs`, `activeTab`, `scripting`
- Host permissions: `<all_urls>`, local Flask hosts, and configured EqWell domain
- Browser/web APIs used in extension and templates:
   - `fetch`
   - `URL` and query parsing
   - `navigator.userAgent`, `navigator.userAgentData`
   - `window.matchMedia`
   - DOM text extraction (`querySelectorAll`, `innerText`, `textContent`)

### AI/ML and external services

- Hugging Face Inference Router (emotion classification)
- Groq Chat Completions API (signal refinement)
- Google OAuth2 + Google Fitness API (steps/sleep)
- Twilio WhatsApp API (alerting path)
- DiceBear Avatars API

### Deployment and infra

- Vercel serverless Python runtime
- Optional Render deployment files included

## 4. External APIs used

### AI / NLP

1. Hugging Face Inference Router
   - Base: `https://router.huggingface.co/hf-inference/models/j-hartmann/emotion-english-distilroberta-base`
   - Purpose: Emotion inference for text snippets and stress signal base scoring.

2. Groq Chat Completions
   - Base: `https://api.groq.com/openai/v1/chat/completions`
   - Purpose: Refine/classify risk signal (`LOW|MEDIUM|HIGH`) from text/query/url context.

### Google Fit integration

1. OAuth Authorization URL
   - `https://accounts.google.com/o/oauth2/v2/auth`
2. OAuth Token URL
   - `https://oauth2.googleapis.com/token`
3. Fitness aggregate endpoint
   - `https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate`
4. Fitness sessions endpoint
   - `https://www.googleapis.com/fitness/v1/users/me/sessions`

### Messaging and avatars

1. Twilio WhatsApp
   - Used for parent/alert communication flows when enabled.
2. DiceBear
   - Base: `https://api.dicebear.com/9.x`
   - Used for generated user avatars.

## 5. Internal API inventory

This section documents routes currently registered by Flask (`application/app.py`) and FastAPI (`application/stress_api.py`).

### 5.1 Flask JSON/API endpoints

#### Extension APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/extension/student/login` | Extension login with student credentials, returns JWT/profile. |
| GET | `/api/extension/student/me` | Validates extension JWT and returns student identity/profile. |
| POST | `/api/extension/student/presence` | Heartbeat/presence state sync from extension. |
| POST | `/api/extension/student/collect-event` | Collects consented event snippet/query/url context. |
| POST | `/api/extension/student/process-collected` | Batch-processes queued extension events into signals. |
| POST | `/api/extension/student/signal` | Push/pull extension signal synchronization. |
| POST | `/api/extension/student/portal-proof` | Generates proof for secure student portal login coupling. |

#### Student APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/student/chat` | Student chat endpoint (wellbeing conversation workflow). |
| GET | `/api/student/live-extension-signal` | Fetches latest extension-derived student signal. |
| GET | `/api/student/quiz/<quiz_key>` | Quiz metadata/details endpoint. |
| POST | `/api/student/quiz/<quiz_key>/submit` | Submits quiz responses and scoring updates. |
| GET | `/api/student/tasks/state` | Returns task claim/state snapshot for student. |
| POST | `/api/student/tasks/claim` | Claims task/action for student workflow. |
| GET | `/api/student/google-fit/connect` | Starts Google Fit OAuth flow. |
| GET | `/api/student/google-fit/callback` | OAuth callback to exchange auth code and persist tokens. |
| POST | `/api/student/google-fit/sync` | Triggers Google Fit sync for steps/sleep metrics. |

#### Other APIs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/avatar` | Avatar generation/provider endpoint. |
| POST | `/api/counsellor/student-signal` | Counsellor signal updates/adjustments. |

### 5.2 Flask web/page routes

#### Core/auth/system

| Method | Path |
|---|---|
| GET | `/` |
| GET,POST | `/signup` |
| GET,POST | `/login` |
| GET,POST | `/login/<role>` |
| GET,POST | `/logout` |
| GET | `/dashboard/<role>` |
| GET | `/install-extension` |
| GET | `/healthz` |
| GET | `/readyz` |
| GET | `/mobile-overrides.css` |
| GET | `/mobile-drawer.js` |

#### Student pages

| Method | Path |
|---|---|
| GET | `/student/dashboard` |
| GET,POST | `/student/mood` |
| GET,POST | `/student/face-check` |
| GET | `/student/profile` |
| GET | `/student/quiz` |
| GET,POST | `/student/quiz/<quiz_key>` |
| GET | `/student/counselling` |
| GET | `/student/tasks` |
| POST | `/student/parent-contact/request-otp` |
| POST | `/student/parent-contact/verify` |

#### Warden pages

| Method | Path |
|---|---|
| GET | `/warden/overview` |
| GET | `/warden/students` |
| GET | `/warden/analytics` |
| GET | `/warden/alerts` |

#### Counsellor pages

| Method | Path |
|---|---|
| GET | `/counsellor` |
| GET | `/counsellor/overview` |
| GET | `/counsellor/appointments` |
| GET | `/counsellor/student-analytics` |
| GET | `/counsellor/session-evaluation` |

#### Developer pages/actions

| Method | Path |
|---|---|
| GET | `/developer` |
| GET | `/developer/overview` |
| GET | `/developer/accounts` |
| GET | `/developer/pipeline` |
| GET | `/developer/requests` |
| POST | `/developer/accounts/create` |
| POST | `/developer/accounts/<int:account_id>/status` |
| POST | `/developer/quizzes/create` |
| POST | `/developer/assignments/parent` |
| POST | `/developer/assignments/proctor` |
| POST | `/developer/parent-contact/edit` |

#### Parent pages

| Method | Path |
|---|---|
| GET | `/parent/overview` |
| GET | `/parent/weekly-trend` |
| GET | `/parent/lifestyle` |
| GET | `/parent/contact` |
| GET | `/parent/alerts` |

#### Proctor pages

| Method | Path |
|---|---|
| GET | `/proctor/overview` |
| GET | `/proctor/students` |
| GET | `/proctor/analytics` |
| GET | `/proctor/contact` |
| GET | `/proctor/alerts` |

### 5.3 FastAPI service endpoints (`application/stress_api.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health check. |
| POST | `/analyze` | Generic mood+text analysis payload. |
| POST | `/extension-analyze` | Extension-oriented stress signal analysis with JWT auth context. |

## 6. Data storage model (SQLite)

Primary database tables created by Flask include:

- `student_score_state`
- `user_accounts`
- `extension_collected_events`
- `student_extension_security_state`
- `extension_risk_events`
- `student_url_history`
- `student_google_fit_state`
- `student_quiz_attempts`
- `Quizzes`
- `Questions`
- `parent_student_links`
- `student_parent_alert_contacts`
- `parent_alert_events`
- `student_auto_counselling_sessions`
- `student_face_check_state`
- `proctor_student_links`
- `student_task_claims`

## 7. Desktop-only enforcement model

EqWell currently enforces desktop-only access through layered checks:

1. Server-side checks in Flask (`should_use_mobile_templates`) based on user-agent + client hints.
2. Query override hardening so mobile cannot bypass via `?view=desktop`.
3. Response-injected client guard using `ismobilejs` plus device-signal heuristics.
4. Block page rendering (`Open EqWell on Desktop`) when mobile/tablet signals are detected.

This is intentionally defense-in-depth to reduce mobile bypass behavior.

## 8. Environment variables

Copy template:

```bash
copy application/.env.example application/.env
```

### Required for secure production

- `FLASK_SECRET_KEY`
- `EQWELL_JWT_SECRET`
- `HUGGINGFACE_API_TOKEN`
- `GROQ_API_KEY`

### Core app/runtime

- `FLASK_ENV`
- `FLASK_HOST`
- `FLASK_PORT`
- `PORT`
- `EQWELL_DB_PATH` (use `/tmp/eqwell_scores.db` on Vercel)
- `EQWELL_TRUST_PROXY`
- `SESSION_COOKIE_SECURE`
- `REMEMBER_COOKIE_SECURE`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_TTL_HOURS`

### AI/signal and extension tuning

- `HF_EMOTION_API_URL`
- `GROQ_MODEL`
- `EQWELL_JWT_ALGORITHM`
- `EXTENSION_HEARTBEAT_MAX_AGE_SECONDS`
- `EQWELL_DEBUG_SIGNAL_LOGS`
- `EXTENSION_MIN_INSTALL_AGE_SECONDS`
- `EXTENSION_MIN_CONSENT_AGE_SECONDS`
- `EXTENSION_BATCH_WINDOW_HOURS`
- `EXTENSION_BATCH_MAX_EVENTS`
- `EXTENSION_REPEAT_WINDOW_SECONDS`
- `EXTENSION_REPEAT_PENALTY_STEP_1`
- `EXTENSION_REPEAT_PENALTY_STEP_2`
- `EXTENSION_REPEAT_PENALTY_STEP_3`
- `EXTENSION_REPEAT_PENALTY_STEP_4`
- `COUNSELLOR_DEFAULT_SCORE`

### Messaging

- `EQWELL_WHATSAPP_MODE`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`

### Google Fit OAuth

- `GOOGLE_FIT_CLIENT_ID`
- `GOOGLE_FIT_CLIENT_SECRET`
- `GOOGLE_FIT_REDIRECT_URI`
- `GOOGLE_FIT_SCOPES`

## 9. Local development setup

## 9.1 Prerequisites

- Python 3.11+
- Google Chrome (for extension)

## 9.2 Install dependencies

From repository root:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 9.3 Run Flask app

```bash
cd application
python app.py
```

Open: `http://127.0.0.1:5000`

## 9.4 Run FastAPI app (optional)

```bash
cd application
python stress_api.py
```

Health: `http://127.0.0.1:8000/health`

## 9.5 Load Chrome extension

1. Open `chrome://extensions`
2. Enable Developer mode
3. Click Load unpacked
4. Select `extension/`

Extension base URL config is in `extension/config.js` (`AUTH_BASE_URL`).

## 10. Deployment

### Vercel

`vercel.json` build/routes:

- `api/index.py` -> Flask app for `/(.*)`
- `api/stress_api.py` -> FastAPI for `/extension-analyze` and `/health`

Important deployment notes:

1. Set `EQWELL_DB_PATH=/tmp/eqwell_scores.db`.
2. Set all required secrets in Vercel project environment.
3. Configure Google OAuth redirect URI to your production domain:
   - `https://<domain>/api/student/google-fit/callback`

### Render (optional)

Render-compatible files are available under `application/`:

- `render.yaml`
- `Procfile`
- `wsgi.py`

## 11. Security and privacy

- `.env` should never be committed.
- Extension model is consent-first and active-tab scoped.
- JWT-based extension auth is used for protected extension endpoints.
- CORS for extension endpoints is origin-restricted to `chrome-extension://` origins.
- Secrets should be rotated if exposed.

## 12. Additional notes

- `frontend/` contains design/prototype assets and experiments not required for core production runtime.
- `api/index.py` and `api/stress_api.py` are thin Vercel adapters that import apps from `application/`.
