from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "eqwell.db"

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    anon_id = Column(String, unique=True, index=True, nullable=False)
    block = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    pulses = relationship("Pulse", back_populates="student", cascade="all,delete")
    quizzes = relationship("QuizResult", back_populates="student", cascade="all,delete")
    counsellor_signals = relationship("CounsellorSignal", back_populates="student", cascade="all,delete")
    chatbot_signals = relationship("ChatbotSignal", back_populates="student", cascade="all,delete")
    bookings = relationship("Booking", back_populates="student", cascade="all,delete")


class Pulse(Base):
    __tablename__ = "pulses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    mood_1_5 = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="pulses")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    category = Column(String, index=True, nullable=False)
    score_1_5 = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="quizzes")


class CounsellorSignal(Base):
    __tablename__ = "counsellor_signals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    counsellor_name = Column(String, index=True, nullable=False)
    rating_1_5 = Column(Float, nullable=False)
    note_summary = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="counsellor_signals")


class ChatbotSignal(Base):
    __tablename__ = "chatbot_signals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    sentiment_1_5 = Column(Float, nullable=False)
    topic = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="chatbot_signals")


class EventSignal(Base):
    __tablename__ = "event_signals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    scope = Column(String, index=True, default="global")
    bias = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Counsellor(Base):
    __tablename__ = "counsellors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    available = Column(Boolean, default=True)
    next_slot = Column(String, default="3:00 PM")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(String, unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), index=True, nullable=False)
    counsellor_name = Column(String, index=True, nullable=False)
    slot_time = Column(DateTime, index=True, nullable=False)
    status = Column(String, default="Pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="bookings")


class MoodInput(BaseModel):
    mood_1_5: float = Field(ge=1, le=5)


class QuizInput(BaseModel):
    category: str
    score_1_5: float = Field(ge=1, le=5)


class CounsellorInput(BaseModel):
    counsellor_name: str
    rating_1_5: float = Field(ge=1, le=5)
    note: str = ""


class VentInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class EventInput(BaseModel):
    name: str
    bias: float = Field(ge=-1.0, le=1.0)
    scope: str = "global"


class AvailabilityInput(BaseModel):
    available: bool


class BookingInput(BaseModel):
    anon_id: str
    counsellor_name: str
    slot_time_iso: str


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def days_ago(created_at: datetime) -> float:
    return max((datetime.utcnow() - created_at).total_seconds() / 86400.0, 0.0)


def apply_decay(value_1_5: float, age_days: float, lam: float = 0.12) -> float:
    decay = math.exp(-lam * age_days)
    return 3.0 + (value_1_5 - 3.0) * decay


def clamp_1_5(value: float) -> float:
    return max(1.0, min(5.0, value))


def convert_1_5_to_100(value: float) -> int:
    return int(round(((value - 1.0) / 4.0) * 100))


def category_from_score(value_1_5: float) -> str:
    if value_1_5 < 2.34:
        return "Low"
    if value_1_5 < 3.67:
        return "Moderate"
    return "High"


def summarize_note(note: str) -> str:
    text = " ".join(note.split())
    return text[:120] if text else "No summary"


def detect_topic(text: str) -> str:
    normalized = text.lower()
    topics = {
        "Academics": ["exam", "cat", "fat", "ffcs", "assignment", "grade", "study", "deadline"],
        "Hostel": ["hostel", "room", "warden", "mess", "noise", "rules", "curfew"],
        "Social": ["friend", "alone", "lonely", "group", "ignored", "relationship"],
    }
    best_topic = "General"
    best_score = 0
    for topic, words in topics.items():
        score = sum(1 for word in words if word in normalized)
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def estimate_chat_stress(text: str) -> float:
    normalized = text.lower()
    negative = [
        "stress",
        "anxious",
        "panic",
        "overwhelmed",
        "burnout",
        "tired",
        "sad",
        "cry",
        "alone",
        "pressure",
    ]
    positive = ["calm", "good", "happy", "relaxed", "fine", "okay", "better"]
    neg_count = sum(1 for word in negative if word in normalized)
    pos_count = sum(1 for word in positive if word in normalized)
    base = 2.7 + (neg_count * 0.35) - (pos_count * 0.25)
    if len(normalized) > 180:
        base += 0.15
    return clamp_1_5(base)


def compute_student_stress(db: Session, student: Student) -> dict:
    latest_pulse = (
        db.query(Pulse)
        .filter(Pulse.student_id == student.id)
        .order_by(Pulse.created_at.desc())
        .first()
    )

    mood_score = latest_pulse.mood_1_5 if latest_pulse else None

    categories = ["StressLoad", "CalmPulse", "MindBalance", "SocialConnect"]
    quiz_values = []
    for category in categories:
        latest_quiz = (
            db.query(QuizResult)
            .filter(QuizResult.student_id == student.id, QuizResult.category == category)
            .order_by(QuizResult.created_at.desc())
            .first()
        )
        if latest_quiz:
            quiz_values.append(apply_decay(latest_quiz.score_1_5, days_ago(latest_quiz.created_at)))
    quiz_score = (sum(quiz_values) / len(quiz_values)) if quiz_values else None

    recent_counsellor = (
        db.query(CounsellorSignal)
        .filter(CounsellorSignal.student_id == student.id)
        .order_by(CounsellorSignal.created_at.desc())
        .limit(3)
        .all()
    )
    counsellor_values = [apply_decay(item.rating_1_5, days_ago(item.created_at)) for item in recent_counsellor]
    counsellor_score = (sum(counsellor_values) / len(counsellor_values)) if counsellor_values else None

    recent_chat = (
        db.query(ChatbotSignal)
        .filter(ChatbotSignal.student_id == student.id)
        .order_by(ChatbotSignal.created_at.desc())
        .limit(5)
        .all()
    )
    chat_values = [apply_decay(item.sentiment_1_5, days_ago(item.created_at), lam=0.18) for item in recent_chat]
    chat_score = (sum(chat_values) / len(chat_values)) if chat_values else None

    recent_events = (
        db.query(EventSignal)
        .filter(EventSignal.created_at >= datetime.utcnow() - timedelta(days=7))
        .all()
    )
    event_bias = 0.0
    for evt in recent_events:
        if evt.scope in ("global", student.block):
            event_bias += evt.bias
    event_bias = max(-0.6, min(0.6, event_bias))

    base_weights = {
        "mood": 0.30,
        "counsellor": 0.30,
        "quiz": 0.20,
        "chat": 0.10,
    }
    available = {
        "mood": mood_score,
        "counsellor": counsellor_score,
        "quiz": quiz_score,
        "chat": chat_score,
    }
    available = {k: v for k, v in available.items() if v is not None}

    if not available:
        final_score = 3.0 + event_bias
    else:
        total_weight = sum(base_weights[key] for key in available)
        weighted_sum = sum((base_weights[key] / total_weight) * value for key, value in available.items())
        final_score = weighted_sum + event_bias

    final_score = clamp_1_5(final_score)
    return {
        "stress_1_5": round(final_score, 2),
        "stress_100": convert_1_5_to_100(final_score),
        "category": category_from_score(final_score),
        "components": {
            "mood": mood_score,
            "counsellor": counsellor_score,
            "quiz": quiz_score,
            "chat": chat_score,
            "event_bias": round(event_bias, 2),
        },
    }


def last_n_days_labels(n: int = 7) -> list[str]:
    return [(date.today() - timedelta(days=idx)).isoformat() for idx in range(n - 1, -1, -1)]


def trend_for_student(db: Session, student: Student) -> list[dict]:
    labels = last_n_days_labels(7)
    trend = []
    for label in labels:
        day_start = datetime.fromisoformat(label)
        day_end = day_start + timedelta(days=1)
        pulse = (
            db.query(Pulse)
            .filter(Pulse.student_id == student.id, Pulse.created_at >= day_start, Pulse.created_at < day_end)
            .order_by(Pulse.created_at.desc())
            .first()
        )
        value_1_5 = pulse.mood_1_5 if pulse else 3.0
        trend.append({"date": label, "stress_100": convert_1_5_to_100(value_1_5)})
    return trend


def get_or_404_student(db: Session, anon_id: str) -> Student:
    student = db.query(Student).filter(Student.anon_id == anon_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def booking_counts(db: Session) -> dict:
    total = db.query(func.count(Booking.id)).scalar() or 0
    pending = db.query(func.count(Booking.id)).filter(Booking.status == "Pending").scalar() or 0
    completed = db.query(func.count(Booking.id)).filter(Booking.status == "Completed").scalar() or 0
    return {"total": total, "pending": pending, "completed": completed}


def seed_data(db: Session) -> None:
    if db.query(Student).count() > 0:
        return

    blocks = ["D1", "D2", "C", "A", "B", "E"]
    for block in blocks:
        for i in range(1, 5):
            anon = f"{block}-ANON-{i:02d}"
            student = Student(anon_id=anon, block=block)
            db.add(student)
            db.flush()

            base = 3.2 if block in ("D2", "B") else 2.4 if block in ("D1", "A") else 1.9
            for day in range(7):
                mood = clamp_1_5(base + (0.25 if day % 2 == 0 else -0.1))
                db.add(
                    Pulse(
                        student_id=student.id,
                        mood_1_5=mood,
                        created_at=datetime.utcnow() - timedelta(days=6 - day),
                    )
                )

            for category in ["StressLoad", "CalmPulse", "MindBalance", "SocialConnect"]:
                db.add(
                    QuizResult(
                        student_id=student.id,
                        category=category,
                        score_1_5=clamp_1_5(base + (0.2 if category in ("StressLoad", "MindBalance") else -0.1)),
                        created_at=datetime.utcnow() - timedelta(days=3),
                    )
                )

            db.add(
                ChatbotSignal(
                    student_id=student.id,
                    sentiment_1_5=clamp_1_5(base + 0.15),
                    topic="Academics" if block in ("D2", "B") else "General",
                    created_at=datetime.utcnow() - timedelta(hours=8),
                )
            )

    counsellors = [
        Counsellor(name="Dr. A", available=True, next_slot="3:00 PM"),
        Counsellor(name="Dr. B", available=False, next_slot="Tomorrow"),
        Counsellor(name="Dr. C", available=True, next_slot="5:00 PM"),
    ]
    db.add_all(counsellors)

    students = db.query(Student).limit(5).all()
    for idx, student in enumerate(students):
        db.add(
            CounsellorSignal(
                student_id=student.id,
                counsellor_name="Dr. A" if idx % 2 == 0 else "Dr. B",
                rating_1_5=clamp_1_5(2.8 + idx * 0.25),
                note_summary="Session indicates exam-cycle fatigue",
                created_at=datetime.utcnow() - timedelta(days=1),
            )
        )

    db.add_all(
        [
            EventSignal(name="Mid-term Exams", scope="global", bias=0.30),
            EventSignal(name="Cultural Fest", scope="global", bias=-0.20, created_at=datetime.utcnow() - timedelta(days=5)),
        ]
    )

    slot_base = datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).replace(hour=10)
    for i in range(3):
        db.add(
            Booking(
                booking_id=f"BK-{i + 1:03d}",
                student_id=students[i].id,
                counsellor_name="Dr. A" if i != 1 else "Dr. B",
                slot_time=slot_base + timedelta(hours=i),
                status="Pending" if i < 2 else "Completed",
            )
        )

    db.commit()


Base.metadata.create_all(bind=engine)
with SessionLocal() as init_db:
    seed_data(init_db)

app = FastAPI(title="EqWell API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "EqWell"}


@app.get("/api/students")
def list_students(db: Session = Depends(get_db)) -> dict:
    students = db.query(Student).order_by(Student.anon_id.asc()).all()
    return {
        "students": [{"anon_id": s.anon_id, "block": s.block} for s in students],
    }


@app.post("/api/student/{anon_id}/pulse")
def add_pulse(anon_id: str, payload: MoodInput, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, anon_id)
    db.add(Pulse(student_id=student.id, mood_1_5=payload.mood_1_5))
    db.commit()
    return {"message": "Pulse recorded"}


@app.post("/api/student/{anon_id}/quiz")
def add_quiz(anon_id: str, payload: QuizInput, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, anon_id)
    db.add(QuizResult(student_id=student.id, category=payload.category, score_1_5=payload.score_1_5))
    db.commit()
    return {"message": "Quiz score recorded"}


@app.post("/api/student/{anon_id}/counsellor")
def add_counsellor_signal(anon_id: str, payload: CounsellorInput, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, anon_id)
    db.add(
        CounsellorSignal(
            student_id=student.id,
            counsellor_name=payload.counsellor_name,
            rating_1_5=payload.rating_1_5,
            note_summary=summarize_note(payload.note),
        )
    )
    db.commit()
    return {"message": "Counsellor signal recorded"}


@app.post("/api/student/{anon_id}/vent")
def process_vent(anon_id: str, payload: VentInput, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, anon_id)
    topic = detect_topic(payload.text)
    stress_1_5 = estimate_chat_stress(payload.text)
    db.add(ChatbotSignal(student_id=student.id, sentiment_1_5=stress_1_5, topic=topic))
    db.commit()
    return {
        "topic": topic,
        "stress_1_5": round(stress_1_5, 2),
        "note": "Vent processed. Raw text was not stored.",
    }


@app.get("/api/student/{anon_id}/dashboard")
def student_dashboard(anon_id: str, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, anon_id)
    stress = compute_student_stress(db, student)
    trend = trend_for_student(db, student)

    nearest_booking = (
        db.query(Booking)
        .filter(Booking.student_id == student.id, Booking.slot_time >= datetime.utcnow())
        .order_by(Booking.slot_time.asc())
        .first()
    )

    auto_suggest_booking = stress["category"] == "High" and nearest_booking is None

    return {
        "anon_id": student.anon_id,
        "block": student.block,
        "stress": stress,
        "trend": trend,
        "mental_battery": max(5, 100 - stress["stress_100"]),
        "auto_suggest_booking": auto_suggest_booking,
    }


@app.get("/api/warden/dashboard")
def warden_dashboard(db: Session = Depends(get_db)) -> dict:
    students = db.query(Student).all()
    block_scores: dict[str, list[int]] = defaultdict(list)
    block_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"Low": 0, "Moderate": 0, "High": 0})

    for student in students:
        stress = compute_student_stress(db, student)
        block_scores[student.block].append(stress["stress_100"])
        block_counts[student.block][stress["category"]] += 1

    blocks = []
    for block in ["D1", "D2", "C", "A", "B", "E"]:
        scores = block_scores.get(block, [50])
        avg = int(round(sum(scores) / len(scores)))
        category = "Low" if avg < 34 else "Moderate" if avg < 67 else "High"
        blocks.append({
            "block": block,
            "avg_stress_100": avg,
            "category": category,
            "distribution": block_counts.get(block, {"Low": 0, "Moderate": 0, "High": 0}),
        })

    labels = last_n_days_labels(7)
    trend = []
    for label in labels:
        day_start = datetime.fromisoformat(label)
        day_end = day_start + timedelta(days=1)
        day_pulses = db.query(Pulse).filter(Pulse.created_at >= day_start, Pulse.created_at < day_end).all()
        if day_pulses:
            avg_1_5 = sum(p.mood_1_5 for p in day_pulses) / len(day_pulses)
            trend.append(convert_1_5_to_100(avg_1_5))
        else:
            trend.append(50)

    latest_pulses_by_student = {}
    for pulse in db.query(Pulse).order_by(Pulse.created_at.desc()).all():
        if pulse.student_id not in latest_pulses_by_student:
            latest_pulses_by_student[pulse.student_id] = pulse
    mood_dist = {"low": 0, "neutral": 0, "good": 0}
    for pulse in latest_pulses_by_student.values():
        if pulse.mood_1_5 <= 2:
            mood_dist["low"] += 1
        elif pulse.mood_1_5 <= 3.5:
            mood_dist["neutral"] += 1
        else:
            mood_dist["good"] += 1

    topic_counts = defaultdict(int)
    for signal in db.query(ChatbotSignal).all():
        topic_counts[signal.topic] += 1
    if not topic_counts:
        topic_counts["General"] = 1
    total_topics = sum(topic_counts.values())
    factors = [
        {"name": topic, "percent": int(round((count / total_topics) * 100))}
        for topic, count in sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
    ][:4]

    alerts = []
    for item in blocks:
        if item["category"] == "High":
            alerts.append(f"Block {item['block']} shows high burnout risk")
    if any(v > 68 for v in trend[-2:]):
        alerts.append("Stress spike observed in the last 48 hours")
    if not alerts:
        alerts.append("No severe alerts. Continue monitoring signals.")

    return {
        "blocks": blocks,
        "trend": {"labels": labels, "values": trend},
        "mood_distribution": mood_dist,
        "top_factors": factors,
        "alerts": alerts[:4],
        "bookings": booking_counts(db),
    }


@app.get("/api/admin/dashboard")
def admin_dashboard(db: Session = Depends(get_db)) -> dict:
    students_count = db.query(func.count(Student.id)).scalar() or 0
    counsellors = db.query(Counsellor).order_by(Counsellor.name.asc()).all()
    active_counsellors = sum(1 for c in counsellors if c.available)

    students = db.query(Student).all()
    stress_list = [compute_student_stress(db, s)["stress_100"] for s in students]
    avg_stress = int(round(sum(stress_list) / len(stress_list))) if stress_list else 0
    high_risk = sum(1 for s in students if compute_student_stress(db, s)["category"] == "High")

    block_report = defaultdict(list)
    for student in students:
        block_report[student.block].append(compute_student_stress(db, student)["stress_100"])
    block_report = {
        block: int(round(sum(values) / len(values)))
        for block, values in block_report.items()
    }

    events = (
        db.query(EventSignal)
        .order_by(EventSignal.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "stats": {
            "students": students_count,
            "active_counsellors": active_counsellors,
            "avg_stress_100": avg_stress,
            "high_risk_students": high_risk,
        },
        "counsellors": [
            {"name": c.name, "available": c.available, "next_slot": c.next_slot}
            for c in counsellors
        ],
        "block_report": block_report,
        "events": [
            {"name": e.name, "scope": e.scope, "bias": e.bias, "created_at": e.created_at.isoformat()}
            for e in events
        ],
    }


@app.get("/api/counsellor/dashboard")
def counsellor_dashboard(db: Session = Depends(get_db)) -> dict:
    upcoming = (
        db.query(Booking)
        .filter(Booking.slot_time >= datetime.utcnow())
        .order_by(Booking.slot_time.asc())
        .all()
    )

    schedule = [
        {
            "booking_id": b.booking_id,
            "anon_id": b.student.anon_id,
            "counsellor": b.counsellor_name,
            "slot_time": b.slot_time.isoformat(),
            "status": b.status,
        }
        for b in upcoming
    ]

    queue = []
    for signal in (
        db.query(ChatbotSignal)
        .order_by(ChatbotSignal.created_at.desc())
        .limit(12)
        .all()
    ):
        stress = compute_student_stress(db, signal.student)
        if stress["category"] in ("Moderate", "High"):
            queue.append(
                {
                    "anon_id": signal.student.anon_id,
                    "topic": signal.topic,
                    "stress": stress["category"],
                    "score": stress["stress_100"],
                }
            )

    counsellors = db.query(Counsellor).order_by(Counsellor.name.asc()).all()
    return {
        "schedule": schedule,
        "queue": queue[:12],
        "availability": [
            {"name": c.name, "available": c.available, "next_slot": c.next_slot}
            for c in counsellors
        ],
    }


@app.get("/api/bookings")
def list_bookings(db: Session = Depends(get_db)) -> dict:
    bookings = db.query(Booking).order_by(Booking.slot_time.desc()).all()
    return {
        "bookings": [
            {
                "booking_id": b.booking_id,
                "anon_id": b.student.anon_id,
                "counsellor": b.counsellor_name,
                "slot_time": b.slot_time.isoformat(),
                "status": b.status,
            }
            for b in bookings
        ],
        "counts": booking_counts(db),
    }


@app.get("/api/bookings/slots")
def available_slots(
    target_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> dict:
    try:
        day = datetime.fromisoformat(target_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format") from exc

    slots = []
    for hour in [9, 10, 11, 13, 14, 15, 16]:
        slot = day.replace(hour=hour, minute=0, second=0, microsecond=0)
        slots.append(slot)

    booked = {
        b.slot_time.replace(second=0, microsecond=0)
        for b in db.query(Booking).filter(
            Booking.slot_time >= day.replace(hour=0, minute=0, second=0, microsecond=0),
            Booking.slot_time < day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        )
    }

    return {
        "date": target_date,
        "slots": [
            {
                "iso": slot.isoformat(),
                "label": slot.strftime("%I:%M %p"),
                "available": slot not in booked,
            }
            for slot in slots
        ],
    }


@app.post("/api/bookings")
def create_booking(payload: BookingInput, db: Session = Depends(get_db)) -> dict:
    student = get_or_404_student(db, payload.anon_id)

    counsellor = db.query(Counsellor).filter(Counsellor.name == payload.counsellor_name).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    if not counsellor.available:
        raise HTTPException(status_code=400, detail="Counsellor is currently busy")

    try:
        slot_time = datetime.fromisoformat(payload.slot_time_iso)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid slot_time_iso") from exc

    existing = db.query(Booking).filter(Booking.slot_time == slot_time, Booking.counsellor_name == payload.counsellor_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slot already booked")

    booking = Booking(
        booking_id=f"BK-{uuid4().hex[:6].upper()}",
        student_id=student.id,
        counsellor_name=payload.counsellor_name,
        slot_time=slot_time,
        status="Pending",
    )
    db.add(booking)
    db.commit()
    return {"message": "Booking created", "booking_id": booking.booking_id}


@app.post("/api/events")
def add_event(payload: EventInput, db: Session = Depends(get_db)) -> dict:
    db.add(EventSignal(name=payload.name, scope=payload.scope, bias=payload.bias))
    db.commit()
    return {"message": "Event signal added"}


@app.put("/api/counsellors/{name}/availability")
def update_availability(name: str, payload: AvailabilityInput, db: Session = Depends(get_db)) -> dict:
    counsellor = db.query(Counsellor).filter(Counsellor.name == name).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    counsellor.available = payload.available
    db.commit()
    return {"message": "Availability updated"}
