# Eval-Gated CI/CD for AI Products

Every PR that touches prompt logic runs a golden-set eval before the merge button appears.
A bad prompt change gets caught in CI — not in production after a customer notices.

---

## The problem this solves

A "small" prompt change regressed answer quality on a specific query type.
No eval ran. The regression shipped. A customer noticed. A renewal was lost.

The fix: every PR that touches the AI surface runs an eval gate automatically.
The gate uses LLM-as-judge with **statistical correction** so it never blocks on judge noise alone.

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
   │  • runs the app on each case
   │  • scores with LLM-as-judge (Claude Haiku — cheap)
   │  • one judge call per case, per failure-mode axis
   │
   ▼
Stage 3 — statistical correction (judgy)
   │  • converts raw judge scores → corrected estimate + 95% CI
   │  • CI lower bound compared against main branch baseline
   │
   ▼
Gate decision
   ├── CI lower bound within tolerance → ✅ merge allowed
   └── regression detected → ❌ blocked with per-axis diff report
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

export ANTHROPIC_API_KEY=sk-ant-...

# run a 25% sample (fast, default for PRs)
python scripts/run_evals.py

# run full golden set
python scripts/run_evals.py --full

# update baseline after a confirmed-good build on main
python scripts/run_evals.py --full --update-baseline
```

---

## Adding your own app

1. Create `examples/your_app.py` with a `run(question: str) -> str` function
2. Add cases to `evals/golden_sets/your_app.yaml`
3. Update `APP` in `scripts/run_evals.py`

The eval runner is app-agnostic — swap in any LLM pipeline.

---

## CI setup

1. Add `ANTHROPIC_API_KEY` to GitHub repo secrets
2. The workflow in `.github/workflows/eval-gate.yml` triggers automatically on PRs that touch `examples/`, `evals/`, or `runner/`
3. It posts a per-axis diff report as a PR comment and blocks merge on regression

---

## Statistical correction

Raw LLM-as-judge scores are biased. The judge has its own precision and recall,
which means a 90% raw pass rate might be a true 87% — or 93%.

We use [judgy](https://github.com/ai-evaluation/judgy) to compute a **corrected estimate with a 95% confidence interval**.
The gate checks the **CI lower bound**, not the raw score.
This means:
- We never block a PR on judge noise
- We never approve a regression the judge merely failed to catch

To calibrate: label 50–100 cases per axis with ground truth, compute precision/recall,
and write them to `baselines/judge_calibration.json`. Until then, the runner falls back to a Wilson CI on raw scores.

---

## File structure

```
evals/
  golden_sets/       YAML golden sets — one file per surface
  judge_prompts/     Versioned judge prompts (treat like model weights)
runner/
  eval_runner.py     Core: load → run → score → correct
  judge.py           LLM-as-judge (Claude Haiku)
  correction.py      Statistical correction via judgy
  report.py          PR comment generator
scripts/
  run_evals.py       CLI entry point
baselines/
  main_baseline.json Baseline scores for main branch
.github/workflows/
  eval-gate.yml      GitHub Actions CI workflow
examples/
  answer_bot.py      Toy app (swap in your own)
```

---

## References

- Hamel Husain — [Your AI product needs evals](https://hamel.dev/blog/posts/evals/)
- Eugene Yan — [Evals for LLM apps](https://eugeneyan.com/writing/evals/)
- [judgy](https://github.com/ai-evaluation/judgy) — statistical correction for LLM judges
- Zheng et al. — [Judging LLM-as-a-Judge](https://arxiv.org/abs/2306.05685)
