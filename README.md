# Eval-Gated CI/CD for AI Products

Every PR that touches prompt logic runs a golden-set eval before the merge button appears.
A bad prompt change gets caught in CI — not in production after a customer notices.

---

## The problem this solves

A "small" prompt change regressed answer quality on a specific query type.
No eval ran. The regression shipped. A customer noticed. A renewal was lost.

The fix: every PR that touches the AI surface runs an eval gate automatically.
The gate uses **LLM-as-judge** (Gemini Flash) with **statistical correction** (judgy)
so it never blocks on judge noise — and never silently approves a real regression.

---

## How it works

```
PR opened
   │
   ▼
Stage 1 — lint + unit tests (2 min)
   │
   ▼
Stage 2 — golden set eval (25% stratified sample by default)
   │  • runs the app on each case (cache hit → zero API calls for unchanged prompts)
   │  • scores with LLM-as-judge (Gemini Flash)
   │  • one judge call per case, per failure-mode axis
   │
   ▼
Stage 3 — statistical correction (judgy)
   │  • converts raw judge scores → corrected estimate + 95% CI
   │  • uses calibrated precision/recall from human-labeled cases
   │  • CI lower bound compared against main branch baseline
   │
   ▼
Gate decision
   ├── CI lower bound within tolerance → ✅ merge allowed
   └── regression detected → ❌ blocked with per-axis diff report posted as PR comment
```

**Failure-mode axes** (scored independently — a composite score hides regressions):

| Axis | What it catches |
|---|---|
| `hallucination` | Model states false facts as true |
| `retrieval_miss` | Model dodges a question it should answer |
| `format_violation` | Wrong structure (missing list, table, etc.) |
| `refusal` | Model refuses a benign request |
| `citation_error` | Misquoted dates, names, measurements |

---

## Quick start

```bash
git clone https://github.com/TanishkaMarrott/eval-gated-cicd
cd eval-gated-cicd
pip install -r requirements.txt

export GEMINI_API_KEY=your-key-here

# run a 25% sample (fast, default for PRs)
python scripts/run_evals.py

# run full golden set
python scripts/run_evals.py --full

# update baseline after a confirmed-good build on main
python scripts/run_evals.py --full --update-baseline

# check SLO report (block-rate, axis failures)
python scripts/slo_tracker.py
```

---

## CI setup

1. Add `GEMINI_API_KEY` to GitHub repo secrets
2. The workflow in `.github/workflows/eval-gate.yml` triggers automatically on PRs that touch `examples/`, `evals/`, or `runner/`
3. It posts a per-axis diff report as a PR comment and blocks merge on regression
4. On push to `main`, it auto-commits `results/latest.md` with the latest scores

---

## Statistical correction

Raw LLM-as-judge scores are biased. The judge has its own precision and recall —
a 90% raw pass rate might be a true 87% or 93%.

We use [judgy](https://github.com/ai-evaluation/judgy) to compute a **corrected estimate with a 95% confidence interval**.
The gate checks the **CI lower bound**, not the raw score:
- Never blocks a PR on judge noise
- Never approves a regression the judge merely failed to catch

**To calibrate your judge:**
```bash
# label cases in evals/calibration/labeled_cases.yaml, then:
python scripts/calibrate_judge.py
# writes precision/recall + test arrays to baselines/judge_calibration.json
# judgy correction activates automatically on the next eval run
```

---

## Judge prompt versioning

Judge prompts are versioned like model weights. See [`evals/judge_prompts/VERSIONING.md`](evals/judge_prompts/VERSIONING.md) for the promotion checklist.

Train/dev/test discipline:
- **60% train** — tune the judge prompt
- **20% dev** — select the best variant
- **20% held-out** — final gate before promoting; never shown in failure reports

---

## Eval output caching

Outputs are cached by `(prompt-hash, model-version)`. PRs that touch only orchestration
code (not prompts) get ~70%+ cache hit rate — near-zero API cost on re-runs.

Cache lives in `.eval_cache/` (gitignored). Clear it when you change the model version:
```bash
rm -rf .eval_cache/
```

---

## Judge drift detection

Run monthly to catch silent degradation in the judge:
```bash
python scripts/drift_detector.py           # replay dev + held-out, alert if accuracy drops >3pp
python scripts/drift_detector.py --history # show accuracy trend over time
python scripts/drift_detector.py --kappa   # inter-judge agreement between v1 and v2 prompts
```

---

## Golden set rotation

Run quarterly to keep the test set fresh and avoid overfitting:
```bash
python scripts/rotate_golden_set.py --dry-run   # preview what would be rotated
python scripts/rotate_golden_set.py              # archive 12% of stale cases, update active set
```

Archived cases move to `evals/golden_sets/archive/` — never deleted, run nightly on `main`.

---

## Auditor pack

Generate a quarterly compliance report covering methodology, calibration, drift history, and block-rate:
```bash
python scripts/generate_auditor_pack.py
# → results/auditor_pack_YYYYQN.md
```

---

## Adding your own app

1. Create `examples/your_app.py` with a `run(question: str) -> str` function
2. Add cases to `evals/golden_sets/your_app.yaml`
3. Update `APP` in `scripts/run_evals.py`

The eval runner is app-agnostic — swap in any LLM pipeline.

---

## File structure

```
evals/
  golden_sets/
    answer_bot.yaml          Active golden set (10 cases, 5 axes)
    archive/                 Rotated cases — run nightly, never deleted
  calibration/
    labeled_cases.yaml       Human-labeled cases (train/dev/held-out split)
  judge_prompts/
    quality_judge.md         Active judge prompt (v1) — versioned like model weights
    quality_judge_v2.md      Candidate v2 prompt — pending calibration
    VERSIONING.md            Promotion checklist + rollback instructions

runner/
  eval_runner.py             Core: load → run → score → correct
  judge.py                   LLM-as-judge (Gemini Flash)
  correction.py              Statistical correction via judgy
  cache.py                   Eval output cache (prompt-hash, model-version)
  report.py                  PR comment generator

scripts/
  run_evals.py               CLI entry point (25% / full / --ci / --update-baseline)
  calibrate_judge.py         Compute judge precision/recall, populate calibration file
  drift_detector.py          Monthly judge replay + inter-judge kappa
  rotate_golden_set.py       Quarterly golden set rotation
  slo_tracker.py             Block-rate SLO report
  generate_auditor_pack.py   Quarterly auditor pack

baselines/
  main_baseline.json         Baseline scores for main branch
  judge_calibration.json     Judge precision/recall + test arrays (judgy input)
  drift_log.json             Monthly drift history
  slo_log.json               Per-run gate outcomes

results/
  latest.md                  Last eval run report (auto-committed by CI)
  auditor_pack_YYYYQN.md     Quarterly auditor pack

.github/workflows/
  eval-gate.yml              GitHub Actions CI — blocks PRs, posts comment, commits results

examples/
  answer_bot.py              Toy app powered by Gemini Flash (swap in your own)
```

---

## References

- Hamel Husain — [Your AI product needs evals](https://hamel.dev/blog/posts/evals/)
- Hamel Husain — [A field guide to rapidly improving AI products](https://hamel.dev/blog/posts/field-guide/)
- Eugene Yan — [Evals for LLM apps](https://eugeneyan.com/writing/evals/)
- Eugene Yan — [LLM-as-judge](https://eugeneyan.com/writing/llm-evaluators/)
- [judgy](https://github.com/ai-evaluation/judgy) — statistical correction for LLM judges
- Zheng et al. — [Judging LLM-as-a-Judge](https://arxiv.org/abs/2306.05685)
