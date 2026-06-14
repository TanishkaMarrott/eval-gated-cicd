# Judge Prompt Versioning

Treat judge prompts like model weights — changes have downstream consequences.

## Promotion checklist

Before merging a new judge prompt version:

- [ ] Run `python scripts/calibrate_judge.py` (train + dev splits)
- [ ] Dev-set accuracy ≥ 80% per axis
- [ ] Cohen's kappa ≥ 0.70 (run `python scripts/drift_detector.py --kappa`)
- [ ] Run `python scripts/calibrate_judge.py --held-out` to verify held-out set
- [ ] Held-out accuracy ≥ 80% per axis
- [ ] Update `JUDGE_PROMPT_PATH` in `runner/judge.py` to point to new version
- [ ] Commit with message: `judge: promote vX.Y — kappa=Z, held-out accuracy=W`

## Version history

| Version | Date | Notes | Held-out accuracy |
|---------|------|-------|-------------------|
| v1.0 | 2026-06-14 | Initial prompt | not measured |
| v2.0 | 2026-06-14 | Clarified negation rule for must_not_contain; partial-answer refusal rule | pending |

## Rollback

Every version is a file in this directory. To rollback:
```bash
# In runner/judge.py, change JUDGE_PROMPT_PATH to point to the previous version
JUDGE_PROMPT_PATH = Path(__file__).parent.parent / "evals" / "judge_prompts" / "quality_judge_v1.md"
```
Then re-run calibration to confirm accuracy is restored.
