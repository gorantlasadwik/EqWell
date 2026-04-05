# EqWell Chrome Extension

Consent-first browser wellbeing monitor for EqWell.

## Privacy Positioning

The extension reads only active-tab context and sends it to the Flask backend as collected events. The backend stores queued events in SQLite for batch processing and clears processed events after each update cycle.

## Files

- manifest.json
- background.js
- content.js
- popup.html
- popup.js
- config.js

## Run Backend

1. Install dependencies:
   pip install -r requirements.txt
2. Set environment variables in .env:
   - HUGGINGFACE_API_TOKEN
   - EQWELL_JWT_SECRET
3. Start Flask app:
   python app.py

## Load Extension

1. Open Chrome and go to chrome://extensions
2. Enable Developer mode
3. Click Load unpacked
4. Select this folder:
   chrome_extension

## Use

1. Click extension icon
2. Sign in with student credentials used in EqWell login page
3. Enable the consent toggle
4. Browse normally

The extension sends only:
- text (temporary snippet, max 300 chars)
- session_duration (minutes)
- current_url (active tab only)
- extracted_query (decoded search intent when available)

The extension auto-receives JWT + student profile from Flask endpoint:
- POST /api/extension/student/login
- GET /api/extension/student/me
- POST /api/extension/student/presence
- POST /api/extension/student/collect-event
- POST /api/extension/student/process-collected

Backend analysis flow for extension events:
- Collect URL/query/snippet events into SQLite queue
- Every batch window (default 12 hours), call Groq to extract relevant risk context
- Run Hugging Face emotion on extracted text
- Merge signals, update live stress state, clear processed queue rows

If repeated HIGH stress signals are detected, the popup displays: Please contact the counsellor.
