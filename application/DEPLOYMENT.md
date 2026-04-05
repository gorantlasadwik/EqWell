# EqWell Deployment Guide (Render Free)

This project is now configured for production-style deployment while preserving demo mock logins and seeded mock data.

## What was added

- Gunicorn production server via `wsgi.py` and `Procfile`
- Render blueprint config in `render.yaml`
- Health endpoints:
  - `GET /healthz`
  - `GET /readyz`
- Production-safe Flask runtime config:
  - cookie hardening
  - proxy trust support
  - environment-driven host/port/debug
- Idempotent full mock data seeding on startup

## Mock Login Credentials (Demo)

- Student: `student@eqwell.app` / `student123`
- Student: `riya.student@eqwell.app` / `student123`
- Student: `liam.student@eqwell.app` / `student123`
- Student: `zoya.student@eqwell.app` / `student123`
- Student: `noah.student@eqwell.app` / `student123`
- Warden: `warden@eqwell.app` / `warden123`
- Warden: `warden.hostelb@eqwell.app` / `warden123`
- Counsellor: `counsellor@eqwell.app` / `counsellor123`
- Counsellor: `counsellor.support@eqwell.app` / `counsellor123`
- Developer: `developer@wellnest` / `WellNest2026`
- Developer: `dev.ops@wellnest` / `WellNest2026`
- Parent: `parent@eqwell.app` / `parent123`
- Parent: `guardian.one@eqwell.app` / `parent123`
- Parent: `guardian.two@eqwell.app` / `parent123`
- Proctor: `proctor@eqwell.app` / `proctor123`
- Proctor: `proctor.science@eqwell.app` / `proctor123`

## Environment Variables

Start from `.env.example`.

Minimum recommended values for Render:

- `FLASK_ENV=production`
- `FLASK_DEBUG=0`
- `EQWELL_TRUST_PROXY=1`
- `SESSION_COOKIE_SECURE=1`
- `REMEMBER_COOKIE_SECURE=1`
- `FLASK_SECRET_KEY=<long-random-secret>`
- `EQWELL_JWT_SECRET=<long-random-secret>`

Optional demo toggles:

- `EQWELL_ENABLE_MOCK_LOGINS=1`
- `EQWELL_SEED_MOCK_DATA=1`

If you want real WhatsApp alerts, set Twilio credentials and use:

- `EQWELL_WHATSAPP_MODE=live`

## Deploy on Render (free)

1. Push this folder to a Git repo.
2. In Render, create a new **Web Service** from the repo.
3. Root directory: this `frontend/flask_app` folder.
4. Render can auto-detect `render.yaml`. If not:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app`
5. Add environment variables from `.env.example`.
6. Deploy and open:
   - `/healthz` for liveness
   - `/readyz` for DB readiness

## Notes

- SQLite is file-based and suitable for demo/small deployments. For larger scale, migrate to Postgres.
- Keep `.env` out of source control.
- Rotate any credentials that were ever exposed.
