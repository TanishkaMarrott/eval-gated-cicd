"""
Eval output cache: (prompt_hash, model_version) -> (answer, judge_verdict)
Cache hit rate ~70% for PRs that touch only orchestration (not prompts).
Stored in .eval_cache/ as JSON files — gitignored, local only.
"""

import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / ".eval_cache"
MODEL_VERSION = os.environ.get("EVAL_MODEL_VERSION", "gemini-2.5-flash")


def _cache_key(question: str, axis: str) -> str:
    raw = f"{MODEL_VERSION}::{axis}::{question}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def get(question: str, axis: str) -> dict | None:
    path = _cache_path(_cache_key(question, axis))
    if path.exists():
        return json.loads(path.read_text())
    return None


def put(question: str, axis: str, answer: str, verdict: dict) -> None:
    path = _cache_path(_cache_key(question, axis))
    path.write_text(json.dumps({"answer": answer, "verdict": verdict}))


def stats() -> dict:
    if not CACHE_DIR.exists():
        return {"entries": 0}
    files = list(CACHE_DIR.glob("*.json"))
    return {"entries": len(files), "cache_dir": str(CACHE_DIR)}
