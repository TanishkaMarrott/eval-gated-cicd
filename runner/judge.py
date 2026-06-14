"""LLM-as-judge: scores one golden-set case on its failure-mode axis."""

import json
import os
import re
from pathlib import Path

from google import genai

JUDGE_PROMPT_PATH = Path(__file__).parent.parent / "evals" / "judge_prompts" / "quality_judge.md"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _load_judge_prompt() -> str:
    return JUDGE_PROMPT_PATH.read_text()


def score(question: str, answer: str, axis: str, expected_contains: str, must_not_contain: list[str]) -> dict:
    """
    Returns {"pass": bool, "confidence": float, "reason": str}
    """
    template = _load_judge_prompt()
    prompt = template.replace("{question}", question)
    prompt = prompt.replace("{answer}", answer)
    prompt = prompt.replace("{axis}", axis)
    prompt = prompt.replace("{expected_contains}", expected_contains or "(none)")
    prompt = prompt.replace("{must_not_contain}", ", ".join(must_not_contain) if must_not_contain else "(none)")

    response = _client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    raw = response.text

    # extract JSON from the response
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # fallback if judge returns malformed output
    return {"pass": False, "confidence": 0.0, "reason": f"Judge returned unparseable output: {raw[:100]}"}
