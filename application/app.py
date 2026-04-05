from functools import wraps
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import re
from urllib.parse import parse_qs, unquote_plus, urlencode, urlparse

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
import jwt
import requests
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

app = Flask(__name__)


def read_env_int(name, default):
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        try:
            return int(float(raw))
        except ValueError:
            return int(default)


def read_env_float(name, default):
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def read_env_bool(name, default=False):
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


FLASK_ENVIRONMENT = str(os.getenv("FLASK_ENV", "development")).strip().lower() or "development"
IS_PRODUCTION = FLASK_ENVIRONMENT in {"production", "prod"}

session_same_site = str(os.getenv("SESSION_COOKIE_SAMESITE", "Lax")).strip().capitalize()
if session_same_site not in {"Lax", "Strict", "None"}:
    session_same_site = "Lax"

session_ttl_hours = max(1, min(read_env_int("SESSION_TTL_HOURS", 12), 168))
app.secret_key = os.getenv("FLASK_SECRET_KEY", "eqwell-dev-secret-change-me")
app.config.update(
    SECRET_KEY=app.secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=session_same_site,
    SESSION_COOKIE_SECURE=read_env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION),
    REMEMBER_COOKIE_SECURE=read_env_bool("REMEMBER_COOKIE_SECURE", IS_PRODUCTION),
    PREFERRED_URL_SCHEME="https" if read_env_bool("PREFERRED_URL_SCHEME_HTTPS", IS_PRODUCTION) else "http",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=session_ttl_hours),
)

if read_env_bool("EQWELL_TRUST_PROXY", IS_PRODUCTION):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def normalize_avatar_style(style):
    cleaned = str(style or "").strip().lower()
    if cleaned in DICEBEAR_ALLOWED_STYLES:
        return cleaned
    return DICEBEAR_AVATAR_STYLE if DICEBEAR_AVATAR_STYLE in DICEBEAR_ALLOWED_STYLES else "lorelei-neutral"


def normalize_avatar_format(image_format):
    cleaned = str(image_format or "").strip().lower()
    if cleaned in DICEBEAR_ALLOWED_FORMATS:
        return cleaned
    return DICEBEAR_AVATAR_FORMAT if DICEBEAR_AVATAR_FORMAT in DICEBEAR_ALLOWED_FORMATS else "svg"


def build_dicebear_avatar_url(seed, style=None, image_format=None):
    seed_value = str(seed or "EqWell User").strip() or "EqWell User"
    style_value = normalize_avatar_style(style)
    format_value = normalize_avatar_format(image_format)
    query = urlencode(
        {
            "seed": seed_value,
            "radius": 18,
            "size": 128,
            "backgroundType": "gradientLinear",
        }
    )
    return f"{DICEBEAR_API_BASE}/{style_value}/{format_value}?{query}"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
HF_EMOTION_MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"
HF_EMOTION_API_URL = os.getenv(
    "HF_EMOTION_API_URL",
    f"https://router.huggingface.co/hf-inference/models/{HF_EMOTION_MODEL_ID}",
)
HF_API_TOKEN = os.getenv(
    "HUGGINGFACE_API_TOKEN",
    os.getenv("HF_API_TOKEN", os.getenv("HF_TOKEN", "")),
).strip()
EQWELL_JWT_SECRET = os.getenv("EQWELL_JWT_SECRET", app.secret_key).strip() or app.secret_key
EQWELL_JWT_ALGORITHM = os.getenv("EQWELL_JWT_ALGORITHM", "HS256").strip() or "HS256"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
EXTENSION_LIVE_SIGNALS = {}
EXTENSION_SECURITY_STATUS = {}
STUDENT_BEHAVIOR_CONTEXT = {}
configured_db_path = str(os.getenv("EQWELL_DB_PATH", "")).strip()
is_vercel_runtime = os.getenv("VERCEL", "").strip() == "1"
if configured_db_path:
    score_db_candidate = Path(configured_db_path).expanduser()
    if not score_db_candidate.is_absolute():
        score_db_candidate = (Path(__file__).resolve().parent / score_db_candidate).resolve()
    SCORE_DB_PATH = score_db_candidate
else:
    # Vercel serverless runtime allows writes only in /tmp.
    if is_vercel_runtime:
        SCORE_DB_PATH = Path("/tmp/eqwell_scores.db")
    else:
        SCORE_DB_PATH = Path(__file__).resolve().with_name("eqwell_scores.db")
EQWELL_ENABLE_MOCK_LOGINS = read_env_bool("EQWELL_ENABLE_MOCK_LOGINS", True)
EQWELL_SEED_MOCK_DATA = read_env_bool("EQWELL_SEED_MOCK_DATA", True)
QUIZ_MODES_DIR = Path(__file__).resolve().parent / "quiz_questions"
if not QUIZ_MODES_DIR.exists():
    # Backward-compatible fallback when running from legacy repository layout.
    QUIZ_MODES_DIR = Path(__file__).resolve().parent.parent / "final" / "quiz questions"
QUIZ_MODE_QUESTION_LIMIT = max(5, min(read_env_int("QUIZ_MODE_QUESTION_LIMIT", 10), 25))
EQWELL_DEBUG_SIGNAL_LOGS = os.getenv("EQWELL_DEBUG_SIGNAL_LOGS", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EXTENSION_BATCH_WINDOW_HOURS = max(0.05, read_env_float("EXTENSION_BATCH_WINDOW_HOURS", 12.0))
EXTENSION_BATCH_MAX_EVENTS = max(1, read_env_int("EXTENSION_BATCH_MAX_EVENTS", 400))
EXTENSION_LOGIN_NONCE_TTL_SECONDS = max(30, min(read_env_int("EXTENSION_LOGIN_NONCE_TTL_SECONDS", 300), 1800))
EXTENSION_PORTAL_PROOF_TTL_SECONDS = max(15, min(read_env_int("EXTENSION_PORTAL_PROOF_TTL_SECONDS", 90), 300))
COUNSELLOR_DEFAULT_SCORE = max(1.0, min(read_env_float("COUNSELLOR_DEFAULT_SCORE", 3.0), 5.0))
DICEBEAR_API_BASE = os.getenv("DICEBEAR_API_BASE", "https://api.dicebear.com/9.x").strip().rstrip("/")
DICEBEAR_AVATAR_STYLE = os.getenv("DICEBEAR_AVATAR_STYLE", "lorelei-neutral").strip().lower() or "lorelei-neutral"
DICEBEAR_AVATAR_FORMAT = os.getenv("DICEBEAR_AVATAR_FORMAT", "svg").strip().lower() or "svg"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886").strip() or "whatsapp:+14155238886"
EQWELL_WHATSAPP_MODE = os.getenv("EQWELL_WHATSAPP_MODE", "mock").strip().lower() or "mock"
PARENT_OTP_TTL_MINUTES = max(2, min(read_env_int("PARENT_OTP_TTL_MINUTES", 10), 30))
PARENT_ALERT_COOLDOWN_MINUTES = max(5, min(read_env_int("PARENT_ALERT_COOLDOWN_MINUTES", 180), 720))
AUTO_COUNSELLING_TRIGGER_BATTERY = max(5, min(read_env_int("AUTO_COUNSELLING_TRIGGER_BATTERY", 30), 60))
AUTO_COUNSELLING_REASSIGN_HOURS = max(1, min(read_env_int("AUTO_COUNSELLING_REASSIGN_HOURS", 12), 168))
AUTO_COUNSELLING_SLOT_MIN_LEAD_MINUTES = max(10, min(read_env_int("AUTO_COUNSELLING_SLOT_MIN_LEAD_MINUTES", 30), 180))
AUTO_COUNSELLING_SLOT_TIMES_UTC = ((9, 30), (10, 30), (12, 0), (14, 0), (15, 30), (17, 0))
DICEBEAR_ALLOWED_STYLES = {
    "adventurer",
    "adventurer-neutral",
    "avataaars",
    "avataaars-neutral",
    "bottts",
    "bottts-neutral",
    "fun-emoji",
    "lorelei",
    "lorelei-neutral",
    "notionists",
    "notionists-neutral",
    "pixel-art",
    "pixel-art-neutral",
}
DICEBEAR_ALLOWED_FORMATS = {"svg", "png", "jpg", "jpeg", "webp", "avif"}
STUDENT_SUPPORT_CONTACTS = [
    {"name": "Tele-MANAS", "phone": "14416", "region": "India", "notes": "24x7 mental health helpline"},
    {
        "name": "Tele-MANAS (Toll Free)",
        "phone": "1800-891-4416",
        "region": "India",
        "notes": "National tele-mental health support",
    },
    {"name": "AASRA", "phone": "+91-22-27546669", "region": "India", "notes": "24x7 crisis support"},
    {
        "name": "iCALL",
        "phone": "+91-9152987821",
        "region": "India",
        "notes": "Counselling helpline",
    },
]

PARENT_ALERT_MESSAGE_HIGH = (
    "EqWell Alert: Your ward has shown signs of increased stress recently. "
    "Please consider checking in or encouraging support."
)
PARENT_ALERT_MESSAGE_CRITICAL = (
    "EqWell Alert: Your ward is currently experiencing significant stress. "
    "Early support is recommended."
)

MULTIMODAL_WEIGHTS = {
    "mood": 0.21,
    "chatbot": 0.17,
    "extension": 0.13,
    "fitness": 0.17,
    "counsellor": 0.17,
    "quiz": 0.15,
}

GOOGLE_FIT_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_FIT_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_FIT_AGGREGATE_URL = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
GOOGLE_FIT_SESSIONS_URL = "https://www.googleapis.com/fitness/v1/users/me/sessions"
GOOGLE_FIT_CLIENT_ID = os.getenv("GOOGLE_FIT_CLIENT_ID", "").strip()
GOOGLE_FIT_CLIENT_SECRET = os.getenv("GOOGLE_FIT_CLIENT_SECRET", "").strip()
GOOGLE_FIT_REDIRECT_URI = os.getenv("GOOGLE_FIT_REDIRECT_URI", "").strip()
GOOGLE_FIT_SCOPES = os.getenv(
    "GOOGLE_FIT_SCOPES",
    "https://www.googleapis.com/auth/fitness.activity.read https://www.googleapis.com/auth/fitness.sleep.read",
).strip()
GOOGLE_FIT_REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "openid",
    "email",
)

EXTENSION_URL_RISK_PATTERNS = [
    re.compile(r"\bhow\s+to\s+die\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:dont|don't)\s+want\s+(?:to\s+)?live\b", re.IGNORECASE),
    re.compile(r"\b(?:want\s+to\s+die|i\s+want\s+to\s+die)\b", re.IGNORECASE),
    re.compile(r"\b(?:kill\s+myself|end\s+my\s+life)\b", re.IGNORECASE),
    re.compile(r"\b(?:kill|killing)\s+(?:my\s*[- ]?self|myself|yourself|himself|herself|themself|themselves)\b", re.IGNORECASE),
    re.compile(r"\b(?:how|ways?)\s+(?:can|do|to)?\s*(?:i\s+)?(?:kill|end)\s+(?:my\s*[- ]?self|myself|my\s+life)\b", re.IGNORECASE),
    re.compile(r"\b(?:suicide|self[\s-]*harm|hurt\s+myself)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+to\s+kill\s+(?:yourself|myself|ourself|ourselves)\b", re.IGNORECASE),
]

EXTENSION_URL_POSITIVE_PATTERNS = [
    re.compile(r"\b(?:happy|happiness|joy|grateful|gratitude|hopeful|positive)\b", re.IGNORECASE),
    re.compile(r"\b(?:calm|peaceful|relax|breathing|mindful|mindfulness|meditation)\b", re.IGNORECASE),
    re.compile(r"\b(?:neutral|balanced|steady|focus|focused|wellbeing|wellness|self\s*care)\b", re.IGNORECASE),
]

EXTENSION_URL_HISTORY_MAX_ITEMS = max(100, read_env_int("EXTENSION_URL_HISTORY_MAX_ITEMS", 400))
EXTENSION_SAFE_STREAK_HOURS_STEP_1 = max(0.5, read_env_float("EXTENSION_SAFE_STREAK_HOURS_STEP_1", 1.0))
EXTENSION_SAFE_STREAK_HOURS_STEP_2 = max(EXTENSION_SAFE_STREAK_HOURS_STEP_1, read_env_float("EXTENSION_SAFE_STREAK_HOURS_STEP_2", 3.0))
EXTENSION_SAFE_STREAK_HOURS_STEP_3 = max(EXTENSION_SAFE_STREAK_HOURS_STEP_2, read_env_float("EXTENSION_SAFE_STREAK_HOURS_STEP_3", 8.0))

EXTENSION_HEARTBEAT_MAX_AGE_SECONDS = max(10, read_env_int("EXTENSION_HEARTBEAT_MAX_AGE_SECONDS", 75))
EXTENSION_MIN_INSTALL_AGE_SECONDS = max(0, read_env_int("EXTENSION_MIN_INSTALL_AGE_SECONDS", 12))
EXTENSION_MIN_CONSENT_AGE_SECONDS = max(0, read_env_int("EXTENSION_MIN_CONSENT_AGE_SECONDS", 8))
EXTENSION_REPEAT_WINDOW_SECONDS = max(30, read_env_int("EXTENSION_REPEAT_WINDOW_SECONDS", 120))
EXTENSION_REPEAT_PENALTY_STEP_1 = max(0, read_env_int("EXTENSION_REPEAT_PENALTY_STEP_1", 2))
EXTENSION_REPEAT_PENALTY_STEP_2 = max(0, read_env_int("EXTENSION_REPEAT_PENALTY_STEP_2", 4))
EXTENSION_REPEAT_PENALTY_STEP_3 = max(0, read_env_int("EXTENSION_REPEAT_PENALTY_STEP_3", 6))
EXTENSION_REPEAT_PENALTY_STEP_4 = max(0, read_env_int("EXTENSION_REPEAT_PENALTY_STEP_4", 9))

CREDENTIALS = {
    "student": {"email": "student@eqwell.app", "password": "student123", "name": "Ariana Vale"},
    "warden": {"email": "warden@eqwell.app", "password": "warden123", "name": "Warden Mitchell"},
    "developer": {"email": "developer@wellnest", "password": "WellNest2026", "name": "Aarav Dev"},
    "counsellor": {
        "email": "counsellor@eqwell.app",
        "password": "counsellor123",
        "name": "Dr. Aris",
    },
    "parent": {
        "email": "parent@eqwell.app",
        "password": "parent123",
        "name": "Parent Access",
    },
    "proctor": {
        "email": "proctor@eqwell.app",
        "password": "proctor123",
        "name": "Proctor Access",
    },
}

MOCK_SHOWCASE_EXTRA_ACCOUNTS = [
    {
        "role": "student",
        "email": "riya.student@eqwell.app",
        "password": "student123",
        "name": "Riya Sharma",
    },
    {
        "role": "student",
        "email": "liam.student@eqwell.app",
        "password": "student123",
        "name": "Liam Carter",
    },
    {
        "role": "student",
        "email": "zoya.student@eqwell.app",
        "password": "student123",
        "name": "Zoya Khan",
    },
    {
        "role": "student",
        "email": "noah.student@eqwell.app",
        "password": "student123",
        "name": "Noah Patel",
    },
    {
        "role": "parent",
        "email": "guardian.one@eqwell.app",
        "password": "parent123",
        "name": "Anika Sharma",
    },
    {
        "role": "parent",
        "email": "guardian.two@eqwell.app",
        "password": "parent123",
        "name": "Rahul Carter",
    },
    {
        "role": "proctor",
        "email": "proctor.science@eqwell.app",
        "password": "proctor123",
        "name": "Prof. N. Singh",
    },
    {
        "role": "counsellor",
        "email": "counsellor.support@eqwell.app",
        "password": "counsellor123",
        "name": "Dr. Maya Reed",
    },
    {
        "role": "warden",
        "email": "warden.hostelb@eqwell.app",
        "password": "warden123",
        "name": "Warden Priya",
    },
    {
        "role": "developer",
        "email": "dev.ops@wellnest",
        "password": "WellNest2026",
        "name": "Nikhil Ops",
    },
]

ACCOUNT_ROLES = ("student", "warden", "developer", "counsellor", "parent", "proctor")
ACCOUNT_STATUSES = ("pending", "approved", "rejected")

STUDENT_MOODS = {
    "very-bad": {"label": "Very Bad", "score": 1, "battery": 18, "tone": "#fc7359"},
    "bad": {"label": "Bad", "score": 2, "battery": 36, "tone": "#dfa342"},
    "not-bad": {"label": "Not Bad", "score": 3, "battery": 54, "tone": "#c8b35f"},
    "good": {"label": "Good", "score": 4, "battery": 73, "tone": "#9fbe59"},
    "very-good": {"label": "Very Good", "score": 5, "battery": 90, "tone": "#6ea73f"},
}

# Product rule: student can skip for up to 3 days, then face check becomes mandatory.
FACE_CHECK_GRACE_DAYS = 3
STUDENT_TASK_DAILY_POINTS_CAP = 20
STUDENT_TASK_STRESS_REWARD_PER_POINT = 0.05
FACE_EMOTION_SCORES = {
    "joy": 5.0,
    "surprise": 3.8,
    "neutral": 3.0,
    "sadness": 1.6,
    "fear": 1.7,
    "anger": 1.5,
    "disgust": 1.8,
}
FACE_EMOTION_LABELS = {
    "joy": "Joy",
    "surprise": "Surprised",
    "neutral": "Neutral",
    "sadness": "Sad",
    "fear": "Fearful",
    "anger": "Angry",
    "disgust": "Disgust",
}
FACE_DEFAULT_BLEND_WEIGHT = 0.4
FACE_EMOTION_WEIGHTS = {
    "joy": 0.45,
    "surprise": 0.35,
    "neutral": 0.2,
    "sadness": 0.45,
    "fear": 0.45,
    "anger": 0.45,
    "disgust": 0.4,
}

STUDENT_QUIZ_LIBRARY = {
    "daily_stress_check": {
        "title": "Daily Stress Check",
        "duration": "4 min",
        "difficulty": "Easy",
        "focus": "Balance",
        "description": "Quick baseline quiz to tune your support plan for the next 24 hours.",
        "cta": "Start Baseline",
        "questions": [
            {
                "id": "sleep_quality",
                "prompt": "How did you sleep last night?",
                "options": [
                    {"id": "great", "label": "Restful and complete", "stress": 1},
                    {"id": "okay", "label": "Decent with short wakeups", "stress": 2},
                    {"id": "restless", "label": "Restless and fragmented", "stress": 4},
                    {"id": "poor", "label": "Barely slept", "stress": 5},
                ],
            },
            {
                "id": "focus_today",
                "prompt": "How is your focus today?",
                "options": [
                    {"id": "clear", "label": "Clear and steady", "stress": 1},
                    {"id": "manageable", "label": "Mostly manageable", "stress": 2},
                    {"id": "scattered", "label": "Scattered and distracted", "stress": 4},
                    {"id": "blocked", "label": "Cannot focus at all", "stress": 5},
                ],
            },
            {
                "id": "emotional_load",
                "prompt": "How heavy does your day feel emotionally?",
                "options": [
                    {"id": "light", "label": "Light and stable", "stress": 1},
                    {"id": "mild", "label": "Mild pressure", "stress": 2},
                    {"id": "anxious", "label": "Anxious often", "stress": 4},
                    {"id": "overwhelmed", "label": "Overwhelmed", "stress": 5},
                ],
            },
            {
                "id": "support_readiness",
                "prompt": "If needed, how likely are you to ask for support today?",
                "options": [
                    {"id": "ready", "label": "I can ask for support", "stress": 1},
                    {"id": "maybe", "label": "Maybe, if it gets worse", "stress": 3},
                    {"id": "avoid", "label": "I would avoid asking", "stress": 4},
                    {"id": "isolated", "label": "I feel fully isolated", "stress": 5},
                ],
            },
        ],
    },
    "exam_pressure_decoder": {
        "title": "Exam Pressure Decoder",
        "duration": "6 min",
        "difficulty": "Medium",
        "focus": "Academics",
        "description": "Identify what is driving academic anxiety and get practical coping prompts.",
        "cta": "Take Quiz",
        "questions": [
            {
                "id": "prep_confidence",
                "prompt": "How confident do you feel about exam preparation?",
                "options": [
                    {"id": "high", "label": "Confident and prepared", "stress": 1},
                    {"id": "fair", "label": "Some gaps, still manageable", "stress": 2},
                    {"id": "low", "label": "Many gaps remain", "stress": 4},
                    {"id": "none", "label": "Not prepared", "stress": 5},
                ],
            },
            {
                "id": "deadline_control",
                "prompt": "How in control are your deadlines?",
                "options": [
                    {"id": "ontrack", "label": "On track", "stress": 1},
                    {"id": "tight", "label": "Tight but possible", "stress": 2},
                    {"id": "behind", "label": "Falling behind", "stress": 4},
                    {"id": "lost", "label": "Completely lost", "stress": 5},
                ],
            },
            {
                "id": "body_signals",
                "prompt": "Which physical stress signals are you noticing?",
                "options": [
                    {"id": "none", "label": "No strong symptoms", "stress": 1},
                    {"id": "mild", "label": "Mild tension", "stress": 2},
                    {"id": "frequent", "label": "Frequent headaches or chest tightness", "stress": 4},
                    {"id": "severe", "label": "Severe symptoms", "stress": 5},
                ],
            },
            {
                "id": "break_pattern",
                "prompt": "How often are you taking recovery breaks while studying?",
                "options": [
                    {"id": "regular", "label": "Regular short breaks", "stress": 1},
                    {"id": "sometimes", "label": "Sometimes", "stress": 2},
                    {"id": "rare", "label": "Rarely", "stress": 4},
                    {"id": "none", "label": "Never", "stress": 5},
                ],
            },
        ],
    },
    "sleep_recovery_scan": {
        "title": "Sleep and Recovery Scan",
        "duration": "5 min",
        "difficulty": "Easy",
        "focus": "Recovery",
        "description": "Measure sleep debt indicators and adjust your week plan before burnout builds.",
        "cta": "Open Scan",
        "questions": [
            {
                "id": "sleep_hours",
                "prompt": "Average sleep over the last 3 nights?",
                "options": [
                    {"id": "7plus", "label": "7+ hours", "stress": 1},
                    {"id": "6to7", "label": "6 to 7 hours", "stress": 2},
                    {"id": "5to6", "label": "5 to 6 hours", "stress": 4},
                    {"id": "under5", "label": "Under 5 hours", "stress": 5},
                ],
            },
            {
                "id": "wake_quality",
                "prompt": "How do you feel after waking up?",
                "options": [
                    {"id": "refreshed", "label": "Refreshed", "stress": 1},
                    {"id": "okay", "label": "Okay after some time", "stress": 2},
                    {"id": "tired", "label": "Tired most mornings", "stress": 4},
                    {"id": "drained", "label": "Exhausted and drained", "stress": 5},
                ],
            },
            {
                "id": "night_screen",
                "prompt": "How late do screens keep you awake?",
                "options": [
                    {"id": "minimal", "label": "Minimal screen time", "stress": 1},
                    {"id": "moderate", "label": "Moderate but controlled", "stress": 2},
                    {"id": "late", "label": "Late scrolling most nights", "stress": 4},
                    {"id": "allnight", "label": "Often up very late", "stress": 5},
                ],
            },
            {
                "id": "day_energy",
                "prompt": "How stable is your daytime energy?",
                "options": [
                    {"id": "stable", "label": "Stable and usable", "stress": 1},
                    {"id": "mixed", "label": "Mixed but manageable", "stress": 2},
                    {"id": "low", "label": "Low energy and crashes", "stress": 4},
                    {"id": "empty", "label": "Almost no energy", "stress": 5},
                ],
            },
        ],
    },
}

ROLE_SIDEBARS = {
    "student": {
        "subtitle": "Student Sanctuary",
        "badge_icon": "person",
        "menu": [
            {"label": "Dashboard", "icon": "home", "key": "dashboard"},
            {"label": "Mood Check-in", "icon": "mood", "key": "mood"},
            {"label": "Counselling", "icon": "psychology", "key": "counselling"},
            {"label": "Profile", "icon": "account_circle", "key": "profile"},
            {"label": "Resources", "icon": "library_books", "key": "resources"},
        ],
        "action": "Quick Pulse",
    },
    "warden": {
        "subtitle": "Warden Operations",
        "badge_icon": "shield_person",
        "menu": [
            {"label": "Dashboard", "icon": "dashboard", "key": "dashboard"},
            {"label": "Analytics", "icon": "analytics", "key": "analytics"},
            {"label": "Students", "icon": "group", "key": "students"},
            {"label": "Sessions", "icon": "psychology", "key": "sessions"},
            {"label": "Reports", "icon": "description", "key": "reports"},
        ],
        "action": "Dispatch Alert",
    },
    "developer": {
        "subtitle": "Ops Studio",
        "badge_icon": "monitoring",
        "menu": [
            {"label": "Overview", "icon": "dashboard", "key": "overview"},
            {"label": "Accounts", "icon": "manage_accounts", "key": "accounts"},
            {"label": "Pipeline", "icon": "schema", "key": "pipeline"},
            {"label": "Requests", "icon": "approval_delegation", "key": "requests"},
        ],
        "action": "Deploy Check",
    },
    "counsellor": {
        "subtitle": "Clinical Console",
        "badge_icon": "clinical_notes",
        "menu": [
            {"label": "Dashboard", "icon": "dashboard", "key": "dashboard"},
            {"label": "Analytics", "icon": "analytics", "key": "analytics"},
            {"label": "Students", "icon": "group", "key": "students"},
            {"label": "Sessions", "icon": "psychology", "key": "sessions"},
            {"label": "Reports", "icon": "description", "key": "reports"},
        ],
        "action": "New Entry",
    },
    "parent": {
        "subtitle": "Parent Insight",
        "badge_icon": "family_restroom",
        "menu": [
            {"label": "Overview", "icon": "dashboard", "key": "overview"},
            {"label": "Trend", "icon": "query_stats", "key": "trend"},
            {"label": "Alerts", "icon": "warning", "key": "alerts"},
            {"label": "Lifestyle", "icon": "self_improvement", "key": "lifestyle"},
        ],
        "action": "View Summary",
    },
    "proctor": {
        "subtitle": "Proctor Console",
        "badge_icon": "school",
        "menu": [
            {"label": "Overview", "icon": "dashboard", "key": "overview"},
            {"label": "Students", "icon": "group", "key": "students"},
            {"label": "Analytics", "icon": "analytics", "key": "analytics"},
            {"label": "Alerts", "icon": "warning", "key": "alerts"},
        ],
        "action": "Review Group",
    },
}


def emit_terminal_debug_log(tag, **fields):
    if not EQWELL_DEBUG_SIGNAL_LOGS:
        return

    ordered_keys = sorted(fields.keys())
    parts = []
    for key in ordered_keys:
        value = fields.get(key)
        text = str(value)
        if len(text) > 220:
            text = f"{text[:217]}..."
        parts.append(f"{key}={text}")

    payload = ", ".join(parts)
    print(f"[EQWELL][{tag}] {payload}", flush=True)


def init_score_store():
    try:
        SCORE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_score_state (
                    email TEXT PRIMARY KEY,
                    stress_score REAL NOT NULL,
                    mental_battery INTEGER NOT NULL,
                    stress_category TEXT NOT NULL,
                    last_checked_url TEXT,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_note TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    approved_by TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_accounts_role_status
                ON user_accounts (role, status)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_collected_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    current_url TEXT,
                    extracted_query TEXT,
                    page_context TEXT,
                    session_duration INTEGER,
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_collected_events_email_id
                ON extension_collected_events (email, id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_extension_security_state (
                    email TEXT PRIMARY KEY,
                    extension_email TEXT,
                    installed_at TEXT,
                    consent_granted_at TEXT,
                    last_seen_at TEXT,
                    source TEXT,
                    last_user_agent TEXT,
                    last_ip TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    risk_signature TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_url_history (
                    email TEXT PRIMARY KEY,
                    urls_json TEXT NOT NULL,
                    total_events INTEGER NOT NULL DEFAULT 0,
                    risky_events INTEGER NOT NULL DEFAULT 0,
                    safe_events INTEGER NOT NULL DEFAULT 0,
                    positive_events INTEGER NOT NULL DEFAULT 0,
                    last_risky_at TEXT,
                    last_safe_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_url_history_updated
                ON student_url_history (updated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_risk_events_email_observed
                ON extension_risk_events (email, observed_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_risk_events_email_signature_observed
                ON extension_risk_events (email, risk_signature, observed_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_google_fit_state (
                    email TEXT PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at TEXT,
                    steps INTEGER NOT NULL DEFAULT 0,
                    sleep_hours REAL NOT NULL DEFAULT 0,
                    steps_component REAL NOT NULL DEFAULT 3,
                    sleep_component REAL NOT NULL DEFAULT 3,
                    fitness_component REAL NOT NULL DEFAULT 3,
                    google_account_email TEXT,
                    google_account_sub TEXT,
                    last_sync_at TEXT,
                    sync_status TEXT,
                    sync_error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            fit_columns = {
                str(row[1]).strip().lower()
                for row in conn.execute("PRAGMA table_info(student_google_fit_state)").fetchall()
            }
            if "google_account_email" not in fit_columns:
                conn.execute("ALTER TABLE student_google_fit_state ADD COLUMN google_account_email TEXT")
            if "google_account_sub" not in fit_columns:
                conn.execute("ALTER TABLE student_google_fit_state ADD COLUMN google_account_sub TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    quiz_key TEXT NOT NULL,
                    quiz_title TEXT NOT NULL,
                    focus TEXT,
                    difficulty TEXT,
                    total_questions INTEGER NOT NULL,
                    average_stress REAL NOT NULL,
                    score_percent INTEGER NOT NULL,
                    risk_band TEXT NOT NULL,
                    answers_json TEXT,
                    result_summary TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Quizzes (
                    quiz_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'casual',
                    created_by TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quiz_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    is_mandatory INTEGER NOT NULL DEFAULT 1,
                    weight INTEGER NOT NULL DEFAULT 1,
                    polarity INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (quiz_id) REFERENCES Quizzes(quiz_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_questions_quiz_id
                ON Questions (quiz_id, question_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_quiz_attempts_email_created
                ON student_quiz_attempts (email, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_quiz_attempts_email_quiz_created
                ON student_quiz_attempts (email, quiz_key, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_student_links (
                    parent_email TEXT PRIMARY KEY,
                    student_email TEXT NOT NULL,
                    assigned_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_parent_alert_contacts (
                    student_email TEXT PRIMARY KEY,
                    parent_name TEXT NOT NULL,
                    parent_phone TEXT NOT NULL,
                    verified INTEGER NOT NULL DEFAULT 0,
                    verified_at TEXT,
                    consent_enabled INTEGER NOT NULL DEFAULT 0,
                    alerts_enabled INTEGER NOT NULL DEFAULT 1,
                    otp_code TEXT,
                    otp_sent_at TEXT,
                    otp_expires_at TEXT,
                    otp_attempts INTEGER NOT NULL DEFAULT 0,
                    admin_edit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_alert_type TEXT,
                    last_alert_trigger TEXT,
                    last_alert_sent_at TEXT,
                    last_known_battery INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_email TEXT NOT NULL,
                    parent_phone TEXT,
                    alert_priority TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    battery INTEGER NOT NULL,
                    previous_battery INTEGER,
                    signal_count INTEGER NOT NULL DEFAULT 0,
                    channel TEXT NOT NULL,
                    send_status TEXT NOT NULL,
                    provider_response TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_auto_counselling_sessions (
                    email TEXT PRIMARY KEY,
                    counsellor_email TEXT,
                    counsellor_name TEXT,
                    session_at TEXT NOT NULL,
                    session_label TEXT NOT NULL,
                    reason TEXT,
                    trigger_battery INTEGER,
                    stress_category TEXT,
                    status TEXT NOT NULL,
                    assigned_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_auto_counselling_session_time
                ON student_auto_counselling_sessions (session_at, status)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_face_check_state (
                    email TEXT PRIMARY KEY,
                    next_due_at TEXT NOT NULL,
                    last_face_check_at TEXT,
                    last_face_emotion TEXT,
                    last_face_score REAL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_face_check_state_due
                ON student_face_check_state (next_due_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_parent_alert_events_student_created
                ON parent_alert_events (student_email, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS proctor_student_links (
                    proctor_email TEXT NOT NULL,
                    student_email TEXT NOT NULL,
                    assigned_by TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (proctor_email, student_email)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_proctor_student_links_proctor
                ON proctor_student_links (proctor_email, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_task_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    claim_date TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    claimed_at TEXT NOT NULL,
                    UNIQUE(email, claim_date, task_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_task_claims_email_date
                ON student_task_claims (email, claim_date, claimed_at)
                """
            )
            conn.commit()
    except sqlite3.Error:
        # Keep app boot resilient if local DB initialization fails.
        pass


def load_student_score_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, stress_score, mental_battery, stress_category, last_checked_url, source, updated_at
                FROM student_score_state
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    try:
        stress_score = max(1.0, min(float(row["stress_score"]), 5.0))
    except (TypeError, ValueError):
        return None

    try:
        mental_battery = max(0, min(int(row["mental_battery"]), 100))
    except (TypeError, ValueError):
        mental_battery = calculate_mental_battery(stress_score)

    return {
        "email": str(row["email"] or key),
        "stress_score": round(stress_score, 2),
        "mental_battery": mental_battery,
        "stress_category": str(row["stress_category"] or classify_live_stress(stress_score)),
        "last_checked_url": str(row["last_checked_url"] or ""),
        "source": str(row["source"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def save_student_score_state(email, stress_score, stress_category, source="runtime", last_checked_url=""):
    key = str(email or "").strip().lower()
    if not key:
        return

    score_value = max(1.0, min(float(stress_score), 5.0))
    battery_value = calculate_mental_battery(score_value)
    category_value = str(stress_category or classify_live_stress(score_value)).upper()
    if category_value not in {"LOW", "MODERATE", "HIGH"}:
        category_value = classify_live_stress(score_value)

    now_iso = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_score_state (
                    email, stress_score, mental_battery, stress_category, last_checked_url, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    stress_score = excluded.stress_score,
                    mental_battery = excluded.mental_battery,
                    stress_category = excluded.stress_category,
                    last_checked_url = excluded.last_checked_url,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    round(score_value, 2),
                    int(battery_value),
                    category_value,
                    str(last_checked_url or "")[:500],
                    str(source or "runtime")[:32],
                    now_iso,
                ),
            )
            conn.commit()
    except sqlite3.Error:
        # Ignore persistence issues so live flow does not fail.
        return


def utc_date_key(value=None):
    dt = value if isinstance(value, datetime) else utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def has_browsable_url_signal(url):
    text = str(url or "").strip().lower()
    if not text:
        return False
    if text.startswith("http://") or text.startswith("https://"):
        return True
    return bool(re.search(r"[a-z0-9-]+\.[a-z]{2,}", text))


def get_student_last_known_extension_url(email):
    key = str(email or "").strip().lower()
    if not key:
        return ""

    live_state = EXTENSION_LIVE_SIGNALS.get(key, {})
    live_url = str(live_state.get("last_checked_url", "")).strip()
    if live_url:
        return live_url[:500]

    saved_state = load_student_score_state(key) or {}
    return str(saved_state.get("last_checked_url", "")).strip()[:500]


def load_student_daily_task_claims(email, claim_date=""):
    key = str(email or "").strip().lower()
    if not key:
        return {"claim_date": utc_date_key(), "claimed_ids": set(), "claimed_points": 0}

    date_key = str(claim_date or "").strip() or utc_date_key()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_key):
        date_key = utc_date_key()

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_id, points
                FROM student_task_claims
                WHERE email = ? AND claim_date = ?
                ORDER BY claimed_at ASC
                """,
                (key, date_key),
            ).fetchall()
    except sqlite3.Error:
        return {"claim_date": date_key, "claimed_ids": set(), "claimed_points": 0}

    claimed_ids = set()
    claimed_points = 0
    for row in rows:
        task_id = str(row["task_id"] or "").strip()
        if task_id:
            claimed_ids.add(task_id)
        try:
            claimed_points += max(0, int(row["points"] or 0))
        except (TypeError, ValueError):
            continue

    return {
        "claim_date": date_key,
        "claimed_ids": claimed_ids,
        "claimed_points": max(0, claimed_points),
    }


def save_student_task_claim(email, claim_date, task_id, points):
    key = str(email or "").strip().lower()
    date_key = str(claim_date or "").strip()
    normalized_task_id = str(task_id or "").strip().lower()[:64]
    try:
        points_value = max(0, int(points or 0))
    except (TypeError, ValueError):
        points_value = 0

    if not key or not date_key or not normalized_task_id or points_value <= 0:
        return "error"

    now_iso = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_task_claims (email, claim_date, task_id, points, claimed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, date_key, normalized_task_id, points_value, now_iso),
            )
            conn.commit()
        return "inserted"
    except sqlite3.IntegrityError:
        return "exists"
    except sqlite3.Error:
        return "error"


def resolve_student_live_score_snapshot(email, mood_score=3):
    key = str(email or "").strip().lower()

    live_stress = session.get("student_live_stress_score")
    live_battery = session.get("student_live_battery")
    live_category = str(session.get("student_live_category", "")).strip().upper()

    if isinstance(live_stress, (int, float)):
        stress_score = max(1.0, min(float(live_stress), 5.0))
        if isinstance(live_battery, (int, float)):
            battery = max(0, min(int(round(live_battery)), 100))
        else:
            battery = calculate_mental_battery(stress_score)
        category = live_category if live_category in {"LOW", "MODERATE", "HIGH"} else classify_live_stress(stress_score)
        return {
            "stress_score": round(stress_score, 2),
            "mental_battery": battery,
            "stress_category": category,
        }

    saved_state = load_student_score_state(key)
    if saved_state:
        return {
            "stress_score": round(float(saved_state.get("stress_score", 3.0)), 2),
            "mental_battery": max(0, min(int(saved_state.get("mental_battery", 50)), 100)),
            "stress_category": str(saved_state.get("stress_category", "MODERATE")).strip().upper() or "MODERATE",
        }

    mood_value = max(1.0, min(float(mood_to_stress_score(mood_score)), 5.0))
    return {
        "stress_score": round(mood_value, 2),
        "mental_battery": calculate_mental_battery(mood_value),
        "stress_category": classify_live_stress(mood_value),
    }


def apply_student_task_reward_score(email, awarded_points):
    key = str(email or "").strip().lower()
    try:
        points_value = max(0, int(awarded_points or 0))
    except (TypeError, ValueError):
        points_value = 0

    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    score_snapshot = resolve_student_live_score_snapshot(key, mood_score=mood["score"])
    if points_value <= 0 or not key:
        return score_snapshot

    reward_delta = float(points_value) * STUDENT_TASK_STRESS_REWARD_PER_POINT
    next_stress = max(1.0, min(float(score_snapshot["stress_score"]) - reward_delta, 5.0))
    next_stress = round(next_stress, 2)
    next_category = classify_live_stress(next_stress)
    next_battery = calculate_mental_battery(next_stress)
    last_checked_url = get_student_last_known_extension_url(key)

    save_student_score_state(
        key,
        next_stress,
        next_category,
        source="task-claim",
        last_checked_url=last_checked_url,
    )

    session["student_live_stress_score"] = next_stress
    session["student_live_category"] = next_category
    session["student_live_battery"] = next_battery

    return {
        "stress_score": next_stress,
        "mental_battery": next_battery,
        "stress_category": next_category,
    }


def build_student_daily_tasks_state(email):
    key = str(email or "").strip().lower()
    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    score_snapshot = resolve_student_live_score_snapshot(key, mood_score=mood["score"])
    google_fit = get_google_fit_overview(key) if key else {
        "connected": False,
        "steps": 0,
        "sleep_hours": 0.0,
        "fitness_component": 3.0,
        "last_sync_at": "",
        "steps_source": "",
        "sync_status": "",
        "sync_error": "",
        "connected_account_email": "",
        "requires_reauth": False,
    }

    steps = max(0, int(google_fit.get("steps", 0) or 0))
    sleep_hours = max(0.0, float(google_fit.get("sleep_hours", 0.0) or 0.0))
    connected_fit = bool(google_fit.get("connected"))

    last_checked_url = get_student_last_known_extension_url(key)
    has_url_signal = has_browsable_url_signal(last_checked_url)
    risky_url = extension_url_context_risk(last_checked_url, "") if has_url_signal else False
    positive_url = extension_url_context_positive_or_neutral(last_checked_url, "", "") if has_url_signal else False

    tasks = []

    tasks.append(
        {
            "id": "mood_pulse",
            "title": "Complete today\'s pulse check",
            "meta": f"Mood tracked as {mood['label']}.",
            "window": "Daily wellbeing",
            "points": 3,
            "completed": True,
            "kind": "mood",
            "icon": "mood",
        }
    )

    if connected_fit:
        tasks.append(
            {
                "id": "steps_4000",
                "title": "Reach 4000 steps",
                "meta": f"Current steps: {steps}.",
                "window": "Movement goal",
                "points": 3,
                "completed": steps >= 4000,
                "kind": "fitness",
                "icon": "directions_walk",
            }
        )
        tasks.append(
            {
                "id": "steps_8000",
                "title": "Reach 8000 steps",
                "meta": f"Current steps: {steps}.",
                "window": "Stretch goal",
                "points": 4,
                "completed": steps >= 8000,
                "kind": "fitness",
                "icon": "hiking",
            }
        )
        tasks.append(
            {
                "id": "sleep_7h",
                "title": "Sleep at least 7 hours",
                "meta": f"Latest sleep record: {sleep_hours:.1f}h.",
                "window": "Sleep routine",
                "points": 4,
                "completed": sleep_hours >= 7.0,
                "kind": "sleep",
                "icon": "bedtime",
            }
        )

    if has_url_signal:
        tasks.append(
            {
                "id": "focus_browsing",
                "title": "Keep browsing focus-friendly",
                "meta": "Recent URL signal indicates low-risk and productive activity." if (positive_url and not risky_url) else "Recent URL signal is still not focus-friendly.",
                "window": "Digital wellbeing",
                "points": 3,
                "completed": bool(positive_url and not risky_url),
                "kind": "digital",
                "icon": "desktop_windows",
            }
        )

    stress_score = max(1.0, min(float(score_snapshot.get("stress_score", 3.0)), 5.0))
    tasks.append(
        {
            "id": "stress_steady",
            "title": "Keep stress in steady zone",
            "meta": f"Current stress score: {stress_score:.2f}/5.",
            "window": "Calm target",
            "points": 3,
            "completed": stress_score <= 2.8,
            "kind": "stress",
            "icon": "self_improvement",
        }
    )

    claim_state = load_student_daily_task_claims(key)
    claimed_ids = claim_state.get("claimed_ids", set())
    claimed_points = max(0, int(claim_state.get("claimed_points", 0)))
    remaining_points = max(0, STUDENT_TASK_DAILY_POINTS_CAP - claimed_points)

    completed_count = 0
    for task in tasks:
        is_completed = bool(task.get("completed"))
        if is_completed:
            completed_count += 1

        is_claimed = str(task.get("id", "")).strip().lower() in claimed_ids
        claim_award = 0
        if is_completed and not is_claimed and remaining_points > 0:
            claim_award = min(int(task.get("points", 0) or 0), remaining_points)

        task["claimed"] = is_claimed
        task["claimable"] = bool(claim_award > 0)
        task["claim_award"] = claim_award

    return {
        "claim_date": str(claim_state.get("claim_date", utc_date_key())),
        "daily_cap": STUDENT_TASK_DAILY_POINTS_CAP,
        "claimed_points": claimed_points,
        "remaining_points": remaining_points,
        "total_tasks": len(tasks),
        "completed_tasks": completed_count,
        "score": {
            "mental_battery": int(score_snapshot.get("mental_battery", mood["battery"])),
            "stress_score": round(float(score_snapshot.get("stress_score", mood_to_stress_score(mood["score"]))), 2),
            "stress_category": str(score_snapshot.get("stress_category", classify_live_stress(mood_to_stress_score(mood["score"])))),
        },
        "signals": {
            "mood_label": mood["label"],
            "mood_score": int(mood["score"]),
            "steps": steps,
            "sleep_hours": round(sleep_hours, 2),
            "fit_connected": connected_fit,
            "fit_sync": str(google_fit.get("last_sync_at", "") or ""),
            "last_checked_url": last_checked_url,
        },
        "tasks": tasks,
    }


def load_student_face_check_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, next_due_at, last_face_check_at, last_face_emotion, last_face_score, updated_at
                FROM student_face_check_state
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    try:
        face_score = float(row["last_face_score"]) if row["last_face_score"] is not None else None
    except (TypeError, ValueError):
        face_score = None

    return {
        "email": str(row["email"] or key),
        "next_due_at": str(row["next_due_at"] or ""),
        "last_face_check_at": str(row["last_face_check_at"] or ""),
        "last_face_emotion": normalize_face_emotion_key(row["last_face_emotion"]),
        "last_face_score": face_score,
        "updated_at": str(row["updated_at"] or ""),
    }


def save_student_face_check_state(
    email,
    next_due_at,
    last_face_check_at=None,
    last_face_emotion="",
    last_face_score=None,
):
    key = str(email or "").strip().lower()
    if not key:
        return

    now_dt = utc_now()
    due_dt = parse_iso_datetime(next_due_at)
    if not due_dt:
        due_dt = now_dt + timedelta(days=FACE_CHECK_GRACE_DAYS)

    checked_dt = parse_iso_datetime(last_face_check_at)
    checked_iso = checked_dt.isoformat(timespec="seconds") if checked_dt else ""

    emotion_key = normalize_face_emotion_key(last_face_emotion)
    if not emotion_key:
        emotion_key = ""

    score_value = None
    if last_face_score is not None:
        try:
            score_value = max(1.0, min(float(last_face_score), 5.0))
        except (TypeError, ValueError):
            score_value = None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_face_check_state (
                    email, next_due_at, last_face_check_at, last_face_emotion, last_face_score, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    next_due_at = excluded.next_due_at,
                    last_face_check_at = excluded.last_face_check_at,
                    last_face_emotion = excluded.last_face_emotion,
                    last_face_score = excluded.last_face_score,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    due_dt.isoformat(timespec="seconds"),
                    checked_iso,
                    emotion_key,
                    score_value,
                    now_dt.isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
    except sqlite3.Error:
        return


def ensure_student_face_check_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    existing = load_student_face_check_state(key)
    now_dt = utc_now()
    if not existing:
        save_student_face_check_state(
            key,
            next_due_at=(now_dt + timedelta(days=FACE_CHECK_GRACE_DAYS)).isoformat(timespec="seconds"),
        )
        return load_student_face_check_state(key)

    due_dt = parse_iso_datetime(existing.get("next_due_at"))
    if due_dt:
        return existing

    save_student_face_check_state(
        key,
        next_due_at=(now_dt + timedelta(days=FACE_CHECK_GRACE_DAYS)).isoformat(timespec="seconds"),
        last_face_check_at=existing.get("last_face_check_at"),
        last_face_emotion=existing.get("last_face_emotion"),
        last_face_score=existing.get("last_face_score"),
    )
    return load_student_face_check_state(key)


def is_student_face_check_required(face_state, now_dt=None):
    if not face_state:
        return False
    due_dt = parse_iso_datetime(face_state.get("next_due_at"))
    if not due_dt:
        return False
    current = now_dt or utc_now()
    return current >= due_dt


def build_face_check_grace_meta(face_state, now_dt=None):
    due_dt = parse_iso_datetime((face_state or {}).get("next_due_at"))
    if not due_dt:
        return {
            "due_iso": "",
            "remaining_days": FACE_CHECK_GRACE_DAYS,
            "remaining_hours": FACE_CHECK_GRACE_DAYS * 24,
            "overdue_hours": 0,
        }

    current = now_dt or utc_now()
    delta_seconds = (due_dt - current).total_seconds()
    if delta_seconds >= 0:
        remaining_hours = int((delta_seconds + 3599) // 3600)
        remaining_days = int((delta_seconds + 86399) // 86400)
        return {
            "due_iso": due_dt.isoformat(timespec="seconds"),
            "remaining_days": max(0, remaining_days),
            "remaining_hours": max(0, remaining_hours),
            "overdue_hours": 0,
        }

    overdue_seconds = abs(delta_seconds)
    overdue_hours = int((overdue_seconds + 3599) // 3600)
    return {
        "due_iso": due_dt.isoformat(timespec="seconds"),
        "remaining_days": 0,
        "remaining_hours": 0,
        "overdue_hours": max(1, overdue_hours),
    }


def quiz_focus_from_stress_band(stress_band):
    focus_map = {
        "LOW": "Growth",
        "MODERATE": "Balance",
        "HIGH": "Stabilize",
    }
    return focus_map.get(str(stress_band or "").upper(), "Balance")


def normalize_quiz_mode_key(value):
    raw = str(value or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return cleaned or "mode"


def format_quiz_mode_title(mode_key):
    cleaned = str(mode_key or "").replace("_", " ").strip()
    return cleaned.title() if cleaned else "Mode"


def quiz_prompt_has_negative_bias(prompt):
    text = str(prompt or "").strip().lower()
    negative_markers = {
        "stressed",
        "stress",
        "anxious",
        "anxiety",
        "lonely",
        "overwhelmed",
        "mood swings",
        "irritated",
        "angry",
        "overthink",
        "sad",
        "restless",
        "burnout",
        "pressure",
        "worry",
        "procrastinate",
        "tension",
        "exhausted",
        "avoid",
        "conflicts",
        "judged",
        "drained",
        "unable to cope",
        "emotionally sensitive",
        "act before thinking",
    }
    return any(marker in text for marker in negative_markers)


def build_mode_question_option_set(mode_key, prompt_text):
    negative = quiz_prompt_has_negative_bias(prompt_text)
    key = str(mode_key or "")
    if key == "casual":
        if negative:
            yes_stress, no_stress = 4.0, 2.5
        else:
            yes_stress, no_stress = 2.0, 3.2
    else:
        if negative:
            yes_stress, no_stress = 5.0, 2.0
        else:
            yes_stress, no_stress = 1.0, 4.0

    return [
        {"id": "yes", "label": "Yes", "stress": round(yes_stress, 2)},
        {"id": "no", "label": "No", "stress": round(no_stress, 2)},
    ]


def infer_quiz_focus_from_title(title, quiz_type=""):
    text = str(title or "").strip().lower()
    quiz_type_text = str(quiz_type or "").strip().lower()

    if "academic" in text:
        return "Academics"
    if "anxiety" in text:
        return "Anxiety"
    if "depression" in text or "mood" in text:
        return "Mood"
    if "social" in text:
        return "Social"
    if "sleep" in text or "recovery" in text:
        return "Recovery"

    return "Balance" if quiz_type_text == "casual" else "Stabilize"


def build_db_question_option_set(quiz_type, polarity, weight):
    quiz_type_text = str(quiz_type or "").strip().lower()
    serious_mode = quiz_type_text == "serious"
    polarity_value = -1 if int(polarity or 1) < 0 else 1

    base_low = 1.7 if serious_mode else 2.1
    base_high = 4.9 if serious_mode else 4.3

    try:
        weight_value = max(1, min(int(weight or 1), 5))
    except (TypeError, ValueError):
        weight_value = 1

    delta = (weight_value - 1) * (0.14 if serious_mode else 0.12)
    high_stress = max(3.2, min(base_high + delta, 5.0))
    low_stress = max(1.0, min(base_low - (delta * 0.4), 3.3))

    yes_stress = high_stress if polarity_value < 0 else low_stress
    no_stress = low_stress if polarity_value < 0 else high_stress

    return [
        {"id": "yes", "label": "Yes, this matches me", "stress": round(yes_stress, 2)},
        {"id": "no", "label": "No, this does not match me", "stress": round(no_stress, 2)},
    ]


def load_quiz_library_from_db():
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            quiz_rows = conn.execute(
                """
                SELECT quiz_id, title, type
                FROM Quizzes
                ORDER BY quiz_id ASC
                """
            ).fetchall()

            if not quiz_rows:
                return {}

            question_rows = conn.execute(
                """
                SELECT quiz_id, question_id, question_text, is_mandatory, weight, COALESCE(polarity, 1) AS polarity
                FROM Questions
                ORDER BY quiz_id ASC, question_id ASC
                """
            ).fetchall()
    except sqlite3.Error:
        return {}

    questions_by_quiz = {}
    for row in question_rows:
        quiz_id = int(row["quiz_id"])
        questions_by_quiz.setdefault(quiz_id, []).append(row)

    library = {}
    for row in quiz_rows:
        quiz_id = int(row["quiz_id"])
        title = str(row["title"] or "Mind Check Quiz").strip()
        quiz_type = str(row["type"] or "casual").strip().lower()

        grouped_questions = questions_by_quiz.get(quiz_id, [])
        if not grouped_questions:
            continue

        base_key = normalize_quiz_mode_key(title)
        quiz_key = base_key
        if quiz_key in library:
            quiz_key = f"{base_key}_{quiz_id}"

        questions = []
        for index, qrow in enumerate(grouped_questions, start=1):
            prompt_text = str(qrow["question_text"] or "").strip()
            if not prompt_text:
                continue

            question_id = str(qrow["question_id"] or "").strip() or f"{quiz_key}_{index}"
            options = build_db_question_option_set(
                quiz_type=quiz_type,
                polarity=qrow["polarity"],
                weight=qrow["weight"],
            )

            questions.append(
                {
                    "id": question_id,
                    "prompt": prompt_text,
                    "options": options,
                }
            )

        if not questions:
            continue

        question_count = len(questions)
        duration_minutes = max(4, min(14, 3 + int(round(question_count / 2.5))))
        difficulty = "Advanced" if quiz_type == "serious" else "Easy"

        library[quiz_key] = {
            "title": title,
            "duration": f"{duration_minutes} min",
            "difficulty": difficulty,
            "focus": infer_quiz_focus_from_title(title, quiz_type),
            "description": f"Question-bank powered quiz with {question_count} statements.",
            "cta": "Start Quiz",
            "questions": questions,
        }

    return library


def load_quiz_library_from_mode_files():
    if not QUIZ_MODES_DIR.exists() or not QUIZ_MODES_DIR.is_dir():
        return {}

    library = {}
    try:
        mode_files = sorted(QUIZ_MODES_DIR.glob("*.txt"), key=lambda item: item.name.lower())
    except OSError:
        mode_files = []

    for file_path in mode_files:
        mode_key = normalize_quiz_mode_key(file_path.stem)
        mode_title = format_quiz_mode_title(mode_key)
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        prompts = []
        for line in lines:
            stripped = str(line or "").strip()
            if not stripped:
                continue
            prompt = re.sub(r"\(\s*yes\s*/\s*no\s*\)\s*$", "", stripped, flags=re.IGNORECASE).strip()
            if prompt:
                prompts.append(prompt)

        if not prompts:
            continue

        questions = []
        for idx, prompt in enumerate(prompts, start=1):
            questions.append(
                {
                    "id": f"{mode_key}_{idx}",
                    "prompt": prompt,
                    "options": build_mode_question_option_set(mode_key, prompt),
                }
            )

        total_in_mode = len(questions)
        session_count = min(QUIZ_MODE_QUESTION_LIMIT, total_in_mode)
        library[mode_key] = {
            "title": f"{mode_title} Mode Quiz",
            "duration": f"{session_count} questions",
            "difficulty": "Easy" if mode_key == "casual" else "Advanced",
            "focus": mode_title,
            "description": f"Built from {file_path.name}. Answer a {session_count}-question check-in for this mode.",
            "cta": f"Start {mode_title}",
            "questions": questions,
        }

    return library


def get_active_quiz_library():
    database_library = load_quiz_library_from_db()
    mode_library = load_quiz_library_from_mode_files()

    if database_library and mode_library:
        merged = {}
        merged.update(database_library)
        merged.update(mode_library)
        return merged

    if database_library:
        return database_library

    if mode_library:
        return mode_library

    return STUDENT_QUIZ_LIBRARY


def normalize_quiz_type(value):
    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in {"casual", "serious"} else "casual"


def parse_developer_quiz_questions(raw_text, max_items=25):
    parsed = []
    for raw_line in str(raw_text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", str(raw_line or "").strip())
        if line:
            parsed.append(line[:260])
        if len(parsed) >= max(3, int(max_items or 25)):
            break
    return parsed


def create_quiz_bank_entry(title, quiz_type, created_by, question_lines):
    safe_title = str(title or "").strip()[:140]
    safe_type = normalize_quiz_type(quiz_type)
    safe_creator = str(created_by or "").strip().lower()[:320]
    questions = [str(item or "").strip()[:260] for item in (question_lines or []) if str(item or "").strip()]

    if not safe_title:
        return False, "Quiz title is required.", None
    if len(questions) < 3:
        return False, "Provide at least 3 quiz questions.", None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO Quizzes (title, type, created_by)
                VALUES (?, ?, ?)
                """,
                (safe_title, safe_type, safe_creator),
            )
            quiz_id = int(cursor.lastrowid or 0)
            if quiz_id <= 0:
                return False, "Could not create quiz record.", None

            rows = []
            for question_text in questions:
                polarity = -1 if quiz_prompt_has_negative_bias(question_text) else 1
                weight = 2 if safe_type == "serious" else 1
                rows.append((quiz_id, question_text, 1, weight, polarity))

            conn.executemany(
                """
                INSERT INTO Questions (
                    quiz_id, question_text, is_mandatory, weight, polarity
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
    except sqlite3.Error:
        return False, "Unable to save quiz right now.", None

    return True, "", {"quiz_id": quiz_id, "question_count": len(questions), "quiz_type": safe_type}


def list_student_quiz_catalog(focus_hint="Balance"):
    library = get_active_quiz_library()
    cards = []
    for quiz_key, quiz_data in library.items():
        focus = str(quiz_data.get("focus", "Balance"))
        if quiz_key == "daily_stress_check" and str(focus_hint or "").strip():
            focus = str(focus_hint).strip()

        cards.append(
            {
                "key": quiz_key,
                "title": str(quiz_data.get("title", "Mind Check")),
                "duration": str(quiz_data.get("duration", "4 min")),
                "difficulty": str(quiz_data.get("difficulty", "Easy")),
                "focus": focus,
                "description": str(quiz_data.get("description", "")),
                "cta": str(quiz_data.get("cta", "Start Quiz")),
            }
        )
    return cards


def get_student_quiz_payload(quiz_key, focus_hint=""):
    key = str(quiz_key or "").strip().lower()
    library = get_active_quiz_library()
    raw = library.get(key)
    if not raw:
        return None

    focus = str(raw.get("focus", "Balance"))
    if key == "daily_stress_check" and str(focus_hint or "").strip():
        focus = str(focus_hint).strip()

    raw_questions = list(raw.get("questions", []))
    questions = []
    for question in raw_questions[: max(1, QUIZ_MODE_QUESTION_LIMIT)]:
        options = []
        for option in question.get("options", []):
            try:
                stress_value = max(1.0, min(float(option.get("stress", 3.0)), 5.0))
            except (TypeError, ValueError):
                stress_value = 3.0

            options.append(
                {
                    "id": str(option.get("id", "")).strip(),
                    "label": str(option.get("label", "")).strip(),
                    "stress": round(stress_value, 2),
                    "preview_score": int(round(((6.0 - stress_value) / 5.0) * 100)),
                }
            )

        questions.append(
            {
                "id": str(question.get("id", "")).strip(),
                "prompt": str(question.get("prompt", "")).strip(),
                "options": options,
            }
        )

    return {
        "key": key,
        "title": str(raw.get("title", "Mind Check")),
        "duration": str(raw.get("duration", "4 min")),
        "difficulty": str(raw.get("difficulty", "Easy")),
        "focus": focus,
        "description": str(raw.get("description", "")),
        "questions": questions,
    }


def evaluate_student_quiz_answers(quiz_key, answers):
    quiz_payload = get_student_quiz_payload(quiz_key)
    if not quiz_payload:
        return None, "Unknown quiz key."

    if not isinstance(answers, dict):
        return None, "Answers payload must be an object."

    normalized_answers = {}
    stress_points = []
    for question in quiz_payload.get("questions", []):
        question_id = str(question.get("id", "")).strip()
        selected_id = str(answers.get(question_id, "")).strip().lower()
        if not question_id or not selected_id:
            return None, "All quiz questions must be answered."

        option_map = {
            str(item.get("id", "")).strip().lower(): item
            for item in question.get("options", [])
            if str(item.get("id", "")).strip()
        }
        selected_option = option_map.get(selected_id)
        if not selected_option:
            return None, "One or more selected answers are invalid."

        try:
            stress_value = max(1.0, min(float(selected_option.get("stress", 3.0)), 5.0))
        except (TypeError, ValueError):
            stress_value = 3.0

        normalized_answers[question_id] = selected_id
        stress_points.append(stress_value)

    if not stress_points:
        return None, "No valid quiz answers were submitted."

    average_stress = round(sum(stress_points) / len(stress_points), 2)
    risk_band = classify_live_stress(average_stress)
    score_percent = int(round(((6.0 - average_stress) / 5.0) * 100))
    score_percent = max(0, min(score_percent, 100))

    summary_map = {
        "LOW": "You are in a stable state. Keep reinforcing your healthy routines.",
        "MODERATE": "You are managing, but stress is building. Add structured recovery today.",
        "HIGH": "Your stress load is elevated. Prioritize support and recovery right away.",
    }
    recommendations_map = {
        "LOW": [
            "Continue short daily reflection and hydration breaks.",
            "Protect your current sleep rhythm for the next 3 days.",
        ],
        "MODERATE": [
            "Use a 25/5 study cycle and schedule two short walks.",
            "Book a check-in slot if symptoms stay the same for 48 hours.",
        ],
        "HIGH": [
            "Reach a counsellor or trusted mentor today.",
            "Reduce workload for the next 24 hours and prioritize sleep.",
        ],
    }

    mood_analysis_map = {
        "LOW": "Mood analysis: your answers indicate a steady and emotionally balanced state.",
        "MODERATE": "Mood analysis: your answers show moderate emotional strain with manageable pressure.",
        "HIGH": "Mood analysis: your answers indicate elevated emotional load and possible overwhelm.",
    }
    risk_analysis_map = {
        "LOW": "Risk analysis: low immediate risk. Continue routine check-ins to maintain momentum.",
        "MODERATE": "Risk analysis: medium risk. Add structured recovery and monitor signs over the next 48 hours.",
        "HIGH": "Risk analysis: high risk. Prioritize support from a counsellor or trusted mentor today.",
    }

    return {
        "average_stress": average_stress,
        "risk_band": risk_band,
        "score_percent": score_percent,
        "summary": summary_map.get(risk_band, summary_map["MODERATE"]),
        "mood_analysis": mood_analysis_map.get(risk_band, mood_analysis_map["MODERATE"]),
        "risk_analysis": risk_analysis_map.get(risk_band, risk_analysis_map["MODERATE"]),
        "recommendations": recommendations_map.get(risk_band, recommendations_map["MODERATE"]),
        "total_questions": len(stress_points),
        "answers": normalized_answers,
    }, ""


def save_student_quiz_attempt(email, quiz_key, quiz_payload, quiz_result):
    key = str(email or "").strip().lower()
    if not key:
        return None

    quiz_name = str((quiz_payload or {}).get("title", "Mind Check"))[:120]
    focus = str((quiz_payload or {}).get("focus", "Balance"))[:48]
    difficulty = str((quiz_payload or {}).get("difficulty", "Easy"))[:32]
    answers_json = json.dumps((quiz_result or {}).get("answers", {}), separators=(",", ":"))[:2000]
    summary = str((quiz_result or {}).get("summary", ""))[:320]
    created_at = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO student_quiz_attempts (
                    email, quiz_key, quiz_title, focus, difficulty,
                    total_questions, average_stress, score_percent,
                    risk_band, answers_json, result_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    str(quiz_key or "")[:64],
                    quiz_name,
                    focus,
                    difficulty,
                    int((quiz_result or {}).get("total_questions", 0) or 0),
                    float((quiz_result or {}).get("average_stress", 3.0) or 3.0),
                    int((quiz_result or {}).get("score_percent", 0) or 0),
                    str((quiz_result or {}).get("risk_band", "MODERATE"))[:16],
                    answers_json,
                    summary,
                    created_at,
                ),
            )
            conn.commit()
            attempt_id = int(cursor.lastrowid or 0)
    except (sqlite3.Error, ValueError, TypeError):
        return None

    return {
        "id": attempt_id,
        "quiz_key": str(quiz_key or ""),
        "quiz_title": quiz_name,
        "focus": focus,
        "difficulty": difficulty,
        "score_percent": int((quiz_result or {}).get("score_percent", 0) or 0),
        "risk_band": str((quiz_result or {}).get("risk_band", "MODERATE")),
        "created_at": created_at,
        "created_at_label": parse_time_label(created_at),
    }


def list_student_quiz_attempts(email, limit=8):
    key = str(email or "").strip().lower()
    if not key:
        return []

    safe_limit = max(1, min(int(limit or 8), 50))
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, quiz_key, quiz_title, focus, difficulty, total_questions,
                       average_stress, score_percent, risk_band, answers_json,
                       result_summary, created_at
                FROM student_quiz_attempts
                WHERE email = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (key, safe_limit),
            ).fetchall()
    except sqlite3.Error:
        return []

    attempts = []
    for row in rows:
        try:
            parsed_answers = json.loads(str(row["answers_json"] or "{}"))
            if not isinstance(parsed_answers, dict):
                parsed_answers = {}
        except json.JSONDecodeError:
            parsed_answers = {}

        risk_band = str(row["risk_band"] or "MODERATE").upper()
        if risk_band not in {"LOW", "MODERATE", "HIGH"}:
            risk_band = "MODERATE"

        attempts.append(
            {
                "id": int(row["id"]),
                "quiz_key": str(row["quiz_key"] or ""),
                "quiz_title": str(row["quiz_title"] or "Mind Check"),
                "focus": str(row["focus"] or "Balance"),
                "difficulty": str(row["difficulty"] or "Easy"),
                "total_questions": int(row["total_questions"] or 0),
                "average_stress": round(float(row["average_stress"] or 3.0), 2),
                "score_percent": int(row["score_percent"] or 0),
                "risk_band": risk_band,
                "result_summary": str(row["result_summary"] or ""),
                "answers": parsed_answers,
                "created_at": str(row["created_at"] or ""),
                "created_at_label": parse_time_label(row["created_at"]),
            }
        )
    return attempts


def latest_student_quiz_attempt_map(email):
    attempts = list_student_quiz_attempts(email, limit=30)
    latest = {}
    for attempt in attempts:
        key = str(attempt.get("quiz_key", "")).strip().lower()
        if key and key not in latest:
            latest[key] = attempt
    return latest


def build_student_weekly_logs(email, mood_battery):
    baseline_stress = max(18, min(90, 100 - int(round(float(mood_battery or 0)))))
    today = datetime.now(timezone.utc).date()
    stress_by_day = {}

    attempts = list_student_quiz_attempts(email, limit=35)
    for attempt in attempts:
        created_raw = str(attempt.get("created_at", "")).strip()
        if not created_raw:
            continue

        try:
            created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            continue

        day = created_dt.date()
        day_delta = (today - day).days
        if day_delta < 0 or day_delta > 6:
            continue

        score_percent = int(attempt.get("score_percent", 0) or 0)
        attempt_stress = max(0, min(100, 100 - score_percent))
        stress_by_day.setdefault(day, []).append(attempt_stress)

    weekly_logs = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily_values = stress_by_day.get(day, [])
        if daily_values:
            stress_value = round(sum(daily_values) / len(daily_values))
        else:
            # Keep gaps visually stable while still reflecting baseline stress.
            weekday_drift = ((day.weekday() * 3) % 11) - 5
            stress_value = baseline_stress + weekday_drift

        weekly_logs.append(
            {
                "day": day.strftime("%a"),
                "stress": max(10, min(95, int(stress_value))),
            }
        )

    return weekly_logs


def build_student_quiz_cards(email, focus_hint):
    cards = list_student_quiz_catalog(focus_hint=focus_hint)
    latest_map = latest_student_quiz_attempt_map(email)

    decorated = []
    for card in cards:
        key = str(card.get("key", "")).strip().lower()
        latest_attempt = latest_map.get(key)
        cta = str(card.get("cta", "Start Quiz"))
        if latest_attempt:
            cta = "Retake Quiz"

        decorated.append(
            {
                **card,
                "cta": cta,
                "last_attempt": latest_attempt,
            }
        )
    return decorated


def suggest_quiz_for_student(quiz_cards, stress_band):
    if not quiz_cards:
        return "", "No quizzes available right now."

    normalized_band = str(stress_band or "").strip().upper()
    key_priority_map = {
        "HIGH": ["serious", "sleep", "recovery", "exam", "stress", "daily"],
        "MODERATE": ["daily", "stress", "exam", "sleep", "balance"],
        "LOW": ["casual", "daily", "growth", "exam", "sleep"],
    }
    reason_map = {
        "HIGH": "Suggested based on your current stress trend: start with a stabilizing quiz.",
        "MODERATE": "Suggested based on your current stress trend: start with a balance check-in.",
        "LOW": "Suggested based on your current stress trend: start with a light growth check-in.",
    }

    priority_tokens = key_priority_map.get(normalized_band, key_priority_map["MODERATE"])

    for token in priority_tokens:
        for card in quiz_cards:
            card_key = str(card.get("key", "")).strip().lower()
            title = str(card.get("title", "")).strip().lower()
            focus = str(card.get("focus", "")).strip().lower()
            if token in card_key or token in title or token in focus:
                return card_key, reason_map.get(normalized_band, reason_map["MODERATE"])

    for card in quiz_cards:
        if not card.get("last_attempt"):
            return str(card.get("key", "")).strip().lower(), "Suggested because this quiz has no previous attempt yet."

    fallback = str(quiz_cards[0].get("key", "")).strip().lower()
    return fallback, reason_map.get(normalized_band, reason_map["MODERATE"])


def seed_session_from_saved_student_state(email):
    if isinstance(session.get("student_live_stress_score"), (int, float)):
        return False

    saved = load_student_score_state(email)
    if not saved:
        return False

    session["student_live_stress_score"] = float(saved["stress_score"])
    session["student_live_battery"] = int(saved["mental_battery"])
    session["student_live_category"] = str(saved["stress_category"])
    return True


def load_google_fit_db_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, access_token, refresh_token, expires_at, steps, sleep_hours,
                      steps_component, sleep_component, fitness_component,
                      google_account_email, google_account_sub,
                       last_sync_at, sync_status, sync_error, updated_at
                FROM student_google_fit_state
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    return {
        "email": key,
        "access_token": str(row["access_token"] or ""),
        "refresh_token": str(row["refresh_token"] or ""),
        "expires_at": str(row["expires_at"] or ""),
        "steps": int(row["steps"] or 0),
        "sleep_hours": round(float(row["sleep_hours"] or 0.0), 2),
        "steps_component": round(float(row["steps_component"] or 3.0), 2),
        "sleep_component": round(float(row["sleep_component"] or 3.0), 2),
        "fitness_component": round(float(row["fitness_component"] or 3.0), 2),
        "google_account_email": str(row["google_account_email"] or "").strip().lower(),
        "google_account_sub": str(row["google_account_sub"] or "").strip(),
        "last_sync_at": str(row["last_sync_at"] or ""),
        "sync_status": str(row["sync_status"] or ""),
        "sync_error": str(row["sync_error"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def save_google_fit_db_state(email, updates):
    key = str(email or "").strip().lower()
    if not key:
        return False

    existing = load_google_fit_db_state(key) or {}
    merged = {**existing, **(updates or {})}
    now_iso = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_google_fit_state (
                    email, access_token, refresh_token, expires_at, steps, sleep_hours,
                    steps_component, sleep_component, fitness_component,
                    google_account_email, google_account_sub,
                    last_sync_at, sync_status, sync_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expires_at = excluded.expires_at,
                    steps = excluded.steps,
                    sleep_hours = excluded.sleep_hours,
                    steps_component = excluded.steps_component,
                    sleep_component = excluded.sleep_component,
                    fitness_component = excluded.fitness_component,
                    google_account_email = excluded.google_account_email,
                    google_account_sub = excluded.google_account_sub,
                    last_sync_at = excluded.last_sync_at,
                    sync_status = excluded.sync_status,
                    sync_error = excluded.sync_error,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    str(merged.get("access_token", ""))[:2000],
                    str(merged.get("refresh_token", ""))[:2000],
                    str(merged.get("expires_at", ""))[:64],
                    int(max(0, int(merged.get("steps", 0) or 0))),
                    float(max(0.0, float(merged.get("sleep_hours", 0.0) or 0.0))),
                    float(normalize_component_score(merged.get("steps_component", 3.0), 3.0)),
                    float(normalize_component_score(merged.get("sleep_component", 3.0), 3.0)),
                    float(normalize_component_score(merged.get("fitness_component", 3.0), 3.0)),
                    str(merged.get("google_account_email", "")).strip().lower()[:320],
                    str(merged.get("google_account_sub", "")).strip()[:160],
                    str(merged.get("last_sync_at", ""))[:64],
                    str(merged.get("sync_status", ""))[:64],
                    str(merged.get("sync_error", ""))[:400],
                    now_iso,
                ),
            )
            conn.commit()
        return True
    except (sqlite3.Error, ValueError, TypeError):
        return False


def load_extension_security_db_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, extension_email, installed_at, consent_granted_at,
                       last_seen_at, source, last_user_agent, last_ip, updated_at
                FROM student_extension_security_state
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    return {
        "email": key,
        "extension_email": str(row["extension_email"] or "").strip().lower(),
        "installed_at": str(row["installed_at"] or ""),
        "consent_granted_at": str(row["consent_granted_at"] or ""),
        "last_seen_at": str(row["last_seen_at"] or ""),
        "source": str(row["source"] or ""),
        "last_user_agent": str(row["last_user_agent"] or ""),
        "last_ip": str(row["last_ip"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def save_extension_security_db_state(email, updates):
    key = str(email or "").strip().lower()
    if not key:
        return False

    existing = load_extension_security_db_state(key) or {}
    merged = {**existing, **(updates or {})}
    now_iso = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_extension_security_state (
                    email, extension_email, installed_at, consent_granted_at,
                    last_seen_at, source, last_user_agent, last_ip, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    extension_email = excluded.extension_email,
                    installed_at = excluded.installed_at,
                    consent_granted_at = excluded.consent_granted_at,
                    last_seen_at = excluded.last_seen_at,
                    source = excluded.source,
                    last_user_agent = excluded.last_user_agent,
                    last_ip = excluded.last_ip,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    str(merged.get("extension_email", key)).strip().lower()[:320],
                    str(merged.get("installed_at", ""))[:64],
                    str(merged.get("consent_granted_at", ""))[:64],
                    str(merged.get("last_seen_at", ""))[:64],
                    str(merged.get("source", ""))[:64],
                    str(merged.get("last_user_agent", ""))[:600],
                    str(merged.get("last_ip", ""))[:120],
                    now_iso,
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def normalize_account_role(role_value):
    role = str(role_value or "").strip().lower()
    if role in ACCOUNT_ROLES:
        return role
    return ""


def normalize_account_status(status_value):
    status = str(status_value or "").strip().lower()
    if status in ACCOUNT_STATUSES:
        return status
    return "pending"


def get_user_account_by_email(email):
    key = str(email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, name, email, password, role, status, requested_note,
                       created_at, approved_at, approved_by
                FROM user_accounts
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    return {
        "id": int(row["id"]),
        "name": str(row["name"] or ""),
        "email": str(row["email"] or "").strip().lower(),
        "password": str(row["password"] or ""),
        "role": normalize_account_role(row["role"]),
        "status": normalize_account_status(row["status"]),
        "requested_note": str(row["requested_note"] or ""),
        "created_at": str(row["created_at"] or ""),
        "approved_at": str(row["approved_at"] or ""),
        "approved_by": str(row["approved_by"] or ""),
    }


def list_user_accounts(role=None, status=None, limit=250):
    safe_role = normalize_account_role(role)
    safe_status = normalize_account_status(status) if status else ""
    safe_limit = max(1, min(int(limit or 250), 1000))

    where_parts = []
    params = []
    if safe_role:
        where_parts.append("role = ?")
        params.append(safe_role)
    if safe_status:
        where_parts.append("status = ?")
        params.append(safe_status)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, name, email, password, role, status, requested_note,
                       created_at, approved_at, approved_by
                FROM user_accounts
                {where_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                tuple([*params, safe_limit]),
            ).fetchall()
    except (sqlite3.Error, ValueError):
        return []

    output = []
    for row in rows:
        output.append(
            {
                "id": int(row["id"]),
                "name": str(row["name"] or ""),
                "email": str(row["email"] or "").strip().lower(),
                "role": normalize_account_role(row["role"]),
                "status": normalize_account_status(row["status"]),
                "requested_note": str(row["requested_note"] or ""),
                "created_at": str(row["created_at"] or ""),
                "approved_at": str(row["approved_at"] or ""),
                "approved_by": str(row["approved_by"] or ""),
            }
        )
    return output


def upsert_user_account(name, email, password, role, status="pending", requested_note="", approved_by=""):
    safe_name = str(name or "").strip()[:120]
    safe_email = str(email or "").strip().lower()[:320]
    safe_password = str(password or "")[:200]
    safe_role = normalize_account_role(role)
    safe_status = normalize_account_status(status)
    safe_note = str(requested_note or "").strip()[:400]
    safe_approved_by = str(approved_by or "").strip().lower()[:320]

    if not safe_name or not safe_email or not safe_password or not safe_role:
        return False, "Missing required account fields."

    now_iso = utc_now().isoformat(timespec="seconds")
    approved_at = now_iso if safe_status == "approved" else ""

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO user_accounts (
                    name, email, password, role, status, requested_note, created_at, approved_at, approved_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = excluded.name,
                    password = excluded.password,
                    role = excluded.role,
                    status = excluded.status,
                    requested_note = excluded.requested_note,
                    approved_at = excluded.approved_at,
                    approved_by = excluded.approved_by
                """,
                (
                    safe_name,
                    safe_email,
                    safe_password,
                    safe_role,
                    safe_status,
                    safe_note,
                    now_iso,
                    approved_at,
                    safe_approved_by,
                ),
            )
            conn.commit()
        return True, ""
    except sqlite3.Error:
        return False, "Unable to save account right now."


def update_user_account_status(account_id, status, approved_by=""):
    safe_status = normalize_account_status(status)
    approved_at = utc_now().isoformat(timespec="seconds") if safe_status == "approved" else ""
    safe_approved_by = str(approved_by or "").strip().lower()[:320]

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            cursor = conn.execute(
                """
                UPDATE user_accounts
                SET status = ?, approved_at = ?, approved_by = ?
                WHERE id = ?
                """,
                (safe_status, approved_at, safe_approved_by, int(account_id)),
            )
            conn.commit()
            return int(cursor.rowcount or 0) > 0
    except (sqlite3.Error, ValueError, TypeError):
        return False


def ensure_default_accounts_seeded():
    for role, payload in CREDENTIALS.items():
        safe_role = normalize_account_role(role)
        if not safe_role:
            continue
        upsert_user_account(
            name=payload.get("name", safe_role.title()),
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            role=safe_role,
            status="approved",
            requested_note="Seeded default account",
            approved_by="system",
        )


def get_mock_showcase_accounts():
    accounts = []
    seen = set()

    for role, payload in CREDENTIALS.items():
        safe_role = normalize_account_role(role)
        if not safe_role:
            continue
        email = str(payload.get("email", "")).strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        accounts.append(
            {
                "role": safe_role,
                "email": email,
                "password": str(payload.get("password", "")),
                "name": str(payload.get("name", safe_role.title())),
            }
        )

    for payload in MOCK_SHOWCASE_EXTRA_ACCOUNTS:
        safe_role = normalize_account_role(payload.get("role", ""))
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        name = str(payload.get("name", "")).strip()
        if not safe_role or not email or not password or email in seen:
            continue
        seen.add(email)
        accounts.append(
            {
                "role": safe_role,
                "email": email,
                "password": password,
                "name": name or safe_role.title(),
            }
        )
    return accounts


def list_mock_login_credentials(selected_role="", unique_per_role=False):
    if not EQWELL_ENABLE_MOCK_LOGINS:
        return []

    safe_role = normalize_account_role(selected_role)
    ordering = {role: idx for idx, role in enumerate(ACCOUNT_ROLES)}
    records = []
    for item in get_mock_showcase_accounts():
        if safe_role and item.get("role") != safe_role:
            continue
        records.append(item)
    records.sort(key=lambda row: (ordering.get(row.get("role", ""), 99), row.get("email", "")))

    if safe_role:
        return records[:1] if unique_per_role else records

    if not unique_per_role:
        return records

    first_by_role = {}
    for row in records:
        role = row.get("role", "")
        if role and role not in first_by_role:
            first_by_role[role] = row

    return [first_by_role[role] for role in ACCOUNT_ROLES if role in first_by_role]


def is_mock_demo_account_email(email, role=""):
    key = str(email or "").strip().lower()
    safe_role = normalize_account_role(role)
    if not key:
        return False

    for item in get_mock_showcase_accounts():
        if item.get("email") != key:
            continue
        if safe_role and item.get("role") != safe_role:
            continue
        return True
    return False


def pick_quiz_option_for_target(options, target_stress):
    candidates = [item for item in (options or []) if str(item.get("id", "")).strip()]
    if not candidates:
        return ""

    try:
        target_value = float(target_stress)
    except (TypeError, ValueError):
        target_value = 3.0

    selected = min(
        candidates,
        key=lambda item: abs(float(item.get("stress", 3.0)) - target_value),
    )
    return str(selected.get("id", "")).strip()


def seed_mock_quiz_attempts_for_student(email, target_stress):
    key = str(email or "").strip().lower()
    if not key:
        return

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM student_quiz_attempts WHERE email = ?",
                (key,),
            ).fetchone()
            existing_attempts = int(row[0]) if row else 0
    except (sqlite3.Error, TypeError, ValueError):
        existing_attempts = 0

    if existing_attempts > 0:
        return

    quiz_keys = list(get_active_quiz_library().keys())[:2]
    for quiz_key in quiz_keys:
        quiz_payload = get_student_quiz_payload(quiz_key)
        if not quiz_payload:
            continue

        answers = {}
        for question in quiz_payload.get("questions", []):
            question_id = str(question.get("id", "")).strip()
            selected_id = pick_quiz_option_for_target(question.get("options", []), target_stress)
            if question_id and selected_id:
                answers[question_id] = selected_id

        if not answers:
            continue

        quiz_result, error = evaluate_student_quiz_answers(quiz_key, answers)
        if error or not quiz_result:
            continue

        created_at = utc_now().isoformat(timespec="seconds")
        answers_json = json.dumps(quiz_result.get("answers", {}), separators=(",", ":"))[:2000]
        try:
            with sqlite3.connect(SCORE_DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT INTO student_quiz_attempts (
                        email, quiz_key, quiz_title, focus, difficulty,
                        total_questions, average_stress, score_percent,
                        risk_band, answers_json, result_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        str(quiz_key or "")[:64],
                        str(quiz_payload.get("title", "Mind Check"))[:120],
                        str(quiz_payload.get("focus", "Balance"))[:48],
                        str(quiz_payload.get("difficulty", "Easy"))[:32],
                        int(quiz_result.get("total_questions", 0) or 0),
                        float(quiz_result.get("average_stress", 3.0) or 3.0),
                        int(quiz_result.get("score_percent", 0) or 0),
                        str(quiz_result.get("risk_band", "MODERATE"))[:16],
                        answers_json,
                        str(quiz_result.get("summary", ""))[:320],
                        created_at,
                    ),
                )
                conn.commit()
        except (sqlite3.Error, TypeError, ValueError):
            continue


def ensure_mock_demo_data_seeded():
    if not EQWELL_ENABLE_MOCK_LOGINS or not EQWELL_SEED_MOCK_DATA:
        return

    showcase_accounts = get_mock_showcase_accounts()
    if not showcase_accounts:
        return

    for account in showcase_accounts:
        upsert_user_account(
            name=account.get("name", account.get("role", "user").title()),
            email=account.get("email", ""),
            password=account.get("password", ""),
            role=account.get("role", "student"),
            status="approved",
            requested_note="Seeded mock demo account",
            approved_by="mock-seeder",
        )

    students = [row for row in showcase_accounts if row.get("role") == "student"]
    parents = [row for row in showcase_accounts if row.get("role") == "parent"]
    proctors = [row for row in showcase_accounts if row.get("role") == "proctor"]
    counsellors = [row for row in showcase_accounts if row.get("role") == "counsellor"]

    if not students:
        return

    stress_cycle = [2.1, 3.2, 4.7, 2.8, 1.9, 3.9]
    face_cycle = ["joy", "neutral", "sadness", "surprise", "anger", "neutral"]
    student_stress = {}

    now_dt = utc_now()
    for idx, student in enumerate(students):
        email = str(student.get("email", "")).strip().lower()
        if not email:
            continue

        stress_score = float(stress_cycle[idx % len(stress_cycle)])
        category = classify_live_stress(stress_score)
        student_stress[email] = stress_score

        save_student_score_state(
            email,
            stress_score,
            category,
            source="mock-seed",
            last_checked_url="https://eqwell.app/mock-dashboard",
        )

        save_student_face_check_state(
            email,
            next_due_at=(now_dt + timedelta(days=max(1, FACE_CHECK_GRACE_DAYS - 1))).isoformat(timespec="seconds"),
            last_face_check_at=(now_dt - timedelta(hours=8 + idx)).isoformat(timespec="seconds"),
            last_face_emotion=face_cycle[idx % len(face_cycle)],
            last_face_score=stress_score,
        )

        seed_mock_quiz_attempts_for_student(email, stress_score)

    now_iso = now_dt.isoformat(timespec="seconds")
    install_at = (now_dt - timedelta(hours=5)).isoformat(timespec="seconds")
    consent_at = (now_dt - timedelta(hours=4, minutes=30)).isoformat(timespec="seconds")
    counsellor = counsellors[0] if counsellors else CREDENTIALS.get("counsellor", {})
    counsellor_email = str(counsellor.get("email", "counsellor@eqwell.app")).strip().lower()
    counsellor_name = str(counsellor.get("name", "Counsellor Team")).strip() or "Counsellor Team"

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            for idx, parent in enumerate(parents):
                parent_email = str(parent.get("email", "")).strip().lower()
                if not parent_email:
                    continue
                student_email = str(students[idx % len(students)].get("email", "")).strip().lower()
                conn.execute(
                    """
                    INSERT INTO parent_student_links (parent_email, student_email, assigned_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(parent_email) DO UPDATE SET
                        student_email = excluded.student_email,
                        assigned_by = excluded.assigned_by,
                        updated_at = excluded.updated_at
                    """,
                    (parent_email, student_email, "mock-seeder", now_iso, now_iso),
                )

            for idx, proctor in enumerate(proctors):
                proctor_email = str(proctor.get("email", "")).strip().lower()
                if not proctor_email:
                    continue
                for student in students[idx:: max(1, len(proctors))] or students:
                    student_email = str(student.get("email", "")).strip().lower()
                    conn.execute(
                        """
                        INSERT INTO proctor_student_links (proctor_email, student_email, assigned_by, created_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(proctor_email, student_email) DO UPDATE SET
                            assigned_by = excluded.assigned_by,
                            created_at = excluded.created_at
                        """,
                        (proctor_email, student_email, "mock-seeder", now_iso),
                    )

            contact_count = min(len(students), max(1, len(parents)))
            for idx in range(contact_count):
                student_email = str(students[idx].get("email", "")).strip().lower()
                parent_row = parents[idx % len(parents)] if parents else CREDENTIALS.get("parent", {})
                parent_name = str(parent_row.get("name", "Parent Contact")).strip() or "Parent Contact"
                parent_phone = f"+1555{1000000 + idx:07d}"
                battery = calculate_mental_battery(student_stress.get(student_email, 3.0))

                conn.execute(
                    """
                    INSERT INTO student_parent_alert_contacts (
                        student_email, parent_name, parent_phone, verified, verified_at,
                        consent_enabled, alerts_enabled, otp_code, otp_sent_at, otp_expires_at,
                        otp_attempts, admin_edit_count, created_at, updated_at,
                        last_alert_type, last_alert_trigger, last_alert_sent_at, last_known_battery
                    ) VALUES (?, ?, ?, 1, ?, 1, 1, '', '', '', 0, 0, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_email) DO UPDATE SET
                        parent_name = excluded.parent_name,
                        parent_phone = excluded.parent_phone,
                        verified = excluded.verified,
                        verified_at = excluded.verified_at,
                        consent_enabled = excluded.consent_enabled,
                        alerts_enabled = excluded.alerts_enabled,
                        otp_code = excluded.otp_code,
                        otp_sent_at = excluded.otp_sent_at,
                        otp_expires_at = excluded.otp_expires_at,
                        otp_attempts = excluded.otp_attempts,
                        admin_edit_count = excluded.admin_edit_count,
                        updated_at = excluded.updated_at,
                        last_alert_type = excluded.last_alert_type,
                        last_alert_trigger = excluded.last_alert_trigger,
                        last_alert_sent_at = excluded.last_alert_sent_at,
                        last_known_battery = excluded.last_known_battery
                    """,
                    (
                        student_email,
                        parent_name,
                        parent_phone,
                        now_iso,
                        now_iso,
                        now_iso,
                        "CRITICAL" if idx % 3 == 2 else "HIGH",
                        "mock-seed",
                        now_iso,
                        battery,
                    ),
                )

                existing_events = conn.execute(
                    "SELECT COUNT(1) FROM parent_alert_events WHERE student_email = ?",
                    (student_email,),
                ).fetchone()
                event_count = int(existing_events[0]) if existing_events else 0
                if event_count == 0:
                    conn.execute(
                        """
                        INSERT INTO parent_alert_events (
                            student_email, parent_phone, alert_priority, trigger_type,
                            battery, previous_battery, signal_count, channel, send_status,
                            provider_response, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            student_email,
                            parent_phone,
                            "CRITICAL" if idx % 3 == 2 else "HIGH",
                            "mock-seed",
                            battery,
                            min(100, battery + 12),
                            3,
                            "dashboard",
                            "mock-sent",
                            "seeded",
                            now_iso,
                        ),
                    )

            for idx, student in enumerate(students):
                student_email = str(student.get("email", "")).strip().lower()
                stress_score = float(student_stress.get(student_email, 3.0))
                risk_category = classify_live_stress(stress_score)
                battery = calculate_mental_battery(stress_score)

                total_events = 70 + (idx * 9)
                risky_events = 4 + (idx % 4)
                positive_events = 18 + (idx * 2)
                safe_events = max(0, total_events - risky_events)

                urls_payload = [
                    {
                        "url": "https://campus.eqwell.app/dashboard",
                        "query": "",
                        "observed_at": (now_dt - timedelta(minutes=20 + idx)).isoformat(timespec="seconds"),
                        "risk": "safe",
                    },
                    {
                        "url": "https://study.example.com/focus-timer",
                        "query": "deep work timer",
                        "observed_at": (now_dt - timedelta(minutes=12 + idx)).isoformat(timespec="seconds"),
                        "risk": "safe",
                    },
                    {
                        "url": "https://community.example.com/wellbeing",
                        "query": "stress support",
                        "observed_at": (now_dt - timedelta(minutes=6 + idx)).isoformat(timespec="seconds"),
                        "risk": "positive",
                    },
                ]

                conn.execute(
                    """
                    INSERT INTO student_url_history (
                        email, urls_json, total_events, risky_events, safe_events, positive_events,
                        last_risky_at, last_safe_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        urls_json = excluded.urls_json,
                        total_events = excluded.total_events,
                        risky_events = excluded.risky_events,
                        safe_events = excluded.safe_events,
                        positive_events = excluded.positive_events,
                        last_risky_at = excluded.last_risky_at,
                        last_safe_at = excluded.last_safe_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        student_email,
                        json.dumps(urls_payload, separators=(",", ":")),
                        total_events,
                        risky_events,
                        safe_events,
                        positive_events,
                        (now_dt - timedelta(hours=2 + idx)).isoformat(timespec="seconds"),
                        (now_dt - timedelta(minutes=25 + idx)).isoformat(timespec="seconds"),
                        now_iso,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO student_extension_security_state (
                        email, extension_email, installed_at, consent_granted_at, last_seen_at,
                        source, last_user_agent, last_ip, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        extension_email = excluded.extension_email,
                        installed_at = excluded.installed_at,
                        consent_granted_at = excluded.consent_granted_at,
                        last_seen_at = excluded.last_seen_at,
                        source = excluded.source,
                        last_user_agent = excluded.last_user_agent,
                        last_ip = excluded.last_ip,
                        updated_at = excluded.updated_at
                    """,
                    (
                        student_email,
                        student_email,
                        install_at,
                        consent_at,
                        now_iso,
                        "mock-seed",
                        "eqwell-mock-client",
                        "127.0.0.1",
                        now_iso,
                    ),
                )

                if risk_category == "HIGH":
                    session_dt = (now_dt + timedelta(hours=6 + idx)).replace(minute=0, second=0, microsecond=0)
                    session_label = session_dt.strftime("%d %b %H:%M UTC")
                    conn.execute(
                        """
                        INSERT INTO student_auto_counselling_sessions (
                            email, counsellor_email, counsellor_name, session_at, session_label,
                            reason, trigger_battery, stress_category, status, assigned_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(email) DO UPDATE SET
                            counsellor_email = excluded.counsellor_email,
                            counsellor_name = excluded.counsellor_name,
                            session_at = excluded.session_at,
                            session_label = excluded.session_label,
                            reason = excluded.reason,
                            trigger_battery = excluded.trigger_battery,
                            stress_category = excluded.stress_category,
                            status = excluded.status,
                            assigned_at = excluded.assigned_at,
                            updated_at = excluded.updated_at
                        """,
                        (
                            student_email,
                            counsellor_email,
                            counsellor_name,
                            session_dt.isoformat(timespec="seconds"),
                            session_label,
                            "mock-high-risk-demo",
                            battery,
                            risk_category,
                            "scheduled",
                            now_iso,
                            now_iso,
                        ),
                    )

            conn.commit()
    except sqlite3.Error:
        return


def authenticate_portal_user(role, email, password):
    safe_role = normalize_account_role(role)
    safe_email = str(email or "").strip().lower()
    raw_password = str(password or "")
    if not safe_role or not safe_email or not raw_password:
        return None, "Email and password are required."

    account = get_user_account_by_email(safe_email)
    if account:
        if account.get("role") != safe_role:
            return None, "Account role mismatch. Select the correct login portal."
        if account.get("status") != "approved":
            return None, "Signup is pending developer approval."
        if str(account.get("password", "")) != raw_password:
            return None, "Invalid credentials for selected role."
        return account, ""

    # Backward-compatible fallback to in-memory demo credentials.
    role_data = CREDENTIALS.get(safe_role)
    if role_data and safe_email == role_data.get("email") and raw_password == role_data.get("password"):
        return {
            "id": 0,
            "name": str(role_data.get("name", safe_role.title())),
            "email": safe_email,
            "role": safe_role,
            "status": "approved",
        }, ""
    return None, "Invalid credentials for selected role."


def is_approved_role_account(email, role):
    account = get_user_account_by_email(email)
    safe_role = normalize_account_role(role)
    return bool(account and account.get("role") == safe_role and account.get("status") == "approved")


def extension_repeat_penalty_points(repeat_count):
    try:
        count_value = int(repeat_count)
    except (TypeError, ValueError):
        count_value = 0

    if count_value <= 0:
        return 0
    if count_value == 1:
        return EXTENSION_REPEAT_PENALTY_STEP_1
    if count_value == 2:
        return EXTENSION_REPEAT_PENALTY_STEP_2
    if count_value == 3:
        return EXTENSION_REPEAT_PENALTY_STEP_3
    return EXTENSION_REPEAT_PENALTY_STEP_4


def normalize_extension_risk_signature(current_url, extracted_query=""):
    query_value = re.sub(r"\s+", " ", str(extracted_query or "").strip().lower())
    query_value = re.sub(r"[^a-z0-9\s]", " ", query_value)
    query_value = re.sub(r"\s+", " ", query_value).strip()
    if query_value:
        return f"q:{query_value[:180]}"

    try:
        parsed = urlparse(str(current_url or ""))
    except ValueError:
        parsed = None

    host = str((parsed.hostname if parsed else "") or "").strip().lower()
    path = str((parsed.path if parsed else "") or "").strip().lower()
    path = re.sub(r"[^a-z0-9/\-_]", "", path)[:180]
    if host:
        return f"u:{host}{path}"

    fallback = re.sub(r"\s+", " ", str(current_url or "").strip().lower())
    fallback = re.sub(r"[^a-z0-9\s]", " ", fallback)
    fallback = re.sub(r"\s+", " ", fallback).strip()
    return f"u:{fallback[:180]}" if fallback else ""


def compute_extension_repeat_penalty(email, events):
    key = str(email or "").strip().lower()
    if not key:
        return {"max_repeat_count": 0, "max_penalty_points": 0, "risk_signature": ""}

    risky_events = []
    for event in events or []:
        current_url = str(event.get("current_url", "")).strip()
        extracted_query = str(event.get("extracted_query", "")).strip()
        if not extension_url_context_risk(current_url, extracted_query):
            continue

        observed_value = parse_iso_datetime(event.get("observed_at")) or utc_now()
        signature = normalize_extension_risk_signature(current_url, extracted_query)
        if not signature:
            continue
        risky_events.append(
            {
                "signature": signature,
                "observed": observed_value,
            }
        )

    if not risky_events:
        return {"max_repeat_count": 0, "max_penalty_points": 0, "risk_signature": ""}

    risky_events.sort(key=lambda item: item["observed"])
    latest_observed = risky_events[-1]["observed"]
    since_iso = (latest_observed - timedelta(seconds=max(60, EXTENSION_REPEAT_WINDOW_SECONDS * 2))).isoformat(timespec="seconds")
    signatures = sorted({item["signature"] for item in risky_events})

    history_by_signature = {signature: [] for signature in signatures}

    placeholders = ",".join(["?"] * len(signatures))
    params = [key, since_iso, *signatures]
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT risk_signature, observed_at
                FROM extension_risk_events
                WHERE email = ?
                  AND observed_at >= ?
                  AND risk_signature IN ({placeholders})
                ORDER BY observed_at ASC
                """,
                tuple(params),
            ).fetchall()

            for row in rows:
                signature = str(row["risk_signature"] or "").strip()
                observed_value = parse_iso_datetime(row["observed_at"])
                if signature in history_by_signature and observed_value:
                    history_by_signature[signature].append(observed_value)

            prune_before = (utc_now() - timedelta(days=5)).isoformat(timespec="seconds")
            conn.execute(
                "DELETE FROM extension_risk_events WHERE email = ? AND observed_at < ?",
                (key, prune_before),
            )

            max_repeat_count = 0
            max_penalty_points = 0
            max_signature = ""
            inserts = []
            created_at = utc_now().isoformat(timespec="seconds")

            for item in risky_events:
                signature = item["signature"]
                observed_value = item["observed"]
                window_start = observed_value - timedelta(seconds=EXTENSION_REPEAT_WINDOW_SECONDS)
                retained = [entry for entry in history_by_signature.get(signature, []) if entry >= window_start]
                repeat_count = len(retained) + 1
                penalty_points = extension_repeat_penalty_points(repeat_count)

                if repeat_count > max_repeat_count:
                    max_repeat_count = repeat_count
                if penalty_points > max_penalty_points:
                    max_penalty_points = penalty_points
                    max_signature = signature

                retained.append(observed_value)
                history_by_signature[signature] = retained
                inserts.append(
                    (
                        key,
                        signature[:200],
                        observed_value.isoformat(timespec="seconds"),
                        created_at,
                    )
                )

            if inserts:
                conn.executemany(
                    """
                    INSERT INTO extension_risk_events (email, risk_signature, observed_at, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    inserts,
                )

            conn.commit()

        return {
            "max_repeat_count": max_repeat_count,
            "max_penalty_points": max_penalty_points,
            "risk_signature": max_signature,
        }
    except sqlite3.Error:
        return {"max_repeat_count": 0, "max_penalty_points": 0, "risk_signature": ""}


def calculate_reentry_score_from_previous_and_mood(previous_stress_score, mood_score):
    previous_value = max(1.0, min(float(previous_stress_score), 5.0))
    mood_target_score = mood_to_stress_score(mood_score)
    blended = (0.65 * previous_value) + (0.35 * mood_target_score)
    return round(max(1.0, min(blended, 5.0)), 2)


def extension_url_context_risk(current_url, extracted_query=""):
    url_text = str(current_url or "").strip()
    query_text = str(extracted_query or "").strip()
    if not url_text and not query_text:
        return False

    parts = []
    if query_text:
        parts.append(query_text)

    if url_text:
        parts.append(unquote_plus(url_text))
        parsed = urlparse(url_text)
        query_map = parse_qs(parsed.query)
        for key in ("q", "query", "search", "p", "oq", "text", "wd", "k", "keyword"):
            for item in query_map.get(key, []):
                cleaned = unquote_plus(str(item)).strip()
                if cleaned:
                    parts.append(cleaned)

        path_text = unquote_plus(parsed.path or "").replace("/", " ").strip()
        if path_text:
            parts.append(path_text)

    merged = " ".join(parts).strip()
    if not merged:
        return False

    return any(pattern.search(merged) for pattern in EXTENSION_URL_RISK_PATTERNS)


def extension_event_context_text(current_url, extracted_query="", page_context=""):
    url_text = str(current_url or "").strip()
    query_text = str(extracted_query or "").strip()
    context_text = str(page_context or "").strip()
    parts = []

    if query_text:
        parts.append(query_text)

    if context_text:
        parts.append(context_text)

    if url_text:
        parts.append(unquote_plus(url_text))
        parsed = urlparse(url_text)
        query_map = parse_qs(parsed.query)
        for key in ("q", "query", "search", "p", "oq", "text", "wd", "k", "keyword"):
            for item in query_map.get(key, []):
                cleaned = unquote_plus(str(item)).strip()
                if cleaned:
                    parts.append(cleaned)

        path_text = unquote_plus(parsed.path or "").replace("/", " ").strip()
        if path_text:
            parts.append(path_text)

    merged = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return merged[:1200]


def extension_url_context_positive_or_neutral(current_url, extracted_query="", page_context=""):
    merged = extension_event_context_text(current_url, extracted_query, page_context)
    if not merged:
        return False

    if extension_url_context_risk(current_url, extracted_query):
        return False

    return any(pattern.search(merged) for pattern in EXTENSION_URL_POSITIVE_PATTERNS)


def load_student_url_history_state(email):
    key = str(email or "").strip().lower()
    if not key:
        return {
            "email": "",
            "urls": [],
            "total_events": 0,
            "risky_events": 0,
            "safe_events": 0,
            "positive_events": 0,
            "last_risky_at": "",
            "last_safe_at": "",
            "updated_at": "",
        }

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, urls_json, total_events, risky_events, safe_events,
                       positive_events, last_risky_at, last_safe_at, updated_at
                FROM student_url_history
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        row = None

    if not row:
        return {
            "email": key,
            "urls": [],
            "total_events": 0,
            "risky_events": 0,
            "safe_events": 0,
            "positive_events": 0,
            "last_risky_at": "",
            "last_safe_at": "",
            "updated_at": "",
        }

    try:
        parsed_urls = json.loads(str(row["urls_json"] or "[]"))
        if not isinstance(parsed_urls, list):
            parsed_urls = []
    except json.JSONDecodeError:
        parsed_urls = []

    return {
        "email": str(row["email"] or key),
        "urls": parsed_urls[-EXTENSION_URL_HISTORY_MAX_ITEMS:],
        "total_events": max(0, int(row["total_events"] or 0)),
        "risky_events": max(0, int(row["risky_events"] or 0)),
        "safe_events": max(0, int(row["safe_events"] or 0)),
        "positive_events": max(0, int(row["positive_events"] or 0)),
        "last_risky_at": str(row["last_risky_at"] or ""),
        "last_safe_at": str(row["last_safe_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def append_student_url_history_events(email, events):
    key = str(email or "").strip().lower()
    if not key:
        return {
            "batch_total": 0,
            "risky_event_count": 0,
            "safe_event_count": 0,
            "positive_event_count": 0,
            "safe_action_points": 0,
            "risky_action_points": 0,
            "no_risk_hours": 0.0,
        }

    history = load_student_url_history_state(key)
    urls = list(history.get("urls", []))
    total_events = int(history.get("total_events", 0) or 0)
    risky_events = int(history.get("risky_events", 0) or 0)
    safe_events = int(history.get("safe_events", 0) or 0)
    positive_events = int(history.get("positive_events", 0) or 0)

    last_risky_dt = parse_iso_datetime(history.get("last_risky_at", ""))
    last_safe_dt = parse_iso_datetime(history.get("last_safe_at", ""))

    batch_total = 0
    batch_risky = 0
    batch_safe = 0
    batch_positive = 0
    safe_action_points = 0
    risky_action_points = 0

    for item in events or []:
        current_url = str((item or {}).get("current_url", "")).strip()[:500]
        extracted_query = str((item or {}).get("extracted_query", "")).strip()[:300]
        page_context = str((item or {}).get("page_context", "")).strip()[:300]

        if not current_url and not extracted_query and not page_context:
            continue

        observed_dt = parse_iso_datetime((item or {}).get("observed_at")) or utc_now()
        observed_iso = observed_dt.isoformat(timespec="seconds")

        try:
            session_duration = int((item or {}).get("session_duration", 0) or 0)
        except (TypeError, ValueError):
            session_duration = 0
        session_duration = max(0, min(session_duration, 1440))

        risky = extension_url_context_risk(current_url, extracted_query)
        positive = extension_url_context_positive_or_neutral(current_url, extracted_query, page_context)
        safe = not risky

        if safe:
            action_points = min(5, 1 + min(2, session_duration // 180) + (1 if positive else 0))
            safe_action_points += action_points
            safe_events += 1
            batch_safe += 1
            if positive:
                positive_events += 1
                batch_positive += 1
            if (not last_safe_dt) or observed_dt > last_safe_dt:
                last_safe_dt = observed_dt
        else:
            action_points = min(5, 2 + min(3, session_duration // 120))
            risky_action_points += action_points
            risky_events += 1
            batch_risky += 1
            if (not last_risky_dt) or observed_dt > last_risky_dt:
                last_risky_dt = observed_dt

        urls.append(
            {
                "url": current_url,
                "query": extracted_query,
                "context": page_context,
                "label": "risky" if risky else ("positive" if positive else "safe"),
                "action_points": action_points,
                "session_duration": session_duration,
                "observed_at": observed_iso,
            }
        )
        batch_total += 1
        total_events += 1

    if batch_total <= 0:
        now_dt = utc_now()
        no_risk_hours = 999.0
        if last_risky_dt:
            no_risk_hours = max(0.0, (now_dt - last_risky_dt).total_seconds() / 3600.0)
        return {
            "batch_total": 0,
            "risky_event_count": 0,
            "safe_event_count": 0,
            "positive_event_count": 0,
            "safe_action_points": 0,
            "risky_action_points": 0,
            "no_risk_hours": round(no_risk_hours, 2),
        }

    urls = urls[-EXTENSION_URL_HISTORY_MAX_ITEMS:]
    updated_at = utc_now().isoformat(timespec="seconds")
    last_risky_iso = last_risky_dt.isoformat(timespec="seconds") if last_risky_dt else ""
    last_safe_iso = last_safe_dt.isoformat(timespec="seconds") if last_safe_dt else ""

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_url_history (
                    email, urls_json, total_events, risky_events, safe_events,
                    positive_events, last_risky_at, last_safe_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    urls_json = excluded.urls_json,
                    total_events = excluded.total_events,
                    risky_events = excluded.risky_events,
                    safe_events = excluded.safe_events,
                    positive_events = excluded.positive_events,
                    last_risky_at = excluded.last_risky_at,
                    last_safe_at = excluded.last_safe_at,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    json.dumps(urls),
                    int(total_events),
                    int(risky_events),
                    int(safe_events),
                    int(positive_events),
                    last_risky_iso,
                    last_safe_iso,
                    updated_at,
                ),
            )
            conn.commit()
    except sqlite3.Error:
        pass

    no_risk_hours = 999.0
    if last_risky_dt:
        no_risk_hours = max(0.0, (utc_now() - last_risky_dt).total_seconds() / 3600.0)

    return {
        "batch_total": batch_total,
        "risky_event_count": batch_risky,
        "safe_event_count": batch_safe,
        "positive_event_count": batch_positive,
        "safe_action_points": safe_action_points,
        "risky_action_points": risky_action_points,
        "no_risk_hours": round(no_risk_hours, 2),
    }


def should_collect_extension_event_url(current_url):
    raw_url = str(current_url or "").strip()
    if not raw_url:
        return False

    parsed = urlparse(raw_url)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        return False

    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return False

    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80

    # Do not store local EqWell app routes as browsing events.
    if host in {"127.0.0.1", "localhost"} and port == 5000:
        return False

    return True


def parse_json_object(raw_text):
    raw = str(raw_text or "").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def queue_extension_collected_event(email, current_url, extracted_query, page_context, session_duration, observed_at):
    key = str(email or "").strip().lower()
    if not key:
        return False

    safe_session_duration = 0
    try:
        safe_session_duration = max(0, min(int(session_duration), 1440))
    except (TypeError, ValueError):
        safe_session_duration = 0

    observed_value = parse_iso_datetime(observed_at) or utc_now()
    observed_iso = observed_value.isoformat(timespec="seconds")
    created_iso = utc_now().isoformat(timespec="seconds")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO extension_collected_events (
                    email, current_url, extracted_query, page_context, session_duration, observed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    str(current_url or "")[:500],
                    str(extracted_query or "")[:300],
                    str(page_context or "")[:300],
                    safe_session_duration,
                    observed_iso,
                    created_iso,
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def load_extension_collected_events(email, max_events):
    key = str(email or "").strip().lower()
    if not key:
        return []

    safe_limit = max(1, min(int(max_events or 1), 2000))
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, email, current_url, extracted_query, page_context, session_duration, observed_at, created_at
                FROM extension_collected_events
                WHERE email = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (key, safe_limit),
            ).fetchall()
    except sqlite3.Error:
        return []

    events = []
    for row in rows:
        events.append(
            {
                "id": int(row["id"]),
                "email": key,
                "current_url": str(row["current_url"] or ""),
                "extracted_query": str(row["extracted_query"] or ""),
                "page_context": str(row["page_context"] or ""),
                "session_duration": int(row["session_duration"] or 0),
                "observed_at": str(row["observed_at"] or ""),
                "created_at": str(row["created_at"] or ""),
            }
        )
    return events


def clear_extension_collected_events(event_ids):
    cleaned_ids = []
    for raw_id in event_ids or []:
        try:
            cleaned_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not cleaned_ids:
        return 0

    placeholders = ",".join(["?"] * len(cleaned_ids))
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            cursor = conn.execute(
                f"DELETE FROM extension_collected_events WHERE id IN ({placeholders})",
                tuple(cleaned_ids),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
    except sqlite3.Error:
        return 0


def groq_extract_relevant_event_text(events):
    if not events:
        return "", "MEDIUM", 0.0, ""

    fallback_items = []
    any_risky = False
    top_url = ""
    for event in events:
        current_url = str(event.get("current_url", ""))
        extracted_query = str(event.get("extracted_query", ""))
        page_context = str(event.get("page_context", ""))
        if extracted_query:
            fallback_items.append(extracted_query)
        elif page_context:
            fallback_items.append(page_context)
        elif current_url:
            fallback_items.append(current_url)

        if extension_url_context_risk(current_url, extracted_query):
            any_risky = True
            if not top_url:
                top_url = current_url

    fallback_text = " | ".join(fallback_items).strip()[:1200]
    fallback_signal = "HIGH" if any_risky else "MEDIUM"

    if not GROQ_API_KEY:
        return fallback_text, fallback_signal, (0.7 if any_risky else 0.45), top_url

    reduced_events = []
    for event in events[:80]:
        reduced_events.append(
            {
                "url": str(event.get("current_url", ""))[:500],
                "query": str(event.get("extracted_query", ""))[:300],
                "context": str(event.get("page_context", ""))[:220],
            }
        )

    payload = {
        "model": GROQ_DEFAULT_MODEL,
        "temperature": 0.0,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a wellbeing risk preprocessor for browsing events. "
                    "Return JSON only with fields relevant_text, risk_signal (LOW|MEDIUM|HIGH), confidence (0..1), top_url."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "events": reduced_events,
                        "task": (
                            "Extract the most relevant distress-related text from queries/URLs. "
                            "If no distress indicators, keep relevant_text neutral."
                        ),
                    }
                ),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=(5, 22))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return fallback_text, fallback_signal, (0.7 if any_risky else 0.45), top_url

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    parsed = parse_json_object(content)
    if not isinstance(parsed, dict):
        return fallback_text, fallback_signal, (0.7 if any_risky else 0.45), top_url

    relevant_text = str(parsed.get("relevant_text", "")).strip()[:1200]
    risk_signal = str(parsed.get("risk_signal", fallback_signal)).strip().upper()
    if risk_signal not in {"LOW", "MEDIUM", "HIGH"}:
        risk_signal = fallback_signal

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))

    top_url_value = str(parsed.get("top_url", top_url)).strip()[:500]
    if not relevant_text:
        relevant_text = fallback_text

    if any_risky and risk_signal != "HIGH":
        risk_signal = "HIGH"
        confidence = max(confidence, 0.72)

    return relevant_text, risk_signal, confidence, top_url_value


def merge_batch_stress_signals(groq_signal, groq_confidence, hf_signal, hf_confidence, risky_url_context=False):
    groq_value = str(groq_signal or "MEDIUM").strip().upper()
    hf_value = str(hf_signal or "MEDIUM").strip().upper()
    if groq_value not in {"LOW", "MEDIUM", "HIGH"}:
        groq_value = "MEDIUM"
    if hf_value not in {"LOW", "MEDIUM", "HIGH"}:
        hf_value = "MEDIUM"

    try:
        groq_conf = max(0.0, min(float(groq_confidence), 1.0))
    except (TypeError, ValueError):
        groq_conf = 0.0

    try:
        hf_conf = max(0.0, min(float(hf_confidence), 1.0))
    except (TypeError, ValueError):
        hf_conf = 0.0

    if risky_url_context or groq_value == "HIGH" or hf_value == "HIGH":
        final_signal = "HIGH"
    elif groq_value == "LOW" and hf_value == "LOW":
        final_signal = "LOW"
    else:
        final_signal = "MEDIUM"

    confidence = max(groq_conf, hf_conf)
    if final_signal == "HIGH":
        confidence = max(confidence, 0.68)
    if risky_url_context:
        confidence = max(confidence, 0.72)

    return final_signal, round(max(0.0, min(confidence, 1.0)), 4)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "role" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                return redirect(url_for("dashboard", role=session.get("role", "student")))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def role_in_required(*roles):
    allowed_roles = {str(role).strip().lower() for role in roles if str(role).strip()}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            current_role = str(session.get("role", "")).strip().lower()
            if current_role not in allowed_roles:
                return redirect(url_for("dashboard", role=session.get("role", "student")))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def student_mood_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("role") == "student" and not session.get("student_mood"):
            pending_mood = str(session.get("student_mood_pending", "")).strip()
            if pending_mood in STUDENT_MOODS:
                return redirect(url_for("student_face_check"))
            return redirect(url_for("student_mood"))
        return view_func(*args, **kwargs)

    return wrapper


def extension_required_for_student(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "student":
            return view_func(*args, **kwargs)

        email = str(session.get("email", "")).strip().lower()
        required_since = parse_iso_datetime(session.get("student_extension_verified_at"))
        valid, message, show_popup = evaluate_student_extension_access(
            email,
            request_obj=request,
            required_since=required_since,
        )
        if valid:
            return view_func(*args, **kwargs)

        flash(message, "security_popup" if show_popup else "error")
        return redirect(url_for("install_extension"))

    return wrapper


def is_student_protected_path(path_value):
    path = str(path_value or "").strip().lower()
    return (
        path.startswith("/student")
        or path.startswith("/api/student")
        or path.startswith("/dashboard/student")
    )


def is_student_profile_setup_exempt_path(path_value):
    path = str(path_value or "").strip().lower()
    return (
        path.startswith("/student/profile")
        or path.startswith("/student/parent-contact/")
        or path.startswith("/api/student/google-fit/")
    )


@app.before_request
def enforce_student_extension_gate_global():
    path = request.path or ""
    if not is_student_protected_path(path):
        return None

    if session.get("role") != "student":
        return None

    email = str(session.get("email", "")).strip().lower()
    if not email or not is_approved_role_account(email, "student"):
        session.clear()
        if path.startswith("/api/student"):
            return jsonify({"error": "Student session mismatch. Please sign in again."}), 401
        return redirect(url_for("login"))

    required_since = parse_iso_datetime(session.get("student_extension_verified_at"))
    valid, message, show_popup = evaluate_student_extension_access(
        email,
        request_obj=request,
        required_since=required_since,
    )
    if valid:
        if is_student_profile_setup_exempt_path(path):
            return None

        setup_ready, setup_details, pending_requirements = evaluate_student_profile_setup_access(email)
        if setup_ready:
            return None

        setup_message = build_student_profile_setup_message(pending_requirements)
        if path.startswith("/api/student"):
            return jsonify(
                {
                    "error": setup_message,
                    "redirect": url_for("student_profile"),
                    "requirements": setup_details,
                }
            ), 403

        flash(setup_message, "error")
        return redirect(url_for("student_profile"))

    if path.startswith("/api/student"):
        return jsonify(
            {
                "error": message,
                "redirect": url_for("install_extension"),
                "show_popup": bool(show_popup),
            }
        ), 403

    flash(message, "security_popup" if show_popup else "error")
    return redirect(url_for("install_extension"))


def build_sidebar(role):
    sidebar = ROLE_SIDEBARS.get(role, ROLE_SIDEBARS["student"])
    items = []

    if role == "student":
        href_map = {
            "dashboard": url_for("student_dashboard"),
            "mood": url_for("student_mood"),
            "counselling": f"{url_for('student_dashboard')}#support-access",
            "profile": url_for("student_profile"),
            "resources": f"{url_for('student_dashboard')}#ai-vent",
        }
        action_href = url_for("student_mood")
    elif role == "developer":
        href_map = {
            "overview": url_for("developer_overview_page"),
            "accounts": url_for("developer_accounts_page"),
            "users": url_for("developer_accounts_page"),
            "quizzes": f"{url_for('developer_accounts_page')}#quiz-manager",
            "pipeline": url_for("developer_pipeline_page"),
            "analytics": url_for("developer_pipeline_page"),
            "requests": url_for("developer_requests_page"),
        }
        action_href = url_for("developer_overview_page")
    else:
        base_href = url_for("dashboard", role=role)
        href_map = {
            "dashboard": base_href,
            "overview": base_href,
            "accounts": base_href,
            "pipeline": base_href,
            "requests": base_href,
            "users": f"{base_href}#users",
            "quizzes": f"{base_href}#quizzes",
            "analytics": f"{base_href}#analytics",
            "students": f"{base_href}#students",
            "sessions": f"{base_href}#sessions",
            "reports": f"{base_href}#reports",
            "sanctuary": base_href,
            "insights": f"{base_href}#insights",
            "pulse-check": f"{base_href}#pulse-check",
            "community": f"{base_href}#community",
            "resources": f"{base_href}#resources",
            "trend": f"{base_href}#trend",
            "alerts": f"{base_href}#alerts",
            "lifestyle": f"{base_href}#lifestyle",
        }
        action_href = base_href

    for item in sidebar["menu"]:
        items.append({**item, "href": href_map.get(item["key"], "#")})

    return {
        **sidebar,
        "menu": items,
        "action_href": action_href,
    }


def ask_groq_student_bot(message):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, "GROQ_API_KEY is missing. Add it to .env and restart the Flask server."

    payload = {
        "model": GROQ_DEFAULT_MODEL,
        "temperature": 0.65,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are EqWell student support assistant. Respond like a calm, counsellor-style guide"
                    " with empathy, practical steps, and clear next actions for students. Keep replies concise"
                    " and avoid diagnosis. If distress appears high, suggest professional support and include"
                    f" these contacts exactly: {support_contacts_text()}."
                ),
            },
            {"role": "user", "content": message},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=(3, 10))
    except requests.RequestException as exc:
        return None, f"Groq request failed: {exc}"

    if response.status_code >= 400:
        try:
            error_payload = response.json()
            error_text = error_payload.get("error", {}).get("message", response.text)
        except ValueError:
            error_text = response.text
        return None, f"Groq API error: {error_text}"

    try:
        data = response.json()
    except ValueError:
        return None, "Groq API returned a non-JSON response."

    reply = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not reply:
        return None, "No reply received from Groq model."

    return reply, None


def normalize_emotion_predictions(payload):
    if isinstance(payload, list):
        if payload and isinstance(payload[0], list):
            return [row for row in payload[0] if isinstance(row, dict)]
        return [row for row in payload if isinstance(row, dict)]
    return []


def analyze_student_emotion(text):
    if not HF_API_TOKEN:
        return "neutral", 0.0, "Hugging Face token is missing; using neutral fallback."

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": text,
        "options": {"wait_for_model": True},
    }

    try:
        response = requests.post(
            HF_EMOTION_API_URL,
            headers=headers,
            json=payload,
            timeout=(2.5, 7),
        )
    except requests.Timeout:
        return "neutral", 0.0, "Emotion analysis timed out; using neutral fallback."
    except requests.RequestException as exc:
        return "neutral", 0.0, f"Emotion analysis request failed: {exc}"

    try:
        data = response.json()
    except ValueError:
        return "neutral", 0.0, "Emotion analysis returned invalid JSON; using neutral fallback."

    if response.status_code >= 400:
        return "neutral", 0.0, f"Emotion analysis API error: {data}"

    predictions = normalize_emotion_predictions(data)
    if not predictions:
        return "neutral", 0.0, "No emotion predictions returned; using neutral fallback."

    top = max(predictions, key=lambda p: float(p.get("score", 0.0)))
    emotion = str(top.get("label", "neutral")).lower()
    confidence = max(0.0, min(float(top.get("score", 0.0)), 1.0))
    return emotion, round(confidence, 4), None


def emotion_to_stress_level(emotion):
    if emotion in {"sadness", "anger", "fear"}:
        return "HIGH"
    if emotion == "joy":
        return "LOW"
    return "MEDIUM"


def stress_level_to_score(stress_level):
    return {
        "LOW": 2,
        "MEDIUM": 3,
        "HIGH": 5,
    }.get(stress_level, 3)


def calculate_live_stress_score(mood_score, stress_level):
    chatbot_score = stress_level_to_score(stress_level)
    final_score = (0.7 * mood_score) + (0.3 * chatbot_score)
    if stress_level == "HIGH":
        final_score = max(final_score, 4.0)
    return round(max(1.0, min(final_score, 5.0)), 2)


def smooth_stress_score(
    previous_score,
    target_score,
    allow_rapid=False,
    max_step_up=None,
    max_step_down=0.5,
):
    prev = max(1.0, min(float(previous_score), 5.0))
    target = max(1.0, min(float(target_score), 5.0))

    if target >= prev:
        step_up = 0.7 if not allow_rapid else 1.5
        if isinstance(max_step_up, (int, float)):
            step_up = max(0.05, min(float(max_step_up), 2.0))
        return round(min(prev + step_up, target), 2)

    # Recovery should remain gradual to avoid visual jumps.
    step_down = max(0.05, min(float(max_step_down), 1.0))
    return round(max(prev - step_down, target), 2)


def should_slow_drop_for_sad_message(message, emotion):
    if str(emotion).lower() == "sadness":
        return True

    lower_text = message.lower()
    sad_markers = {
        "sad",
        "down",
        "lonely",
        "hopeless",
        "empty",
        "cry",
        "depressed",
        "upset",
        "heartbroken",
    }
    return any(marker in lower_text for marker in sad_markers)


def classify_live_stress(score):
    if score <= 2:
        return "LOW"
    if score <= 3.5:
        return "MODERATE"
    return "HIGH"


def calculate_mental_battery(score):
    stress_percentage = (score / 5.0) * 100.0
    battery = 100.0 - stress_percentage
    return int(round(max(0.0, min(battery, 100.0))))


def battery_to_stress_score(battery):
    battery_value = max(0.0, min(float(battery), 100.0))
    stress_percentage = 100.0 - battery_value
    score = stress_percentage / 20.0
    return round(max(1.0, min(score, 5.0)), 2)


def topic_from_text(text):
    lower_text = text.lower()
    if "exam" in lower_text or "study" in lower_text:
        return "ACADEMICS"
    if "hostel" in lower_text or "roommate" in lower_text:
        return "HOSTEL"
    if "friend" in lower_text or "alone" in lower_text:
        return "SOCIAL"
    return "GENERAL"


def is_short_greeting_message(text):
    cleaned = re.sub(r"[^a-zA-Z\s]", "", str(text or "").lower()).strip()
    return cleaned in {
        "hi",
        "hii",
        "hello",
        "hey",
        "yo",
        "hola",
        "good morning",
        "good afternoon",
        "good evening",
    }


def support_contacts_text():
    parts = []
    for contact in STUDENT_SUPPORT_CONTACTS:
        name = str(contact.get("name", "Support")).strip()
        phone = str(contact.get("phone", "")).strip()
        if name and phone:
            parts.append(f"{name}: {phone}")
    return "; ".join(parts)


def detect_crisis_message(text):
    lower_text = text.lower()
    crisis_phrases = {
        "want to die",
        "kill myself",
        "end my life",
        "suicide",
        "self harm",
        "hurt myself",
        "dont want to live",
        "don't want to live",
        "i want to die",
    }
    return any(phrase in lower_text for phrase in crisis_phrases)


def build_safety_prefix(crisis_streak):
    if crisis_streak <= 1:
        return (
            "I am really glad you shared this. You matter. "
            "I strongly recommend joining a counselling session now."
        )
    return (
        "I am concerned for your immediate safety. "
        "Please contact emergency support right now and reach out to your counsellor or warden immediately."
    )


def battery_to_tone(battery):
    if battery <= 20:
        return "#fc7359"
    if battery <= 40:
        return "#dfa342"
    if battery <= 60:
        return "#c8b35f"
    if battery <= 80:
        return "#9fbe59"
    return "#6ea73f"


def utc_now():
    return datetime.now(timezone.utc)


def parse_iso_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_request_client_fingerprint(request_obj):
    if request_obj is None:
        return {"user_agent": "", "ip": ""}

    user_agent = str(request_obj.headers.get("User-Agent", "")).strip().lower()[:240]
    forwarded_for = str(request_obj.headers.get("X-Forwarded-For", "")).split(",", 1)[0].strip()
    remote_ip = forwarded_for or str(request_obj.remote_addr or "").strip()
    return {"user_agent": user_agent, "ip": remote_ip}


def browser_family_from_user_agent(user_agent):
    ua = str(user_agent or "").lower()
    if "edg/" in ua or "edge/" in ua:
        return "edge"
    if "opr/" in ua or "opera" in ua:
        return "opera"
    if "chrome/" in ua and "edg/" not in ua:
        return "chrome"
    if "firefox/" in ua:
        return "firefox"
    if "safari/" in ua and "chrome/" not in ua:
        return "safari"
    return "unknown"


def is_loopback_ip(ip_value):
    ip = str(ip_value or "").strip().lower()
    return ip in {"", "127.0.0.1", "::1", "localhost", "0.0.0.0"}


def mood_to_stress_score(mood_score):
    try:
        score = float(mood_score)
    except (TypeError, ValueError):
        score = 3.0
    # Mood 5 (very good) should imply lower stress, mood 1 higher stress.
    stress = 6.0 - score
    return round(max(1.0, min(stress, 5.0)), 2)


def normalize_face_emotion_key(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return ""

    compact = re.sub(r"[^a-z]", "", raw)
    aliases = {
        "happy": "joy",
        "happiness": "joy",
        "joyful": "joy",
        "sad": "sadness",
        "sadness": "sadness",
        "angry": "anger",
        "anger": "anger",
        "fear": "fear",
        "fearful": "fear",
        "anxious": "fear",
        "surprised": "surprise",
        "surprise": "surprise",
        "neutral": "neutral",
        "disgust": "disgust",
        "disgusted": "disgust",
    }
    mapped = aliases.get(compact, compact)
    if mapped in FACE_EMOTION_SCORES:
        return mapped
    return ""


def pulse_score(mood, face_score=None, face_emotion=""):
    try:
        mood_value = max(1.0, min(float(mood), 5.0))
    except (TypeError, ValueError):
        mood_value = 3.0

    if face_score is None:
        return round(mood_value, 2)

    try:
        face_value = max(1.0, min(float(face_score), 5.0))
    except (TypeError, ValueError):
        return round(mood_value, 2)

    emotion_key = normalize_face_emotion_key(face_emotion)
    face_weight = FACE_EMOTION_WEIGHTS.get(emotion_key, FACE_DEFAULT_BLEND_WEIGHT)
    face_weight = max(0.1, min(float(face_weight), 0.9))
    mood_weight = 1.0 - face_weight

    return round((mood_weight * mood_value) + (face_weight * face_value), 2)


def normalize_component_score(value, default=3.0):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return round(max(1.0, min(parsed, 5.0)), 2)


def steps_to_score(steps):
    try:
        value = int(steps)
    except (TypeError, ValueError):
        value = 0

    if value >= 8000:
        return 1.0
    if value >= 4000:
        return 3.0
    return 5.0


def sleep_to_score(sleep_hours):
    try:
        value = float(sleep_hours)
    except (TypeError, ValueError):
        value = 0.0

    if value >= 7.0:
        return 1.0
    if value >= 5.0:
        return 3.0
    return 5.0


def calculate_fitness_score(steps, sleep_hours):
    step_component = steps_to_score(steps)
    sleep_component = sleep_to_score(sleep_hours)
    return round((step_component + sleep_component) / 2.0, 2)


def calculate_multimodal_stress_score(components):
    final = (
        (MULTIMODAL_WEIGHTS["mood"] * normalize_component_score(components.get("mood"), 3.0))
        + (MULTIMODAL_WEIGHTS["chatbot"] * normalize_component_score(components.get("chatbot"), 3.0))
        + (MULTIMODAL_WEIGHTS["extension"] * normalize_component_score(components.get("extension"), 3.0))
        + (MULTIMODAL_WEIGHTS["fitness"] * normalize_component_score(components.get("fitness"), 3.0))
        + (MULTIMODAL_WEIGHTS["counsellor"] * normalize_component_score(components.get("counsellor"), COUNSELLOR_DEFAULT_SCORE))
        + (MULTIMODAL_WEIGHTS["quiz"] * normalize_component_score(components.get("quiz"), 3.0))
    )
    return round(max(1.0, min(final, 5.0)), 2)


def build_google_fit_redirect_uri():
    if GOOGLE_FIT_REDIRECT_URI:
        return GOOGLE_FIT_REDIRECT_URI

    try:
        return url_for("student_google_fit_callback", _external=True)
    except RuntimeError:
        return "http://127.0.0.1:5000/api/student/google-fit/callback"


def resolve_google_fit_scopes():
    configured = [scope.strip() for scope in str(GOOGLE_FIT_SCOPES or "").split() if scope.strip()]
    ordered = []
    for scope in [*configured, *GOOGLE_FIT_REQUIRED_SCOPES]:
        if scope not in ordered:
            ordered.append(scope)
    return " ".join(ordered)


def build_google_fit_auth_url(state):
    if not GOOGLE_FIT_CLIENT_ID:
        return ""

    params = {
        "client_id": GOOGLE_FIT_CLIENT_ID,
        "redirect_uri": build_google_fit_redirect_uri(),
        "response_type": "code",
        "scope": resolve_google_fit_scopes(),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent select_account",
        "state": state,
    }
    return f"{GOOGLE_FIT_OAUTH_AUTH_URL}?{urlencode(params)}"


def exchange_google_fit_code_for_tokens(code):
    if not GOOGLE_FIT_CLIENT_ID or not GOOGLE_FIT_CLIENT_SECRET:
        return None, "Google Fit client credentials are missing."

    data = {
        "client_id": GOOGLE_FIT_CLIENT_ID,
        "client_secret": GOOGLE_FIT_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": build_google_fit_redirect_uri(),
    }
    try:
        response = requests.post(GOOGLE_FIT_OAUTH_TOKEN_URL, data=data, timeout=(5, 20))
    except requests.RequestException as exc:
        return None, f"Google Fit token exchange failed: {exc}"

    try:
        payload = response.json()
    except ValueError:
        return None, "Google Fit token exchange returned invalid JSON."

    if response.status_code >= 400:
        return None, f"Google Fit token exchange error: {payload}"

    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        return None, "Google Fit did not return an access token."

    refresh_token = str(payload.get("refresh_token", "")).strip()
    expires_in = max(60, read_env_int("GOOGLE_FIT_ACCESS_MIN_TTL_SECONDS", payload.get("expires_in", 3600)))
    expires_at = (utc_now() + timedelta(seconds=expires_in)).isoformat(timespec="seconds")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }, None


def fetch_google_oauth_identity(access_token):
    token = str(access_token or "").strip()
    if not token:
        return {}, ""

    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(GOOGLE_OAUTH_USERINFO_URL, headers=headers, timeout=(5, 20))
    except requests.RequestException as exc:
        return {}, f"Google account lookup failed: {exc}"

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        return {}, f"Google account lookup error: {payload}"

    identity = {}
    account_email = str(payload.get("email", "")).strip().lower()
    account_sub = str(payload.get("sub", "")).strip()
    if account_email:
        identity["google_fit_account_email"] = account_email
    if account_sub:
        identity["google_fit_account_sub"] = account_sub

    return identity, ""


def refresh_google_fit_access_token(refresh_token):
    if not refresh_token:
        return None, "Google Fit refresh token is missing.", True
    if not GOOGLE_FIT_CLIENT_ID or not GOOGLE_FIT_CLIENT_SECRET:
        return None, "Google Fit client credentials are missing.", False

    data = {
        "client_id": GOOGLE_FIT_CLIENT_ID,
        "client_secret": GOOGLE_FIT_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        response = requests.post(GOOGLE_FIT_OAUTH_TOKEN_URL, data=data, timeout=(5, 20))
    except requests.RequestException as exc:
        return None, f"Google Fit token refresh failed: {exc}", False

    try:
        payload = response.json()
    except ValueError:
        return None, "Google Fit token refresh returned invalid JSON.", False

    if response.status_code >= 400:
        payload_text = str(payload).lower()
        requires_reauth = response.status_code in {400, 401} and "invalid_grant" in payload_text
        return None, f"Google Fit token refresh error: {payload}", requires_reauth

    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        return None, "Google Fit did not return a refreshed access token.", False

    expires_in = max(60, read_env_int("GOOGLE_FIT_ACCESS_MIN_TTL_SECONDS", payload.get("expires_in", 3600)))
    expires_at = (utc_now() + timedelta(seconds=expires_in)).isoformat(timespec="seconds")
    return {"access_token": access_token, "expires_at": expires_at}, None, False


def fetch_google_fit_steps(access_token):
    end = utc_now()
    start = end - timedelta(days=1)
    payload = {
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": int(start.timestamp() * 1000),
        "endTimeMillis": int(end.timestamp() * 1000),
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(GOOGLE_FIT_AGGREGATE_URL, headers=headers, json=payload, timeout=(5, 20))
    except requests.RequestException as exc:
        return None, f"Google Fit steps request failed: {exc}", False

    try:
        data = response.json()
    except ValueError:
        return None, "Google Fit steps API returned invalid JSON.", False

    if response.status_code in {401, 403}:
        return None, f"Google Fit steps API auth error: {data}", True

    if response.status_code >= 400:
        return None, f"Google Fit steps API error: {data}", False

    total_steps = 0.0
    point_count = 0
    for bucket in data.get("bucket", []):
        for dataset in bucket.get("dataset", []):
            for point in dataset.get("point", []):
                point_count += 1
                for value in point.get("value", []):
                    if "intVal" in value:
                        total_steps += float(value.get("intVal", 0) or 0)
                    elif "fpVal" in value:
                        total_steps += float(value.get("fpVal", 0.0) or 0.0)

    if point_count == 0:
        return None, "No step points returned by Google Fit API for this account/time window.", False

    return int(max(0, round(total_steps))), None, False


def fetch_google_fit_sleep_hours(access_token):
    end = utc_now()
    start = end - timedelta(days=1)
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "startTime": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "endTime": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }

    try:
        response = requests.get(GOOGLE_FIT_SESSIONS_URL, headers=headers, params=params, timeout=(5, 20))
    except requests.RequestException as exc:
        return None, f"Google Fit sleep request failed: {exc}", False

    try:
        data = response.json()
    except ValueError:
        return None, "Google Fit sleep API returned invalid JSON.", False

    if response.status_code in {401, 403}:
        return None, f"Google Fit sleep API auth error: {data}", True

    if response.status_code >= 400:
        return None, f"Google Fit sleep API error: {data}", False

    total_sleep_ms = 0
    for item in data.get("session", []):
        activity_type = str(item.get("activityType", "")).strip()
        name = str(item.get("name", "")).lower()
        if activity_type != "72" and "sleep" not in name:
            continue

        try:
            start_ms = int(item.get("startTimeMillis", 0) or 0)
            end_ms = int(item.get("endTimeMillis", 0) or 0)
        except (TypeError, ValueError):
            start_ms = 0
            end_ms = 0

        if end_ms > start_ms:
            total_sleep_ms += end_ms - start_ms

    sleep_hours = round(max(0.0, total_sleep_ms / 3600000.0), 2)
    return sleep_hours, None, False


def get_student_behavior_context(email):
    key = str(email or "").strip().lower()
    if not key:
        return {}
    return STUDENT_BEHAVIOR_CONTEXT.get(key, {})


def upsert_student_behavior_context(email, updates):
    key = str(email or "").strip().lower()
    if not key:
        return

    existing = STUDENT_BEHAVIOR_CONTEXT.get(key, {})
    merged = {**existing, **updates, "updated_at": utc_now().isoformat(timespec="seconds")}
    STUDENT_BEHAVIOR_CONTEXT[key] = merged


def get_student_multimodal_components(email):
    behavior = get_student_behavior_context(email)
    mood_base = float(behavior.get("mood_score", 3.0))

    return {
        "mood": normalize_component_score(behavior.get("component_mood", mood_to_stress_score(mood_base)), 3.0),
        "chatbot": normalize_component_score(behavior.get("component_chatbot", 3.0), 3.0),
        "extension": normalize_component_score(behavior.get("component_extension", 3.0), 3.0),
        "fitness": normalize_component_score(behavior.get("component_fitness", 3.0), 3.0),
        "counsellor": normalize_component_score(behavior.get("component_counsellor", COUNSELLOR_DEFAULT_SCORE), COUNSELLOR_DEFAULT_SCORE),
        "quiz": normalize_component_score(
            behavior.get("component_quiz", behavior.get("last_quiz_average_stress", 3.0)),
            3.0,
        ),
    }


def recompute_student_multimodal_state(email, source="runtime", last_checked_url=""):
    key = str(email or "").strip().lower()
    if not key:
        return None

    components = get_student_multimodal_components(key)
    final_score = calculate_multimodal_stress_score(components)
    final_category = classify_live_stress(final_score)
    mental_battery = calculate_mental_battery(final_score)

    upsert_student_behavior_context(
        key,
        {
            "component_mood": components["mood"],
            "component_chatbot": components["chatbot"],
            "component_extension": components["extension"],
            "component_fitness": components["fitness"],
            "component_counsellor": components["counsellor"],
            "component_quiz": components["quiz"],
            "last_multimodal_stress_score": final_score,
            "last_multimodal_stress_category": final_category,
            "last_multimodal_source": str(source or "runtime")[:40],
        },
    )

    if session.get("role") == "student" and str(session.get("email", "")).strip().lower() == key:
        session["student_live_stress_score"] = final_score
        session["student_live_category"] = final_category
        session["student_live_battery"] = mental_battery

    save_student_score_state(
        key,
        final_score,
        final_category,
        source=str(source or "runtime")[:32],
        last_checked_url=str(last_checked_url or "")[:500],
    )

    parent_alert = process_parent_alert_for_student(
        key,
        mental_battery,
        final_category,
        components,
    )

    return {
        "stress_score": final_score,
        "stress_category": final_category,
        "mental_battery": mental_battery,
        "components": components,
        "parent_alert": parent_alert,
    }


def get_google_fit_access_token(email):
    key = str(email or "").strip().lower()
    behavior = get_student_behavior_context(key)
    persisted = load_google_fit_db_state(key) or {}
    access_token = str(behavior.get("google_fit_access_token", "")).strip()
    refresh_token = str(behavior.get("google_fit_refresh_token", "")).strip()
    expires_at = parse_iso_datetime(behavior.get("google_fit_expires_at"))

    if not access_token:
        access_token = str(persisted.get("access_token", "")).strip()
    if not refresh_token:
        refresh_token = str(persisted.get("refresh_token", "")).strip()
    if not expires_at:
        expires_at = parse_iso_datetime(persisted.get("expires_at"))

    if access_token and expires_at and expires_at > (utc_now() + timedelta(seconds=30)):
        return access_token, None, False

    if refresh_token:
        refreshed, refresh_error, requires_reauth = refresh_google_fit_access_token(refresh_token)
        if refreshed:
            upsert_student_behavior_context(
                key,
                {
                    "google_fit_access_token": refreshed.get("access_token", ""),
                    "google_fit_refresh_token": refresh_token,
                    "google_fit_expires_at": refreshed.get("expires_at", ""),
                },
            )
            save_google_fit_db_state(
                key,
                {
                    **persisted,
                    "access_token": refreshed.get("access_token", ""),
                    "refresh_token": refresh_token,
                    "expires_at": refreshed.get("expires_at", ""),
                    "sync_status": "TOKEN_REFRESHED",
                    "sync_error": "",
                },
            )
            return str(refreshed.get("access_token", "")).strip(), None, False

        if requires_reauth:
            upsert_student_behavior_context(
                key,
                {
                    "google_fit_access_token": "",
                    "google_fit_refresh_token": "",
                    "google_fit_expires_at": "",
                },
            )
            save_google_fit_db_state(
                key,
                {
                    **persisted,
                    "access_token": "",
                    "refresh_token": "",
                    "expires_at": "",
                    "sync_status": "AUTH_EXPIRED",
                    "sync_error": str(refresh_error or "Token expired. Reconnect Google Fit."),
                },
            )
        return None, refresh_error, requires_reauth

    return None, "Google Fit is not connected for this student yet.", True


def sync_google_fit_for_student(email):
    key = str(email or "").strip().lower()
    if not key:
        return None, "Missing student email context for Google Fit sync.", False

    persisted = load_google_fit_db_state(key) or {}

    access_token, token_error, token_requires_reauth = get_google_fit_access_token(key)
    if not access_token:
        return None, token_error, bool(token_requires_reauth)

    steps, steps_error, steps_auth_failed = fetch_google_fit_steps(access_token)
    sleep_hours, sleep_error, sleep_auth_failed = fetch_google_fit_sleep_hours(access_token)

    if steps_auth_failed or sleep_auth_failed:
        auth_error = steps_error or sleep_error or "Google Fit token sync failed. Please login again."
        upsert_student_behavior_context(
            key,
            {
                "google_fit_access_token": "",
                "google_fit_refresh_token": "",
                "google_fit_expires_at": "",
            },
        )
        save_google_fit_db_state(
            key,
            {
                **persisted,
                "access_token": "",
                "refresh_token": "",
                "expires_at": "",
                "sync_status": "AUTH_EXPIRED",
                "sync_error": str(auth_error),
            },
        )
        return None, auth_error, True

    if steps is None and sleep_hours is None:
        generic_error = steps_error or sleep_error or "Unable to read Google Fit data."
        save_google_fit_db_state(
            key,
            {
                **persisted,
                "sync_status": "SYNC_FAILED",
                "sync_error": str(generic_error),
            },
        )
        return None, generic_error, False

    persisted_steps = int(persisted.get("steps", 0) or 0)
    persisted_sleep = round(float(persisted.get("sleep_hours", 0.0) or 0.0), 2)

    if steps is None:
        steps_value = int(max(0, persisted_steps))
        steps_source = "cache" if persisted_steps > 0 else "api-no-points"
    else:
        steps_value = int(max(0, steps or 0))
        steps_source = "api"

    if sleep_hours is None:
        sleep_value = round(max(0.0, persisted_sleep), 2)
    else:
        sleep_value = round(max(0.0, float(sleep_hours or 0.0)), 2)

    steps_component = steps_to_score(steps_value)
    sleep_component = sleep_to_score(sleep_value)
    fitness_component = calculate_fitness_score(steps_value, sleep_value)
    last_sync_at = utc_now().isoformat(timespec="seconds")

    warnings = []
    if steps_error:
        warnings.append(str(steps_error))
    if sleep_error:
        warnings.append(str(sleep_error))

    sync_status = "SYNCED"
    sync_error = ""
    if steps_source == "api-no-points":
        sync_status = "SYNCED_NO_STEP_POINTS"
        sync_error = str(steps_error or "No step points returned by Google Fit API.")
    elif warnings:
        sync_status = "SYNCED_WITH_WARNINGS"
        sync_error = " | ".join(warnings)[:500]

    upsert_student_behavior_context(
        key,
        {
            "google_fit_steps": steps_value,
            "google_fit_sleep_hours": sleep_value,
            "google_fit_steps_component": steps_component,
            "google_fit_sleep_component": sleep_component,
            "google_fit_last_sync_at": last_sync_at,
            "component_fitness": fitness_component,
        },
    )

    save_google_fit_db_state(
        key,
        {
            **persisted,
            "access_token": str(get_student_behavior_context(key).get("google_fit_access_token", persisted.get("access_token", ""))),
            "refresh_token": str(get_student_behavior_context(key).get("google_fit_refresh_token", persisted.get("refresh_token", ""))),
            "expires_at": str(get_student_behavior_context(key).get("google_fit_expires_at", persisted.get("expires_at", ""))),
            "google_account_email": str(
                get_student_behavior_context(key).get("google_fit_account_email", persisted.get("google_account_email", ""))
            ),
            "google_account_sub": str(
                get_student_behavior_context(key).get("google_fit_account_sub", persisted.get("google_account_sub", ""))
            ),
            "steps": steps_value,
            "sleep_hours": sleep_value,
            "steps_component": steps_component,
            "sleep_component": sleep_component,
            "fitness_component": fitness_component,
            "last_sync_at": last_sync_at,
            "sync_status": sync_status,
            "sync_error": sync_error,
        },
    )

    return {
        "steps": steps_value,
        "sleep_hours": sleep_value,
        "steps_component": steps_component,
        "sleep_component": sleep_component,
        "fitness_component": fitness_component,
        "warnings": warnings,
        "connected": True,
        "steps_source": steps_source,
        "last_sync_at": last_sync_at,
        "sync_status": sync_status,
        "sync_error": sync_error,
        "connected_account_email": str(
            get_student_behavior_context(key).get("google_fit_account_email", persisted.get("google_account_email", ""))
        ).strip().lower(),
        "requires_reauth": False,
    }, None, False


def get_google_fit_overview(email):
    behavior = get_student_behavior_context(email)
    persisted = load_google_fit_db_state(email) or {}
    sync_status = str(persisted.get("sync_status", "")).upper()
    requires_reauth = sync_status == "AUTH_EXPIRED"
    access_token = str(behavior.get("google_fit_access_token", persisted.get("access_token", ""))).strip()
    refresh_token = str(behavior.get("google_fit_refresh_token", persisted.get("refresh_token", ""))).strip()
    connected = bool(access_token or refresh_token) and not requires_reauth

    return {
        "connected": connected,
        "steps": int(persisted.get("steps", behavior.get("google_fit_steps", 0)) or 0),
        "sleep_hours": round(float(persisted.get("sleep_hours", behavior.get("google_fit_sleep_hours", 0.0)) or 0.0), 2),
        "fitness_component": normalize_component_score(
            persisted.get("fitness_component", behavior.get("component_fitness", 3.0)),
            3.0,
        ),
        "last_sync_at": str(persisted.get("last_sync_at", behavior.get("google_fit_last_sync_at", ""))),
        "steps_source": (
            "api"
            if persisted and sync_status in {"SYNCED", "TOKEN_REFRESHED", "SYNCED_WITH_WARNINGS"}
            else (
                "api-no-points"
                if persisted and sync_status == "SYNCED_NO_STEP_POINTS"
                else ("cache" if persisted else "memory")
            )
        ),
        "sync_status": sync_status,
        "sync_error": str(persisted.get("sync_error", "")),
        "connected_account_email": str(
            behavior.get("google_fit_account_email", persisted.get("google_account_email", ""))
        ).strip().lower(),
        "requires_reauth": requires_reauth,
    }


def update_extension_security_status(email, payload, request_obj=None):
    key = str(email or "").strip().lower()
    if not key:
        return None

    existing = EXTENSION_SECURITY_STATUS.get(key, {}) or load_extension_security_db_state(key) or {}
    now = utc_now()

    installed_in_payload = "installed_at" in payload
    consent_in_payload = "consent_granted_at" in payload

    installed_at = parse_iso_datetime(payload.get("installed_at")) if installed_in_payload else parse_iso_datetime(existing.get("installed_at"))
    consent_at = parse_iso_datetime(payload.get("consent_granted_at")) if consent_in_payload else parse_iso_datetime(existing.get("consent_granted_at"))
    observed_at = parse_iso_datetime(payload.get("observed_at")) or now

    if not installed_at:
        installed_at = observed_at

    extension_email = str(payload.get("student_email", existing.get("extension_email", key)) or key).strip().lower()
    if not extension_email:
        extension_email = key

    fingerprint = get_request_client_fingerprint(request_obj)

    status = {
        **existing,
        "extension_email": extension_email,
        "installed_at": installed_at.isoformat(timespec="seconds") if installed_at else None,
        "consent_granted_at": consent_at.isoformat(timespec="seconds") if consent_at else None,
        "last_seen_at": observed_at.isoformat(timespec="seconds"),
        "source": str(payload.get("source", existing.get("source", "unknown"))),
        "last_user_agent": fingerprint.get("user_agent") or existing.get("last_user_agent", ""),
        "last_ip": fingerprint.get("ip") or existing.get("last_ip", ""),
    }
    EXTENSION_SECURITY_STATUS[key] = status
    save_extension_security_db_state(key, status)
    return status


def evaluate_student_extension_access(email, request_obj=None, required_since=None):
    key = str(email or "").strip().lower()
    if not key:
        return False, "Student account is missing email context.", False

    status = EXTENSION_SECURITY_STATUS.get(key) or load_extension_security_db_state(key)
    if not status:
        return False, "Install and connect the EqWell extension before student access.", False

    EXTENSION_SECURITY_STATUS[key] = status

    now = utc_now()
    installed_at = parse_iso_datetime(status.get("installed_at"))
    consent_at = parse_iso_datetime(status.get("consent_granted_at"))
    last_seen_at = parse_iso_datetime(status.get("last_seen_at"))
    extension_email = str(status.get("extension_email", "")).strip().lower()

    if extension_email and extension_email != key:
        return False, "Extension login does not match this student account. Login again in extension.", False

    if not consent_at:
        return False, "Enable wellbeing consent in the extension to continue.", False

    if not last_seen_at:
        return False, "EqWell extension heartbeat was not detected. Reconnect extension.", False

    required_since_dt = parse_iso_datetime(required_since) if required_since else None
    if required_since_dt and (last_seen_at + timedelta(seconds=3)) < required_since_dt:
        return (
            False,
            "Extension verification for this login session is missing. Open EqWell extension and sign in again.",
            False,
        )

    stored_user_agent = str(status.get("last_user_agent", "")).strip().lower()
    if not stored_user_agent:
        return False, "Extension verification session is missing. Please reconnect extension.", False

    if (now - last_seen_at).total_seconds() > EXTENSION_HEARTBEAT_MAX_AGE_SECONDS:
        return False, "EqWell extension looks offline. Open extension and keep monitoring enabled.", False

    if request_obj is not None:
        current_fp = get_request_client_fingerprint(request_obj)
        current_user_agent = str(current_fp.get("user_agent", "")).strip().lower()
        stored_ip = str(status.get("last_ip", "")).strip()
        current_ip = str(current_fp.get("ip", "")).strip()

        stored_family = browser_family_from_user_agent(stored_user_agent)
        current_family = browser_family_from_user_agent(current_user_agent)
        if (
            current_user_agent
            and stored_user_agent
            and stored_family != "unknown"
            and current_family != "unknown"
            and current_family != stored_family
        ):
            return (
                False,
                "Extension verification is not from this browser session. Please keep EqWell extension active in this browser.",
                False,
            )

        if (
            stored_ip
            and current_ip
            and stored_ip != current_ip
            and not is_loopback_ip(stored_ip)
            and not is_loopback_ip(current_ip)
        ):
            return (
                False,
                "Extension verification is not from this device network session. Reconnect extension and retry.",
                False,
            )

    install_age = (now - installed_at).total_seconds() if installed_at else None
    consent_age = (now - consent_at).total_seconds() if consent_at else None

    suspicious_recent_enable = (
        (install_age is not None and install_age < EXTENSION_MIN_INSTALL_AGE_SECONDS)
        or (consent_age is not None and consent_age < EXTENSION_MIN_CONSENT_AGE_SECONDS)
    )

    if suspicious_recent_enable:
        return (
            False,
            "Security check: extension was enabled very recently. Please keep it active for a short while and retry.",
            True,
        )

    return True, "", False


def evaluate_student_profile_setup_access(email):
    key = str(email or "").strip().lower()
    if not key:
        return False, {
            "parent_ready": False,
            "google_fit_ready": False,
            "google_fit_account_match": False,
            "google_fit_connected": False,
            "google_fit_account": "",
            "required_email": "",
        }, ["student email context"]

    parent_contact = load_parent_alert_contact(key) or {}
    parent_name = str(parent_contact.get("parent_name", "")).strip()
    parent_phone = str(parent_contact.get("parent_phone", "")).strip()
    parent_verified = bool(parent_contact.get("verified"))
    parent_consent = bool(parent_contact.get("consent_enabled"))
    parent_ready = bool(parent_name and parent_phone and parent_verified and parent_consent)
    is_mock_student = bool(EQWELL_ENABLE_MOCK_LOGINS and is_mock_demo_account_email(key, "student"))

    google_fit = get_google_fit_overview(key)
    google_fit_connected = bool(google_fit.get("connected")) and not bool(google_fit.get("requires_reauth"))
    google_fit_account = str(google_fit.get("connected_account_email", "")).strip().lower()
    google_fit_account_match = bool(google_fit_account and google_fit_account == key)
    google_fit_ready = bool(google_fit_connected and google_fit_account_match)

    if is_mock_student:
        # Mock students skip Google Fit gating to keep demo login friction-free.
        google_fit_ready = True
        google_fit_account_match = True

    pending_requirements = []
    if not parent_ready:
        pending_requirements.append("parent information with OTP verification")
    if not is_mock_student:
        if not google_fit_connected:
            pending_requirements.append("Google Fit connection")
        elif not google_fit_account_match:
            pending_requirements.append("Google Fit account must match your student login email")

    details = {
        "parent_ready": parent_ready,
        "google_fit_ready": google_fit_ready,
        "google_fit_account_match": google_fit_account_match,
        "google_fit_connected": google_fit_connected,
        "google_fit_account": google_fit_account,
        "required_email": key,
    }
    return bool(parent_ready and google_fit_ready), details, pending_requirements


def build_student_profile_setup_message(pending_requirements):
    pending = [str(item).strip() for item in (pending_requirements or []) if str(item).strip()]
    if not pending:
        return "Complete your student profile setup before continuing."
    return "Complete setup before continuing: " + ", ".join(pending) + "."


def issue_extension_token(email, name, role="student"):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "name": name,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, EQWELL_JWT_SECRET, algorithm=EQWELL_JWT_ALGORITHM)


def decode_extension_bearer_token(auth_header):
    header_value = str(auth_header or "").strip()
    if not header_value.lower().startswith("bearer "):
        return None

    token = header_value.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        return jwt.decode(token, EQWELL_JWT_SECRET, algorithms=[EQWELL_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def validate_extension_student_identity(token_email, payload):
    token_key = str(token_email or "").strip().lower()
    claimed_email = str((payload or {}).get("student_email", "")).strip().lower()

    if claimed_email and claimed_email != token_key:
        return False, "Extension login mismatch. Use the same student account in app and extension.", ""

    effective_email = claimed_email or token_key
    if not effective_email:
        return False, "Student email is missing from extension identity payload.", ""

    if not is_approved_role_account(effective_email, "student"):
        return False, "Extension is connected with an unknown student account.", ""

    return True, "", effective_email


def apply_extension_signal_runtime(
    email,
    stress_signal,
    confidence,
    session_duration,
    current_url,
    hf_signal="",
    groq_signal="",
    event_started_at=None,
    risky_url_context=False,
    repeat_risk_count=0,
    repeat_risk_penalty_points=0,
    safe_event_count=0,
    risky_event_count=0,
    positive_event_count=0,
    safe_action_points=0,
    risky_action_points=0,
    no_risk_hours=0.0,
):
    key = str(email or "").strip().lower()
    if not key:
        return None

    signal = str(stress_signal or "MEDIUM").strip().upper()
    if signal not in {"LOW", "MEDIUM", "HIGH"}:
        signal = "MEDIUM"

    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    confidence_value = max(0.0, min(confidence_value, 1.0))

    try:
        session_duration_value = int(session_duration)
    except (TypeError, ValueError):
        session_duration_value = 0
    session_duration_value = max(0, min(session_duration_value, 1440))

    try:
        repeat_risk_count_value = max(0, int(repeat_risk_count))
    except (TypeError, ValueError):
        repeat_risk_count_value = 0

    try:
        repeat_risk_penalty_points_value = max(0, int(repeat_risk_penalty_points))
    except (TypeError, ValueError):
        repeat_risk_penalty_points_value = 0

    try:
        safe_event_count_value = max(0, int(safe_event_count))
    except (TypeError, ValueError):
        safe_event_count_value = 0

    try:
        risky_event_count_value = max(0, int(risky_event_count))
    except (TypeError, ValueError):
        risky_event_count_value = 0

    try:
        positive_event_count_value = max(0, int(positive_event_count))
    except (TypeError, ValueError):
        positive_event_count_value = 0

    try:
        safe_action_points_value = max(0, int(safe_action_points))
    except (TypeError, ValueError):
        safe_action_points_value = 0

    try:
        risky_action_points_value = max(0, int(risky_action_points))
    except (TypeError, ValueError):
        risky_action_points_value = 0

    try:
        no_risk_hours_value = max(0.0, float(no_risk_hours))
    except (TypeError, ValueError):
        no_risk_hours_value = 0.0

    current_url_value = str(current_url or "").strip()[:500]
    parsed_event_started = parse_iso_datetime(event_started_at) or utc_now()

    behavior = get_student_behavior_context(key)
    saved_state = load_student_score_state(key) or {}

    try:
        baseline_stress_score = max(1.0, min(float(saved_state.get("stress_score", 3.0)), 5.0))
    except (TypeError, ValueError):
        baseline_stress_score = 3.0

    try:
        baseline_battery = max(0, min(int(saved_state.get("mental_battery", calculate_mental_battery(baseline_stress_score))), 100))
    except (TypeError, ValueError):
        baseline_battery = calculate_mental_battery(baseline_stress_score)

    has_risky_activity = bool(
        risky_url_context
        or signal == "HIGH"
        or risky_event_count_value > 0
        or risky_action_points_value > 0
        or repeat_risk_penalty_points_value > 0
    )
    has_safe_or_neutral_activity = bool(
        (not has_risky_activity)
        and (
            signal == "LOW"
            or safe_event_count_value > 0
            or positive_event_count_value > 0
            or safe_action_points_value > 0
        )
    )

    previous_extension_component = normalize_component_score(behavior.get("component_extension", 3.0), 3.0)
    previous_extension_high_streak = int(behavior.get("extension_high_streak", 0))
    if has_risky_activity:
        extension_high_streak = previous_extension_high_streak + 1
    else:
        extension_high_streak = max(previous_extension_high_streak - 1, 0)

    signal_bias = 0.0
    if signal == "HIGH":
        signal_bias = 0.08 + (0.12 * confidence_value)
    elif signal == "LOW":
        signal_bias = -0.04 - (0.06 * confidence_value)

    risky_pressure = min(1.1, (risky_action_points_value / 18.0) + (0.14 * risky_event_count_value))
    if risky_url_context:
        risky_pressure = min(1.35, risky_pressure + 0.2)
    repeat_pressure = min(0.9, repeat_risk_penalty_points_value / 12.0)

    safe_window_factor = 0.25
    if no_risk_hours_value >= EXTENSION_SAFE_STREAK_HOURS_STEP_1:
        safe_window_factor = 0.5
    if no_risk_hours_value >= EXTENSION_SAFE_STREAK_HOURS_STEP_2:
        safe_window_factor = 0.8
    if no_risk_hours_value >= EXTENSION_SAFE_STREAK_HOURS_STEP_3:
        safe_window_factor = 1.0

    stability_gate = 0.45
    if baseline_battery >= 60 and baseline_stress_score <= 3.2:
        stability_gate = 1.0
    elif baseline_battery >= 45:
        stability_gate = 0.72

    safe_relief = (
        (safe_action_points_value / 20.0)
        + (0.08 * safe_event_count_value)
        + (0.05 * positive_event_count_value)
    )
    safe_relief = min(0.95, safe_relief * safe_window_factor * stability_gate)

    session_relief = 0.0
    if safe_event_count_value > 0:
        session_relief = min(0.1, session_duration_value / 1800.0)

    if has_risky_activity:
        safe_relief = 0.0
        session_relief = 0.0

    delta_component = signal_bias + risky_pressure + repeat_pressure - safe_relief - session_relief

    if has_risky_activity:
        risk_floor = 0.24 + min(
            0.42,
            (0.05 * risky_event_count_value)
            + (risky_action_points_value / 30.0)
            + (repeat_risk_penalty_points_value / 28.0)
            + (0.08 * confidence_value),
        )
        delta_component = max(delta_component, risk_floor)
    elif has_safe_or_neutral_activity:
        safe_floor = 0.06 + min(
            0.34,
            (safe_action_points_value / 45.0)
            + (0.03 * safe_event_count_value)
            + (0.03 * positive_event_count_value)
            + (0.015 * min(no_risk_hours_value, 12.0))
            + (0.04 if signal == "LOW" else 0.0),
        )
        delta_component = min(delta_component, -safe_floor)

    max_drop = 0.35 if safe_window_factor < 0.8 else 0.55
    if has_risky_activity:
        delta_component = max(0.1, min(0.95, delta_component))
    elif has_safe_or_neutral_activity:
        delta_component = max(-max_drop, min(-0.05, delta_component))
    else:
        delta_component = max(-max_drop, min(0.9, delta_component))

    extension_component = max(1.0, min(5.0, previous_extension_component + delta_component))

    upsert_student_behavior_context(
        key,
        {
            "component_extension": round(extension_component, 2),
            "extension_high_streak": extension_high_streak,
            "extension_repeat_risk_count": repeat_risk_count_value,
            "extension_repeat_risk_penalty": repeat_risk_penalty_points_value,
            "extension_safe_event_count": safe_event_count_value,
            "extension_risky_event_count": risky_event_count_value,
            "extension_positive_event_count": positive_event_count_value,
            "extension_safe_action_points": safe_action_points_value,
            "extension_risky_action_points": risky_action_points_value,
            "extension_no_risk_hours": round(no_risk_hours_value, 2),
            "extension_repeat_risk_updated_at": utc_now().isoformat(timespec="seconds"),
        },
    )

    runtime_state = recompute_student_multimodal_state(
        key,
        source="extension-signal",
        last_checked_url=current_url_value,
    ) or {
        "stress_score": 3.0,
        "stress_category": "MODERATE",
        "components": {
            "mood": 3.0,
            "chatbot": 3.0,
            "extension": round(extension_component, 2),
            "fitness": 3.0,
            "counsellor": COUNSELLOR_DEFAULT_SCORE,
        },
    }

    blended_target_score = float(runtime_state.get("stress_score", 3.0))
    runtime_components = runtime_state.get("components", {})

    EXTENSION_LIVE_SIGNALS[key] = {
        "stress_signal": signal,
        "confidence": round(confidence_value, 4),
        "session_duration": session_duration_value,
        "last_checked_url": current_url_value,
        "risky_url_context": bool(risky_url_context),
        "event_started_at": parsed_event_started.isoformat(timespec="milliseconds"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "target_stress_score": blended_target_score,
        "stress_category": str(runtime_state.get("stress_category", classify_live_stress(blended_target_score))),
        "hf_signal": str(hf_signal or "").upper(),
        "groq_signal": str(groq_signal or "").upper(),
        "mood_component": round(float(runtime_components.get("mood", 3.0)), 2),
        "chat_component": round(float(runtime_components.get("chatbot", 3.0)), 2),
        "fitness_component": round(float(runtime_components.get("fitness", 3.0)), 2),
        "counsellor_component": round(float(runtime_components.get("counsellor", COUNSELLOR_DEFAULT_SCORE)), 2),
        "extension_component": round(float(runtime_components.get("extension", extension_component)), 2),
        "extension_delta": round(delta_component, 3),
        "risky_gate_applied": has_risky_activity,
        "safe_gate_applied": has_safe_or_neutral_activity,
        "extension_high_streak": extension_high_streak,
        "repeat_risk_count": repeat_risk_count_value,
        "repeat_risk_penalty_points": repeat_risk_penalty_points_value,
        "safe_event_count": safe_event_count_value,
        "risky_event_count": risky_event_count_value,
        "positive_event_count": positive_event_count_value,
        "safe_action_points": safe_action_points_value,
        "risky_action_points": risky_action_points_value,
        "no_risk_hours": round(no_risk_hours_value, 2),
    }

    emit_terminal_debug_log(
        "extension-signal-applied",
        email=key,
        current_url=current_url_value,
        extracted_query="",
        final_signal=signal,
        final_confidence=round(confidence_value, 4),
        target_stress_score=blended_target_score,
        extension_high_streak=extension_high_streak,
        risky_url_context=bool(risky_url_context),
        repeat_risk_count=repeat_risk_count_value,
        repeat_risk_penalty_points=repeat_risk_penalty_points_value,
        safe_event_count=safe_event_count_value,
        risky_event_count=risky_event_count_value,
        positive_event_count=positive_event_count_value,
        safe_action_points=safe_action_points_value,
        risky_action_points=risky_action_points_value,
        no_risk_hours=round(no_risk_hours_value, 2),
    )

    return EXTENSION_LIVE_SIGNALS[key]


init_score_store()
ensure_default_accounts_seeded()
ensure_mock_demo_data_seeded()


@app.context_processor
def inject_globals():
    active_role = session.get("role")
    sidebar = build_sidebar(active_role) if active_role else ROLE_SIDEBARS["student"]
    display_name = session.get("name", "EqWell User")
    user_email = session.get("email", "")
    avatar_seed = str(user_email or display_name).strip() or "EqWell User"
    return {
        "active_role": active_role,
        "role_sidebar": sidebar,
        "display_name": display_name,
        "student_mood": session.get("student_mood"),
        "user_avatar_url": build_dicebear_avatar_url(avatar_seed),
    }


@app.get("/api/avatar")
def avatar_api():
    seed = str(request.args.get("seed", "")).strip() or str(session.get("email") or session.get("name") or "EqWell User")
    style = normalize_avatar_style(request.args.get("style", ""))
    image_format = normalize_avatar_format(request.args.get("format", ""))
    return jsonify(
        {
            "ok": True,
            "provider": "dicebear",
            "style": style,
            "format": image_format,
            "seed": seed,
            "url": build_dicebear_avatar_url(seed, style=style, image_format=image_format),
        }
    )


def render_login_page(initial_role="student", lock_role=False):
    scoped_role = initial_role if lock_role else ""
    portal_extension_nonce = ensure_student_login_extension_nonce(refresh=False)
    return render_template(
        "login.html",
        initial_role=initial_role,
        lock_role=bool(lock_role),
        portal_extension_nonce=portal_extension_nonce,
        mock_logins=list_mock_login_credentials(scoped_role, unique_per_role=True),
    )


def ensure_student_login_extension_nonce(refresh=False):
    now = utc_now()
    existing_nonce = str(session.get("student_extension_login_nonce", "")).strip()
    issued_at = parse_iso_datetime(session.get("student_extension_login_nonce_issued_at"))
    is_expired = bool(
        issued_at and (now - issued_at).total_seconds() > EXTENSION_LOGIN_NONCE_TTL_SECONDS
    )

    if refresh or not existing_nonce or not issued_at or is_expired:
        existing_nonce = secrets.token_urlsafe(24)
        session["student_extension_login_nonce"] = existing_nonce
        session["student_extension_login_nonce_issued_at"] = now.isoformat(timespec="seconds")

    return existing_nonce


def issue_extension_portal_login_proof(email, nonce, request_obj=None):
    now = utc_now()
    fingerprint = get_request_client_fingerprint(request_obj)
    user_agent = str(fingerprint.get("user_agent", "")).strip().lower()
    payload = {
        "sub": str(email or "").strip().lower(),
        "role": "student",
        "typ": "portal-login-proof",
        "nonce": str(nonce or "").strip(),
        "ua": user_agent,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=EXTENSION_PORTAL_PROOF_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, EQWELL_JWT_SECRET, algorithm=EQWELL_JWT_ALGORITHM)


def decode_extension_portal_login_proof(token):
    raw_token = str(token or "").strip()
    if not raw_token:
        return None
    try:
        return jwt.decode(raw_token, EQWELL_JWT_SECRET, algorithms=[EQWELL_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def validate_student_extension_login_proof(expected_email, submitted_nonce, proof_token, request_obj=None):
    expected_key = str(expected_email or "").strip().lower()
    nonce = str(submitted_nonce or "").strip()
    proof = str(proof_token or "").strip()

    if not expected_key:
        return False, "Student email context is missing during extension verification."

    session_nonce = str(session.get("student_extension_login_nonce", "")).strip()
    nonce_issued_at = parse_iso_datetime(session.get("student_extension_login_nonce_issued_at"))
    if not session_nonce or not nonce_issued_at:
        return False, "Extension verification session expired. Reload login and try again."

    nonce_age_seconds = (utc_now() - nonce_issued_at).total_seconds()
    if nonce_age_seconds > EXTENSION_LOGIN_NONCE_TTL_SECONDS:
        return False, "Extension verification session expired. Reload login and try again."

    if not nonce or nonce != session_nonce:
        return False, "Extension browser proof is missing for this tab. Keep extension active in this browser and retry."

    if not proof:
        return False, "Open EqWell extension in this browser, login there, then retry student login."

    claims = decode_extension_portal_login_proof(proof)
    if not claims:
        return False, "Extension browser proof is invalid or expired. Retry student login from this browser."

    claim_email = str(claims.get("sub", "")).strip().lower()
    claim_role = str(claims.get("role", "")).strip().lower()
    claim_type = str(claims.get("typ", "")).strip().lower()
    claim_nonce = str(claims.get("nonce", "")).strip()

    if claim_role != "student" or claim_type != "portal-login-proof":
        return False, "Extension browser proof is malformed. Reconnect extension and retry."
    if claim_email != expected_key:
        return False, "Extension account does not match this student login. Use same account in extension."
    if claim_nonce != nonce:
        return False, "Extension browser proof does not match this login tab session."

    if request_obj is not None:
        current_fp = get_request_client_fingerprint(request_obj)
        claim_ua = str(claims.get("ua", "")).strip().lower()
        current_ua = str(current_fp.get("user_agent", "")).strip().lower()
        claim_family = browser_family_from_user_agent(claim_ua)
        current_family = browser_family_from_user_agent(current_ua)
        if (
            claim_ua
            and current_ua
            and claim_family != "unknown"
            and current_family != "unknown"
            and claim_family != current_family
        ):
            return False, "Student login must happen from the same browser where extension proof was generated."

    return True, ""


@app.get("/")
def home():
    role = session.get("role")
    if role == "admin":
        session["role"] = "developer"
        role = "developer"

    if role == "student":
        pending_mood = str(session.get("student_mood_pending", "")).strip()
        if pending_mood in STUDENT_MOODS:
            return redirect(url_for("student_face_check"))
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))
    if role in {"warden", "counsellor", "developer", "parent", "proctor"}:
        return redirect(url_for("dashboard", role=role))
    return render_template("landing.html")


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "status": "ok",
            "service": "eqwell-flask",
            "environment": FLASK_ENVIRONMENT,
            "time": utc_now().isoformat(timespec="seconds"),
        }
    )


@app.get("/readyz")
def readyz():
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except sqlite3.Error:
        db_ok = False

    status_code = 200 if db_ok else 503
    return (
        jsonify(
            {
                "status": "ready" if db_ok else "degraded",
                "database": "ok" if db_ok else "unreachable",
                "db_path": str(SCORE_DB_PATH),
                "time": utc_now().isoformat(timespec="seconds"),
            }
        ),
        status_code,
    )


@app.route("/signup", methods=["GET", "POST"])
def signup_showcase():
    if request.method == "POST":
        name = str(request.form.get("name", "")).strip()
        email = str(request.form.get("email", "")).strip().lower()
        password = str(request.form.get("password", ""))
        confirm_password = str(request.form.get("confirm_password", ""))
        role = normalize_account_role(request.form.get("role", ""))
        note = str(request.form.get("note", "")).strip()

        if not name or not email or not password or not role:
            flash("Name, email, password, and role are required.", "error")
            return render_template("signup_showcase.html", selected_role=role or "student")

        if "@" not in email:
            flash("Use a valid email address.", "error")
            return render_template("signup_showcase.html", selected_role=role)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup_showcase.html", selected_role=role)

        if password != confirm_password:
            flash("Password confirmation does not match.", "error")
            return render_template("signup_showcase.html", selected_role=role)

        existing = get_user_account_by_email(email)
        if existing and existing.get("status") == "approved":
            flash("Account already approved. Please login.", "error")
            return redirect(url_for("login", role=existing.get("role", role)))

        saved, save_error = upsert_user_account(
            name=name,
            email=email,
            password=password,
            role=role,
            status="pending",
            requested_note=note or "Self-signup pending approval",
            approved_by="",
        )
        if not saved:
            flash(save_error or "Could not submit signup request right now.", "error")
            return render_template("signup_showcase.html", selected_role=role)

        flash("Signup submitted. Wait for developer approval before login.", "success")
        return redirect(url_for("login", role=role))

    return render_template("signup_showcase.html", selected_role="student")


@app.get("/install-extension")
def install_extension():
    return render_template("install_extension.html")


@app.post("/api/extension/student/login")
def extension_student_login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    account, auth_error = authenticate_portal_user("student", email, password)
    if auth_error or not account:
        return jsonify({"error": auth_error or "Invalid student credentials."}), 401

    token = issue_extension_token(account["email"], account["name"], role="student")
    return jsonify(
        {
            "token": token,
            "student": {
                "name": account["name"],
                "email": account["email"],
                "role": "student",
            },
            "message": "Extension connected to EqWell student account.",
        }
    )


@app.get("/api/extension/student/me")
def extension_student_me():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension identity is supported."}), 403

    account = get_user_account_by_email(email)
    if not account or account.get("role") != "student" or account.get("status") != "approved":
        return jsonify({"error": "Student profile not found."}), 404

    return jsonify(
        {
            "student": {
                "name": account.get("name", "Student"),
                "email": account.get("email", email),
                "role": "student",
            }
        }
    )


@app.post("/api/extension/student/presence")
def extension_student_presence():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension presence is supported."}), 403

    payload = request.get_json(silent=True) or {}
    identity_ok, identity_error, effective_email = validate_extension_student_identity(email, payload)
    if not identity_ok:
        return jsonify({"error": identity_error}), 403

    payload = {
        **payload,
        "student_email": effective_email,
        "observed_at": payload.get("observed_at") or utc_now().isoformat(timespec="seconds"),
        "source": payload.get("source") or "presence",
    }
    status = update_extension_security_status(email, payload, request_obj=request)
    valid, _, suspicious_popup = evaluate_student_extension_access(email, request_obj=request)
    return jsonify(
        {
            "ok": bool(status),
            "extension_ready": valid,
            "suspicious": suspicious_popup,
        }
    )


@app.post("/api/extension/student/portal-proof")
def extension_student_portal_proof():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension proof is supported."}), 403

    payload = request.get_json(silent=True) or {}
    submitted_nonce = str(payload.get("nonce", "")).strip()
    if not submitted_nonce:
        return jsonify({"error": "Login nonce is required."}), 400

    identity_ok, identity_error, effective_email = validate_extension_student_identity(email, payload)
    if not identity_ok:
        return jsonify({"error": identity_error}), 403

    session_nonce = str(session.get("student_extension_login_nonce", "")).strip()
    nonce_issued_at = parse_iso_datetime(session.get("student_extension_login_nonce_issued_at"))
    if not session_nonce or not nonce_issued_at:
        return jsonify({"error": "Portal login session expired. Reload login page and retry."}), 403

    nonce_age_seconds = (utc_now() - nonce_issued_at).total_seconds()
    if nonce_age_seconds > EXTENSION_LOGIN_NONCE_TTL_SECONDS:
        return jsonify({"error": "Portal login session expired. Reload login page and retry."}), 403

    if submitted_nonce != session_nonce:
        return jsonify({"error": "Portal nonce mismatch for this browser tab."}), 403

    # Refresh last-seen proof of this exact browser session before validating gate checks.
    update_extension_security_status(
        email,
        {
            "student_email": effective_email,
            "observed_at": utc_now().isoformat(timespec="seconds"),
            "source": payload.get("source") or "portal-proof",
        },
        request_obj=request,
    )

    valid, message, show_popup = evaluate_student_extension_access(effective_email, request_obj=request)
    if not valid:
        return jsonify({"error": message, "show_popup": bool(show_popup)}), 403

    proof_token = issue_extension_portal_login_proof(effective_email, submitted_nonce, request_obj=request)
    return jsonify(
        {
            "ok": True,
            "proof": proof_token,
            "expires_in": EXTENSION_PORTAL_PROOF_TTL_SECONDS,
        }
    )


@app.post("/api/extension/student/collect-event")
def extension_student_collect_event():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension event collection is supported."}), 403

    payload = request.get_json(silent=True) or {}
    identity_ok, identity_error, effective_email = validate_extension_student_identity(email, payload)
    if not identity_ok:
        return jsonify({"error": identity_error}), 403

    current_url = str(payload.get("current_url", "")).strip()[:500]
    extracted_query = str(payload.get("extracted_query", "")).strip()[:300]
    page_context = str(payload.get("page_context", "")).strip()[:300]
    observed_at = payload.get("observed_at") or utc_now().isoformat(timespec="seconds")

    if current_url and not should_collect_extension_event_url(current_url):
        current_url = ""
        extracted_query = ""
        page_context = ""

    try:
        session_duration = int(payload.get("session_duration", 0))
    except (TypeError, ValueError):
        session_duration = 0
    session_duration = max(0, min(session_duration, 1440))

    if not current_url and not extracted_query and not page_context:
        return jsonify({"ok": True, "queued": False, "skipped": True})

    queued = queue_extension_collected_event(
        email,
        current_url=current_url,
        extracted_query=extracted_query,
        page_context=page_context,
        session_duration=session_duration,
        observed_at=observed_at,
    )

    update_extension_security_status(
        email,
        {
            "student_email": effective_email,
            "installed_at": payload.get("installed_at"),
            "consent_granted_at": payload.get("consent_granted_at"),
            "observed_at": observed_at,
            "source": payload.get("source") or "collect-event",
        },
        request_obj=request,
    )

    emit_terminal_debug_log(
        "extension-event-collected",
        email=email,
        queued=queued,
        current_url=current_url,
        extracted_query=extracted_query,
        session_duration=session_duration,
        observed_at=observed_at,
    )

    if not queued:
        return jsonify({"error": "Unable to queue event."}), 503

    return jsonify({"ok": True, "queued": True})


@app.post("/api/extension/student/process-collected")
def extension_student_process_collected_events():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension processing is supported."}), 403

    payload = request.get_json(silent=True) or {}
    identity_ok, identity_error, effective_email = validate_extension_student_identity(email, payload)
    if not identity_ok:
        return jsonify({"error": identity_error}), 403

    observed_at = payload.get("observed_at") or utc_now().isoformat(timespec="seconds")
    requested_max_events = payload.get("max_events", EXTENSION_BATCH_MAX_EVENTS)
    try:
        max_events = int(requested_max_events)
    except (TypeError, ValueError):
        max_events = EXTENSION_BATCH_MAX_EVENTS
    max_events = max(1, min(max_events, EXTENSION_BATCH_MAX_EVENTS))

    update_extension_security_status(
        email,
        {
            "student_email": effective_email,
            "installed_at": payload.get("installed_at"),
            "consent_granted_at": payload.get("consent_granted_at"),
            "observed_at": observed_at,
            "source": payload.get("source") or "process-collected",
        },
        request_obj=request,
    )

    events = load_extension_collected_events(email, max_events)
    if not events:
        emit_terminal_debug_log(
            "extension-batch-empty",
            email=email,
            requested_max_events=max_events,
        )
        return jsonify(
            {
                "ok": True,
                "has_update": False,
                "processed_count": 0,
                "cleared_count": 0,
                "batch_window_hours": EXTENSION_BATCH_WINDOW_HOURS,
            }
        )

    url_activity = append_student_url_history_events(email, events)

    event_ids = [event.get("id") for event in events]
    any_risky_context = any(
        extension_url_context_risk(event.get("current_url", ""), event.get("extracted_query", ""))
        for event in events
    )
    repeat_risk = compute_extension_repeat_penalty(email, events)
    repeat_risk_count = int(repeat_risk.get("max_repeat_count", 0) or 0)
    repeat_risk_penalty_points = int(repeat_risk.get("max_penalty_points", 0) or 0)

    relevant_text, groq_signal, groq_confidence, top_url = groq_extract_relevant_event_text(events)
    emotion, hf_confidence, analysis_warning = analyze_student_emotion(relevant_text)
    hf_signal = emotion_to_stress_level(emotion)
    final_signal, final_confidence = merge_batch_stress_signals(
        groq_signal=groq_signal,
        groq_confidence=groq_confidence,
        hf_signal=hf_signal,
        hf_confidence=hf_confidence,
        risky_url_context=any_risky_context,
    )

    if any_risky_context and repeat_risk_penalty_points >= EXTENSION_REPEAT_PENALTY_STEP_2:
        final_signal = "HIGH"
        final_confidence = max(float(final_confidence or 0.0), 0.8)

    latest_event = events[-1]
    latest_observed_at = parse_iso_datetime(latest_event.get("observed_at")) or utc_now()
    session_duration = max(int(event.get("session_duration", 0) or 0) for event in events)
    selected_url = str(top_url or "").strip()[:500]
    if not selected_url or not should_collect_extension_event_url(selected_url):
        selected_url = ""
        for event in reversed(events):
            candidate_url = str(event.get("current_url", "")).strip()[:500]
            if should_collect_extension_event_url(candidate_url):
                selected_url = candidate_url
                break

    live_signal = apply_extension_signal_runtime(
        email=email,
        stress_signal=final_signal,
        confidence=final_confidence,
        session_duration=session_duration,
        current_url=selected_url,
        hf_signal=hf_signal,
        groq_signal=groq_signal,
        event_started_at=latest_observed_at,
        risky_url_context=any_risky_context,
        repeat_risk_count=repeat_risk_count,
        repeat_risk_penalty_points=repeat_risk_penalty_points,
        safe_event_count=url_activity.get("safe_event_count", 0),
        risky_event_count=url_activity.get("risky_event_count", 0),
        positive_event_count=url_activity.get("positive_event_count", 0),
        safe_action_points=url_activity.get("safe_action_points", 0),
        risky_action_points=url_activity.get("risky_action_points", 0),
        no_risk_hours=url_activity.get("no_risk_hours", 0.0),
    ) or {}

    save_student_score_state(
        email,
        float(live_signal.get("target_stress_score", 3.0)),
        str(live_signal.get("stress_category", "MODERATE")),
        source="extension-batch",
        last_checked_url=selected_url,
    )

    cleared_count = clear_extension_collected_events(event_ids)

    emit_terminal_debug_log(
        "extension-batch-processed",
        email=email,
        processed_count=len(events),
        cleared_count=cleared_count,
        relevant_text=relevant_text,
        groq_signal=groq_signal,
        groq_confidence=round(float(groq_confidence or 0.0), 4),
        hf_signal=hf_signal,
        hf_confidence=round(float(hf_confidence or 0.0), 4),
        final_signal=final_signal,
        final_confidence=final_confidence,
        selected_url=selected_url,
        risky_url_context=any_risky_context,
        repeat_risk_count=repeat_risk_count,
        repeat_risk_penalty_points=repeat_risk_penalty_points,
        safe_event_count=url_activity.get("safe_event_count", 0),
        risky_event_count=url_activity.get("risky_event_count", 0),
        positive_event_count=url_activity.get("positive_event_count", 0),
        safe_action_points=url_activity.get("safe_action_points", 0),
        risky_action_points=url_activity.get("risky_action_points", 0),
        no_risk_hours=url_activity.get("no_risk_hours", 0.0),
        warning=str(analysis_warning or ""),
    )

    return jsonify(
        {
            "ok": True,
            "has_update": True,
            "processed_count": len(events),
            "cleared_count": cleared_count,
            "batch_window_hours": EXTENSION_BATCH_WINDOW_HOURS,
            "stress_signal": final_signal,
            "confidence": final_confidence,
            "hf_signal": hf_signal,
            "groq_signal": groq_signal,
            "emotion": emotion,
            "analysis_warning": analysis_warning,
            "last_checked_url": selected_url,
            "repeat_risk_count": repeat_risk_count,
            "repeat_risk_penalty_points": repeat_risk_penalty_points,
            "safe_event_count": url_activity.get("safe_event_count", 0),
            "risky_event_count": url_activity.get("risky_event_count", 0),
            "positive_event_count": url_activity.get("positive_event_count", 0),
            "safe_action_points": url_activity.get("safe_action_points", 0),
            "risky_action_points": url_activity.get("risky_action_points", 0),
            "no_risk_hours": url_activity.get("no_risk_hours", 0.0),
            "updated_at": str(live_signal.get("updated_at", "")),
        }
    )


@app.post("/api/extension/student/signal")
def extension_student_signal_sync():
    claims = decode_extension_bearer_token(request.headers.get("Authorization"))
    if not claims:
        return jsonify({"error": "Invalid or missing extension token."}), 401

    email = str(claims.get("sub", "")).strip().lower()
    role = str(claims.get("role", "")).strip().lower()
    if role != "student" or not email:
        return jsonify({"error": "Only student extension signals are supported."}), 403

    payload = request.get_json(silent=True) or {}
    identity_ok, identity_error, effective_email = validate_extension_student_identity(email, payload)
    if not identity_ok:
        return jsonify({"error": identity_error}), 403

    stress_signal = str(payload.get("stress_signal", "")).strip().upper()
    if stress_signal not in {"LOW", "MEDIUM", "HIGH"}:
        return jsonify({"error": "Invalid stress_signal value."}), 400

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))

    try:
        session_duration = int(payload.get("session_duration", 0))
    except (TypeError, ValueError):
        session_duration = 0
    session_duration = max(0, min(session_duration, 1440))
    current_url = str(payload.get("current_url", "")).strip()[:500]
    extracted_query = str(payload.get("extracted_query", "")).strip()[:300]
    page_context = str(payload.get("page_context", "")).strip()[:300]
    incoming_stress_signal = stress_signal
    incoming_confidence = confidence
    event_started_at = parse_iso_datetime(payload.get("event_started_at"))
    if not event_started_at:
        event_started_at = utc_now()

    existing_live_signal = EXTENSION_LIVE_SIGNALS.get(email, {})
    existing_event_started_at = parse_iso_datetime(existing_live_signal.get("event_started_at"))
    if existing_event_started_at and event_started_at <= existing_event_started_at:
        update_extension_security_status(
            email,
            {
                **payload,
                "student_email": effective_email,
                "observed_at": payload.get("observed_at") or utc_now().isoformat(timespec="seconds"),
                "source": payload.get("source") or "signal",
            },
            request_obj=request,
        )
        emit_terminal_debug_log(
            "extension-signal-stale-ignored",
            email=email,
            current_url=current_url,
            extracted_query=extracted_query,
            event_started_at=event_started_at.isoformat(timespec="milliseconds"),
            existing_event_started_at=existing_event_started_at.isoformat(timespec="milliseconds"),
        )
        return jsonify({"ok": True, "ignored_stale": True, "received_url": bool(current_url)})

    event_observed_at = payload.get("observed_at") or utc_now().isoformat(timespec="seconds")
    event_record = {
        "current_url": current_url,
        "extracted_query": extracted_query,
        "page_context": page_context,
        "session_duration": session_duration,
        "observed_at": event_observed_at,
    }
    has_event_context = bool(current_url or extracted_query or page_context)

    risky_url_context = extension_url_context_risk(current_url, extracted_query)
    single_event_activity = append_student_url_history_events(
        email,
        [event_record] if has_event_context else [],
    )

    repeat_risk_count = 0
    repeat_risk_penalty_points = 0
    if has_event_context:
        repeat_risk = compute_extension_repeat_penalty(email, [event_record])
        repeat_risk_count = int(repeat_risk.get("max_repeat_count", 0) or 0)
        repeat_risk_penalty_points = int(repeat_risk.get("max_penalty_points", 0) or 0)

    server_hf_signal = str(payload.get("hf_signal", "")).upper()
    server_groq_signal = str(payload.get("groq_signal", "")).upper()
    analysis_warning = None
    if has_event_context:
        relevant_text, server_groq_signal, groq_confidence, _ = groq_extract_relevant_event_text([event_record])
        if not relevant_text:
            relevant_text = extension_event_context_text(current_url, extracted_query, page_context)

        emotion, hf_confidence, analysis_warning = analyze_student_emotion(relevant_text)
        server_hf_signal = emotion_to_stress_level(emotion)
        stress_signal, confidence = merge_batch_stress_signals(
            groq_signal=server_groq_signal,
            groq_confidence=groq_confidence,
            hf_signal=server_hf_signal,
            hf_confidence=hf_confidence,
            risky_url_context=risky_url_context,
        )

    if risky_url_context and stress_signal != "HIGH":
        stress_signal = "HIGH"
        confidence = max(confidence, 0.72)

    emit_terminal_debug_log(
        "extension-signal-incoming",
        email=email,
        current_url=current_url,
        extracted_query=extracted_query,
        incoming_signal=incoming_stress_signal,
        incoming_confidence=round(incoming_confidence, 4),
        session_duration=session_duration,
        risky_url_context=risky_url_context,
        hf_signal=server_hf_signal,
        groq_signal=server_groq_signal,
        repeat_risk_count=repeat_risk_count,
        repeat_risk_penalty_points=repeat_risk_penalty_points,
        analysis_warning=str(analysis_warning or ""),
    )

    update_extension_security_status(
        email,
        {
            **payload,
            "student_email": effective_email,
            "observed_at": event_observed_at,
            "source": payload.get("source") or "signal",
        },
        request_obj=request,
    )

    apply_extension_signal_runtime(
        email=email,
        stress_signal=stress_signal,
        confidence=confidence,
        session_duration=session_duration,
        current_url=current_url,
        hf_signal=server_hf_signal,
        groq_signal=server_groq_signal,
        event_started_at=event_started_at,
        risky_url_context=risky_url_context,
        repeat_risk_count=repeat_risk_count,
        repeat_risk_penalty_points=repeat_risk_penalty_points,
        safe_event_count=single_event_activity.get("safe_event_count", 0),
        risky_event_count=single_event_activity.get("risky_event_count", 0),
        positive_event_count=single_event_activity.get("positive_event_count", 0),
        safe_action_points=single_event_activity.get("safe_action_points", 0),
        risky_action_points=single_event_activity.get("risky_action_points", 0),
        no_risk_hours=single_event_activity.get("no_risk_hours", 0.0),
    )

    emit_terminal_debug_log(
        "extension-signal-applied",
        email=email,
        final_signal=stress_signal,
        final_confidence=round(float(confidence or 0.0), 4),
        hf_signal=server_hf_signal,
        groq_signal=server_groq_signal,
        risky_url_context=risky_url_context,
        repeat_risk_count=repeat_risk_count,
        repeat_risk_penalty_points=repeat_risk_penalty_points,
        current_url=current_url,
        extracted_query=extracted_query,
    )

    return jsonify(
        {
            "ok": True,
            "received_url": bool(current_url),
            "stress_signal": stress_signal,
            "confidence": round(float(confidence or 0.0), 4),
            "hf_signal": server_hf_signal,
            "groq_signal": server_groq_signal,
            "risky_url_context": risky_url_context,
            "repeat_risk_count": repeat_risk_count,
            "repeat_risk_penalty_points": repeat_risk_penalty_points,
            "analysis_warning": str(analysis_warning or ""),
        }
    )


@app.get("/api/student/live-extension-signal")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_live_extension_signal():
    email = str(session.get("email", "")).strip().lower()
    if not email:
        return jsonify({"available": False})

    signal_data = EXTENSION_LIVE_SIGNALS.get(email, {})
    saved_last_checked_url = ""
    saved_state = load_student_score_state(email)
    if saved_state:
        stress_score = float(saved_state.get("stress_score", 3.0))
        stress_category = str(saved_state.get("stress_category", "MODERATE"))
        mental_battery = int(saved_state.get("mental_battery", calculate_mental_battery(stress_score)))
        saved_last_checked_url = str(saved_state.get("last_checked_url", "")).strip()[:500]
        components = get_student_multimodal_components(email)
    else:
        runtime_state = recompute_student_multimodal_state(
            email,
            source="live-poll-init",
            last_checked_url=signal_data.get("last_checked_url", ""),
        )
        if not runtime_state:
            return jsonify({"available": False})
        stress_score = float(runtime_state.get("stress_score", 3.0))
        stress_category = str(runtime_state.get("stress_category", "MODERATE"))
        mental_battery = int(runtime_state.get("mental_battery", calculate_mental_battery(stress_score)))
        components = runtime_state.get("components", {})

    google_fit = get_google_fit_overview(email)
    stress_signal = str(signal_data.get("stress_signal", stress_category)).upper()
    response_last_checked_url = str(signal_data.get("last_checked_url", "")).strip()[:500] or saved_last_checked_url

    emit_terminal_debug_log(
        "live-signal-response",
        email=email,
        stress_signal=stress_signal,
        stress_score=round(stress_score, 2),
        stress_category=stress_category,
        mental_battery=mental_battery,
        current_url=response_last_checked_url,
        updated_at=signal_data.get("updated_at", ""),
    )

    return jsonify(
        {
            "available": True,
            "stress_signal": stress_signal,
            "confidence": signal_data.get("confidence", 0.0),
            "stress_score": stress_score,
            "stress_category": stress_category,
            "mental_battery": mental_battery,
            "session_duration": signal_data.get("session_duration", 0),
            "last_checked_url": response_last_checked_url,
            "updated_at": signal_data.get("updated_at", ""),
            "hf_signal": signal_data.get("hf_signal", ""),
            "groq_signal": signal_data.get("groq_signal", ""),
            "components": components,
            "google_fit": google_fit,
        }
    )


@app.get("/api/student/tasks/state")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_tasks_state_api():
    email = str(session.get("email", "")).strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Student session missing."}), 401

    state = build_student_daily_tasks_state(email)
    return jsonify({"ok": True, **state})


@app.post("/api/student/tasks/claim")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_tasks_claim_api():
    email = str(session.get("email", "")).strip().lower()
    if not email:
        return jsonify({"ok": False, "error": "Student session missing."}), 401

    payload = request.get_json(silent=True) or {}
    task_id = str(payload.get("task_id", "")).strip().lower()[:64]
    if not task_id:
        return jsonify({"ok": False, "error": "Task ID is required."}), 400

    state = build_student_daily_tasks_state(email)
    task = next((item for item in state.get("tasks", []) if str(item.get("id", "")).strip().lower() == task_id), None)
    if not task:
        return jsonify({"ok": False, "error": "Task not found for today\'s data."}), 404

    if bool(task.get("claimed")):
        refreshed = build_student_daily_tasks_state(email)
        return jsonify(
            {
                "ok": True,
                "message": "Reward already claimed for this task.",
                "awarded_points": 0,
                **refreshed,
            }
        )

    if not bool(task.get("completed")):
        return jsonify({"ok": False, "error": "Task is not completed yet."}), 409

    remaining_points = max(0, int(state.get("remaining_points", 0) or 0))
    if remaining_points <= 0:
        refreshed = build_student_daily_tasks_state(email)
        return jsonify(
            {
                "ok": False,
                "error": "You reached today\'s 20-point cap.",
                **refreshed,
            }
        ), 409

    awarded_points = min(int(task.get("points", 0) or 0), remaining_points)
    if awarded_points <= 0:
        refreshed = build_student_daily_tasks_state(email)
        return jsonify(
            {
                "ok": False,
                "error": "No reward points available for this task right now.",
                **refreshed,
            }
        ), 409

    claim_result = save_student_task_claim(
        email,
        state.get("claim_date", utc_date_key()),
        task_id,
        awarded_points,
    )
    if claim_result == "error":
        return jsonify({"ok": False, "error": "Unable to claim reward right now."}), 500

    if claim_result == "exists":
        refreshed = build_student_daily_tasks_state(email)
        return jsonify(
            {
                "ok": True,
                "message": "Reward already claimed for this task.",
                "awarded_points": 0,
                **refreshed,
            }
        )

    apply_student_task_reward_score(email, awarded_points)
    refreshed = build_student_daily_tasks_state(email)

    return jsonify(
        {
            "ok": True,
            "message": f"+{awarded_points} points claimed.",
            "awarded_points": awarded_points,
            **refreshed,
        }
    )


@app.get("/api/student/google-fit/connect")
@login_required
@role_required("student")
@extension_required_for_student
def student_google_fit_connect():
    if not GOOGLE_FIT_CLIENT_ID or not GOOGLE_FIT_CLIENT_SECRET:
        flash("Google Fit credentials are missing in .env.", "error")
        return redirect(url_for("student_dashboard"))

    oauth_state = secrets.token_urlsafe(24)
    session["google_fit_oauth_state"] = oauth_state
    auth_url = build_google_fit_auth_url(oauth_state)
    if not auth_url:
        flash("Unable to create Google Fit consent URL.", "error")
        return redirect(url_for("student_dashboard"))

    return redirect(auth_url)


@app.get("/api/student/google-fit/callback")
@login_required
@role_required("student")
@extension_required_for_student
def student_google_fit_callback():
    callback_error = str(request.args.get("error", "")).strip()
    if callback_error:
        flash(f"Google Fit authorization failed: {callback_error}", "error")
        return redirect(url_for("student_dashboard"))

    expected_state = str(session.pop("google_fit_oauth_state", "")).strip()
    returned_state = str(request.args.get("state", "")).strip()
    if not expected_state or expected_state != returned_state:
        flash("Google Fit callback state mismatch. Retry connection.", "error")
        return redirect(url_for("student_dashboard"))

    auth_code = str(request.args.get("code", "")).strip()
    if not auth_code:
        flash("Google Fit did not return an authorization code.", "error")
        return redirect(url_for("student_dashboard"))

    token_state, token_error = exchange_google_fit_code_for_tokens(auth_code)
    if token_error:
        flash(token_error, "error")
        return redirect(url_for("student_dashboard"))

    email = str(session.get("email", "")).strip().lower()
    identity_updates, identity_error = fetch_google_oauth_identity(token_state.get("access_token", ""))
    token_updates = {
        "google_fit_access_token": token_state.get("access_token", ""),
        "google_fit_expires_at": token_state.get("expires_at", ""),
        **identity_updates,
    }
    refresh_token = str(token_state.get("refresh_token", "")).strip()
    if refresh_token:
        token_updates["google_fit_refresh_token"] = refresh_token

    upsert_student_behavior_context(email, token_updates)
    persisted = load_google_fit_db_state(email) or {}
    behavior = get_student_behavior_context(email)
    save_google_fit_db_state(
        email,
        {
            **persisted,
            "access_token": token_updates.get("google_fit_access_token", persisted.get("access_token", "")),
            "refresh_token": token_updates.get(
                "google_fit_refresh_token",
                behavior.get("google_fit_refresh_token", persisted.get("refresh_token", "")),
            ),
            "expires_at": token_updates.get("google_fit_expires_at", persisted.get("expires_at", "")),
            "google_account_email": token_updates.get(
                "google_fit_account_email",
                behavior.get("google_fit_account_email", persisted.get("google_account_email", "")),
            ),
            "google_account_sub": token_updates.get(
                "google_fit_account_sub",
                behavior.get("google_fit_account_sub", persisted.get("google_account_sub", "")),
            ),
            "sync_status": "CONNECTED",
            "sync_error": "",
        },
    )

    fit_payload, fit_error, requires_reauth = sync_google_fit_for_student(email)
    runtime_state = recompute_student_multimodal_state(email, source="google-fit-connect", last_checked_url="google-fit")
    connected_account_email = str(token_updates.get("google_fit_account_email", "")).strip().lower()
    account_mismatch = bool(connected_account_email and connected_account_email != email)

    if fit_error and requires_reauth:
        flash("Google Fit token sync failed. Please login/connect again.", "error")
    elif fit_error:
        flash(f"Google Fit connected, but sync failed: {fit_error}", "error")
    elif (fit_payload or {}).get("steps_source") == "api-no-points":
        flash(
            "Google Fit connected, but Google API returned no step data for this account yet. "
            "Reconnect and select the exact Google account that shows steps in your fitness app.",
            "error",
        )
    else:
        flash("Google Fit connected successfully and wellbeing score updated.", "success")

    if account_mismatch:
        flash(
            f"Connected Google account is {connected_account_email}, but student login is {email}. "
            "Reconnect and choose the correct Google account for accurate steps.",
            "error",
        )
    elif connected_account_email:
        flash(f"Connected Google account: {connected_account_email}", "success")
    elif identity_error:
        flash(f"Google Fit connected, but account identity check failed: {identity_error}", "error")

    emit_terminal_debug_log(
        "google-fit-connected",
        email=email,
        steps=(fit_payload or {}).get("steps", 0),
        sleep_hours=(fit_payload or {}).get("sleep_hours", 0.0),
        fitness_component=(fit_payload or {}).get("fitness_component", 3.0),
        stress_score=(runtime_state or {}).get("stress_score", 3.0),
    )
    return redirect(url_for("student_dashboard"))


@app.post("/api/student/google-fit/sync")
@login_required
@role_required("student")
@extension_required_for_student
def student_google_fit_sync():
    email = str(session.get("email", "")).strip().lower()
    fit_payload, fit_error, requires_reauth = sync_google_fit_for_student(email)
    if fit_error:
        status_code = 401 if requires_reauth else 503
        return jsonify(
            {
                "error": fit_error,
                "requires_reauth": bool(requires_reauth),
                "connect_url": url_for("student_google_fit_connect"),
                "google_fit": get_google_fit_overview(email),
            }
        ), status_code

    runtime_state = recompute_student_multimodal_state(email, source="google-fit-sync", last_checked_url="google-fit") or {}
    return jsonify(
        {
            "ok": True,
            "google_fit": fit_payload,
            "requires_reauth": False,
            "stress_score": runtime_state.get("stress_score", 3.0),
            "stress_category": runtime_state.get("stress_category", "MODERATE"),
            "mental_battery": runtime_state.get("mental_battery", 40),
            "components": runtime_state.get("components", {}),
        }
    )


@app.post("/api/counsellor/student-signal")
@login_required
@role_required("counsellor")
def counsellor_update_student_signal():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    if not email:
        email = str(CREDENTIALS.get("student", {}).get("email", "")).strip().lower()

    known_student_emails = {
        str(account.get("email", "")).strip().lower()
        for account in list_user_accounts(role="student", status="approved", limit=800)
        if str(account.get("email", "")).strip()
    }
    known_student_emails.update(
        {
            str(row.get("email", "")).strip().lower()
            for row in build_student_monitor_rows(limit=800)
            if str(row.get("email", "")).strip()
        }
    )
    credential_student = str(CREDENTIALS.get("student", {}).get("email", "")).strip().lower()
    if credential_student:
        known_student_emails.add(credential_student)

    if email not in known_student_emails:
        return jsonify({"error": "Unknown student email."}), 404

    try:
        counsellor_score = float(payload.get("counsellor_score", COUNSELLOR_DEFAULT_SCORE))
    except (TypeError, ValueError):
        counsellor_score = COUNSELLOR_DEFAULT_SCORE

    counsellor_component = normalize_component_score(counsellor_score, COUNSELLOR_DEFAULT_SCORE)
    upsert_student_behavior_context(
        email,
        {
            "component_counsellor": counsellor_component,
            "counsellor_note": str(payload.get("note", "")).strip()[:300],
            "counsellor_updated_at": utc_now().isoformat(timespec="seconds"),
        },
    )

    runtime_state = recompute_student_multimodal_state(email, source="counsellor", last_checked_url="counsellor") or {}
    return jsonify(
        {
            "ok": True,
            "email": email,
            "counsellor_component": counsellor_component,
            "stress_score": runtime_state.get("stress_score", 3.0),
            "stress_category": runtime_state.get("stress_category", "MODERATE"),
            "mental_battery": runtime_state.get("mental_battery", 40),
            "components": runtime_state.get("components", {}),
        }
    )


@app.route("/login", defaults={"role": ""}, methods=["GET", "POST"])
@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    forced_role = normalize_account_role(role)
    if str(role or "").strip().lower() == "admin":
        return redirect(url_for("login", role="developer"))

    session_role = str(session.get("role", "")).strip().lower()
    if session_role == "admin":
        session["role"] = "developer"
        session_role = "developer"

    # If user intentionally opens another role portal, reset old session first.
    if forced_role and session_role and session_role != forced_role:
        session.clear()
        session_role = ""

    if request.method == "POST":
        requested_role = normalize_account_role(request.form.get("role", ""))
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_role = forced_role or requested_role

        if not selected_role:
            flash("Select a valid dashboard role.", "error")
            return render_login_page(initial_role=forced_role or "student", lock_role=bool(forced_role))

        if forced_role and requested_role and requested_role != forced_role:
            flash("This portal is locked to one role. Use the selected login.", "error")
            return render_login_page(initial_role=forced_role, lock_role=True)

        account, auth_error = authenticate_portal_user(selected_role, email, password)
        if auth_error or not account:
            flash(auth_error or "Invalid credentials for selected role.", "error")
            return render_login_page(initial_role=selected_role, lock_role=bool(forced_role))

        if selected_role == "student":
            posted_extension_nonce = request.form.get("extension_portal_nonce", "")
            posted_extension_proof = request.form.get("extension_portal_proof", "")
            proof_valid, proof_error = validate_student_extension_login_proof(
                account["email"],
                posted_extension_nonce,
                posted_extension_proof,
                request_obj=request,
            )
            if not proof_valid:
                flash(proof_error, "error")
                return redirect(url_for("install_extension"))

            valid, message, show_popup = evaluate_student_extension_access(
                account["email"],
                request_obj=request,
            )
            if not valid:
                flash(message, "security_popup" if show_popup else "error")
                return redirect(url_for("install_extension"))

        session["role"] = selected_role
        session["name"] = account.get("name") or selected_role.title()
        session["email"] = account.get("email") or email
        if selected_role == "student":
            session.pop("student_extension_login_nonce", None)
            session.pop("student_extension_login_nonce_issued_at", None)
            session["student_mood"] = None
            session.pop("student_mood_pending", None)
            session["student_extension_verified_at"] = utc_now().isoformat(timespec="seconds")
            session.pop("student_live_battery", None)
            session.pop("student_live_stress_score", None)
            session.pop("student_live_category", None)
            session.pop("student_last_extension_signal_at", None)
            session.pop("student_live_emotion", None)
            session.pop("student_crisis_streak", None)
            session.pop("student_face_emotion", None)
            session.pop("student_face_used", None)
            session.pop("student_pulse_score", None)
            session.pop("student_google_fit_synced_once", None)
            session.pop("student_google_fit_synced_at", None)

            setup_ready, _, pending_requirements = evaluate_student_profile_setup_access(session["email"])
            if not setup_ready:
                flash(build_student_profile_setup_message(pending_requirements), "error")
                return redirect(url_for("student_profile"))

            return redirect(url_for("student_mood"))
        return redirect(url_for("dashboard", role=selected_role))

    if session.get("role") == "student":
        session_email = str(session.get("email", "")).strip().lower()
        setup_ready, _, _ = evaluate_student_profile_setup_access(session_email)
        if not setup_ready:
            return redirect(url_for("student_profile"))
        pending_mood = str(session.get("student_mood_pending", "")).strip()
        if pending_mood in STUDENT_MOODS:
            return redirect(url_for("student_face_check"))
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))
    if session.get("role") in {"warden", "counsellor", "developer", "parent", "proctor"}:
        return redirect(url_for("dashboard", role=session["role"]))

    initial_role = forced_role or normalize_account_role(request.args.get("role", "")) or "student"
    return render_login_page(initial_role=initial_role, lock_role=bool(forced_role))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if session.get("role") == "student":
        email = str(session.get("email", "")).strip().lower()
        stress_score = session.get("student_live_stress_score")
        stress_category = str(session.get("student_live_category", "")).strip().upper()
        if email and isinstance(stress_score, (int, float)):
            save_student_score_state(
                email,
                float(stress_score),
                stress_category or classify_live_stress(float(stress_score)),
                source="logout-snapshot",
                last_checked_url="logout",
            )
    session.clear()
    return redirect(url_for("login"))


@app.route("/student/mood", methods=["GET", "POST"])
@login_required
@role_required("student")
@extension_required_for_student
def student_mood():
    email = str(session.get("email", "")).strip().lower()
    face_state = ensure_student_face_check_state(email) if email else None
    face_check_required = is_student_face_check_required(face_state)

    if request.method == "POST":
        mood_key = request.form.get("mood", "").strip()
        if mood_key not in STUDENT_MOODS:
            flash("Select your current mood to continue.", "error")
            return render_template(
                "student_mood_gate.html",
                mood_options=STUDENT_MOODS,
                selected_mood=session.get("student_mood_pending") or session.get("student_mood"),
                face_check_required=face_check_required,
                face_check_grace_days=FACE_CHECK_GRACE_DAYS,
                face_check_due_at=(face_state or {}).get("next_due_at", ""),
                last_face_check_at=(face_state or {}).get("last_face_check_at", ""),
                last_face_emotion=(face_state or {}).get("last_face_emotion", ""),
                face_emotion_labels=FACE_EMOTION_LABELS,
            )

        session["student_mood_pending"] = mood_key
        return redirect(url_for("student_face_check"))

    return render_template(
        "student_mood_gate.html",
        mood_options=STUDENT_MOODS,
        selected_mood=session.get("student_mood_pending") or session.get("student_mood"),
        face_check_required=face_check_required,
        face_check_grace_days=FACE_CHECK_GRACE_DAYS,
        face_check_due_at=(face_state or {}).get("next_due_at", ""),
        last_face_check_at=(face_state or {}).get("last_face_check_at", ""),
        last_face_emotion=(face_state or {}).get("last_face_emotion", ""),
        face_emotion_labels=FACE_EMOTION_LABELS,
    )


def finalize_student_mood_submission(email, mood_key, face_emotion):
    normalized_face_emotion = normalize_face_emotion_key(face_emotion)
    face_score = FACE_EMOTION_SCORES.get(normalized_face_emotion)
    face_used = face_score is not None

    mood_score_value = float(STUDENT_MOODS[mood_key]["score"])
    pulse_value = pulse_score(mood_score_value, face_score if face_used else None, normalized_face_emotion)
    mood_component = mood_to_stress_score(pulse_value)

    session["student_mood"] = mood_key
    session.pop("student_mood_pending", None)
    session.pop("student_live_battery", None)
    session.pop("student_live_stress_score", None)
    session.pop("student_live_category", None)
    session.pop("student_last_extension_signal_at", None)
    session.pop("student_live_emotion", None)
    session.pop("student_crisis_streak", None)
    session["student_face_emotion"] = normalized_face_emotion if face_used else ""
    session["student_face_used"] = bool(face_used)
    session["student_pulse_score"] = pulse_value

    if not email:
        return

    existing_behavior = get_student_behavior_context(email)
    upsert_student_behavior_context(
        email,
        {
            "mood_score": mood_score_value,
            "pulse_score": pulse_value,
            "pulse_face_used": bool(face_used),
            "pulse_face_emotion": normalized_face_emotion if face_used else "",
            "pulse_face_score": face_score if face_used else None,
            "component_mood": mood_component,
            "component_counsellor": normalize_component_score(
                existing_behavior.get("component_counsellor", COUNSELLOR_DEFAULT_SCORE),
                COUNSELLOR_DEFAULT_SCORE,
            ),
        },
    )

    if face_used:
        now_dt = utc_now()
        save_student_face_check_state(
            email,
            next_due_at=(now_dt + timedelta(days=FACE_CHECK_GRACE_DAYS)).isoformat(timespec="seconds"),
            last_face_check_at=now_dt.isoformat(timespec="seconds"),
            last_face_emotion=normalized_face_emotion,
            last_face_score=face_score,
        )

    recompute_student_multimodal_state(
        email,
        source="mood+face" if face_used else "mood-only",
        last_checked_url="mood",
    )


@app.route("/student/face-check", methods=["GET", "POST"])
@login_required
@role_required("student")
@extension_required_for_student
def student_face_check():
    email = str(session.get("email", "")).strip().lower()
    mood_key = str(session.get("student_mood_pending", "")).strip()
    if mood_key not in STUDENT_MOODS:
        flash("Complete your pulse check first.", "error")
        return redirect(url_for("student_mood"))

    face_state = ensure_student_face_check_state(email) if email else None
    face_check_required = is_student_face_check_required(face_state)
    grace_meta = build_face_check_grace_meta(face_state)

    if request.method == "POST":
        action = str(request.form.get("action", "capture")).strip().lower()
        face_emotion = normalize_face_emotion_key(request.form.get("face_emotion", ""))
        if action == "skip" and not face_check_required:
            face_emotion = ""

        face_score = FACE_EMOTION_SCORES.get(face_emotion)
        face_used = face_score is not None

        if face_check_required and not face_used:
            flash(
                f"Facial check is required once every {FACE_CHECK_GRACE_DAYS} days. Please complete the 3-second capture.",
                "error",
            )
            return render_template(
                "student_face_check.html",
                mood_key=mood_key,
                mood=STUDENT_MOODS.get(mood_key, STUDENT_MOODS["not-bad"]),
                face_check_required=face_check_required,
                face_check_grace_days=FACE_CHECK_GRACE_DAYS,
                face_check_due_at=(face_state or {}).get("next_due_at", ""),
                face_check_grace_remaining_days=grace_meta.get("remaining_days", 0),
                face_check_grace_remaining_hours=grace_meta.get("remaining_hours", 0),
                face_check_overdue_hours=grace_meta.get("overdue_hours", 0),
                last_face_check_at=(face_state or {}).get("last_face_check_at", ""),
                last_face_emotion=(face_state or {}).get("last_face_emotion", ""),
                face_emotion_labels=FACE_EMOTION_LABELS,
            )

        finalize_student_mood_submission(email, mood_key, face_emotion)
        return redirect(url_for("student_dashboard"))

    return render_template(
        "student_face_check.html",
        mood_key=mood_key,
        mood=STUDENT_MOODS.get(mood_key, STUDENT_MOODS["not-bad"]),
        face_check_required=face_check_required,
        face_check_grace_days=FACE_CHECK_GRACE_DAYS,
        face_check_due_at=(face_state or {}).get("next_due_at", ""),
        face_check_grace_remaining_days=grace_meta.get("remaining_days", 0),
        face_check_grace_remaining_hours=grace_meta.get("remaining_hours", 0),
        face_check_overdue_hours=grace_meta.get("overdue_hours", 0),
        last_face_check_at=(face_state or {}).get("last_face_check_at", ""),
        last_face_emotion=(face_state or {}).get("last_face_emotion", ""),
        face_emotion_labels=FACE_EMOTION_LABELS,
    )


@app.get("/student/dashboard")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_dashboard():
    email = str(session.get("email", "")).strip().lower()
    if email:
        seed_session_from_saved_student_state(email)
        google_fit = get_google_fit_overview(email)

        should_auto_sync_google_fit = (
            bool(google_fit.get("connected"))
            and not bool(google_fit.get("requires_reauth"))
            and not bool(session.get("student_google_fit_synced_once"))
        )

        if should_auto_sync_google_fit:
            fit_payload, fit_error, fit_requires_reauth = sync_google_fit_for_student(email)
            session["student_google_fit_synced_once"] = True
            session["student_google_fit_synced_at"] = utc_now().isoformat(timespec="seconds")
            if fit_payload:
                google_fit = fit_payload
            elif fit_requires_reauth:
                google_fit = get_google_fit_overview(email)
            elif fit_error:
                google_fit = get_google_fit_overview(email)

        runtime_state = recompute_student_multimodal_state(email, source="dashboard-open", last_checked_url="dashboard")
        components = (runtime_state or {}).get("components", get_student_multimodal_components(email))
        if not should_auto_sync_google_fit:
            google_fit = get_google_fit_overview(email)
    else:
        components = {
            "mood": 3.0,
            "chatbot": 3.0,
            "extension": 3.0,
            "fitness": 3.0,
            "counsellor": COUNSELLOR_DEFAULT_SCORE,
        }
        google_fit = {
            "connected": False,
            "steps": 0,
            "sleep_hours": 0.0,
            "fitness_component": 3.0,
            "last_sync_at": "",
        }

    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    live_stress_score = session.get("student_live_stress_score")
    if isinstance(live_stress_score, (int, float)):
        stress_band = classify_live_stress(float(live_stress_score))
    else:
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    student_quiz_cards = build_student_quiz_cards(email, quiz_focus)
    student_quiz_history = list_student_quiz_attempts(email, limit=5) if email else []
    sidebar_quiz_key = (
        str(student_quiz_cards[0].get("key", "")).strip().lower()
        if student_quiz_cards
        else "daily_stress_check"
    ) or "daily_stress_check"

    live_battery = session.get("student_live_battery")
    if isinstance(live_battery, (int, float)):
        mood_battery = max(0, min(int(round(live_battery)), 100))
    else:
        mood_battery = mood["battery"]

    weekly_logs = build_student_weekly_logs(email, mood_battery)
    dashboard_saved_state = load_student_score_state(email) if email else None
    dashboard_last_checked_url = str((dashboard_saved_state or {}).get("last_checked_url", "")).strip()[:500]

    return render_template(
        "student_dashboard.html",
        page_title="Student Dashboard",
        page_subtitle="Your private wellbeing pulse and support tools.",
        active_nav="dashboard",
        mood_label=mood["label"],
        mood_score=mood["score"],
        mood_battery=mood_battery,
        mood_tone=battery_to_tone(mood_battery),
        live_stress_score=live_stress_score,
        live_stress_category=session.get("student_live_category"),
        multimodal_components=components,
        google_fit=google_fit,
        student_quiz_cards=student_quiz_cards,
        student_quiz_focus=quiz_focus,
        student_quiz_history=student_quiz_history,
        sidebar_quiz_key=sidebar_quiz_key,
        weekly_logs=weekly_logs,
        dashboard_last_checked_url=dashboard_last_checked_url,
    )


@app.get("/student/tasks")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_tasks_page():
    email = str(session.get("email", "")).strip().lower()

    if email:
        seed_session_from_saved_student_state(email)
        runtime_state = recompute_student_multimodal_state(email, source="tasks-open", last_checked_url="tasks") or {}
        google_fit = get_google_fit_overview(email)
        components = runtime_state.get("components", get_student_multimodal_components(email))
        saved_state = load_student_score_state(email) or {}
        task_last_checked_url = str(saved_state.get("last_checked_url", "")).strip()[:500]
    else:
        components = {
            "mood": 3.0,
            "chatbot": 3.0,
            "extension": 3.0,
            "fitness": 3.0,
            "counsellor": COUNSELLOR_DEFAULT_SCORE,
        }
        google_fit = {
            "connected": False,
            "steps": 0,
            "sleep_hours": 0.0,
            "fitness_component": 3.0,
            "last_sync_at": "",
            "steps_source": "",
            "connected_account_email": "",
            "sync_status": "",
            "sync_error": "",
            "requires_reauth": False,
        }
        task_last_checked_url = ""

    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    live_stress_score = session.get("student_live_stress_score")
    live_battery = session.get("student_live_battery")
    if isinstance(live_battery, (int, float)):
        mood_battery = max(0, min(int(round(live_battery)), 100))
    else:
        mood_battery = mood["battery"]

    if isinstance(live_stress_score, (int, float)):
        stress_band = classify_live_stress(float(live_stress_score))
    else:
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    student_quiz_cards = build_student_quiz_cards(email, quiz_focus)
    sidebar_quiz_key = (
        str(student_quiz_cards[0].get("key", "")).strip().lower()
        if student_quiz_cards
        else "daily_stress_check"
    ) or "daily_stress_check"

    return render_template(
        "student_tasks.html",
        page_title="Daily Tasks",
        page_subtitle="Data-backed tasks from your wellbeing signals.",
        active_nav="tasks",
        sidebar_quiz_key=sidebar_quiz_key,
        mood_label=mood["label"],
        mood_score=mood["score"],
        mood_battery=mood_battery,
        live_stress_score=live_stress_score,
        live_stress_category=session.get("student_live_category"),
        multimodal_components=components,
        google_fit=google_fit,
        task_last_checked_url=task_last_checked_url,
        task_daily_cap=STUDENT_TASK_DAILY_POINTS_CAP,
    )


@app.get("/student/counselling")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_counselling_page():
    email = str(session.get("email", "")).strip().lower()
    current_stress = session.get("student_live_stress_score")

    if isinstance(current_stress, (int, float)):
        stress_band = classify_live_stress(float(current_stress))
    else:
        mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    student_quiz_cards = build_student_quiz_cards(email, quiz_focus)
    sidebar_quiz_key = (
        str(student_quiz_cards[0].get("key", "")).strip().lower()
        if student_quiz_cards
        else "daily_stress_check"
    ) or "daily_stress_check"

    student_name = "Student"
    if email:
        student_name = email.split("@")[0].replace(".", " ").replace("_", " ").strip().title() or "Student"

    return render_template(
        "student_counselling.html",
        page_title="Student Counselling",
        page_subtitle="Book a session with your preferred counsellor.",
        active_nav="counselling",
        sidebar_quiz_key=sidebar_quiz_key,
        student_name=student_name,
    )


@app.get("/student/quiz")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_quiz_selector_page():
    email = str(session.get("email", "")).strip().lower()
    current_stress = session.get("student_live_stress_score")

    if isinstance(current_stress, (int, float)):
        stress_band = classify_live_stress(float(current_stress))
    else:
        mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    quiz_cards = build_student_quiz_cards(email, quiz_focus)
    suggested_quiz_key, recommendation_reason = suggest_quiz_for_student(quiz_cards, stress_band)

    requested_key = str(request.args.get("quiz", "")).strip().lower()
    valid_keys = {str(card.get("key", "")).strip().lower() for card in quiz_cards}
    selected_quiz_key = requested_key if requested_key in valid_keys else suggested_quiz_key

    selected_quiz = None
    for card in quiz_cards:
        key = str(card.get("key", "")).strip().lower()
        if key == selected_quiz_key:
            selected_quiz = card
            break

    return render_template(
        "student_quiz_selector.html",
        page_title="Quiz Selection",
        quiz_cards=quiz_cards,
        selected_quiz=selected_quiz,
        selected_quiz_key=selected_quiz_key,
        suggested_quiz_key=suggested_quiz_key,
        recommendation_reason=recommendation_reason,
        student_quiz_focus=quiz_focus,
        stress_band=stress_band,
    )


@app.route("/student/quiz/<quiz_key>", methods=["GET", "POST"])
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_quiz_attempt_page(quiz_key):
    email = str(session.get("email", "")).strip().lower()
    current_stress = session.get("student_live_stress_score")
    if isinstance(current_stress, (int, float)):
        stress_band = classify_live_stress(float(current_stress))
    else:
        mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    quiz = get_student_quiz_payload(quiz_key, focus_hint=quiz_focus)
    if not quiz:
        flash("Quiz not found.", "error")
        return redirect(url_for("student_quiz_selector_page"))

    quiz_key_normalized = str(quiz_key or "").strip().lower()
    latest_attempt = latest_student_quiz_attempt_map(email).get(quiz_key_normalized)
    selected_answers = {}
    quiz_result = None

    if request.method == "POST":
        for question in quiz.get("questions", []):
            question_id = str(question.get("id", "")).strip()
            if not question_id:
                continue
            selected_answers[question_id] = str(request.form.get(f"answer_{question_id}", "")).strip()

        quiz_result, quiz_error = evaluate_student_quiz_answers(quiz_key, selected_answers)
        if quiz_error:
            flash(quiz_error, "error")
        else:
            saved_attempt = save_student_quiz_attempt(email, quiz_key, quiz, quiz_result)

            quiz_component = float(quiz_result.get("average_stress", 3.0))

            upsert_student_behavior_context(
                email,
                {
                    "component_quiz": normalize_component_score(quiz_component, 3.0),
                    "last_quiz_key": str(quiz_key or "")[:64],
                    "last_quiz_average_stress": round(quiz_component, 2),
                    "last_quiz_score_percent": int(quiz_result.get("score_percent", 0) or 0),
                    "last_quiz_risk_band": str(quiz_result.get("risk_band", "MODERATE")).upper(),
                    "last_quiz_at": utc_now().isoformat(timespec="seconds"),
                },
            )

            recompute_student_multimodal_state(
                email,
                source="quiz",
                last_checked_url=f"quiz:{str(quiz_key or '')[:40]}",
            )

            selected_answers = dict(quiz_result.get("answers", {}))
            latest_attempt = saved_attempt or latest_student_quiz_attempt_map(email).get(quiz_key_normalized)
            score_value = int(quiz_result.get("score_percent", 0) or 0)
            risk_value = str(quiz_result.get("risk_band", "MODERATE")).upper()
            mood_value = str(quiz_result.get("mood_analysis", "")).strip()
            risk_analysis_value = str(quiz_result.get("risk_analysis", "")).strip()
            flash(
                f"Quiz score: {score_value}% | Risk: {risk_value}. {mood_value} {risk_analysis_value}".strip(),
                "success",
            )

    return render_template(
        "student_quiz_attempt.html",
        page_title="Quiz Attempt",
        quiz=quiz,
        latest_attempt=latest_attempt,
        quiz_result=quiz_result,
        selected_answers=selected_answers,
        quiz_history=list_student_quiz_attempts(email, limit=8),
        sidebar_quiz_key=str(quiz.get("key", "")).strip().lower() or "daily_stress_check",
    )


@app.get("/api/student/quiz/<quiz_key>")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_quiz_detail(quiz_key):
    email = str(session.get("email", "")).strip().lower()
    current_stress = session.get("student_live_stress_score")
    if isinstance(current_stress, (int, float)):
        stress_band = classify_live_stress(float(current_stress))
    else:
        mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz = get_student_quiz_payload(quiz_key, focus_hint=quiz_focus_from_stress_band(stress_band))
    if not quiz:
        return jsonify({"error": "Quiz not found."}), 404

    latest_attempt = latest_student_quiz_attempt_map(email).get(str(quiz_key or "").strip().lower())
    return jsonify({
        "ok": True,
        "quiz": quiz,
        "latest_attempt": latest_attempt,
    })


@app.post("/api/student/quiz/<quiz_key>/submit")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_quiz_submit(quiz_key):
    email = str(session.get("email", "")).strip().lower()
    payload = request.get_json(silent=True) or {}
    answers = payload.get("answers", {})

    quiz_result, quiz_error = evaluate_student_quiz_answers(quiz_key, answers)
    if quiz_error:
        return jsonify({"error": quiz_error}), 400

    stress_band = str(quiz_result.get("risk_band", "MODERATE")).upper()
    quiz_payload = get_student_quiz_payload(quiz_key, focus_hint=quiz_focus_from_stress_band(stress_band))
    if not quiz_payload:
        return jsonify({"error": "Quiz not found."}), 404

    saved_attempt = save_student_quiz_attempt(email, quiz_key, quiz_payload, quiz_result)

    quiz_component = float(quiz_result.get("average_stress", 3.0))

    upsert_student_behavior_context(
        email,
        {
            "component_quiz": normalize_component_score(quiz_component, 3.0),
            "last_quiz_key": str(quiz_key or "")[:64],
            "last_quiz_average_stress": round(quiz_component, 2),
            "last_quiz_score_percent": int(quiz_result.get("score_percent", 0) or 0),
            "last_quiz_risk_band": stress_band,
            "last_quiz_at": utc_now().isoformat(timespec="seconds"),
        },
    )

    runtime_state = recompute_student_multimodal_state(
        email,
        source="quiz",
        last_checked_url=f"quiz:{str(quiz_key or '')[:40]}",
    ) or {}

    return jsonify(
        {
            "ok": True,
            "quiz": {
                "key": quiz_payload.get("key", ""),
                "title": quiz_payload.get("title", "Mind Check"),
                "focus": quiz_payload.get("focus", "Balance"),
            },
            "result": quiz_result,
            "attempt": saved_attempt,
            "history": list_student_quiz_attempts(email, limit=5),
            "stress_score": runtime_state.get("stress_score", 3.0),
            "stress_category": runtime_state.get("stress_category", "MODERATE"),
            "mental_battery": runtime_state.get("mental_battery", 40),
            "components": runtime_state.get("components", {}),
            "google_fit": get_google_fit_overview(email),
        }
    )


@app.get("/student/profile")
@login_required
@role_required("student")
@extension_required_for_student
def student_profile():
    email = str(session.get("email", "")).strip().lower()
    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])

    current_stress = session.get("student_live_stress_score")
    if isinstance(current_stress, (int, float)):
        stress_band = classify_live_stress(float(current_stress))
    else:
        stress_band = classify_live_stress(mood_to_stress_score(mood["score"]))

    quiz_focus = quiz_focus_from_stress_band(stress_band)
    student_quiz_cards = build_student_quiz_cards(email, quiz_focus)
    sidebar_quiz_key = (
        str(student_quiz_cards[0].get("key", "")).strip().lower()
        if student_quiz_cards
        else "daily_stress_check"
    ) or "daily_stress_check"

    live_battery = session.get("student_live_battery")
    if isinstance(live_battery, (int, float)):
        mood_battery = max(0, min(int(round(live_battery)), 100))
    else:
        mood_battery = mood["battery"]

    weekly_logs = build_student_weekly_logs(email, mood_battery)
    student_badges = build_student_profile_badges(email, stress_band, mood_battery, weekly_logs)
    google_fit = get_google_fit_overview(email) if email else {
        "connected": False,
        "connected_account_email": "",
        "last_sync_at": "",
        "requires_reauth": False,
        "sync_error": "",
    }
    student_setup_ready, student_setup_details, _ = evaluate_student_profile_setup_access(email)
    parent_contact = load_parent_alert_contact(email) or {
        "parent_name": "",
        "parent_phone": "",
        "parent_phone_masked": "",
        "verified": False,
        "alerts_enabled": True,
        "consent_enabled": False,
        "admin_edit_count": 0,
        "verified_at": "",
    }

    return render_template(
        "student_profile.html",
        page_title="Student Profile",
        page_subtitle="Personal wellbeing profile and support preferences.",
        active_nav="profile",
        mood_label=mood["label"],
        mood_score=mood["score"],
        mood_battery=mood_battery,
        sidebar_quiz_key=sidebar_quiz_key,
        weekly_logs=weekly_logs,
        student_badges=student_badges,
        google_fit=google_fit,
        student_setup_ready=student_setup_ready,
        student_setup_details=student_setup_details,
        parent_contact=parent_contact,
        parent_otp_ttl_minutes=PARENT_OTP_TTL_MINUTES,
    )


@app.post("/student/parent-contact/request-otp")
@login_required
@role_required("student")
@extension_required_for_student
def student_parent_contact_request_otp():
    student_email = str(session.get("email", "")).strip().lower()
    parent_name = str(request.form.get("parent_name", "")).strip()
    parent_phone = normalize_phone_number(request.form.get("parent_phone", ""))
    consent_enabled = str(request.form.get("consent_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}
    alerts_enabled = str(request.form.get("alerts_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}

    if not parent_name:
        flash("Parent name is required.", "error")
        return redirect(url_for("student_profile"))

    if not parent_phone:
        flash("Enter a valid parent phone number in international format.", "error")
        return redirect(url_for("student_profile"))

    if not consent_enabled:
        flash("Consent is required to enable parent alerts.", "error")
        return redirect(url_for("student_profile"))

    existing = load_parent_alert_contact(student_email)
    if existing and existing.get("verified"):
        flash("Parent number is already verified. Ask admin for the one-time edit if changes are required.", "error")
        return redirect(url_for("student_profile"))

    otp_code = generate_parent_otp_code()
    otp_saved = save_parent_contact_otp(
        student_email,
        parent_name,
        parent_phone,
        consent_enabled=consent_enabled,
        alerts_enabled=alerts_enabled,
        otp_code=otp_code,
    )
    if not otp_saved:
        flash("Unable to save parent contact right now.", "error")
        return redirect(url_for("student_profile"))

    sent, provider, provider_response = send_whatsapp(parent_phone, build_parent_otp_message(otp_code))
    if sent:
        flash("OTP sent to parent WhatsApp. Enter code to verify.", "success")
    else:
        flash(
            "OTP generated but WhatsApp delivery failed. "
            f"Provider response: {provider}: {provider_response}. OTP for demo: {otp_code}",
            "error",
        )
    return redirect(url_for("student_profile"))


@app.post("/student/parent-contact/verify")
@login_required
@role_required("student")
@extension_required_for_student
def student_parent_contact_verify_otp():
    student_email = str(session.get("email", "")).strip().lower()
    otp_code = str(request.form.get("otp_code", "")).strip()
    verified, message = verify_parent_contact_otp(student_email, otp_code)
    flash(message, "success" if verified else "error")
    return redirect(url_for("student_profile"))


@app.post("/developer/parent-contact/edit")
@login_required
@role_required("developer")
def developer_edit_parent_contact_once():
    student_email = str(request.form.get("student_email", "")).strip().lower()
    parent_name = str(request.form.get("parent_name", "")).strip()
    parent_phone = normalize_phone_number(request.form.get("parent_phone", ""))
    consent_enabled = str(request.form.get("consent_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}
    alerts_enabled = str(request.form.get("alerts_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}

    if not student_email or not is_approved_role_account(student_email, "student"):
        flash("Provide a valid approved student email.", "error")
        return redirect(url_for("developer_accounts_page"))

    if not parent_name or not parent_phone:
        flash("Parent name and phone are required for admin edit.", "error")
        return redirect(url_for("developer_accounts_page"))

    existing = load_parent_alert_contact(student_email)
    if not existing:
        flash("No parent contact exists for this student yet.", "error")
        return redirect(url_for("developer_accounts_page"))

    if int(existing.get("admin_edit_count", 0) or 0) >= 1:
        flash("Admin one-time edit already used for this student.", "error")
        return redirect(url_for("developer_accounts_page"))

    otp_code = generate_parent_otp_code()
    saved = save_parent_contact_otp(
        student_email,
        parent_name,
        parent_phone,
        consent_enabled=consent_enabled,
        alerts_enabled=alerts_enabled,
        otp_code=otp_code,
        admin_edit_count=1,
    )
    if not saved:
        flash("Unable to apply admin edit right now.", "error")
        return redirect(url_for("developer_accounts_page"))

    sent, provider, provider_response = send_whatsapp(parent_phone, build_parent_otp_message(otp_code))
    if sent:
        flash("Admin edit saved. New parent number requires OTP verification.", "success")
    else:
        flash(
            "Admin edit saved but OTP WhatsApp delivery failed. "
            f"Provider response: {provider}: {provider_response}. OTP for demo: {otp_code}",
            "error",
        )
    return redirect(url_for("developer_accounts_page"))


@app.post("/api/student/chat")
@login_required
@role_required("student")
@student_mood_required
@extension_required_for_student
def student_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()

    if len(message) < 2:
        return jsonify({"error": "Please enter a longer message."}), 400

    if len(message) > 1200:
        message = message[:1200]

    try:
        mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
        greeting_detected = is_short_greeting_message(message)
        crisis_detected = detect_crisis_message(message)
        if greeting_detected and not crisis_detected:
            # Fast path for short greetings avoids external model latency.
            emotion = "neutral"
            confidence = 0.35
            analysis_warning = "Fast greeting path used for low-latency response."
            stress_level = "LOW"
            base_chat_component = 2.0
        else:
            emotion, confidence, analysis_warning = analyze_student_emotion(message)
            stress_level = emotion_to_stress_level(emotion)
            base_chat_component = stress_level_to_score(stress_level)

        previous_streak = int(session.get("student_crisis_streak", 0))
        if crisis_detected:
            crisis_streak = previous_streak + 1
        else:
            crisis_streak = max(previous_streak - 1, 0)
        chat_component = float(base_chat_component)
        if crisis_detected:
            if crisis_streak == 1:
                chat_component = max(chat_component, 4.0)
            elif crisis_streak == 2:
                chat_component = max(chat_component, 4.5)
            else:
                chat_component = 5.0

        topic = topic_from_text(message)
        session["student_live_emotion"] = emotion
        session["student_crisis_streak"] = crisis_streak

        email = str(session.get("email", "")).strip().lower()
        runtime_state = None
        if email:
            upsert_student_behavior_context(
                email,
                {
                    "mood_score": mood["score"],
                    "component_mood": mood_to_stress_score(mood["score"]),
                    "component_chatbot": round(chat_component, 2),
                    "last_emotion": str(emotion or "").strip().lower(),
                    "last_emotion_confidence": round(float(confidence or 0.0), 4),
                    "last_chat_topic": str(topic or "")[:60],
                },
            )
            runtime_state = recompute_student_multimodal_state(
                email,
                source="chat",
                last_checked_url="chat",
            )

        if runtime_state:
            stress_score = float(runtime_state.get("stress_score", 3.0))
            stress_category = str(runtime_state.get("stress_category", "MODERATE"))
            mental_battery = int(runtime_state.get("mental_battery", calculate_mental_battery(stress_score)))
        else:
            stress_score = 3.0
            stress_category = "MODERATE"
            mental_battery = calculate_mental_battery(stress_score)

        if greeting_detected and not crisis_detected:
            reply = (
                "Hi, I am here with you. I can help with stress, study pressure, sleep, or loneliness. "
                "Tell me in one line what feels hardest right now, and I will suggest a step-by-step plan. "
                f"If you prefer a human counsellor now, contact: {support_contacts_text()}."
            )
            error = None
        else:
            reply, error = ask_groq_student_bot(message)
            if error:
                reply = (
                    "I am having trouble reaching the assistant right now. "
                    "Your wellbeing signals were still updated from your message. "
                    f"For immediate human support, contact: {support_contacts_text()}."
                )

        if crisis_detected:
            reply = (
                f"{build_safety_prefix(crisis_streak)} {reply} "
                f"Immediate support numbers: {support_contacts_text()}."
            ).strip()

        response_payload = {
            "reply": reply,
            "emotion": emotion,
            "confidence": confidence,
            "stress_level": stress_level,
            "stress_score": stress_score,
            "stress_category": stress_category,
            "mental_battery": mental_battery,
            "topic": topic,
            "crisis_detected": crisis_detected,
            "crisis_streak": crisis_streak,
            "greeting_detected": greeting_detected,
            "support_contacts": STUDENT_SUPPORT_CONTACTS if (greeting_detected or crisis_detected) else [],
            "components": (runtime_state or {}).get("components", {}),
            "google_fit": get_google_fit_overview(email) if email else {"connected": False},
        }
        if analysis_warning:
            response_payload["analysis_warning"] = analysis_warning
        if error:
            response_payload["chat_warning"] = error

        return jsonify(response_payload)
    except Exception as exc:
        return (
            jsonify(
                {
                    "error": "Chat service is temporarily unavailable. Please try again.",
                    "details": str(exc)[:300],
                }
            ),
            500,
        )


@app.post("/developer/accounts/create")
@login_required
@role_required("developer")
def developer_create_account():
    name = str(request.form.get("name", "")).strip()
    email = str(request.form.get("email", "")).strip().lower()
    password = str(request.form.get("password", ""))
    role = normalize_account_role(request.form.get("role", ""))
    status = normalize_account_status(request.form.get("status", "approved"))
    note = str(request.form.get("requested_note", "")).strip()

    if not name or not email or not password or not role:
        flash("Name, email, password, and role are required to create an account.", "error")
        return redirect(url_for("developer_accounts_page"))

    saved, save_error = upsert_user_account(
        name=name,
        email=email,
        password=password,
        role=role,
        status=status,
        requested_note=note or "Created by developer",
        approved_by=session.get("email", "developer@wellnest"),
    )
    if not saved:
        flash(save_error or "Unable to create account.", "error")
    else:
        flash(f"Account saved for {email} as {role} ({status}).", "success")
    return redirect(url_for("developer_accounts_page"))


@app.post("/developer/quizzes/create")
@login_required
@role_required("developer")
def developer_create_quiz():
    title = str(request.form.get("quiz_title", "")).strip()
    quiz_type = normalize_quiz_type(request.form.get("quiz_type", "casual"))
    questions_raw = request.form.get("quiz_questions", "")
    parsed_questions = parse_developer_quiz_questions(questions_raw, max_items=25)

    saved, error_message, result = create_quiz_bank_entry(
        title=title,
        quiz_type=quiz_type,
        created_by=session.get("email", "developer@wellnest"),
        question_lines=parsed_questions,
    )
    if not saved:
        flash(error_message or "Unable to create quiz.", "error")
        return redirect(url_for("developer_accounts_page"))

    flash(
        f"Quiz created (ID {result.get('quiz_id')}) with {result.get('question_count')} questions.",
        "success",
    )
    return redirect(url_for("developer_accounts_page"))


@app.post("/developer/accounts/<int:account_id>/status")
@login_required
@role_required("developer")
def developer_update_account_status(account_id):
    status = normalize_account_status(request.form.get("status", "pending"))
    if status not in {"approved", "rejected", "pending"}:
        flash("Invalid account status.", "error")
        return redirect(url_for("developer_requests_page"))

    updated = update_user_account_status(
        account_id,
        status,
        approved_by=session.get("email", "developer@wellnest"),
    )
    if not updated:
        flash("Account status update failed.", "error")
    else:
        flash(f"Account status updated to {status}.", "success")
    return redirect(url_for("developer_requests_page"))


@app.post("/developer/assignments/parent")
@login_required
@role_required("developer")
def developer_assign_parent_student():
    parent_email = str(request.form.get("parent_email", "")).strip().lower()
    student_email = str(request.form.get("student_email", "")).strip().lower()

    if not parent_email or not student_email:
        flash("Parent email and student email are required for assignment.", "error")
        return redirect(url_for("developer_accounts_page"))

    if not is_approved_role_account(parent_email, "parent"):
        flash("Parent account must be approved before assignment.", "error")
        return redirect(url_for("developer_accounts_page"))

    if not is_approved_role_account(student_email, "student"):
        flash("Student account must be approved before assignment.", "error")
        return redirect(url_for("developer_accounts_page"))

    saved = upsert_parent_assignment(
        parent_email,
        student_email,
        assigned_by=str(session.get("email", "developer@wellnest")),
    )
    if not saved:
        flash("Unable to save parent assignment right now.", "error")
    else:
        flash(f"Assigned parent {parent_email} to student {student_email}.", "success")
    return redirect(url_for("developer_accounts_page"))


@app.post("/developer/assignments/proctor")
@login_required
@role_required("developer")
def developer_assign_proctor_students():
    proctor_email = str(request.form.get("proctor_email", "")).strip().lower()
    hostel_filter = normalize_hostel_block(request.form.get("hostel_block", ""))
    try:
        max_students = int(request.form.get("max_students", 24) or 24)
    except (TypeError, ValueError):
        max_students = 24
    max_students = max(8, min(max_students, 30))

    if not proctor_email:
        flash("Proctor email is required for assignment.", "error")
        return redirect(url_for("developer_accounts_page"))

    if not is_approved_role_account(proctor_email, "proctor"):
        flash("Proctor account must be approved before assignment.", "error")
        return redirect(url_for("developer_accounts_page"))

    candidate_rows = build_student_monitor_rows(limit=1000)
    if hostel_filter:
        candidate_rows = [
            row for row in candidate_rows if normalize_hostel_block(row.get("hostel_block", "")) == hostel_filter
        ]

    student_emails = [str(row.get("email", "")).strip().lower() for row in candidate_rows if str(row.get("email", "")).strip()]
    student_emails = student_emails[:max_students]

    if not student_emails:
        flash("No eligible students found for the selected filter.", "error")
        return redirect(url_for("developer_accounts_page"))

    saved = replace_proctor_assignments(
        proctor_email,
        student_emails,
        assigned_by=str(session.get("email", "developer@wellnest")),
    )
    if not saved:
        flash("Unable to save proctor assignments right now.", "error")
    else:
        scope = hostel_filter if hostel_filter else "all hostels"
        flash(f"Assigned {len(student_emails)} students to {proctor_email} ({scope}).", "success")
    return redirect(url_for("developer_accounts_page"))


def list_student_score_snapshots(limit=400):
    safe_limit = max(1, min(int(limit or 400), 2000))
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT email, stress_score, mental_battery, stress_category, last_checked_url, source, updated_at
                FROM student_score_state
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    except (sqlite3.Error, ValueError, TypeError):
        return []

    snapshots = []
    for row in rows:
        try:
            stress_score = max(1.0, min(float(row["stress_score"]), 5.0))
        except (TypeError, ValueError):
            stress_score = 3.0

        try:
            battery = max(0, min(int(row["mental_battery"]), 100))
        except (TypeError, ValueError):
            battery = calculate_mental_battery(stress_score)

        category = str(row["stress_category"] or classify_live_stress(stress_score)).upper()
        if category not in {"LOW", "MODERATE", "HIGH"}:
            category = classify_live_stress(stress_score)

        snapshots.append(
            {
                "email": str(row["email"] or "").strip().lower(),
                "stress_score": round(stress_score, 2),
                "mental_battery": battery,
                "stress_category": category,
                "last_checked_url": str(row["last_checked_url"] or ""),
                "source": str(row["source"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
    return snapshots


def student_name_from_email(email, account_lookup):
    key = str(email or "").strip().lower()
    if key in account_lookup:
        return str(account_lookup.get(key) or "Student")

    local = key.split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    return local.title() if local else "Student"


def parse_time_label(iso_value):
    dt_value = parse_iso_datetime(iso_value)
    if not dt_value:
        return "recently"
    return dt_value.astimezone(timezone.utc).strftime("%H:%M UTC")


WARDEN_BLOCK_LABELS = ["Block A", "Block B", "Block C", "Block D2", "Block D1", "Block E"]


def normalize_hostel_block(value):
    token = str(value or "").strip().upper()
    token = token.replace("HOSTEL", "").replace("BLOCK", "")
    token = token.replace("-", "").replace("_", "").replace(" ", "")
    mapping = {
        "A": "Block A",
        "B": "Block B",
        "C": "Block C",
        "D1": "Block D1",
        "D2": "Block D2",
        "E": "Block E",
    }
    return mapping.get(token, "")


def infer_student_hostel_block(email="", profile_text=""):
    source = f"{str(profile_text or '')} {str(email or '')}".lower()
    patterns = [
        ("Block D1", r"\bblock\s*d\s*[- ]?1\b|\bd\s*[- ]?1\b"),
        ("Block D2", r"\bblock\s*d\s*[- ]?2\b|\bd\s*[- ]?2\b"),
        ("Block A", r"\bblock\s*a\b|\ba\b"),
        ("Block B", r"\bblock\s*b\b|\bb\b"),
        ("Block C", r"\bblock\s*c\b|\bc\b"),
        ("Block E", r"\bblock\s*e\b|\be\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, source, flags=re.IGNORECASE):
            return label

    safe_email = str(email or "")
    idx = sum(ord(ch) for ch in safe_email) % len(WARDEN_BLOCK_LABELS) if safe_email else 0
    return WARDEN_BLOCK_LABELS[idx]


def build_student_monitor_rows(limit=250):
    approved_students = list_user_accounts(role="student", status="approved", limit=max(50, limit))
    account_lookup = {
        str(account.get("email", "")).strip().lower(): str(account.get("name", "Student"))
        for account in approved_students
        if str(account.get("email", "")).strip()
    }
    account_meta = {
        str(account.get("email", "")).strip().lower(): {
            "name": str(account.get("name", "Student")),
            "profile_hint": f"{account.get('name', '')} {account.get('requested_note', '')}",
        }
        for account in approved_students
        if str(account.get("email", "")).strip()
    }

    snapshots = list_student_score_snapshots(limit=max(80, limit * 2))
    merged = []
    seen_emails = set()

    for snap in snapshots:
        email = str(snap.get("email", "")).strip().lower()
        if not email or email in seen_emails:
            continue

        category = str(snap.get("stress_category", "MODERATE")).upper()
        if category not in {"LOW", "MODERATE", "HIGH"}:
            category = "MODERATE"

        stress_score = max(1.0, min(float(snap.get("stress_score", 3.0)), 5.0))
        battery = max(0, min(int(snap.get("mental_battery", calculate_mental_battery(stress_score))), 100))
        profile_hint = str((account_meta.get(email) or {}).get("profile_hint", ""))
        merged.append(
            {
                "email": email,
                "name": student_name_from_email(email, account_lookup),
                "stress_score": round(stress_score, 2),
                "mental_battery": battery,
                "stress_category": category,
                "updated_at": str(snap.get("updated_at", "")),
                "updated_at_label": parse_time_label(snap.get("updated_at")),
                "last_checked_url": str(snap.get("last_checked_url", "")),
                "hostel_block": infer_student_hostel_block(email=email, profile_text=profile_hint),
            }
        )
        seen_emails.add(email)

    for account in approved_students:
        email = str(account.get("email", "")).strip().lower()
        if not email or email in seen_emails:
            continue
        default_score = 3.0
        merged.append(
            {
                "email": email,
                "name": str(account.get("name") or student_name_from_email(email, account_lookup)),
                "stress_score": default_score,
                "mental_battery": calculate_mental_battery(default_score),
                "stress_category": "MODERATE",
                "updated_at": "",
                "updated_at_label": "awaiting sync",
                "last_checked_url": "",
                "hostel_block": infer_student_hostel_block(
                    email=email,
                    profile_text=f"{account.get('name', '')} {account.get('requested_note', '')}",
                ),
            }
        )

    priority = {"HIGH": 0, "MODERATE": 1, "LOW": 2}
    merged.sort(
        key=lambda item: (
            priority.get(str(item.get("stress_category", "MODERATE")).upper(), 3),
            -float(item.get("stress_score", 3.0)),
            str(item.get("name", "")),
        )
    )
    return merged[: max(1, limit)]


def normalize_phone_number(phone_value):
    raw = str(phone_value or "").strip()
    if not raw:
        return ""

    cleaned = re.sub(r"[\s()\-]", "", raw)
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"

    if not cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) == 10:
            cleaned = f"+91{digits}"
        else:
            cleaned = f"+{digits}"

    normalized = f"+{re.sub(r'\D', '', cleaned)}"
    if not re.fullmatch(r"\+\d{8,15}", normalized):
        return ""
    return normalized


def mask_phone_number(phone_value):
    normalized = normalize_phone_number(phone_value)
    if not normalized:
        return ""

    if len(normalized) <= 6:
        return "*" * len(normalized)
    return f"{normalized[:4]}{'*' * max(2, len(normalized) - 6)}{normalized[-2:]}"


def build_parent_otp_message(code):
    return (
        f"Your EqWell verification code is {code}. "
        f"It expires in {PARENT_OTP_TTL_MINUTES} minutes."
    )


def send_whatsapp(phone, message):
    phone_value = str(phone or "").strip()
    body = str(message or "").strip()
    if not phone_value or not body:
        return False, "invalid", "Phone or message missing."

    to_value = phone_value if phone_value.startswith("whatsapp:") else f"whatsapp:{phone_value}"
    from_value = TWILIO_WHATSAPP_FROM
    if not from_value.startswith("whatsapp:"):
        from_value = f"whatsapp:{from_value}"

    if EQWELL_WHATSAPP_MODE == "mock":
        emit_terminal_debug_log("whatsapp-mock-send", to=to_value, message=body)
        return True, "mock", "mock-send"

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return False, "twilio", "Missing Twilio credentials."

    try:
        import importlib

        twilio_rest = importlib.import_module("twilio.rest")
        Client = getattr(twilio_rest, "Client", None)
    except Exception:
        Client = None

    if Client is None:
        return False, "twilio", "Twilio package is not installed."

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        response = client.messages.create(from_=from_value, body=body, to=to_value)
        return True, "twilio", str(getattr(response, "sid", "sent"))
    except Exception as exc:
        return False, "twilio", str(exc)[:280]


def generate_parent_otp_code():
    return f"{secrets.randbelow(900000) + 100000}"


def load_parent_alert_contact(student_email):
    key = str(student_email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT student_email, parent_name, parent_phone, verified, verified_at,
                       consent_enabled, alerts_enabled, otp_code, otp_sent_at, otp_expires_at,
                       otp_attempts, admin_edit_count, created_at, updated_at,
                       last_alert_type, last_alert_trigger, last_alert_sent_at, last_known_battery
                FROM student_parent_alert_contacts
                WHERE student_email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    phone = str(row["parent_phone"] or "")
    try:
        last_known_battery = int(row["last_known_battery"])
    except (TypeError, ValueError):
        last_known_battery = None

    return {
        "student_email": str(row["student_email"] or key).strip().lower(),
        "parent_name": str(row["parent_name"] or "").strip(),
        "parent_phone": phone,
        "parent_phone_masked": mask_phone_number(phone),
        "verified": bool(int(row["verified"] or 0)),
        "verified_at": str(row["verified_at"] or ""),
        "consent_enabled": bool(int(row["consent_enabled"] or 0)),
        "alerts_enabled": bool(int(row["alerts_enabled"] or 0)),
        "otp_code": str(row["otp_code"] or ""),
        "otp_sent_at": str(row["otp_sent_at"] or ""),
        "otp_expires_at": str(row["otp_expires_at"] or ""),
        "otp_attempts": int(row["otp_attempts"] or 0),
        "admin_edit_count": int(row["admin_edit_count"] or 0),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "last_alert_type": str(row["last_alert_type"] or ""),
        "last_alert_trigger": str(row["last_alert_trigger"] or ""),
        "last_alert_sent_at": str(row["last_alert_sent_at"] or ""),
        "last_known_battery": last_known_battery,
    }


def save_parent_contact_otp(student_email, parent_name, parent_phone, consent_enabled, alerts_enabled, otp_code, admin_edit_count=None):
    key = str(student_email or "").strip().lower()
    safe_name = str(parent_name or "").strip()[:140]
    safe_phone = normalize_phone_number(parent_phone)
    safe_otp = str(otp_code or "").strip()
    if not key or not safe_name or not safe_phone or not re.fullmatch(r"\d{6}", safe_otp):
        return False

    existing = load_parent_alert_contact(key) or {}
    now = utc_now()
    now_iso = now.isoformat(timespec="seconds")
    expires_iso = (now + timedelta(minutes=PARENT_OTP_TTL_MINUTES)).isoformat(timespec="seconds")

    try:
        edit_count = int(existing.get("admin_edit_count", 0) if admin_edit_count is None else admin_edit_count)
    except (TypeError, ValueError):
        edit_count = 0

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_parent_alert_contacts (
                    student_email, parent_name, parent_phone, verified, verified_at,
                    consent_enabled, alerts_enabled, otp_code, otp_sent_at, otp_expires_at,
                    otp_attempts, admin_edit_count, created_at, updated_at,
                    last_alert_type, last_alert_trigger, last_alert_sent_at, last_known_battery
                ) VALUES (?, ?, ?, 0, '', ?, ?, ?, ?, ?, 0, ?, ?, ?, NULL, NULL, NULL, ?)
                ON CONFLICT(student_email) DO UPDATE SET
                    parent_name = excluded.parent_name,
                    parent_phone = excluded.parent_phone,
                    verified = 0,
                    verified_at = '',
                    consent_enabled = excluded.consent_enabled,
                    alerts_enabled = excluded.alerts_enabled,
                    otp_code = excluded.otp_code,
                    otp_sent_at = excluded.otp_sent_at,
                    otp_expires_at = excluded.otp_expires_at,
                    otp_attempts = 0,
                    admin_edit_count = excluded.admin_edit_count,
                    updated_at = excluded.updated_at,
                    last_alert_type = NULL,
                    last_alert_trigger = NULL,
                    last_alert_sent_at = NULL
                """,
                (
                    key,
                    safe_name,
                    safe_phone,
                    1 if consent_enabled else 0,
                    1 if alerts_enabled else 0,
                    safe_otp,
                    now_iso,
                    expires_iso,
                    max(0, edit_count),
                    str(existing.get("created_at") or now_iso),
                    now_iso,
                    existing.get("last_known_battery"),
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def verify_parent_contact_otp(student_email, otp_code):
    key = str(student_email or "").strip().lower()
    submitted = str(otp_code or "").strip()
    if not key or not re.fullmatch(r"\d{6}", submitted):
        return False, "Enter a valid 6-digit OTP."

    contact = load_parent_alert_contact(key)
    if not contact:
        return False, "Add parent contact first."

    expected = str(contact.get("otp_code") or "").strip()
    expires_at = parse_iso_datetime(contact.get("otp_expires_at"))
    now = utc_now()

    if not expected or not expires_at:
        return False, "No active OTP. Request a new code."

    if expires_at < now:
        try:
            with sqlite3.connect(SCORE_DB_PATH) as conn:
                conn.execute(
                    """
                    UPDATE student_parent_alert_contacts
                    SET otp_code = '', otp_sent_at = '', otp_expires_at = '', updated_at = ?
                    WHERE student_email = ?
                    """,
                    (now.isoformat(timespec="seconds"), key),
                )
                conn.commit()
        except sqlite3.Error:
            pass
        return False, "OTP expired. Request a new code."

    if submitted != expected:
        try:
            with sqlite3.connect(SCORE_DB_PATH) as conn:
                conn.execute(
                    """
                    UPDATE student_parent_alert_contacts
                    SET otp_attempts = otp_attempts + 1, updated_at = ?
                    WHERE student_email = ?
                    """,
                    (now.isoformat(timespec="seconds"), key),
                )
                conn.commit()
        except sqlite3.Error:
            pass
        return False, "Incorrect OTP."

    now_iso = now.isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                UPDATE student_parent_alert_contacts
                SET verified = 1,
                    verified_at = ?,
                    otp_code = '',
                    otp_sent_at = '',
                    otp_expires_at = '',
                    otp_attempts = 0,
                    updated_at = ?
                WHERE student_email = ?
                """,
                (now_iso, now_iso, key),
            )
            conn.commit()
    except sqlite3.Error:
        return False, "Could not verify OTP right now."
    return True, "Parent contact verified."


def update_parent_contact_runtime_state(student_email, battery, alert_priority="", trigger_type="", sent_at=""):
    key = str(student_email or "").strip().lower()
    if not key:
        return

    now_iso = utc_now().isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            if alert_priority:
                conn.execute(
                    """
                    UPDATE student_parent_alert_contacts
                    SET last_known_battery = ?,
                        last_alert_type = ?,
                        last_alert_trigger = ?,
                        last_alert_sent_at = ?,
                        updated_at = ?
                    WHERE student_email = ?
                    """,
                    (
                        int(max(0, min(int(battery), 100))),
                        str(alert_priority)[:24],
                        str(trigger_type)[:40],
                        str(sent_at or now_iso)[:40],
                        now_iso,
                        key,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE student_parent_alert_contacts
                    SET last_known_battery = ?, updated_at = ?
                    WHERE student_email = ?
                    """,
                    (int(max(0, min(int(battery), 100))), now_iso, key),
                )
            conn.commit()
    except (sqlite3.Error, TypeError, ValueError):
        return


def record_parent_alert_event(student_email, parent_phone, alert_priority, trigger_type, battery, previous_battery, signal_count, channel, send_status, provider_response):
    now_iso = utc_now().isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO parent_alert_events (
                    student_email, parent_phone, alert_priority, trigger_type,
                    battery, previous_battery, signal_count, channel, send_status,
                    provider_response, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(student_email or "").strip().lower()[:320],
                    str(parent_phone or "")[:30],
                    str(alert_priority or "NONE")[:20],
                    str(trigger_type or "NONE")[:40],
                    int(max(0, min(int(battery or 0), 100))),
                    int(previous_battery) if isinstance(previous_battery, int) else None,
                    max(0, int(signal_count or 0)),
                    str(channel or "dashboard")[:24],
                    str(send_status or "none")[:40],
                    str(provider_response or "")[:280],
                    now_iso,
                ),
            )
            conn.commit()
    except (sqlite3.Error, TypeError, ValueError):
        return


def compute_nearest_counselling_slot_utc(now_dt=None):
    base_dt = now_dt if isinstance(now_dt, datetime) else utc_now()
    if base_dt.tzinfo is None:
        base_dt = base_dt.replace(tzinfo=timezone.utc)

    minimum_slot_time = base_dt + timedelta(minutes=AUTO_COUNSELLING_SLOT_MIN_LEAD_MINUTES)

    for day_offset in range(0, 8):
        day_base = minimum_slot_time + timedelta(days=day_offset)
        for hour_value, minute_value in AUTO_COUNSELLING_SLOT_TIMES_UTC:
            slot_dt = day_base.replace(hour=hour_value, minute=minute_value, second=0, microsecond=0)
            if slot_dt >= minimum_slot_time:
                return slot_dt

    return minimum_slot_time.replace(second=0, microsecond=0)


def load_auto_counselling_session(student_email):
    key = str(student_email or "").strip().lower()
    if not key:
        return None

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT email, counsellor_email, counsellor_name, session_at, session_label,
                       reason, trigger_battery, stress_category, status, assigned_at, updated_at
                FROM student_auto_counselling_sessions
                WHERE email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row:
        return None

    try:
        trigger_battery = int(row["trigger_battery"]) if row["trigger_battery"] is not None else None
    except (TypeError, ValueError):
        trigger_battery = None

    return {
        "email": str(row["email"] or key),
        "counsellor_email": str(row["counsellor_email"] or "").strip().lower(),
        "counsellor_name": str(row["counsellor_name"] or "Counsellor Team").strip() or "Counsellor Team",
        "session_at": str(row["session_at"] or ""),
        "session_label": str(row["session_label"] or "").strip(),
        "reason": str(row["reason"] or "").strip(),
        "trigger_battery": trigger_battery,
        "stress_category": str(row["stress_category"] or "").strip().upper(),
        "status": str(row["status"] or "scheduled").strip().lower() or "scheduled",
        "assigned_at": str(row["assigned_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def upsert_auto_counselling_session(
    student_email,
    counsellor_email,
    counsellor_name,
    session_at,
    session_label,
    reason,
    trigger_battery,
    stress_category,
    status="scheduled",
):
    key = str(student_email or "").strip().lower()
    if not key:
        return None

    session_dt = parse_iso_datetime(session_at) or compute_nearest_counselling_slot_utc()
    session_iso = session_dt.isoformat(timespec="seconds")
    assigned_iso = utc_now().isoformat(timespec="seconds")

    try:
        trigger_value = int(max(0, min(int(trigger_battery or 0), 100)))
    except (TypeError, ValueError):
        trigger_value = None

    counsellor_email_value = str(counsellor_email or "").strip().lower()
    counsellor_name_value = str(counsellor_name or "Counsellor Team").strip() or "Counsellor Team"
    stress_category_value = str(stress_category or "").strip().upper()[:24]
    status_value = str(status or "scheduled").strip().lower()[:24] or "scheduled"
    reason_value = str(reason or "").strip()[:160]
    label_value = str(session_label or "").strip()[:80]
    if not label_value:
        label_value = session_dt.strftime("%d %b %H:%M UTC")

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO student_auto_counselling_sessions (
                    email, counsellor_email, counsellor_name, session_at, session_label,
                    reason, trigger_battery, stress_category, status, assigned_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    counsellor_email = excluded.counsellor_email,
                    counsellor_name = excluded.counsellor_name,
                    session_at = excluded.session_at,
                    session_label = excluded.session_label,
                    reason = excluded.reason,
                    trigger_battery = excluded.trigger_battery,
                    stress_category = excluded.stress_category,
                    status = excluded.status,
                    assigned_at = excluded.assigned_at,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    counsellor_email_value,
                    counsellor_name_value,
                    session_iso,
                    label_value,
                    reason_value,
                    trigger_value,
                    stress_category_value,
                    status_value,
                    assigned_iso,
                    assigned_iso,
                ),
            )
            conn.commit()
    except sqlite3.Error:
        return None

    return load_auto_counselling_session(key)


def ensure_auto_counselling_session(student_email, battery, stress_category, reason="battery-below-threshold"):
    key = str(student_email or "").strip().lower()
    if not key:
        return {"status": "missing-student"}

    try:
        safe_battery = max(0, min(int(battery or 0), 100))
    except (TypeError, ValueError):
        safe_battery = 100

    if safe_battery >= AUTO_COUNSELLING_TRIGGER_BATTERY:
        return {
            "status": "not-required",
            "trigger_threshold": AUTO_COUNSELLING_TRIGGER_BATTERY,
            "battery": safe_battery,
        }

    now_dt = utc_now()
    existing = load_auto_counselling_session(key)
    if existing:
        existing_status = str(existing.get("status") or "").lower()
        session_dt = parse_iso_datetime(existing.get("session_at"))
        assigned_dt = parse_iso_datetime(existing.get("assigned_at"))
        if (
            existing_status in {"scheduled", "pending"}
            and session_dt
            and session_dt >= (now_dt - timedelta(minutes=30))
            and assigned_dt
            and (now_dt - assigned_dt) < timedelta(hours=AUTO_COUNSELLING_REASSIGN_HOURS)
        ):
            return {
                "status": "already-scheduled",
                "auto_assigned": False,
                **existing,
            }

    counsellor_rows = list_user_accounts(role="counsellor", status="approved", limit=1)
    counsellor_info = (counsellor_rows[0] or {}) if counsellor_rows else {}
    counsellor_email = str(counsellor_info.get("email", "")).strip().lower() or "counsellor@eqwell.app"
    counsellor_name = str(counsellor_info.get("name", "")).strip() or "Dr. Aris"

    slot_dt = compute_nearest_counselling_slot_utc(now_dt)
    slot_label = slot_dt.strftime("%d %b %H:%M UTC")
    saved = upsert_auto_counselling_session(
        key,
        counsellor_email,
        counsellor_name,
        session_at=slot_dt,
        session_label=slot_label,
        reason=reason,
        trigger_battery=safe_battery,
        stress_category=stress_category,
        status="scheduled",
    )
    if not saved:
        return {"status": "save-failed"}

    upsert_student_behavior_context(
        key,
        {
            "auto_counselling_status": "scheduled",
            "auto_counselling_assigned_at": str(saved.get("assigned_at", "")),
            "auto_counselling_session_at": str(saved.get("session_at", "")),
            "auto_counselling_session_label": str(saved.get("session_label", "")),
            "auto_counselling_counsellor_email": str(saved.get("counsellor_email", "")),
            "auto_counselling_counsellor_name": str(saved.get("counsellor_name", "")),
            "auto_counselling_trigger_battery": safe_battery,
            "auto_counselling_reason": str(reason or "")[:160],
        },
    )

    emit_terminal_debug_log(
        "auto-counselling-assigned",
        student_email=key,
        battery=safe_battery,
        stress_category=str(stress_category or "").upper(),
        session_at=str(saved.get("session_at", "")),
        counsellor_email=str(saved.get("counsellor_email", "")),
    )

    return {
        "status": "scheduled",
        "auto_assigned": True,
        **saved,
    }


def list_parent_alert_contacts(limit=80):
    safe_limit = max(1, min(int(limit or 80), 300))
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT c.student_email, c.parent_name, c.parent_phone, c.verified, c.verified_at,
                       c.alerts_enabled, c.consent_enabled, c.admin_edit_count, c.updated_at,
                       u.name AS student_name
                FROM student_parent_alert_contacts c
                LEFT JOIN user_accounts u ON u.email = c.student_email
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    except sqlite3.Error:
        return []

    output = []
    for row in rows:
        output.append(
            {
                "student_email": str(row["student_email"] or "").strip().lower(),
                "student_name": str(row["student_name"] or student_name_from_email(row["student_email"], {})),
                "parent_name": str(row["parent_name"] or "").strip(),
                "parent_phone_masked": mask_phone_number(row["parent_phone"]),
                "verified": bool(int(row["verified"] or 0)),
                "verified_at": str(row["verified_at"] or ""),
                "alerts_enabled": bool(int(row["alerts_enabled"] or 0)),
                "consent_enabled": bool(int(row["consent_enabled"] or 0)),
                "admin_edit_count": int(row["admin_edit_count"] or 0),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
    return output


def load_parent_alert_contact_stats():
    stats = {
        "total": 0,
        "verified": 0,
        "pending": 0,
        "alerts_enabled": 0,
    }
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) AS verified,
                    SUM(CASE WHEN verified = 0 THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN alerts_enabled = 1 THEN 1 ELSE 0 END) AS alerts_enabled
                FROM student_parent_alert_contacts
                """
            ).fetchone()
            if row:
                stats["total"] = int(row["total"] or 0)
                stats["verified"] = int(row["verified"] or 0)
                stats["pending"] = int(row["pending"] or 0)
                stats["alerts_enabled"] = int(row["alerts_enabled"] or 0)
    except sqlite3.Error:
        pass
    return stats


def count_recent_extension_risk_signals(student_email, hours=24):
    key = str(student_email or "").strip().lower()
    if not key:
        return 0

    cutoff = (utc_now() - timedelta(hours=max(1, int(hours or 24)))).isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM extension_risk_events
                WHERE email = ? AND observed_at >= ?
                """,
                (key, cutoff),
            ).fetchone()
    except sqlite3.Error:
        return 0

    try:
        return int(row[0] or 0) if row else 0
    except (TypeError, ValueError):
        return 0


def count_high_risk_signals_for_student(student_email, battery, stress_category, components):
    key = str(student_email or "").strip().lower()
    signal_count = 0
    signal_labels = []
    behavior = get_student_behavior_context(key)

    emotion = str(behavior.get("last_emotion", "")).strip().lower()
    chatbot_component = float(components.get("chatbot", 3.0) or 3.0)
    if emotion in {"sadness", "sad", "fear", "anger", "anxious", "anxiety"} or chatbot_component >= 4.0:
        signal_count += 1
        signal_labels.append("negative_emotion")

    fit = get_google_fit_overview(key)
    try:
        steps = int(fit.get("steps", 0) or 0)
    except (TypeError, ValueError):
        steps = 0
    if steps and steps < 3000:
        signal_count += 1
        signal_labels.append("long_inactivity")

    try:
        sleep_hours = float(fit.get("sleep_hours", 0.0) or 0.0)
    except (TypeError, ValueError):
        sleep_hours = 0.0
    if 0 < sleep_hours < 6.0:
        signal_count += 1
        signal_labels.append("low_sleep")

    if str(stress_category or "").upper() == "HIGH" or int(battery or 0) <= 30:
        signal_count += 1
        signal_labels.append("high_stress")

    extension_component = float(components.get("extension", 3.0) or 3.0)
    risk_count = count_recent_extension_risk_signals(key, hours=24)
    if extension_component >= 4.0 or risk_count >= 2:
        signal_count += 1
        signal_labels.append("risk_pattern")

    return signal_count, signal_labels


def check_alert(battery, previous_battery, signals):
    if battery <= 20:
        return "CRITICAL"

    if battery <= 30:
        return "HIGH"

    if previous_battery - battery >= 30:
        return "SUDDEN_DROP"

    if signals >= 4:
        return "RISK_ACCUMULATION"

    return "NONE"


def alert_priority_from_trigger(trigger_type, battery):
    trigger = str(trigger_type or "NONE").upper()
    battery_value = max(0, min(int(battery or 0), 100))
    if trigger == "CRITICAL":
        return "CRITICAL"
    if trigger in {"HIGH", "SUDDEN_DROP", "RISK_ACCUMULATION"}:
        return "HIGH"
    if 30 < battery_value <= 40:
        return "MEDIUM"
    return "NONE"


def build_parent_alert_message(priority):
    level = str(priority or "").upper()
    if level == "CRITICAL":
        return PARENT_ALERT_MESSAGE_CRITICAL
    return PARENT_ALERT_MESSAGE_HIGH


def process_parent_alert_for_student(student_email, battery, stress_category, components):
    key = str(student_email or "").strip().lower()
    if not key:
        return {"status": "missing-student"}

    try:
        safe_battery = max(0, min(int(battery or 0), 100))
    except (TypeError, ValueError):
        safe_battery = 100

    auto_counselling = ensure_auto_counselling_session(
        key,
        safe_battery,
        stress_category,
        reason="battery-below-threshold",
    )

    contact = load_parent_alert_contact(key)
    if not contact:
        return {"status": "no-parent-contact", "auto_counselling": auto_counselling}

    previous_raw = contact.get("last_known_battery")
    try:
        previous_battery = int(previous_raw)
    except (TypeError, ValueError):
        previous_battery = safe_battery

    if not (contact.get("verified") and contact.get("consent_enabled") and contact.get("alerts_enabled")):
        update_parent_contact_runtime_state(key, safe_battery)
        return {"status": "inactive-contact", "auto_counselling": auto_counselling}

    signal_count, signal_labels = count_high_risk_signals_for_student(key, safe_battery, stress_category, components)
    trigger_type = check_alert(safe_battery, previous_battery, signal_count)
    alert_priority = alert_priority_from_trigger(trigger_type, safe_battery)
    if alert_priority == "NONE":
        update_parent_contact_runtime_state(key, safe_battery)
        return {
            "status": "no-alert",
            "trigger_type": trigger_type,
            "signal_count": signal_count,
            "auto_counselling": auto_counselling,
        }

    now = utc_now()
    last_sent = parse_iso_datetime(contact.get("last_alert_sent_at"))
    last_priority = str(contact.get("last_alert_type") or "").upper()
    last_trigger = str(contact.get("last_alert_trigger") or "").upper()
    crossed_low_threshold = previous_battery >= AUTO_COUNSELLING_TRIGGER_BATTERY and safe_battery < AUTO_COUNSELLING_TRIGGER_BATTERY
    cooldown_window = timedelta(minutes=PARENT_ALERT_COOLDOWN_MINUTES)
    if alert_priority == "CRITICAL":
        cooldown_window = timedelta(minutes=max(5, PARENT_ALERT_COOLDOWN_MINUTES // 6))

    if (
        last_sent
        and (now - last_sent) < cooldown_window
        and last_priority == alert_priority
        and last_trigger == str(trigger_type or "").upper()
        and not crossed_low_threshold
    ):
        update_parent_contact_runtime_state(key, safe_battery)
        return {
            "status": "suppressed",
            "trigger_type": trigger_type,
            "signal_count": signal_count,
            "auto_counselling": auto_counselling,
        }

    parent_phone = normalize_phone_number(contact.get("parent_phone"))
    message = build_parent_alert_message(alert_priority)
    channel = "dashboard"
    send_status = "dashboard-only"
    provider_response = "No WhatsApp dispatch for medium-priority alerts."

    if alert_priority in {"HIGH", "CRITICAL"}:
        sent, provider, provider_response = send_whatsapp(parent_phone, message)
        channel = "whatsapp" if sent else "dashboard"
        send_status = "sent" if sent else "failed"
        provider_response = f"{provider}: {provider_response}"

    record_parent_alert_event(
        key,
        parent_phone,
        alert_priority,
        trigger_type,
        safe_battery,
        previous_battery,
        signal_count,
        channel,
        send_status,
        provider_response,
    )
    update_parent_contact_runtime_state(
        key,
        safe_battery,
        alert_priority=alert_priority,
        trigger_type=trigger_type,
        sent_at=now.isoformat(timespec="seconds"),
    )

    emit_terminal_debug_log(
        "parent-alert-dispatch",
        student_email=key,
        priority=alert_priority,
        trigger_type=trigger_type,
        battery=safe_battery,
        previous_battery=previous_battery,
        signal_count=signal_count,
        signal_labels="|".join(signal_labels),
        channel=channel,
        send_status=send_status,
    )
    return {
        "status": "dispatched",
        "priority": alert_priority,
        "trigger_type": trigger_type,
        "signal_count": signal_count,
        "channel": channel,
        "auto_counselling": auto_counselling,
    }


def load_parent_assigned_student(parent_email):
    key = str(parent_email or "").strip().lower()
    if not key:
        return ""

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT student_email
                FROM parent_student_links
                WHERE parent_email = ?
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return ""

    if not row:
        return ""
    return str(row[0] or "").strip().lower()


def upsert_parent_assignment(parent_email, student_email, assigned_by=""):
    parent_key = str(parent_email or "").strip().lower()
    student_key = str(student_email or "").strip().lower()
    if not parent_key or not student_key:
        return False

    now_iso = utc_now().isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO parent_student_links (
                    parent_email, student_email, assigned_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(parent_email) DO UPDATE SET
                    student_email = excluded.student_email,
                    assigned_by = excluded.assigned_by,
                    updated_at = excluded.updated_at
                """,
                (
                    parent_key,
                    student_key,
                    str(assigned_by or "").strip().lower()[:320],
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def load_proctor_assigned_students(proctor_email):
    key = str(proctor_email or "").strip().lower()
    if not key:
        return []

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT student_email
                FROM proctor_student_links
                WHERE proctor_email = ?
                ORDER BY created_at ASC
                """,
                (key,),
            ).fetchall()
    except sqlite3.Error:
        return []

    return [str(row[0] or "").strip().lower() for row in rows if str(row[0] or "").strip()]


def replace_proctor_assignments(proctor_email, student_emails, assigned_by=""):
    proctor_key = str(proctor_email or "").strip().lower()
    normalized_students = [
        str(email or "").strip().lower()
        for email in (student_emails or [])
        if str(email or "").strip()
    ]
    if not proctor_key:
        return False

    now_iso = utc_now().isoformat(timespec="seconds")
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.execute(
                """
                DELETE FROM proctor_student_links
                WHERE proctor_email = ?
                """,
                (proctor_key,),
            )
            if normalized_students:
                conn.executemany(
                    """
                    INSERT INTO proctor_student_links (proctor_email, student_email, assigned_by, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            proctor_key,
                            student_key,
                            str(assigned_by or "").strip().lower()[:320],
                            now_iso,
                        )
                        for student_key in normalized_students
                    ],
                )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def load_student_assigned_proctor(student_email):
    key = str(student_email or "").strip().lower()
    if not key:
        return ""

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            row = conn.execute(
                """
                SELECT proctor_email
                FROM proctor_student_links
                WHERE student_email = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return ""

    if not row:
        return ""
    return str(row[0] or "").strip().lower()


def build_role_profile(email, role_title, fallback_name):
    account = get_user_account_by_email(email) if email else None
    account = account or {}
    account_email = str(account.get("email") or str(email or "").strip().lower())
    status_raw = str(account.get("status", "approved") or "approved").strip().lower()
    status_label = "Active" if status_raw == "approved" else status_raw.capitalize()

    return {
        "name": str(account.get("name") or fallback_name),
        "email": account_email,
        "role_title": role_title,
        "status_label": status_label,
        "member_since": parse_time_label(account.get("created_at")) if account else "recently",
    }


def build_support_contacts(student_email="", proctor_email=""):
    counsellor_row = list_user_accounts(role="counsellor", status="approved", limit=1)
    warden_row = list_user_accounts(role="warden", status="approved", limit=1)

    resolved_proctor = str(proctor_email or "").strip().lower()
    if not resolved_proctor and student_email:
        resolved_proctor = load_student_assigned_proctor(student_email)

    contacts = []

    def add_contact(email_value, role_label, fallback_name, channel_hint):
        account = get_user_account_by_email(email_value) if email_value else None
        account = account or {}
        contact_email = str(account.get("email") or str(email_value or "").strip().lower())
        if not contact_email:
            return
        contacts.append(
            {
                "name": str(account.get("name") or fallback_name),
                "email": contact_email,
                "role": role_label,
                "channel": channel_hint,
            }
        )

    add_contact(
        str((counsellor_row[0] or {}).get("email", "")).strip().lower() if counsellor_row else "",
        "Counsellor",
        "Counsellor Team",
        "Email for session support",
    )
    add_contact(
        str((warden_row[0] or {}).get("email", "")).strip().lower() if warden_row else "",
        "Hostel Warden",
        "Hostel Warden",
        "Hostel and safety coordination",
    )
    add_contact(
        resolved_proctor,
        "Proctor",
        "Academic Proctor",
        "Academic follow-up and mentoring",
    )

    contacts.append(
        {
            "name": "EqWell Emergency Line",
            "email": "support@eqwell.app",
            "role": "Emergency Support",
            "channel": "24x7 escalation support",
        }
    )
    return contacts


def build_student_analysis_summary(student_email, student_row, weekly_logs, lifestyle, counselling):
    weekly_values = [int(item.get("stress", 0) or 0) for item in (weekly_logs or [])]
    weekly_avg = int(round(sum(weekly_values) / max(1, len(weekly_values)))) if weekly_values else 0
    weekly_peak = max(weekly_values) if weekly_values else 0
    weekly_low = min(weekly_values) if weekly_values else 0
    delta = weekly_stress_delta(weekly_logs)

    if delta <= -4:
        momentum = "Improving"
    elif delta >= 4:
        momentum = "Elevated"
    else:
        momentum = "Stable"

    stress_category = str((student_row or {}).get("stress_category", "MODERATE")).upper()
    risk_level = "Moderate"
    if stress_category == "HIGH" or weekly_peak >= 70:
        risk_level = "High"
    elif stress_category == "LOW" and weekly_avg <= 42:
        risk_level = "Low"

    recommendations = []
    if risk_level == "High":
        recommendations.append("Schedule an immediate counselling follow-up within 24 hours.")
    if float((lifestyle or {}).get("sleep_hours", 0.0) or 0.0) > 0 and float((lifestyle or {}).get("sleep_hours", 0.0) or 0.0) < 6.0:
        recommendations.append("Prioritize sleep recovery: target at least 7 hours for the next 3 nights.")
    if not (counselling or {}).get("booked"):
        recommendations.append("Book a support session to maintain continuity of care.")
    if not recommendations:
        recommendations.append("Current indicators are stable; continue regular wellness check-ins.")

    attempts = list_student_quiz_attempts(student_email, limit=5) if student_email else []
    recent_attempts = [
        {
            "quiz_title": str(attempt.get("quiz_title", "Quiz")),
            "score_percent": int(attempt.get("score_percent", 0) or 0),
            "risk_band": str(attempt.get("risk_band", "MODERATE")),
            "created_at_label": str(attempt.get("created_at_label", "recently")),
        }
        for attempt in attempts[:5]
    ]

    return {
        "weekly_average": weekly_avg,
        "weekly_peak": weekly_peak,
        "weekly_low": weekly_low,
        "trend_delta": delta,
        "momentum_label": momentum,
        "risk_level": risk_level,
        "recommendations": recommendations,
        "recent_attempts": recent_attempts,
    }


def ensure_parent_assignment(parent_email, student_emails):
    available = [str(email or "").strip().lower() for email in (student_emails or []) if str(email or "").strip()]
    if not available:
        return ""

    assigned_student = load_parent_assigned_student(parent_email)
    if assigned_student in available:
        return assigned_student

    seed = sum(ord(ch) for ch in str(parent_email or "").strip().lower())
    selected = available[seed % len(available)]
    upsert_parent_assignment(parent_email, selected, assigned_by="system")
    return selected


def ensure_proctor_assignments(proctor_email, student_emails, target_size=24):
    available = [str(email or "").strip().lower() for email in (student_emails or []) if str(email or "").strip()]
    if not available:
        return []

    existing = [email for email in load_proctor_assigned_students(proctor_email) if email in available]
    target_count = max(8, min(int(target_size or 24), 30))

    if len(existing) >= min(target_count, len(available)):
        return existing

    seed = sum(ord(ch) for ch in str(proctor_email or "").strip().lower())
    start = seed % len(available)
    selected = [available[(start + idx) % len(available)] for idx in range(min(target_count, len(available)))]
    replace_proctor_assignments(proctor_email, selected, assigned_by="system")
    return selected


def weekly_stress_delta(weekly_logs):
    rows = list(weekly_logs or [])
    if len(rows) < 2:
        return 0

    split = max(1, len(rows) // 2)
    first_half = rows[:split]
    second_half = rows[split:]
    if not second_half:
        second_half = first_half

    first_avg = sum(float(item.get("stress", 0) or 0) for item in first_half) / max(1, len(first_half))
    second_avg = sum(float(item.get("stress", 0) or 0) for item in second_half) / max(1, len(second_half))
    return int(round(second_avg - first_avg))


def student_counselling_snapshot(student_email, stress_category):
    attempts = list_student_quiz_attempts(student_email, limit=8)
    now_utc = utc_now()
    auto_session = load_auto_counselling_session(student_email) or {}
    auto_session_dt = parse_iso_datetime(auto_session.get("session_at", ""))
    auto_status = str(auto_session.get("status", "")).strip().lower()
    auto_assigned = bool(auto_session) and auto_status in {"scheduled", "pending"}
    auto_upcoming = bool(auto_assigned and auto_session_dt and auto_session_dt >= (now_utc - timedelta(minutes=30)))

    recent_attempt = attempts[0] if attempts else None
    recent_dt = parse_iso_datetime((recent_attempt or {}).get("created_at", ""))
    recent_days = 999
    if recent_dt:
        recent_days = max(0, (now_utc - recent_dt).days)

    category = str(stress_category or "MODERATE").upper()
    needs_help = category in {"HIGH", "MODERATE"}
    booked = bool(recent_attempt) or auto_upcoming or needs_help
    attended = bool(recent_attempt) and recent_days <= 21

    if auto_upcoming:
        booked_label = "Auto-assigned"
    else:
        booked_label = "Booked" if booked else "Not booked"
    attended_label = "Attended" if attended else ("Missed / Pending" if booked else "Not scheduled")
    if auto_upcoming and not attended:
        attended_label = "Scheduled"

    if auto_upcoming and auto_session_dt:
        last_check_label = f"next at {auto_session_dt.astimezone(timezone.utc).strftime('%H:%M UTC')}"
    else:
        last_check_label = parse_time_label((recent_attempt or {}).get("created_at", "")) if recent_attempt else "no recent check"

    return {
        "booked": booked,
        "attended": attended,
        "booked_label": booked_label,
        "attended_label": attended_label,
        "needs_help": needs_help,
        "last_check_label": last_check_label,
        "auto_assigned": auto_upcoming,
        "auto_session_at": str(auto_session.get("session_at", "")),
        "auto_session_label": str(auto_session.get("session_label", "")),
        "auto_counsellor_name": str(auto_session.get("counsellor_name", "")),
        "auto_counsellor_email": str(auto_session.get("counsellor_email", "")),
    }


def build_student_profile_badges(student_email, stress_category, mood_battery, weekly_logs):
    attempts = list_student_quiz_attempts(student_email, limit=8)
    counselling = student_counselling_snapshot(student_email, stress_category)
    saved_state = load_student_score_state(student_email) or {}

    try:
        battery = int(saved_state.get("mental_battery", mood_battery) or mood_battery or 0)
    except (TypeError, ValueError):
        battery = int(mood_battery or 0)
    battery = max(0, min(100, battery))

    stress_values = [int(item.get("stress", 0) or 0) for item in (weekly_logs or [])]
    weekly_avg_stress = int(round(sum(stress_values) / max(1, len(stress_values)))) if stress_values else 0

    quiz_scores = [int(item.get("score_percent", 0) or 0) for item in attempts]
    quiz_attempt_count = len(quiz_scores)
    quiz_average = int(round(sum(quiz_scores) / max(1, quiz_attempt_count))) if quiz_scores else 0

    session_keeper_unlocked = bool(counselling.get("booked")) and bool(counselling.get("attended"))
    health_index_unlocked = battery >= 72 and (weekly_avg_stress == 0 or weekly_avg_stress <= 48)
    quiz_consistency_unlocked = quiz_attempt_count >= 3 and quiz_average >= 75

    return [
        {
            "key": "session_keeper",
            "label": "Session Keeper",
            "icon": "verified_user",
            "tone": "emerald",
            "unlocked": session_keeper_unlocked,
            "description": "No missed counselling check-ins in recent weeks.",
            "progress": (
                "Great follow-through with your support sessions."
                if session_keeper_unlocked
                else "Complete your next counselling session to unlock this badge."
            ),
        },
        {
            "key": "health_index_hero",
            "label": "Health Index Hero",
            "icon": "monitoring",
            "tone": "sky",
            "unlocked": health_index_unlocked,
            "description": "Strong health index with stable weekly stress trend.",
            "progress": (
                f"Battery {battery}% and weekly average stress {weekly_avg_stress}."
                if health_index_unlocked
                else f"Keep battery above 72% and weekly stress near 48 or lower (now {weekly_avg_stress})."
            ),
        },
        {
            "key": "quiz_consistency",
            "label": "Consistency Scholar",
            "icon": "military_tech",
            "tone": "amber",
            "unlocked": quiz_consistency_unlocked,
            "description": "Consistent quiz performance across multiple check-ins.",
            "progress": (
                f"Average {quiz_average}% over {quiz_attempt_count} attempts."
                if quiz_consistency_unlocked
                else f"Reach 3 attempts with 75%+ average (now {quiz_attempt_count} attempts at {quiz_average}%)."
            ),
        },
    ]


def build_mock_parent_dashboard_context(parent_email):
    guardian_email = str(parent_email or "parent.demo@eqwell.app").strip().lower() or "parent.demo@eqwell.app"
    weekly_logs = [
        {"day": "Mon", "stress": 61},
        {"day": "Tue", "stress": 58},
        {"day": "Wed", "stress": 56},
        {"day": "Thu", "stress": 54},
        {"day": "Fri", "stress": 53},
        {"day": "Sat", "stress": 51},
        {"day": "Sun", "stress": 49},
    ]
    recent_attempts = [
        {
            "quiz_title": "MindBalance Check",
            "score_percent": 68,
            "risk_band": "MODERATE",
            "created_at_label": "today 09:20",
        },
        {
            "quiz_title": "CalmPulse Assessment",
            "score_percent": 71,
            "risk_band": "MODERATE",
            "created_at_label": "yesterday 19:15",
        },
        {
            "quiz_title": "StressLoad Analyzer",
            "score_percent": 74,
            "risk_band": "LOW",
            "created_at_label": "2 days ago",
        },
    ]

    student_profile = {
        "name": "Ariana Vale",
        "email": "student@eqwell.app",
        "hostel_block": "Block A",
        "battery": 63,
        "stress_percent": 47,
        "stress_category": "MODERATE",
        "updated_at_label": "today 10:30",
    }

    parent_analysis = {
        "weekly_average": 55,
        "weekly_peak": 61,
        "weekly_low": 49,
        "momentum_label": "Improving",
        "risk_level": "Moderate",
        "recommendations": [
            "Keep sleep above 7 hours for at least 5 days this week.",
            "Maintain one short evening check-in to reduce overthinking.",
            "Book one counsellor follow-up if stress rises for two consecutive days.",
        ],
        "recent_attempts": recent_attempts,
    }

    return {
        "parent_guardian_profile": {
            "name": "Ananya Raman",
            "email": guardian_email,
            "member_since": "Jan 2026",
            "status_label": "Demo View",
        },
        "parent_student_profile": student_profile,
        "parent_snapshot": {
            "student_name": student_profile["name"],
            "hostel_block": student_profile["hostel_block"],
            "battery": student_profile["battery"],
            "stress_percent": student_profile["stress_percent"],
            "stress_category": student_profile["stress_category"],
            "updated_at_label": student_profile["updated_at_label"],
        },
        "parent_analysis": parent_analysis,
        "parent_recent_attempts": recent_attempts,
        "parent_weekly_logs": weekly_logs,
        "parent_trend_label": "Stress trend improving",
        "parent_alerts": [
            "Late-night usage increased on Tuesday and Wednesday.",
            "Sleep dipped below 6.5h once this week.",
            "No critical risk event in the last 72 hours.",
        ],
        "parent_lifestyle": {
            "sleep_hours": 6.9,
            "steps": 6480,
            "fitness_component": 3.6,
        },
        "parent_lifestyle_insights": {
            "sleep_hours": 6.9,
            "steps": 6480,
            "fitness_component": 3.6,
            "sleep_status": "Improving",
            "activity_status": "Active",
        },
        "parent_counselling": {
            "booked": True,
            "attended": True,
            "booked_label": "Booked",
            "attended_label": "Attended",
            "needs_help": True,
            "last_check_label": "today 08:40",
        },
        "parent_contact_cards": [
            {"role": "Counsellor", "name": "Dr. Aris", "email": "counsellor@eqwell.app", "channel": "Campus wellness office"},
            {"role": "Warden", "name": "Warden Mitchell", "email": "warden@eqwell.app", "channel": "Hostel block office"},
            {"role": "Proctor", "name": "Proctor Access", "email": "proctor@eqwell.app", "channel": "Assigned proctor desk"},
            {"role": "Emergency", "name": "Campus Help Desk", "email": "support@eqwell.app", "channel": "24x7 safety line"},
        ],
        "parent_proctor_email": "proctor@eqwell.app",
        "parent_privacy_line": "Demo data shown for representation. No sensitive logs are exposed.",
    }


def build_mock_proctor_dashboard_context(proctor_email):
    proctor_profile = {
        "name": "Proctor Access",
        "email": str(proctor_email or "proctor@eqwell.app").strip().lower() or "proctor@eqwell.app",
        "member_since": "Jan 2026",
        "status_label": "Demo View",
    }

    seed_students = [
        {"name": "Ariana Vale", "email": "student1@eqwell.app", "hostel_block": "Block A", "stress": 71, "battery": 44, "sleep": 5.8, "steps": 4120, "trend": "rising"},
        {"name": "Dev Nair", "email": "student2@eqwell.app", "hostel_block": "Block B", "stress": 62, "battery": 52, "sleep": 6.3, "steps": 5320, "trend": "steady"},
        {"name": "Maya Jain", "email": "student3@eqwell.app", "hostel_block": "Block C", "stress": 77, "battery": 39, "sleep": 5.4, "steps": 3900, "trend": "rising"},
        {"name": "Rohan Paul", "email": "student4@eqwell.app", "hostel_block": "Block D1", "stress": 55, "battery": 59, "sleep": 6.7, "steps": 6480, "trend": "improving"},
        {"name": "Isha Khan", "email": "student5@eqwell.app", "hostel_block": "Block D2", "stress": 48, "battery": 64, "sleep": 7.1, "steps": 7210, "trend": "steady"},
        {"name": "Kabir Sen", "email": "student6@eqwell.app", "hostel_block": "Block E", "stress": 67, "battery": 49, "sleep": 6.0, "steps": 5030, "trend": "rising"},
        {"name": "Nina Roy", "email": "student7@eqwell.app", "hostel_block": "Block A", "stress": 53, "battery": 61, "sleep": 6.8, "steps": 6720, "trend": "improving"},
        {"name": "Arjun Das", "email": "student8@eqwell.app", "hostel_block": "Block B", "stress": 59, "battery": 56, "sleep": 6.5, "steps": 5840, "trend": "steady"},
    ]

    def _status_from_stress(stress_percent):
        if stress_percent >= 70:
            return "HIGH", "High"
        if stress_percent >= 55:
            return "MODERATE", "Watch"
        return "LOW", "Stable"

    students_payload = []
    for idx, seed in enumerate(seed_students):
        category, status_label = _status_from_stress(int(seed["stress"]))
        students_payload.append(
            {
                "id": f"demo{idx + 1}",
                "name": seed["name"],
                "email": seed["email"],
                "hostel_block": seed["hostel_block"],
                "battery": int(seed["battery"]),
                "stress_percent": int(seed["stress"]),
                "stress_category": category,
                "status_label": status_label,
                "trend_label": seed["trend"],
                "weekly_logs": [
                    {"day": "Mon", "stress": max(35, int(seed["stress"]) - 4)},
                    {"day": "Tue", "stress": max(35, int(seed["stress"]) - 2)},
                    {"day": "Wed", "stress": int(seed["stress"]), "stress_value": int(seed["stress"])},
                    {"day": "Thu", "stress": int(seed["stress"]) + (2 if seed["trend"] == "rising" else -1)},
                    {"day": "Fri", "stress": int(seed["stress"]) + (3 if seed["trend"] == "rising" else -2)},
                    {"day": "Sat", "stress": int(seed["stress"]) - 1},
                    {"day": "Sun", "stress": int(seed["stress"]) - 2},
                ],
                "updated_at_label": "today",
                "counselling": {
                    "booked": True,
                    "attended": category != "HIGH",
                    "booked_label": "Booked",
                    "attended_label": "Attended" if category != "HIGH" else "Pending",
                    "needs_help": category != "LOW",
                },
                "sleep_hours": float(seed["sleep"]),
                "steps": int(seed["steps"]),
                "fitness_component": round(min(5.0, max(2.5, (float(seed["sleep"]) + (int(seed["steps"]) / 3000.0)) / 2.4)), 1),
                "recent_attempts": [
                    {"quiz_title": "MindBalance Check", "score_percent": max(45, 100 - int(seed["stress"])), "risk_band": status_label.upper(), "created_at_label": "today"},
                    {"quiz_title": "CalmPulse Assessment", "score_percent": max(45, 98 - int(seed["stress"])), "risk_band": status_label.upper(), "created_at_label": "2 days ago"},
                ],
                "analysis_note": "Immediate intervention suggested" if category == "HIGH" else ("Track trend and maintain weekly check-in" if category == "MODERATE" else "Maintain preventive routine"),
            }
        )

    high_count = sum(1 for student in students_payload if student["stress_category"] == "HIGH")
    watch_count = sum(1 for student in students_payload if student["stress_category"] == "MODERATE")
    stable_count = sum(1 for student in students_payload if student["stress_category"] == "LOW")
    avg_stress = int(round(sum(student["stress_percent"] for student in students_payload) / max(1, len(students_payload))))
    avg_battery = int(round(sum(student["battery"] for student in students_payload) / max(1, len(students_payload))))

    group_weekly_logs = [
        {"day": "Mon", "stress": 64},
        {"day": "Tue", "stress": 62},
        {"day": "Wed", "stress": 63},
        {"day": "Thu", "stress": 61},
        {"day": "Fri", "stress": 60},
        {"day": "Sat", "stress": 58},
        {"day": "Sun", "stress": 57},
    ]

    hostel_counts = {}
    for student in students_payload:
        hostel_counts[student["hostel_block"]] = hostel_counts.get(student["hostel_block"], 0) + 1
    hostel_distribution = [{"label": label, "count": hostel_counts[label]} for label in sorted(hostel_counts.keys())]

    priority_students = sorted(
        students_payload,
        key=lambda item: (-int(item.get("stress_percent", 0)), int(item.get("battery", 0))),
    )[:6]

    return {
        "proctor_profile": proctor_profile,
        "proctor_students": students_payload,
        "proctor_group_weekly_logs": group_weekly_logs,
        "proctor_alerts": [
            f"{high_count} students are currently in high-risk range.",
            f"{watch_count} students are on watchlist this week.",
            "Follow up with the top two priority students before evening round.",
        ],
        "proctor_total_students": len(students_payload),
        "proctor_high_count": high_count,
        "proctor_watch_count": watch_count,
        "proctor_stable_count": stable_count,
        "proctor_avg_stress": avg_stress,
        "proctor_avg_battery": avg_battery,
        "proctor_hostel_distribution": hostel_distribution,
        "proctor_priority_students": priority_students,
        "proctor_counselling_overview": {
            "booked": 6,
            "needs_help": high_count + watch_count,
            "attended": 5,
        },
        "proctor_contact_cards": [
            {"role": "Counsellor", "name": "Dr. Aris", "email": "counsellor@eqwell.app", "channel": "Wellness center"},
            {"role": "Warden", "name": "Warden Mitchell", "email": "warden@eqwell.app", "channel": "Hostel command desk"},
            {"role": "Developer", "name": "Ops User", "email": "ops_user@eqwell.app", "channel": "System escalation"},
        ],
        "proctor_summary_narrative": f"Demo roster loaded: {high_count} high-risk and {watch_count} watchlist students currently require supervision.",
        "proctor_default_student": priority_students[0] if priority_students else None,
        "proctor_privacy_line": "Demo data shown for representation. Sensitive personal logs remain hidden.",
    }


def build_mock_warden_dashboard_context():
    block_cards = [
        {"label": "Block A", "health_index": 76, "students": 82, "note": "Balanced with exam-week spikes", "high": 8, "moderate": 24, "low": 50},
        {"label": "Block B", "health_index": 80, "students": 78, "note": "Strong recovery trend", "high": 6, "moderate": 19, "low": 53},
        {"label": "Block C", "health_index": 63, "students": 74, "note": "Moderate stress cluster", "high": 13, "moderate": 27, "low": 34},
        {"label": "Block D1", "health_index": 58, "students": 69, "note": "High-risk signals detected", "high": 16, "moderate": 25, "low": 28},
        {"label": "Block D2", "health_index": 66, "students": 71, "note": "Workload pressure signals", "high": 11, "moderate": 23, "low": 37},
        {"label": "Block E", "health_index": 83, "students": 75, "note": "Most stable wellbeing block", "high": 4, "moderate": 15, "low": 56},
    ]

    warden_students = [
        {"name": "Ariana Vale", "email": "student1@eqwell.app", "hostel_block": "Block A", "stress_category": "HIGH", "status_label": "High", "stress_percent": 74, "mental_battery": 41, "updated_at_label": "today 09:10"},
        {"name": "Dev Nair", "email": "student2@eqwell.app", "hostel_block": "Block B", "stress_category": "MODERATE", "status_label": "Watch", "stress_percent": 59, "mental_battery": 52, "updated_at_label": "today 08:54"},
        {"name": "Maya Jain", "email": "student3@eqwell.app", "hostel_block": "Block C", "stress_category": "HIGH", "status_label": "High", "stress_percent": 79, "mental_battery": 36, "updated_at_label": "today 10:03"},
        {"name": "Rohan Paul", "email": "student4@eqwell.app", "hostel_block": "Block D1", "stress_category": "MODERATE", "status_label": "Watch", "stress_percent": 57, "mental_battery": 55, "updated_at_label": "today 07:58"},
        {"name": "Isha Khan", "email": "student5@eqwell.app", "hostel_block": "Block E", "stress_category": "LOW", "status_label": "Stable", "stress_percent": 44, "mental_battery": 67, "updated_at_label": "today 09:42"},
    ]

    return {
        "warden_total_signals": 449,
        "warden_alert_blocks": 4,
        "warden_counselling_demand": 131,
        "warden_avg_battery": 59,
        "warden_block_cards": block_cards,
        "warden_alerts": [
            "Block D1 has repeated high-risk signals in the last 24 hours.",
            "Block C reports elevated stress before assessment window.",
            "Block A has a moderate spike in late-night stress activity.",
        ],
        "warden_stress_factors": [
            {"label": "Academic pressure", "pct": 41},
            {"label": "Sleep debt", "pct": 33},
            {"label": "Social friction", "pct": 26},
        ],
        "warden_demand_split": {
            "pending": 54,
            "in_progress": 37,
            "completed": 46,
        },
        "warden_students": warden_students,
        "warden_weekly_trend": [
            {"day": "Mon", "stress": 64},
            {"day": "Tue", "stress": 62},
            {"day": "Wed", "stress": 65},
            {"day": "Thu", "stress": 63},
            {"day": "Fri", "stress": 61},
            {"day": "Sat", "stress": 58},
            {"day": "Sun", "stress": 56},
        ],
    }


def build_parent_dashboard_context(parent_email):
    student_rows = build_student_monitor_rows(limit=500)
    if len(student_rows) < 1:
        return build_mock_parent_dashboard_context(parent_email)

    row_lookup = {str(row.get("email", "")).strip().lower(): row for row in student_rows if str(row.get("email", "")).strip()}
    student_emails = sorted(row_lookup.keys())

    assigned_email = ensure_parent_assignment(parent_email, student_emails)
    student_row = row_lookup.get(assigned_email)
    if not student_row and student_rows:
        student_row = student_rows[0]
        assigned_email = str(student_row.get("email", "")).strip().lower()

    if not student_row:
        student_row = {
            "name": "Student",
            "stress_category": "MODERATE",
            "stress_score": 3.0,
            "mental_battery": 40,
            "hostel_block": "Block A",
            "updated_at_label": "recently",
        }
        assigned_email = ""

    battery = int(student_row.get("mental_battery", 40) or 40)
    stress_score = float(student_row.get("stress_score", 3.0) or 3.0)
    stress_percent = max(0, min(100, int(round(stress_score * 20))))
    stress_category = str(student_row.get("stress_category", "MODERATE")).upper()

    weekly_logs = build_student_weekly_logs(assigned_email, battery) if assigned_email else build_student_weekly_logs("fallback@eqwell.app", battery)
    trend_delta = weekly_stress_delta(weekly_logs)
    if trend_delta <= -4:
        trend_label = "Stress trend improving"
    elif trend_delta >= 4:
        trend_label = "Stress trend elevated"
    else:
        trend_label = "Stress trend stable"

    fit = get_google_fit_overview(assigned_email) if assigned_email else {}
    lifestyle = {
        "sleep_hours": round(float(fit.get("sleep_hours", 0.0) or 0.0), 1),
        "steps": int(fit.get("steps", 0) or 0),
        "fitness_component": round(float(fit.get("fitness_component", 3.0) or 3.0), 1),
    }

    counselling = student_counselling_snapshot(assigned_email, stress_category) if assigned_email else {
        "booked_label": "Not scheduled",
        "attended_label": "Not scheduled",
        "last_check_label": "no recent check",
        "needs_help": False,
        "booked": False,
        "attended": False,
    }

    proctor_email = load_student_assigned_proctor(assigned_email) if assigned_email else ""
    analysis = build_student_analysis_summary(
        assigned_email,
        student_row,
        weekly_logs,
        lifestyle,
        counselling,
    )

    recent_attempts = list(analysis.get("recent_attempts", []))
    has_lifestyle_data = float(lifestyle.get("sleep_hours", 0.0) or 0.0) > 0 or int(lifestyle.get("steps", 0) or 0) > 0
    has_weekly_data = any(int(item.get("stress", 0) or 0) > 0 for item in weekly_logs)
    if (not assigned_email) or ((not has_lifestyle_data) and (not has_weekly_data) and (not recent_attempts)):
        return build_mock_parent_dashboard_context(parent_email)

    resolved_student_email = assigned_email or str(student_row.get("email", "")).strip().lower()

    student_profile = {
        "name": str(student_row.get("name", "Student")),
        "email": resolved_student_email,
        "hostel_block": str(student_row.get("hostel_block", "Block A")),
        "battery": battery,
        "stress_percent": stress_percent,
        "stress_category": stress_category,
        "updated_at_label": str(student_row.get("updated_at_label", "recently")),
    }

    lifestyle_insights = {
        "sleep_hours": lifestyle["sleep_hours"],
        "steps": lifestyle["steps"],
        "fitness_component": lifestyle["fitness_component"],
        "sleep_status": "Low" if 0 < float(lifestyle["sleep_hours"]) < 6 else "Healthy",
        "activity_status": "Low" if int(lifestyle["steps"] or 0) < 5000 else "Active",
    }

    alerts = []
    recent_three = weekly_logs[-3:]
    if recent_three and all(int(item.get("stress", 0) or 0) >= 65 for item in recent_three):
        alerts.append("Stress level has remained high for the last 3 days.")
    if float(lifestyle["sleep_hours"]) > 0 and float(lifestyle["sleep_hours"]) < 6.0:
        alerts.append("Low sleep duration detected recently.")
    if stress_category == "HIGH":
        alerts.append("Current wellbeing status is in high-risk range and needs support.")
    if not alerts:
        alerts.append("No active wellbeing alerts right now.")

    return {
        "parent_guardian_profile": build_role_profile(parent_email, "Parent / Guardian", "Parent User"),
        "parent_student_profile": student_profile,
        "parent_snapshot": {
            "student_name": str(student_row.get("name", "Student")),
            "hostel_block": str(student_row.get("hostel_block", "Block A")),
            "battery": battery,
            "stress_percent": stress_percent,
            "stress_category": stress_category,
            "updated_at_label": str(student_row.get("updated_at_label", "recently")),
        },
        "parent_analysis": analysis,
        "parent_recent_attempts": recent_attempts,
        "parent_weekly_logs": weekly_logs,
        "parent_trend_label": trend_label,
        "parent_alerts": alerts,
        "parent_lifestyle": lifestyle,
        "parent_lifestyle_insights": lifestyle_insights,
        "parent_counselling": counselling,
        "parent_contact_cards": build_support_contacts(assigned_email, proctor_email=proctor_email),
        "parent_proctor_email": proctor_email,
        "parent_privacy_line": "Parents receive only summarized wellbeing insights.",
    }


def build_proctor_dashboard_context(proctor_email):
    student_rows = build_student_monitor_rows(limit=900)
    row_lookup = {str(row.get("email", "")).strip().lower(): row for row in student_rows if str(row.get("email", "")).strip()}
    all_student_emails = sorted(row_lookup.keys())

    assigned_emails = ensure_proctor_assignments(proctor_email, all_student_emails, target_size=24)
    assigned_rows = [row_lookup[email] for email in assigned_emails if email in row_lookup]
    if not assigned_rows:
        assigned_rows = student_rows[:24]
    if len(assigned_rows) < 6:
        return build_mock_proctor_dashboard_context(proctor_email)

    students_payload = []
    group_weekly_totals = [0] * 7
    group_weekly_counts = [0] * 7
    counselling_booked = 0
    counselling_need_help = 0
    counselling_attended = 0

    for idx, row in enumerate(assigned_rows):
        student_email = str(row.get("email", "")).strip().lower()
        battery = int(row.get("mental_battery", 40) or 40)
        stress_score = float(row.get("stress_score", 3.0) or 3.0)
        stress_percent = max(0, min(100, int(round(stress_score * 20))))
        stress_category = str(row.get("stress_category", "MODERATE")).upper()

        weekly_logs = build_student_weekly_logs(student_email, battery)
        for day_index, day in enumerate(weekly_logs[:7]):
            group_weekly_totals[day_index] += int(day.get("stress", 0) or 0)
            group_weekly_counts[day_index] += 1

        delta = weekly_stress_delta(weekly_logs)
        if delta >= 5:
            trend_label = "rising"
        elif delta <= -5:
            trend_label = "improving"
        else:
            trend_label = "steady"

        counselling = student_counselling_snapshot(student_email, stress_category)
        if counselling.get("booked"):
            counselling_booked += 1
        if counselling.get("attended"):
            counselling_attended += 1
        if counselling.get("needs_help"):
            counselling_need_help += 1

        fit = get_google_fit_overview(student_email)
        recent_attempts = list_student_quiz_attempts(student_email, limit=2)

        status_label = "Stable"
        if stress_category == "HIGH":
            status_label = "High"
        elif stress_category == "MODERATE":
            status_label = "Watch"

        students_payload.append(
            {
                "id": f"p{idx + 1}",
                "name": str(row.get("name", "Student")),
                "email": student_email,
                "hostel_block": str(row.get("hostel_block", "Block A")),
                "battery": battery,
                "stress_percent": stress_percent,
                "stress_category": stress_category,
                "status_label": status_label,
                "trend_label": trend_label,
                "weekly_logs": weekly_logs,
                "updated_at_label": str(row.get("updated_at_label", "recently")),
                "counselling": counselling,
                "sleep_hours": round(float(fit.get("sleep_hours", 0.0) or 0.0), 1),
                "steps": int(fit.get("steps", 0) or 0),
                "fitness_component": round(float(fit.get("fitness_component", 3.0) or 3.0), 1),
                "recent_attempts": [
                    {
                        "quiz_title": str(attempt.get("quiz_title", "Quiz")),
                        "score_percent": int(attempt.get("score_percent", 0) or 0),
                        "risk_band": str(attempt.get("risk_band", "MODERATE")),
                        "created_at_label": str(attempt.get("created_at_label", "recently")),
                    }
                    for attempt in recent_attempts
                ],
                "analysis_note": (
                    "Immediate intervention suggested" if stress_category == "HIGH" else (
                        "Track trend and maintain weekly check-in" if stress_category == "MODERATE" else "Maintain preventive routine"
                    )
                ),
            }
        )

    high_count = sum(1 for student in students_payload if student.get("stress_category") == "HIGH")
    watch_count = sum(1 for student in students_payload if student.get("stress_category") == "MODERATE")
    stable_count = sum(1 for student in students_payload if student.get("stress_category") == "LOW")
    sudden_change_count = sum(1 for student in students_payload if student.get("trend_label") in {"rising", "improving"})

    avg_stress = int(round(sum(student.get("stress_percent", 0) for student in students_payload) / max(1, len(students_payload))))
    avg_battery = int(round(sum(student.get("battery", 0) for student in students_payload) / max(1, len(students_payload))))

    group_weekly_logs = []
    day_labels = students_payload[0].get("weekly_logs", []) if students_payload else []
    for day_index in range(min(7, len(day_labels))):
        avg_day_stress = int(round(group_weekly_totals[day_index] / max(1, group_weekly_counts[day_index])))
        group_weekly_logs.append(
            {
                "day": str(day_labels[day_index].get("day", "Day")),
                "stress": avg_day_stress,
            }
        )

    alerts = []
    if high_count > 0:
        alerts.append(f"{high_count} students are currently in high-risk range.")
    if sudden_change_count > 0:
        alerts.append(f"{sudden_change_count} students show sudden trend changes this week.")
    if counselling_need_help > counselling_booked:
        alerts.append("Some students need support but have no recent counselling booking.")
    if not alerts:
        alerts.append("No critical proctor alerts right now.")

    hostel_distribution = []
    hostel_counts = {}
    for student in students_payload:
        label = str(student.get("hostel_block", "Block A"))
        hostel_counts[label] = hostel_counts.get(label, 0) + 1
    for label in sorted(hostel_counts.keys()):
        hostel_distribution.append({"label": label, "count": int(hostel_counts[label])})

    priority_students = sorted(
        students_payload,
        key=lambda item: (-int(item.get("stress_percent", 0)), int(item.get("battery", 0))),
    )[:6]

    default_student = None
    for student in students_payload:
        if student.get("stress_category") == "HIGH":
            default_student = student
            break
    if not default_student and students_payload:
        default_student = students_payload[0]

    return {
        "proctor_profile": build_role_profile(proctor_email, "Proctor", "Proctor User"),
        "proctor_students": students_payload,
        "proctor_group_weekly_logs": group_weekly_logs,
        "proctor_alerts": alerts,
        "proctor_total_students": len(students_payload),
        "proctor_high_count": high_count,
        "proctor_watch_count": watch_count,
        "proctor_stable_count": stable_count,
        "proctor_avg_stress": avg_stress,
        "proctor_avg_battery": avg_battery,
        "proctor_hostel_distribution": hostel_distribution,
        "proctor_priority_students": priority_students,
        "proctor_counselling_overview": {
            "booked": counselling_booked,
            "needs_help": counselling_need_help,
            "attended": counselling_attended,
        },
        "proctor_contact_cards": build_support_contacts(),
        "proctor_summary_narrative": (
            f"{high_count} high-risk and {watch_count} watchlist students are currently in your group."
            if len(students_payload)
            else "No assigned students found for this proctor yet."
        ),
        "proctor_default_student": default_student,
        "proctor_privacy_line": "Proctor view excludes chat logs, browsing trails, and sensitive personal details.",
    }


@app.get("/parent/overview")
@login_required
@role_required("parent")
def parent_overview_page():
    parent_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "parent_dashboard.html",
        page_title="Parent Dashboard",
        page_subtitle="Ward overview and summary signals.",
        active_nav="overview",
        display_name=str(session.get("name") or parent_email or "Parent User"),
        **build_parent_dashboard_context(parent_email),
    )


@app.get("/parent/weekly-trend")
@login_required
@role_required("parent")
def parent_weekly_trend_page():
    parent_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "parent_weekly_trend.html",
        page_title="Parent Weekly Trend",
        page_subtitle="Detailed weekly stress analysis.",
        active_nav="weekly-trend",
        display_name=str(session.get("name") or parent_email or "Parent User"),
        **build_parent_dashboard_context(parent_email),
    )


@app.get("/parent/alerts")
@login_required
@role_required("parent")
def parent_alerts_page():
    parent_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "parent_alerts.html",
        page_title="Parent Alerts",
        page_subtitle="Risk alerts and action guidance.",
        active_nav="alerts",
        display_name=str(session.get("name") or parent_email or "Parent User"),
        **build_parent_dashboard_context(parent_email),
    )


@app.get("/parent/lifestyle")
@login_required
@role_required("parent")
def parent_lifestyle_page():
    parent_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "parent_lifestyle.html",
        page_title="Parent Lifestyle",
        page_subtitle="Sleep, activity, and balance indicators.",
        active_nav="lifestyle",
        display_name=str(session.get("name") or parent_email or "Parent User"),
        **build_parent_dashboard_context(parent_email),
    )


@app.get("/parent/contact")
@login_required
@role_required("parent")
def parent_contact_page():
    parent_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "parent_contact.html",
        page_title="Parent Contact",
        page_subtitle="Support channels and escalation contacts.",
        active_nav="contact",
        display_name=str(session.get("name") or parent_email or "Parent User"),
        **build_parent_dashboard_context(parent_email),
    )


@app.get("/proctor/overview")
@login_required
@role_required("proctor")
def proctor_overview_page():
    proctor_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "proctor_dashboard.html",
        page_title="Proctor Dashboard",
        page_subtitle="Group overview and student risk summary.",
        active_nav="overview",
        display_name=str(session.get("name") or proctor_email or "Proctor User"),
        **build_proctor_dashboard_context(proctor_email),
    )


@app.get("/proctor/students")
@login_required
@role_required("proctor")
def proctor_students_page():
    proctor_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "proctor_students.html",
        page_title="Proctor Students",
        page_subtitle="Detailed ward-level student profiles.",
        active_nav="students",
        display_name=str(session.get("name") or proctor_email or "Proctor User"),
        **build_proctor_dashboard_context(proctor_email),
    )


@app.get("/proctor/analytics")
@login_required
@role_required("proctor")
def proctor_analytics_page():
    proctor_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "proctor_analytics.html",
        page_title="Proctor Analytics",
        page_subtitle="Group patterns, trends, and distribution.",
        active_nav="analytics",
        display_name=str(session.get("name") or proctor_email or "Proctor User"),
        **build_proctor_dashboard_context(proctor_email),
    )


@app.get("/proctor/alerts")
@login_required
@role_required("proctor")
def proctor_alerts_page():
    proctor_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "proctor_alerts.html",
        page_title="Proctor Alerts",
        page_subtitle="Risk alerts and intervention checklist.",
        active_nav="alerts",
        display_name=str(session.get("name") or proctor_email or "Proctor User"),
        **build_proctor_dashboard_context(proctor_email),
    )


@app.get("/proctor/contact")
@login_required
@role_required("proctor")
def proctor_contact_page():
    proctor_email = str(session.get("email", "")).strip().lower()
    return render_template(
        "proctor_contact.html",
        page_title="Proctor Contact",
        page_subtitle="Support coordination and contact channels.",
        active_nav="contact",
        display_name=str(session.get("name") or proctor_email or "Proctor User"),
        **build_proctor_dashboard_context(proctor_email),
    )


def build_warden_dashboard_context():
    student_rows = build_student_monitor_rows(limit=240)
    total_students = len(student_rows)
    if total_students < 12:
        return build_mock_warden_dashboard_context()

    high_count = sum(1 for row in student_rows if row.get("stress_category") == "HIGH")
    moderate_count = sum(1 for row in student_rows if row.get("stress_category") == "MODERATE")
    low_count = sum(1 for row in student_rows if row.get("stress_category") == "LOW")

    avg_battery = 0
    if total_students:
        avg_battery = int(round(sum(int(row.get("mental_battery", 0)) for row in student_rows) / total_students))

    block_labels = list(WARDEN_BLOCK_LABELS)
    block_buckets = {
        label: {"students": 0, "battery_total": 0, "high": 0, "moderate": 0, "low": 0}
        for label in block_labels
    }
    for row in student_rows:
        label = normalize_hostel_block(row.get("hostel_block"))
        if not label:
            email = str(row.get("email", ""))
            idx = sum(ord(ch) for ch in email) % len(block_labels) if email else 0
            label = block_labels[idx]
        bucket = block_buckets[label]
        bucket["students"] += 1
        bucket["battery_total"] += int(row.get("mental_battery", 0))
        if row.get("stress_category") == "HIGH":
            bucket["high"] += 1
        elif row.get("stress_category") == "MODERATE":
            bucket["moderate"] += 1
        else:
            bucket["low"] += 1

    block_cards = []
    for label in block_labels:
        bucket = block_buckets[label]
        students = int(bucket.get("students", 0))
        health_index = int(round(bucket["battery_total"] / students)) if students else 0
        note = "Stable wellbeing pattern"
        if bucket.get("high", 0) > 0:
            note = "High-risk signals detected"
        elif bucket.get("moderate", 0) > max(1, students // 2):
            note = "Moderate stress cluster"
        block_cards.append(
            {
                "label": label,
                "health_index": health_index,
                "students": students,
                "note": note,
                "high": int(bucket.get("high", 0)),
                "moderate": int(bucket.get("moderate", 0)),
                "low": int(bucket.get("low", 0)),
            }
        )

    sorted_alert_rows = [
        row for row in student_rows if row.get("stress_category") in {"HIGH", "MODERATE"}
    ]
    warden_alerts = []
    for row in sorted_alert_rows[:5]:
        category = str(row.get("stress_category", "MODERATE")).title()
        alert_text = (
            f"{row.get('name')} marked {category} stress at {row.get('updated_at_label')} "
            f"(score {row.get('stress_score')}/5)."
        )
        warden_alerts.append(alert_text)

    if not warden_alerts:
        warden_alerts = ["No active alerts. Signals are currently stable campus-wide."]

    component_values = {"chatbot": 0.0, "fitness": 0.0, "counsellor": 0.0}
    component_count = 0
    for row in student_rows[:120]:
        components = get_student_multimodal_components(row.get("email", ""))
        component_values["chatbot"] += float(components.get("chatbot", 3.0))
        component_values["fitness"] += float(components.get("fitness", 3.0))
        component_values["counsellor"] += float(components.get("counsellor", COUNSELLOR_DEFAULT_SCORE))
        component_count += 1

    if component_count > 0:
        avg_chat = component_values["chatbot"] / component_count
        avg_fitness = component_values["fitness"] / component_count
        avg_social = component_values["counsellor"] / component_count
    else:
        avg_chat = avg_fitness = avg_social = 3.0

    raw_factors = {
        "Academic pressure": avg_chat,
        "Sleep debt": avg_fitness,
        "Social friction": avg_social,
    }
    raw_total = sum(raw_factors.values()) or 1.0
    stress_factors = []
    running_total = 0
    factor_items = list(raw_factors.items())
    for index, (label, value) in enumerate(factor_items):
        if index == len(factor_items) - 1:
            pct = max(0, 100 - running_total)
        else:
            pct = int(round((value / raw_total) * 100))
            running_total += pct
        stress_factors.append({"label": label, "pct": pct})

    in_progress = max(0, moderate_count // 2)
    completed = max(0, low_count // 2)
    pending = max(0, high_count + moderate_count - in_progress)

    warden_students = []
    for row in student_rows[:80]:
        category = str(row.get("stress_category", "MODERATE")).upper()
        if category == "HIGH":
            status_label = "High"
        elif category == "LOW":
            status_label = "Stable"
        else:
            status_label = "Watch"

        warden_students.append(
            {
                "name": str(row.get("name", "Student")),
                "email": str(row.get("email", "")),
                "hostel_block": str(row.get("hostel_block", "")),
                "stress_category": category,
                "status_label": status_label,
                "stress_percent": max(0, min(100, int(round(float(row.get("stress_score", 3.0)) * 20.0)))),
                "mental_battery": max(0, min(100, int(row.get("mental_battery", 0)))),
                "updated_at_label": str(row.get("updated_at_label", "recently")),
            }
        )

    weekly_trend = [
        {"day": "Mon", "stress": max(35, min(95, int(round(58 + (high_count * 0.9) - (low_count * 0.2)))))},
        {"day": "Tue", "stress": max(35, min(95, int(round(56 + (high_count * 0.8) - (low_count * 0.2)))))},
        {"day": "Wed", "stress": max(35, min(95, int(round(59 + (high_count * 0.85) - (low_count * 0.25)))))},
        {"day": "Thu", "stress": max(35, min(95, int(round(57 + (high_count * 0.75) - (low_count * 0.2)))))},
        {"day": "Fri", "stress": max(35, min(95, int(round(55 + (high_count * 0.7) - (low_count * 0.2)))))},
        {"day": "Sat", "stress": max(30, min(92, int(round(52 + (high_count * 0.55) - (low_count * 0.28)))))},
        {"day": "Sun", "stress": max(28, min(90, int(round(50 + (high_count * 0.5) - (low_count * 0.3)))))},
    ]

    return {
        "warden_total_signals": max(total_students, len(list_student_score_snapshots(limit=1200))),
        "warden_alert_blocks": sum(1 for card in block_cards if card.get("high", 0) > 0),
        "warden_counselling_demand": high_count + moderate_count,
        "warden_avg_battery": avg_battery,
        "warden_block_cards": block_cards,
        "warden_alerts": warden_alerts,
        "warden_stress_factors": stress_factors,
        "warden_demand_split": {
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
        },
        "warden_students": warden_students,
        "warden_weekly_trend": weekly_trend,
    }


@app.get("/warden/overview")
@login_required
@role_required("warden")
def warden_overview_page():
    return render_template(
        "warden_dashboard.html",
        page_title="Warden Dashboard",
        page_subtitle="Campus overview and signal health summary.",
        active_nav="overview",
        **build_warden_dashboard_context(),
    )


@app.get("/warden/students")
@login_required
@role_required("warden")
def warden_students_page():
    return render_template(
        "warden_students.html",
        page_title="Warden Students",
        page_subtitle="Student-wise status and hostel coverage.",
        active_nav="students",
        **build_warden_dashboard_context(),
    )


@app.get("/warden/analytics")
@login_required
@role_required("warden")
def warden_analytics_page():
    return render_template(
        "warden_analytics.html",
        page_title="Warden Analytics",
        page_subtitle="Visual analytics for block risk and trends.",
        active_nav="analytics",
        **build_warden_dashboard_context(),
    )


@app.get("/warden/alerts")
@login_required
@role_required("warden")
def warden_alerts_page():
    return render_template(
        "warden_alerts.html",
        page_title="Warden Alerts",
        page_subtitle="Active risk alerts and counselling demand.",
        active_nav="alerts",
        **build_warden_dashboard_context(),
    )


def build_counsellor_dashboard_context():
    student_rows = build_student_monitor_rows(limit=220)
    total_students = len(student_rows)
    high_rows = [row for row in student_rows if row.get("stress_category") == "HIGH"]
    moderate_rows = [row for row in student_rows if row.get("stress_category") == "MODERATE"]
    queue_rows = (high_rows + moderate_rows + student_rows)[:3]

    focus_by_category = {
        "HIGH": "Crisis Intervention",
        "MODERATE": "Stress Management",
        "LOW": "Regular Check-in",
    }

    times = [
        {"from": "Now", "to": "10:30", "location": "Room 402"},
        {"from": "12:00", "to": "13:00", "location": "Virtual"},
        {"from": "14:30", "to": "15:30", "location": "Room 108"},
    ]

    counsellor_schedule = []
    for index, slot in enumerate(times):
        row = queue_rows[index] if index < len(queue_rows) else None
        category = str((row or {}).get("stress_category", "MODERATE")).upper()
        counsellor_schedule.append(
            {
                "status": "live" if index == 0 and row else "scheduled",
                "from": slot["from"],
                "to": slot["to"],
                "name": (row or {}).get("name", f"Student {index + 1}"),
                "focus": focus_by_category.get(category, "Regular Check-in"),
                "location": slot["location"],
                "category": category,
            }
        )

    component_values = {"extension": 0.0, "chatbot": 0.0, "counsellor": 0.0}
    sample_count = 0
    for row in student_rows[:120]:
        components = get_student_multimodal_components(row.get("email", ""))
        component_values["extension"] += float(components.get("extension", 3.0))
        component_values["chatbot"] += float(components.get("chatbot", 3.0))
        component_values["counsellor"] += float(components.get("counsellor", COUNSELLOR_DEFAULT_SCORE))
        sample_count += 1

    if sample_count > 0:
        avg_extension = component_values["extension"] / sample_count
        avg_chat = component_values["chatbot"] / sample_count
        avg_counsellor = component_values["counsellor"] / sample_count
    else:
        avg_extension = avg_chat = avg_counsellor = 3.0

    physiological_score = round(max(1.0, min(avg_extension * 2.0, 10.0)), 1)
    cognitive_score = round(max(1.0, min(avg_chat * 2.0, 10.0)), 1)
    social_score = round(max(1.0, min((6.0 - avg_counsellor) * 2.0, 10.0)), 1)

    high_count = len(high_rows)
    low_count = sum(1 for row in student_rows if row.get("stress_category") == "LOW")
    scheduled_count = len([item for item in counsellor_schedule if item.get("name")])

    validation_accuracy = 90.0
    if total_students > 0:
        validation_accuracy = 88.0 + min(10.0, total_students * 0.35) - min(5.0, high_count * 0.6)
    validation_accuracy = round(max(80.0, min(validation_accuracy, 99.0)), 1)

    recovery_rate = int(round((low_count / total_students) * 100)) if total_students else 0
    confidence_pct = int(round(max(55.0, min(98.0, 72.0 + (total_students * 1.5) - (high_count * 3.5)))))

    queue_items = []
    for row in queue_rows:
        queue_items.append(
            {
                "name": row.get("name", "Student"),
                "initials": "".join(part[:1] for part in str(row.get("name", "Student")).split()[:2]).upper() or "ST",
                "meta": f"{row.get('stress_category', 'MODERATE').title()} • {row.get('updated_at_label', 'recently')}",
                "priority": "High" if row.get("stress_category") == "HIGH" else "Queued",
            }
        )

    dominant_label = "Balanced"
    if high_count > len(moderate_rows):
        dominant_label = "Heightened"
    elif low_count > (high_count + len(moderate_rows)):
        dominant_label = "Calm"

    departments = [
        "Computer Science",
        "Electronics",
        "Mechanical",
        "Architecture",
        "Civil",
        "Biotech",
    ]
    year_labels = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
    month_labels = ["Jan", "Feb", "Mar", "Apr"]

    def clamp_percent(value):
        return max(0, min(int(round(value)), 100))

    counsellor_students = []
    for index, row in enumerate(student_rows[:24]):
        email = str(row.get("email", "")).strip().lower()
        if not email:
            continue

        seed = sum(ord(ch) for ch in email) + (index * 37)
        base_stress = clamp_percent(float(row.get("stress_score", 3.0)) * 20.0)
        battery = clamp_percent(row.get("mental_battery", calculate_mental_battery(float(row.get("stress_score", 3.0)))))
        dept = departments[seed % len(departments)]
        year = year_labels[seed % len(year_labels)]
        reg_year = 22 + (seed % 4)
        reg_code = ["CS", "EC", "ME", "AR", "CE", "BT"][seed % 6]
        reg_number = f"{reg_year}{reg_code}{1000 + (seed % 9000)}"
        hostel_label = str(row.get("hostel_block", "")).strip() or WARDEN_BLOCK_LABELS[seed % len(WARDEN_BLOCK_LABELS)]

        wellbeing = {
            "stress": base_stress,
            "anxiety": clamp_percent(base_stress + ((seed % 17) - 8)),
            "focus": clamp_percent((100 - base_stress) + ((seed % 13) - 6)),
            "sleep": clamp_percent(battery + ((seed % 11) - 5)),
            "mood": clamp_percent((100 - base_stress) + ((seed % 9) - 4)),
            "resilience": clamp_percent((100 - base_stress) + 8 + ((seed % 7) - 3)),
        }

        trends = []
        for month_index, month in enumerate(month_labels):
            drift = (month_index - 1) * -2
            trends.append(
                {
                    "m": month,
                    "stress": clamp_percent(base_stress + ((seed + month_index * 5) % 12) - 6 + drift),
                    "anxiety": clamp_percent(wellbeing["anxiety"] + ((seed + month_index * 4) % 10) - 5 + drift),
                    "focus": clamp_percent(wellbeing["focus"] + ((seed + month_index * 3) % 9) - 4 - drift),
                    "mood": clamp_percent(wellbeing["mood"] + ((seed + month_index * 2) % 8) - 4 - drift),
                }
            )

        heatmap = [
            clamp_percent(base_stress + ((seed + slot * 3) % 16) - 8)
            for slot in range(14)
        ]

        stress_category = str(row.get("stress_category", "MODERATE")).upper()
        notes = [
            f"Latest update: {row.get('updated_at_label', 'recently')}.",
            "Encourage structured decompression between classes.",
        ]
        if stress_category == "HIGH":
            notes = [
                f"High-risk pattern detected at {row.get('updated_at_label', 'recently')}.",
                "Prioritize immediate counselling follow-up and short-term safety plan.",
            ]
        elif stress_category == "LOW":
            notes = [
                "Stable trend over recent checks.",
                "Keep routine follow-up and preventive support prompts.",
            ]

        counsellor_students.append(
            {
                "id": f"s{index + 1}",
                "email": email,
                "name": str(row.get("name", "Student")),
                "reg_number": reg_number,
                "hostel": hostel_label,
                "year": year,
                "department": dept,
                "stress_level": base_stress,
                "stress_category": stress_category,
                "wellbeing": wellbeing,
                "trends": trends,
                "heatmap": heatmap,
                "notes": notes,
            }
        )

    appointment_times = ["09:30 AM", "10:30 AM", "12:00 PM", "02:00 PM", "03:30 PM", "05:00 PM"]
    status_cycle = ["pending", "upcoming", "completed"]
    counsellor_appointments = []
    now_utc = datetime.now(timezone.utc)
    for index, student in enumerate(counsellor_students[:20]):
        stress_category = str(student.get("stress_category", "MODERATE")).upper()
        urgency = "low"
        if stress_category == "HIGH":
            urgency = "high"
        elif stress_category == "MODERATE":
            urgency = "medium"

        status = status_cycle[index % len(status_cycle)]
        if urgency == "high" and status == "completed":
            status = "pending"

        date_value = (now_utc + timedelta(days=(index % 12) - 2)).date().isoformat()
        focus = {
            "high": "Acute anxiety support",
            "medium": "Stress management follow-up",
            "low": "Routine wellbeing check-in",
        }[urgency]

        counsellor_appointments.append(
            {
                "id": f"a{index + 1}",
                "student_id": student.get("id"),
                "student_name": student.get("name"),
                "hostel": student.get("hostel"),
                "reg_number": student.get("reg_number"),
                "date": date_value,
                "time": appointment_times[index % len(appointment_times)],
                "urgency": urgency,
                "status": status,
                "focus": focus,
            }
        )

    return {
        "counsellor_sessions_count": max(scheduled_count, len(counsellor_schedule)),
        "counsellor_priority_count": high_count,
        "counsellor_schedule": counsellor_schedule,
        "counsellor_queue": queue_items,
        "counsellor_validation_accuracy": validation_accuracy,
        "counsellor_model_cards": [
            {
                "label": "Physiological",
                "value": physiological_score,
                "delta": "+0.2",
                "meter": int(round((physiological_score / 10.0) * 100)),
                "tone": "#c74971",
            },
            {
                "label": "Cognitive Load",
                "value": cognitive_score,
                "delta": "-0.3",
                "meter": int(round((cognitive_score / 10.0) * 100)),
                "tone": "#355f8e",
            },
            {
                "label": "Social Metric",
                "value": social_score,
                "delta": "+0.4",
                "meter": int(round((social_score / 10.0) * 100)),
                "tone": "#11131a",
            },
        ],
        "counsellor_recovery_rate": recovery_rate,
        "counsellor_confidence_pct": confidence_pct,
        "counsellor_mood_label": dominant_label,
        "counsellor_validation_events": [
            {
                "title": "Stress Model Validated",
                "note": "Latest risk cluster aligned with counsellor review.",
                "delta": "+0.3",
                "icon": "check_circle",
                "icon_color": "#355f8e",
            },
            {
                "title": "Clinical Override Logged",
                "note": "Manual adjustment applied for context-specific escalation.",
                "delta": "-0.1",
                "icon": "feedback",
                "icon_color": "#c74971",
            },
        ],
        "counsellor_students": counsellor_students,
        "counsellor_appointments": counsellor_appointments,
    }


def render_counsellor_console_page(page_key):
    page_map = {
        "dashboard": {
            "title": "Counsellor Dashboard",
            "subtitle": "Queue, interventions, and model reliability overview.",
        },
        "appointments": {
            "title": "Counsellor Appointments",
            "subtitle": "Filter requests, manage urgency, and open student cases.",
        },
        "student-analytics": {
            "title": "Student Analytics",
            "subtitle": "Deep profile analysis with trends and wellbeing metrics.",
        },
        "session-evaluation": {
            "title": "Session Evaluation",
            "subtitle": "Submit counselling session updates and track validation feed.",
        },
    }
    active_key = str(page_key or "dashboard").strip().lower()
    page = page_map.get(active_key, page_map["dashboard"])
    context = build_counsellor_dashboard_context()
    return render_template(
        "counsellor_dashboard.html",
        page_title=page["title"],
        page_subtitle=page["subtitle"],
        active_nav=active_key,
        counsellor_page=active_key,
        **context,
    )


@app.get("/counsellor")
@login_required
@role_required("counsellor")
def counsellor_overview_page_alias():
    return redirect(url_for("counsellor_overview_page"))


@app.get("/counsellor/overview")
@login_required
@role_required("counsellor")
def counsellor_overview_page():
    return render_counsellor_console_page("dashboard")


@app.get("/counsellor/appointments")
@login_required
@role_required("counsellor")
def counsellor_appointments_page():
    return render_counsellor_console_page("appointments")


@app.get("/counsellor/student-analytics")
@login_required
@role_required("counsellor")
def counsellor_student_analytics_page():
    return render_counsellor_console_page("student-analytics")


@app.get("/counsellor/session-evaluation")
@login_required
@role_required("counsellor")
def counsellor_session_evaluation_page():
    return render_counsellor_console_page("session-evaluation")


def load_system_pipeline_counts():
    counts = {
        "score_rows": 0,
        "event_rows": 0,
        "risk_rows": 0,
    }
    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            score_row = conn.execute("SELECT COUNT(*) AS count FROM student_score_state").fetchone()
            event_row = conn.execute("SELECT COUNT(*) AS count FROM extension_collected_events").fetchone()
            risk_row = conn.execute("SELECT COUNT(*) AS count FROM extension_risk_events").fetchone()
            counts["score_rows"] = int(score_row["count"]) if score_row else 0
            counts["event_rows"] = int(event_row["count"]) if event_row else 0
            counts["risk_rows"] = int(risk_row["count"]) if risk_row else 0
    except sqlite3.Error:
        pass
    return counts


def load_recent_risk_events(limit=6):
    safe_limit = max(1, min(int(limit or 6), 20))
    approved_students = list_user_accounts(role="student", status="approved", limit=500)
    account_lookup = {
        str(account.get("email", "")).strip().lower(): str(account.get("name", "Student"))
        for account in approved_students
        if str(account.get("email", "")).strip()
    }

    try:
        with sqlite3.connect(SCORE_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT email, risk_signature, observed_at
                FROM extension_risk_events
                ORDER BY observed_at DESC, id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    except sqlite3.Error:
        rows = []

    events = []
    for row in rows:
        email = str(row["email"] or "").strip().lower()
        events.append(
            {
                "name": student_name_from_email(email, account_lookup),
                "signature": str(row["risk_signature"] or "").strip()[:120],
                "observed_at": parse_time_label(row.get("observed_at") if isinstance(row, dict) else row["observed_at"]),
            }
        )
    return events


def build_developer_dashboard_context():
    pending_accounts = list_user_accounts(status="pending", limit=200)
    approved_accounts = list_user_accounts(status="approved", limit=300)
    rejected_accounts = list_user_accounts(status="rejected", limit=200)
    all_accounts = list_user_accounts(limit=1000)

    for row in all_accounts:
        row["created_at_label"] = parse_time_label(row.get("created_at"))
        row["approved_at_label"] = parse_time_label(row.get("approved_at")) if row.get("approved_at") else "-"
        row["requested_note_short"] = str(row.get("requested_note", "") or "").strip()[:80]

    role_totals = {name: 0 for name in ACCOUNT_ROLES}
    for account in approved_accounts:
        role_key = account.get("role")
        if role_key in role_totals:
            role_totals[role_key] += 1

    pipeline_counts = load_system_pipeline_counts()
    student_rows = build_student_monitor_rows(limit=220)
    high_risk_students = sum(1 for row in student_rows if row.get("stress_category") == "HIGH")
    parent_contact_stats = load_parent_alert_contact_stats()
    parent_contacts = list_parent_alert_contacts(limit=14)

    return {
        "pending_accounts": pending_accounts,
        "approved_accounts": approved_accounts[:12],
        "all_accounts": all_accounts,
        "pending_count": len(pending_accounts),
        "approved_count": len(approved_accounts),
        "rejected_count": len(rejected_accounts),
        "role_totals": role_totals,
        "developer_live_signals": len(EXTENSION_LIVE_SIGNALS),
        "developer_score_rows": int(pipeline_counts.get("score_rows", 0)),
        "developer_event_rows": int(pipeline_counts.get("event_rows", 0)),
        "developer_risk_rows": int(pipeline_counts.get("risk_rows", 0)),
        "developer_high_risk_students": high_risk_students,
        "developer_recent_risk_events": load_recent_risk_events(limit=6),
        "parent_contact_stats": parent_contact_stats,
        "parent_contact_rows": parent_contacts,
        "developer_quiz_catalog": list_student_quiz_catalog(focus_hint="Balance"),
    }


def render_developer_console_page(page_key):
    page_map = {
        "overview": {
            "title": "Developer Overview",
            "subtitle": "System health, API telemetry, and extension diagnostics.",
        },
        "accounts": {
            "title": "Developer Accounts",
            "subtitle": "Manage accounts, assignments, parent contacts, and quiz authoring.",
        },
        "pipeline": {
            "title": "Developer Pipeline",
            "subtitle": "Storage counters, processing flow, and recent risk stream.",
        },
        "requests": {
            "title": "Developer Requests",
            "subtitle": "Review and process pending signup approvals.",
        },
    }
    page = page_map.get(str(page_key or "").strip().lower(), page_map["overview"])
    active_key = str(page_key or "overview").strip().lower()
    context = build_developer_dashboard_context()
    return render_template(
        "developer_dashboard.html",
        page_title=page["title"],
        page_subtitle=page["subtitle"],
        active_nav=active_key,
        developer_page=active_key,
        **context,
    )


@app.get("/developer")
@login_required
@role_required("developer")
def developer_overview_page_alias():
    return redirect(url_for("developer_overview_page"))


@app.get("/developer/overview")
@login_required
@role_required("developer")
def developer_overview_page():
    return render_developer_console_page("overview")


@app.get("/developer/accounts")
@login_required
@role_required("developer")
def developer_accounts_page():
    return render_developer_console_page("accounts")


@app.get("/developer/pipeline")
@login_required
@role_required("developer")
def developer_pipeline_page():
    return render_developer_console_page("pipeline")


@app.get("/developer/requests")
@login_required
@role_required("developer")
def developer_requests_page():
    return render_developer_console_page("requests")


@app.get("/dashboard/<role>")
@login_required
def dashboard(role):
    if role == "admin":
        return redirect(url_for("dashboard", role="developer"))

    if role == "student":
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))

    if role == "warden":
        return redirect(url_for("warden_overview_page"))

    if role == "parent":
        return redirect(url_for("parent_overview_page"))

    if role == "proctor":
        return redirect(url_for("proctor_overview_page"))

    if role == "counsellor":
        return redirect(url_for("counsellor_overview_page"))

    if role == "developer":
        return redirect(url_for("developer_overview_page"))

    current_role = session.get("role")
    if role != current_role:
        if current_role == "student":
            if session.get("student_mood"):
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("student_mood"))
        return redirect(url_for("dashboard", role=current_role))

    page_map = {
        "warden": {
            "template": "warden_dashboard.html",
            "title": "Warden Dashboard",
            "subtitle": "Hostel-level anonymized patterns, alerts, and demand.",
            "active_nav": "dashboard",
        },
        "parent": {
            "template": "parent_dashboard.html",
            "title": "Parent Dashboard",
            "subtitle": "Summarized wellbeing insights for your ward.",
            "active_nav": "overview",
        },
        "proctor": {
            "template": "proctor_dashboard.html",
            "title": "Proctor Dashboard",
            "subtitle": "Group wellbeing monitoring with privacy-safe drill downs.",
            "active_nav": "overview",
        },
        "counsellor": {
            "template": "counsellor_dashboard.html",
            "title": "Counsellor Dashboard",
            "subtitle": "Queue, sessions, and validation signals for interventions.",
            "active_nav": "dashboard",
        },
        "developer": {
            "template": "developer_dashboard.html",
            "title": "Developer Dashboard",
            "subtitle": "System health, API telemetry, and extension processing diagnostics.",
            "active_nav": "overview",
        },
    }

    page = page_map.get(role)
    if not page:
        if current_role == "student":
            if session.get("student_mood"):
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("student_mood"))
        return redirect(url_for("dashboard", role=current_role))

    extra_context = {}
    if role == "warden":
        extra_context = build_warden_dashboard_context()
    elif role == "counsellor":
        extra_context = build_counsellor_dashboard_context()
    elif role == "parent":
        extra_context = build_parent_dashboard_context(str(session.get("email", "")).strip().lower())
    elif role == "proctor":
        extra_context = build_proctor_dashboard_context(str(session.get("email", "")).strip().lower())

    return render_template(
        page["template"],
        page_title=page["title"],
        page_subtitle=page["subtitle"],
        active_nav=page["active_nav"],
        **extra_context,
    )


if __name__ == "__main__":
    debug_mode = read_env_bool("FLASK_DEBUG", not IS_PRODUCTION)
    bind_host = os.getenv("FLASK_HOST", "0.0.0.0").strip() or "0.0.0.0"
    bind_port = read_env_int("PORT", read_env_int("FLASK_PORT", 5000))
    app.run(host=bind_host, port=bind_port, debug=debug_mode)
