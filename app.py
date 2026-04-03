from functools import wraps
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
import requests

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "eqwell-dev-secret-change-me")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

CREDENTIALS = {
    "student": {"email": "student@eqwell.app", "password": "student123", "name": "Ariana Vale"},
    "warden": {"email": "warden@eqwell.app", "password": "warden123", "name": "Warden Mitchell"},
    "admin": {"email": "admin@eqwell.app", "password": "admin123", "name": "System Admin"},
    "counsellor": {
        "email": "counsellor@eqwell.app",
        "password": "counsellor123",
        "name": "Dr. Aris",
    },
}

STUDENT_MOODS = {
    "very-bad": {"label": "Very Bad", "score": 1, "battery": 18, "tone": "#fc7359"},
    "bad": {"label": "Bad", "score": 2, "battery": 36, "tone": "#dfa342"},
    "not-bad": {"label": "Not Bad", "score": 3, "battery": 54, "tone": "#c8b35f"},
    "good": {"label": "Good", "score": 4, "battery": 73, "tone": "#9fbe59"},
    "very-good": {"label": "Very Good", "score": 5, "battery": 90, "tone": "#6ea73f"},
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
    "admin": {
        "subtitle": "Digital Sanctuary",
        "badge_icon": "admin_panel_settings",
        "menu": [
            {"label": "Sanctuary", "icon": "spa", "key": "sanctuary"},
            {"label": "Insights", "icon": "analytics", "key": "insights"},
            {"label": "Pulse Check", "icon": "favorite", "key": "pulse-check"},
            {"label": "Community", "icon": "groups", "key": "community"},
            {"label": "Resources", "icon": "library_books", "key": "resources"},
        ],
        "action": "Quick Pulse",
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
}


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


def student_mood_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if session.get("role") == "student" and not session.get("student_mood"):
            return redirect(url_for("student_mood"))
        return view_func(*args, **kwargs)

    return wrapper


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
    else:
        base_href = url_for("dashboard", role=role)
        href_map = {
            "dashboard": base_href,
            "analytics": f"{base_href}#analytics",
            "students": f"{base_href}#students",
            "sessions": f"{base_href}#sessions",
            "reports": f"{base_href}#reports",
            "sanctuary": base_href,
            "insights": f"{base_href}#insights",
            "pulse-check": f"{base_href}#pulse-check",
            "community": f"{base_href}#community",
            "resources": f"{base_href}#resources",
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
        "temperature": 0.7,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are EqWell student support assistant. Respond with empathetic, concise,"
                    " practical wellbeing guidance for students. Do not provide diagnosis."
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
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
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


@app.context_processor
def inject_globals():
    active_role = session.get("role")
    sidebar = build_sidebar(active_role) if active_role else ROLE_SIDEBARS["student"]
    return {
        "active_role": active_role,
        "role_sidebar": sidebar,
        "display_name": session.get("name", "EqWell User"),
        "student_mood": session.get("student_mood"),
    }


@app.get("/")
def home():
    role = session.get("role")
    if role == "student":
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))
    if role in {"warden", "admin", "counsellor"}:
        return redirect(url_for("dashboard", role=role))
    return render_template("landing.html")


@app.get("/signup")
def signup_showcase():
    return render_template("signup_showcase.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        role_data = CREDENTIALS.get(role)
        if not role_data:
            flash("Select a valid dashboard role.", "error")
            return render_template("login.html")

        if email != role_data["email"] or password != role_data["password"]:
            flash("Invalid credentials for selected role.", "error")
            return render_template("login.html")

        session["role"] = role
        session["name"] = role_data["name"]
        session["email"] = role_data["email"]
        if role == "student":
            session["student_mood"] = None
            return redirect(url_for("student_mood"))
        return redirect(url_for("dashboard", role=role))

    if session.get("role") == "student":
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))
    if session.get("role") in {"warden", "admin", "counsellor"}:
        return redirect(url_for("dashboard", role=session["role"]))

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/student/mood", methods=["GET", "POST"])
@login_required
@role_required("student")
def student_mood():
    if request.method == "POST":
        mood_key = request.form.get("mood", "").strip()
        if mood_key not in STUDENT_MOODS:
            flash("Select your current mood to continue.", "error")
            return render_template(
                "student_mood_gate.html",
                mood_options=STUDENT_MOODS,
                selected_mood=session.get("student_mood"),
            )

        session["student_mood"] = mood_key
        return redirect(url_for("student_dashboard"))

    return render_template(
        "student_mood_gate.html",
        mood_options=STUDENT_MOODS,
        selected_mood=session.get("student_mood"),
    )


@app.get("/student/dashboard")
@login_required
@role_required("student")
@student_mood_required
def student_dashboard():
    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    return render_template(
        "student_dashboard.html",
        page_title="Student Dashboard",
        page_subtitle="Your private wellbeing pulse and support tools.",
        active_nav="dashboard",
        mood_label=mood["label"],
        mood_score=mood["score"],
        mood_battery=mood["battery"],
        mood_tone=mood["tone"],
    )


@app.get("/student/profile")
@login_required
@role_required("student")
@student_mood_required
def student_profile():
    mood = STUDENT_MOODS.get(session.get("student_mood"), STUDENT_MOODS["not-bad"])
    return render_template(
        "student_profile.html",
        page_title="Student Profile",
        page_subtitle="Personal wellbeing profile and support preferences.",
        active_nav="profile",
        mood_label=mood["label"],
        mood_score=mood["score"],
        mood_battery=mood["battery"],
    )


@app.post("/api/student/chat")
@login_required
@role_required("student")
@student_mood_required
def student_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()

    if len(message) < 2:
        return jsonify({"error": "Please enter a longer message."}), 400

    if len(message) > 1200:
        message = message[:1200]

    reply, error = ask_groq_student_bot(message)
    if error:
        return jsonify({"error": error}), 503

    return jsonify({"reply": reply})


@app.get("/dashboard/<role>")
@login_required
def dashboard(role):
    if role == "student":
        if session.get("student_mood"):
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("student_mood"))

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
        "admin": {
            "template": "admin_dashboard.html",
            "title": "Admin Dashboard",
            "subtitle": "System controls, reports, model settings, and staffing.",
            "active_nav": "sanctuary",
        },
        "counsellor": {
            "template": "counsellor_dashboard.html",
            "title": "Counsellor Dashboard",
            "subtitle": "Queue, sessions, and validation signals for interventions.",
            "active_nav": "dashboard",
        },
    }

    page = page_map.get(role)
    if not page:
        if current_role == "student":
            if session.get("student_mood"):
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("student_mood"))
        return redirect(url_for("dashboard", role=current_role))

    return render_template(
        page["template"],
        page_title=page["title"],
        page_subtitle=page["subtitle"],
        active_nav=page["active_nav"],
    )


if __name__ == "__main__":
    app.run(debug=True)
