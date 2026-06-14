#!/usr/bin/env python3
"""
CLI entry point.

Usage:
  # quick run (25% sample)
  python scripts/run_evals.py

  # full run
  python scripts/run_evals.py --full

  # update baseline (run on main after a confirmed-good build)
  python scripts/run_evals.py --full --update-baseline

  # CI mode: exits with code 1 if gate fails
  python scripts/run_evals.py --ci
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from runner.eval_runner import compare_to_baseline, run_eval
from runner.report import build_pr_comment

GOLDEN_SET = ROOT / "evals" / "golden_sets" / "answer_bot.yaml"
BASELINE = ROOT / "baselines" / "main_baseline.json"
APP = "examples.answer_bot"


def main():
    parser = argparse.ArgumentParser(description="Run eval gate")
    parser.add_argument("--full", action="store_true", help="Run 100%% of golden set (default: 25%%)")
    parser.add_argument("--update-baseline", action="store_true", help="Store current result as new baseline")
    parser.add_argument("--ci", action="store_true", help="Exit 1 on gate failure (for CI)")
    parser.add_argument("--tolerance", type=float, default=0.02, help="Regression tolerance (default 0.02 = 2pp)")
    args = parser.parse_args()

    sample_pct = 1.0 if args.full else 0.25

    print(f"\n{'='*60}")
    print(f"  Eval Gate — {'FULL' if args.full else '25% SAMPLE'}")
    print(f"{'='*60}\n")

    result = run_eval(APP, GOLDEN_SET, sample_pct=sample_pct)
    gate = compare_to_baseline(result, BASELINE, tolerance=args.tolerance)

    print(f"\n{'='*60}")
    print(f"  Gate: {gate['gate'].upper()}")
    for axis, ax_data in gate["axes"].items():
        status = ax_data.get("gate", "pass")
        icon = "✓" if status == "pass" else "✗"
        print(f"  {icon} {axis}: {ax_data}")
    print(f"{'='*60}\n")

    if args.update_baseline:
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(result, indent=2))
        print(f"Baseline updated → {BASELINE}")

    # always print the report
    comment = build_pr_comment(result, gate, sample_pct)
    print("\n--- PR Comment Preview ---\n")
    print(comment)

    if args.ci and gate["gate"] == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
