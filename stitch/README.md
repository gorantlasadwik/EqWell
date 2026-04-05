# EqWell Full App (Stitch UI Based)

This is a full EqWell prototype built with the stitch visual style and component language.

## Stack
- Backend: FastAPI
- Database: SQLite via SQLAlchemy
- Frontend: HTML + Tailwind CSS + Chart.js

## Features Included
- 4 dashboards: Student, Warden, Admin, Counsellor
- Booking and scheduling center
- Privacy-first design (no raw vent text storage)
- Multi-source stress scoring with dynamic weighting
- Context event bias support
- Alerts, trends, block heatmap analytics, and counselling demand

## Stress Formula
Stress Score (1-5) =
- Mood (0.30)
- Counsellor (0.30)
- Quiz (0.20)
- Chatbot (0.10)
- Event Bias (additive)

With dynamic re-weighting when some inputs are missing.

## Run
From the stitch folder:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:
- http://127.0.0.1:8000/

## Notes
- Seed data is auto-created on first run.
- Anonymous IDs are used everywhere.
- Vent endpoint only stores derived topic and stress estimate.
