from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from typing import Literal
from urllib.parse import parse_qs, unquote_plus, urlparse

import jwt
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Load environment variables from .env if present.
load_dotenv()

HF_MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"
HF_API_URL = os.getenv(
    "HF_EMOTION_API_URL",
    f"https://router.huggingface.co/hf-inference/models/{HF_MODEL_ID}",
)
HF_API_TOKEN = os.getenv(
    "HUGGINGFACE_API_TOKEN",
    os.getenv("HF_API_TOKEN", os.getenv("HF_TOKEN", "")),
).strip()
REQUEST_TIMEOUT_SECONDS = (5, 25)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
EQWELL_JWT_SECRET = os.getenv("EQWELL_JWT_SECRET", "").strip()
EQWELL_JWT_ALGORITHM = os.getenv("EQWELL_JWT_ALGORITHM", "HS256").strip() or "HS256"
MAX_SIGNAL_EVENTS = 2000
SIGNAL_EVENTS: list[dict[str, str | float]] = []
AUTH_SCHEME = HTTPBearer(auto_error=False)
EQWELL_DEBUG_SIGNAL_LOGS = os.getenv("EQWELL_DEBUG_SIGNAL_LOGS", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

URL_RISK_PATTERNS = [
    re.compile(r"\bhow\s+to\s+die\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:dont|don't)\s+want\s+(?:to\s+)?live\b", re.IGNORECASE),
    re.compile(r"\b(?:want\s+to\s+die|i\s+want\s+to\s+die)\b", re.IGNORECASE),
    re.compile(r"\b(?:kill\s+myself|end\s+my\s+life)\b", re.IGNORECASE),
    re.compile(r"\b(?:suicide|self[\s-]*harm|hurt\s+myself)\b", re.IGNORECASE),
    re.compile(r"\bi\s+can(?:not|'?t)\s+live\b", re.IGNORECASE),
]

PRIMARY_QUERY_REGEX = re.compile(r"[?&](?:q|query|search|p|oq)=([^&]+)", re.IGNORECASE)


def emit_terminal_debug_log(tag: str, **fields) -> None:
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
    print(f"[EQWELL][STRESS_API][{tag}] {payload}", flush=True)


class AnalyzeRequest(BaseModel):
    mood: int = Field(..., ge=1, le=5, description="Mood slider value from 1 to 5")
    text: str = Field(..., min_length=1, max_length=4000, description="Anonymous student chat text")


class AnalyzeResponse(BaseModel):
    emotion: str
    confidence: float
    stress_level: Literal["LOW", "MEDIUM", "HIGH"]
    stress_score: float
    category: Literal["LOW", "MODERATE", "HIGH"]
    mental_battery: int
    topic: Literal["ACADEMICS", "HOSTEL", "SOCIAL", "GENERAL"]


class ExtensionAnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Temporary snippet processed in-memory only",
    )
    session_duration: int = Field(
        ...,
        ge=0,
        le=1440,
        description="Active browsing session duration in minutes",
    )
    current_url: str | None = Field(
        default=None,
        max_length=500,
        description="Current active tab URL only; no history list",
    )
    extracted_query: str | None = Field(
        default=None,
        max_length=300,
        description="Exact decoded search query extracted client-side from active URL",
    )


class ExtensionAnalyzeResponse(BaseModel):
    stress_signal: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: float
    hf_signal: Literal["LOW", "MEDIUM", "HIGH"]
    groq_signal: Literal["LOW", "MEDIUM", "HIGH"]
    final_score: float


app = FastAPI(
    title="EqWell Stress Analysis API",
    description="Privacy-first stress insights from mood slider + chat emotion metadata",
    version="1.0.0",
)


def require_extension_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(AUTH_SCHEME),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
        )

    try:
        if EQWELL_JWT_SECRET:
            return jwt.decode(token, EQWELL_JWT_SECRET, algorithms=[EQWELL_JWT_ALGORITHM])
        # Dev fallback: validate JWT format only when signing secret is not configured.
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT token: {exc}",
        ) from exc


def promote_stress(level: Literal["LOW", "MEDIUM", "HIGH"]) -> Literal["LOW", "MEDIUM", "HIGH"]:
    if level == "LOW":
        return "MEDIUM"
    if level == "MEDIUM":
        return "HIGH"
    return "HIGH"


def signal_to_score(level: Literal["LOW", "MEDIUM", "HIGH"]) -> float:
    if level == "LOW":
        return 2.0
    if level == "HIGH":
        return 5.0
    return 3.2


def score_to_signal(score: float) -> Literal["LOW", "MEDIUM", "HIGH"]:
    value = max(1.0, min(float(score), 5.0))
    if value >= 4.0:
        return "HIGH"
    if value <= 2.4:
        return "LOW"
    return "MEDIUM"


def parse_groq_json(content: str) -> dict | None:
    raw = str(content or "").strip()
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


def groq_refine_signal(
    text: str,
    current_url: str | None,
    exact_query: str,
    hf_signal: Literal["LOW", "MEDIUM", "HIGH"],
    hf_confidence: float,
    session_duration: int,
) -> tuple[Literal["LOW", "MEDIUM", "HIGH"], float]:
    if not GROQ_API_KEY:
        return hf_signal, hf_confidence

    prompt = {
        "text": text[:300],
        "current_url": str(current_url or "")[:500],
        "exact_query": str(exact_query or "")[:300],
        "hf_signal": hf_signal,
        "hf_confidence": round(hf_confidence, 4),
        "session_duration": int(session_duration),
        "task": "Return strict JSON with keys stress_signal (LOW|MEDIUM|HIGH) and confidence (0..1).",
    }
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.1,
        "max_tokens": 140,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a wellbeing risk classifier. Use the HuggingFace hint plus user text and URL context. "
                    "Always output JSON only with fields stress_signal and confidence."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return hf_signal, hf_confidence

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    parsed = parse_groq_json(content)
    if not isinstance(parsed, dict):
        return hf_signal, hf_confidence

    candidate_signal = str(parsed.get("stress_signal", "")).upper()
    if candidate_signal not in {"LOW", "MEDIUM", "HIGH"}:
        candidate_signal = hf_signal

    candidate_confidence = parsed.get("confidence", hf_confidence)
    try:
        candidate_confidence = float(candidate_confidence)
    except (TypeError, ValueError):
        candidate_confidence = hf_confidence
    candidate_confidence = max(0.0, min(candidate_confidence, 1.0))

    return candidate_signal, round(candidate_confidence, 4)


def url_context_risk(url: str | None) -> bool:
    return url_context_risk_with_query(url=url, query_text="")


def extract_exact_query_from_url(url: str | None) -> str:
    raw_url = str(url or "").strip()
    if not raw_url:
        return ""

    direct_match = PRIMARY_QUERY_REGEX.search(raw_url)
    if direct_match:
        candidate = unquote_plus(str(direct_match.group(1))).strip()
        if candidate:
            return candidate[:300]

    parsed = urlparse(raw_url)
    query_map = parse_qs(parsed.query)
    for key in ("q", "query", "search", "p", "oq", "text", "wd", "k", "keyword"):
        for item in query_map.get(key, []):
            cleaned = unquote_plus(str(item)).strip()
            if cleaned:
                return cleaned[:300]

    return ""


def url_context_risk_with_query(url: str | None, query_text: str) -> bool:
    raw_url = str(url or "").strip()
    query = str(query_text or "").strip()

    parts = []
    if query:
        parts.append(query)

    if raw_url:
        parts.append(unquote_plus(raw_url))
        parsed = urlparse(raw_url)
        path_text = unquote_plus(parsed.path or "").replace("/", " ").strip()
        if path_text:
            parts.append(path_text)

    merged = " ".join(parts).strip()
    if not merged:
        return False

    return any(pattern.search(merged) for pattern in URL_RISK_PATTERNS)


def groq_extract_query_and_risk_from_url(url: str | None) -> tuple[str, bool, float]:
    raw_url = str(url or "").strip()
    if not raw_url or not GROQ_API_KEY:
        return "", False, 0.0

    prompt = {
        "url": raw_url[:500],
        "task": (
            "Extract the exact user search intent from this URL when possible. "
            "Return strict JSON only with keys: extracted_query (string), stress_signal (LOW|MEDIUM|HIGH), confidence (0..1)."
        ),
    }
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.0,
        "max_tokens": 180,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify student search safety from URL context. "
                    "Only return JSON with extracted_query, stress_signal, confidence."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return "", False, 0.0

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    parsed = parse_groq_json(content)
    if not isinstance(parsed, dict):
        return "", False, 0.0

    extracted_query = str(parsed.get("extracted_query", "")).strip()[:300]
    signal = str(parsed.get("stress_signal", "")).upper()
    if signal not in {"LOW", "MEDIUM", "HIGH"}:
        signal = "MEDIUM"

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))

    return extracted_query, signal == "HIGH", round(confidence, 4)


def store_signal_event(stress_signal: Literal["LOW", "MEDIUM", "HIGH"], confidence: float) -> None:
    SIGNAL_EVENTS.append(
        {
            "stress_signal": stress_signal,
            "confidence": round(max(0.0, min(float(confidence), 1.0)), 4),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    if len(SIGNAL_EVENTS) > MAX_SIGNAL_EVENTS:
        del SIGNAL_EVENTS[: len(SIGNAL_EVENTS) - MAX_SIGNAL_EVENTS]


def normalize_prediction_payload(payload: object) -> list[dict]:
    """Normalize Hugging Face response to a list of prediction dicts."""
    if isinstance(payload, list):
        if payload and isinstance(payload[0], list):
            return [p for p in payload[0] if isinstance(p, dict)]
        return [p for p in payload if isinstance(p, dict)]
    return []


def analyze_text(text: str) -> tuple[str, float]:
    """Call Hugging Face and return top emotion label + confidence."""
    if not HF_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="HUGGINGFACE_API_TOKEN is missing. Add it to environment variables.",
        )

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "inputs": text,
        "options": {"wait_for_model": True},
    }

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise HTTPException(status_code=504, detail=f"Hugging Face timeout: {exc}") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Hugging Face request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Hugging Face returned invalid JSON") from exc

    if response.status_code >= 400:
        if isinstance(data, dict):
            hf_error = data.get("error") or data
        else:
            hf_error = data
        raise HTTPException(status_code=503, detail=f"Hugging Face API error: {hf_error}")

    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=503, detail=f"Hugging Face API error: {data['error']}")

    predictions = normalize_prediction_payload(data)
    if not predictions:
        raise HTTPException(status_code=502, detail="No emotion predictions returned by Hugging Face")

    top = max(predictions, key=lambda p: float(p.get("score", 0.0)))
    emotion = str(top.get("label", "neutral")).lower()
    confidence = float(top.get("score", 0.0))
    confidence = max(0.0, min(confidence, 1.0))

    return emotion, round(confidence, 4)


def map_stress(emotion: str) -> Literal["LOW", "MEDIUM", "HIGH"]:
    """Map emotion labels to stress level buckets."""
    if emotion in {"sadness", "anger", "fear"}:
        return "HIGH"
    if emotion == "joy":
        return "LOW"
    if emotion == "neutral":
        return "MEDIUM"
    return "MEDIUM"


def stress_to_numeric(stress_level: Literal["LOW", "MEDIUM", "HIGH"]) -> int:
    mapping = {
        "LOW": 2,
        "MEDIUM": 3,
        "HIGH": 5,
    }
    return mapping[stress_level]


def calculate_score(
    mood: int,
    chatbot_stress_level: Literal["LOW", "MEDIUM", "HIGH"],
) -> float:
    """Compute weighted stress score and apply override rule for HIGH chatbot stress."""
    chatbot_score = stress_to_numeric(chatbot_stress_level)
    final_score = (0.7 * mood) + (0.3 * chatbot_score)

    if chatbot_stress_level == "HIGH":
        final_score = max(final_score, 4.0)

    final_score = max(1.0, min(final_score, 5.0))
    return round(final_score, 2)


def classify_category(score: float) -> Literal["LOW", "MODERATE", "HIGH"]:
    if score <= 2:
        return "LOW"
    if score <= 3.5:
        return "MODERATE"
    return "HIGH"


def calculate_battery(score: float) -> int:
    """Convert stress score to stress percentage, then to mental battery percentage."""
    stress_percentage = (score / 5.0) * 100.0
    mental_battery = 100.0 - stress_percentage
    mental_battery = max(0.0, min(mental_battery, 100.0))
    return int(round(mental_battery))


def detect_topic(text: str) -> Literal["ACADEMICS", "HOSTEL", "SOCIAL", "GENERAL"]:
    lower_text = text.lower()

    if "exam" in lower_text or "study" in lower_text:
        return "ACADEMICS"
    if "hostel" in lower_text or "roommate" in lower_text:
        return "HOSTEL"
    if "friend" in lower_text or "alone" in lower_text:
        return "SOCIAL"
    return "GENERAL"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": HF_MODEL_ID}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    # Privacy-first: the raw text is processed in memory only and never stored.
    emotion, confidence = analyze_text(payload.text)
    stress_level = map_stress(emotion)
    stress_score = calculate_score(payload.mood, stress_level)
    category = classify_category(stress_score)
    mental_battery = calculate_battery(stress_score)
    topic = detect_topic(payload.text)

    return AnalyzeResponse(
        emotion=emotion,
        confidence=confidence,
        stress_level=stress_level,
        stress_score=stress_score,
        category=category,
        mental_battery=mental_battery,
        topic=topic,
    )


@app.post("/extension-analyze", response_model=ExtensionAnalyzeResponse)
def extension_analyze(
    payload: ExtensionAnalyzeRequest,
    _: dict = Depends(require_extension_jwt),
) -> ExtensionAnalyzeResponse:
    # Privacy-first: process text in-memory and do not persist raw snippets.
    temp_text = payload.text.strip()[:300]
    extracted_query = str(payload.extracted_query or "").strip()[:300]
    if not extracted_query:
        extracted_query = extract_exact_query_from_url(payload.current_url)

    url_fallback_confidence = 0.0
    if not extracted_query and payload.current_url:
        groq_query, groq_url_high, groq_url_confidence = groq_extract_query_and_risk_from_url(
            payload.current_url
        )
        if groq_query:
            extracted_query = groq_query
        url_fallback_confidence = groq_url_confidence
    else:
        groq_url_high = False

    emit_terminal_debug_log(
        "extension-analyze-incoming",
        current_url=str(payload.current_url or "")[:500],
        extracted_query=extracted_query,
        session_duration=payload.session_duration,
        text_preview=temp_text[:120],
    )

    ai_text = temp_text
    if extracted_query:
        ai_text = f"Student search query: {extracted_query}. Page snippet: {temp_text}"[:460]

    emotion, confidence = analyze_text(ai_text)
    hf_signal = map_stress(emotion)

    if payload.session_duration > 90:
        hf_signal = promote_stress(hf_signal)

    if url_context_risk_with_query(payload.current_url, extracted_query) or groq_url_high:
        hf_signal = promote_stress(hf_signal)
        url_risky = True
    else:
        url_risky = False

    groq_signal, groq_confidence = groq_refine_signal(
        text=temp_text,
        current_url=payload.current_url,
        exact_query=extracted_query,
        hf_signal=hf_signal,
        hf_confidence=confidence,
        session_duration=payload.session_duration,
    )

    combined_score = (0.6 * signal_to_score(hf_signal)) + (0.4 * signal_to_score(groq_signal))
    if url_risky:
        combined_score = max(combined_score, 4.1)
    stress_signal = score_to_signal(combined_score)
    final_confidence = round((0.6 * confidence) + (0.3 * groq_confidence) + (0.1 * url_fallback_confidence), 4)

    store_signal_event(stress_signal, final_confidence)

    emit_terminal_debug_log(
        "extension-analyze-result",
        current_url=str(payload.current_url or "")[:500],
        extracted_query=extracted_query,
        hf_signal=hf_signal,
        groq_signal=groq_signal,
        final_signal=stress_signal,
        final_score=round(max(1.0, min(combined_score, 5.0)), 2),
        confidence=final_confidence,
    )

    # Explicitly clear temporary variable reference after processing.
    temp_text = ""
    ai_text = ""
    extracted_query = ""

    return ExtensionAnalyzeResponse(
        stress_signal=stress_signal,
        confidence=final_confidence,
        hf_signal=hf_signal,
        groq_signal=groq_signal,
        final_score=round(max(1.0, min(combined_score, 5.0)), 2),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("stress_api:app", host="0.0.0.0", port=8000, reload=True)
