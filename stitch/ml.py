from __future__ import annotations

import os
import re
import sys
from pathlib import Path


DEFAULT_TEXT = "I can't handle exams anymore"
MODEL_ID = "j-hartmann/emotion-english-distilroberta-base"

EMOTION_KEYWORDS = {
	"sadness": {"sad", "down", "cry", "lonely", "hopeless", "tired"},
	"anger": {"angry", "mad", "hate", "annoyed", "furious"},
	"fear": {"afraid", "scared", "panic", "anxious", "worried", "stress"},
	"joy": {"happy", "great", "good", "excited", "relieved", "calm"},
}


def keyword_fallback(text: str) -> list[dict[str, float | str]]:
	tokens = re.findall(r"[a-z']+", text.lower())
	scores = {label: 0 for label in EMOTION_KEYWORDS}

	for token in tokens:
		for label, words in EMOTION_KEYWORDS.items():
			if token in words:
				scores[label] += 1

	best_label = max(scores, key=scores.get)
	best_count = scores[best_label]

	if best_count == 0:
		return [{"label": "neutral", "score": 0.51, "source": "keyword-fallback"}]

	confidence = min(0.55 + (best_count * 0.1), 0.95)
	return [{"label": best_label, "score": round(confidence, 4), "source": "keyword-fallback"}]


def find_local_snapshot() -> str | None:
	cache_root = Path.home() / ".cache" / "huggingface" / "hub"
	repo_dir = cache_root / "models--j-hartmann--emotion-english-distilroberta-base" / "snapshots"
	if not repo_dir.exists():
		return None

	snapshots = [p for p in repo_dir.iterdir() if p.is_dir()]
	if not snapshots:
		return None

	# Pick latest snapshot folder; each should contain config/model/tokenizer files.
	snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
	return str(snapshots[0])


def classify_text(text: str) -> list[dict[str, float | str]]:
	try:
		from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

		local_model_path = find_local_snapshot()
		if not local_model_path:
			return keyword_fallback(text)

		os.environ["TRANSFORMERS_OFFLINE"] = "1"
		tokenizer = AutoTokenizer.from_pretrained(local_model_path, local_files_only=True)
		model = AutoModelForSequenceClassification.from_pretrained(local_model_path, local_files_only=True)

		classifier = pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=1)
		raw = classifier(text)

		if isinstance(raw, list) and raw and isinstance(raw[0], list):
			result = raw[0]
		else:
			result = raw

		if result and isinstance(result[0], dict):
			result[0]["source"] = "cached-transformer"
			result[0]["model"] = MODEL_ID
		return result
	except Exception:
		return keyword_fallback(text)


if __name__ == "__main__":
	text = " ".join(sys.argv[1:]).strip() or DEFAULT_TEXT
	print(classify_text(text))