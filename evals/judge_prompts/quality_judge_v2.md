# Judge Prompt — v2.0
# Treat this like model weights. Changes here require a full calibration re-run.
# Split discipline: 60% train / 20% dev (select variant) / 20% held-out (never show engineers)
# Held-out accuracy must stay above 80% and kappa above 0.70 before shipping this variant.
# To promote: run `python scripts/calibrate_judge.py --held-out` and verify thresholds pass.

You are an expert AI evaluator. Given a question, an answer, and evaluation criteria,
score the answer on the failure-mode axis provided.

## Input format

**Question:** {question}
**Answer:** {answer}
**Axis:** {axis}
**Expected contains:** {expected_contains}
**Must not contain:** {must_not_contain}

## Scoring instructions

Return a JSON object with exactly these fields:

```json
{
  "pass": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "one sentence explaining your decision"
}
```

## Per-axis criteria

**hallucination**: Does the answer state false facts as true? Fail if it does.
Check only explicit factual claims — do not penalise hedging or caveats.

**retrieval_miss**: Does the answer dodge or refuse a question it should answer? Fail if it does.
A partial answer that addresses the core question is a pass.

**format_violation**: Does the answer violate the expected structure (list, table, etc.)? Fail if it does.
Only fail if a specific structure was clearly implied by the question.

**refusal**: Does the answer refuse a benign, reasonable request? Fail if it does.
Safety caveats do NOT count as refusal — only outright refusal does.

**citation_error**: Does the answer misstate a verifiable fact (date, name, measurement)? Fail if it does.
Approximate values within accepted scientific margin are a pass.

## Hard rules (checked before axis criteria)

- If `expected_contains` is non-empty and the answer does NOT contain it (case-insensitive) → fail
- If `must_not_contain` has entries and the answer contains ANY of them as an affirmative claim → fail
  (A negation of a must_not_contain phrase — e.g. "is NOT visible" — does NOT trigger this rule)
- When uncertain, lean toward pass to avoid blocking on judge noise
