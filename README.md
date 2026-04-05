# EqWell

EqWell is a student wellbeing platform with:

- A web application (Flask) for students, wardens, counsellors, developers, proctors, and parents.
- A Chrome extension for consent-first browsing risk signals.
- An optional dedicated stress analysis API (FastAPI) for extension-style signal scoring.

## Repository layout

```
EqWell/
  application/
    app.py
    stress_api.py
    templates/
    static/
    sql/
    requirements.txt
    .env.example
  extension/
    manifest.json
    background.js
    content.js
    popup.html
    popup.js
    config.js
```

## Components

### 1) Application server (Flask)

Path: `application/app.py`

Responsibilities:

- Full web app routes and dashboards
- Authentication/session handling
- Quiz, counselling, and risk workflows
- Extension auth/presence/event endpoints used by the Chrome extension

Default local URL: `http://127.0.0.1:5000`

### 2) Stress API server (FastAPI)

Path: `application/stress_api.py`

Responsibilities:

- Dedicated text/url stress signal analysis endpoint (`/extension-analyze`)
- Hugging Face + Groq based signal refinement flow

Default local URL when run directly: `http://127.0.0.1:8000`

Note: This repository keeps both servers as separate files. You can run only Flask for normal app flows, or run both when you want a dedicated analysis API service.

### 3) Chrome extension

Path: `extension/`

Responsibilities:

- Consent toggle and student extension login
- Active-tab event collection (privacy-first)
- Sending events to backend extension endpoints

## Local setup

## Requirements

- Python 3.11+
- Google Chrome (for extension)

## 1. Create environment and install dependencies

From repo root:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r application/requirements.txt
```

## 2. Configure environment variables

```bash
copy application/.env.example application/.env
```

Update at least:

- `FLASK_SECRET_KEY`
- `EQWELL_JWT_SECRET`
- `HUGGINGFACE_API_TOKEN`
- `GROQ_API_KEY`

## 3. Run Flask application server

```bash
cd application
python app.py
```

Open: `http://127.0.0.1:5000`

## 4. (Optional) Run dedicated stress API server

In a second terminal:

```bash
cd application
python stress_api.py
```

Open health check: `http://127.0.0.1:8000/health`

## 5. Load Chrome extension

1. Open `chrome://extensions`
2. Enable Developer mode
3. Click Load unpacked
4. Select the `extension` folder

## Extension backend base URL

Extension auth/event base URL is configured in:

- `extension/config.js` -> `AUTH_BASE_URL`

For local development, default is `http://127.0.0.1:5000`.

## Deployment notes

Current production files are inside `application/`:

- `application/render.yaml`
- `application/Procfile`
- `application/wsgi.py`

These are ready for Render-style deployment.

If you deploy on Vercel:

- Treat `application/` as the application root.
- Deploy Flask app as one service.
- If you need isolated analysis scaling, deploy `stress_api.py` as a separate service and point your app to it via environment configuration.

## Security notes

- Never commit `.env` files.
- Rotate any credentials that were shared.
- Keep `EQWELL_JWT_SECRET` and API tokens strong and private.

## Status

Repository has been cleaned and reorganized to this new structure:

- `application/` for all backend and web templates/static assets
- `extension/` for Chrome extension source
