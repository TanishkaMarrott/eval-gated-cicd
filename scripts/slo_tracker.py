#!/usr/bin/env python3
"""
SLO tracker — records each eval run's outcome and reports block-rate, cost, and latency trends.
Called automatically at the end of run_evals.py.

SLO targets (from the case study):
  - Block-rate:            5–12%   (too low = gate is theater; too high = devs ignore it)
  - Eval cost per PR p95:  < $40
  - Judge kappa:           > 0.70
  - Holdout accuracy delta month-over-month: < 3 points

Usage:
  python scripts/slo_tracker.py           # show current SLO status
  python scripts/slo_tracker.py --record  # (called by run_evals.py internally)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SLO_LOG_PATH = ROOT / "baselines" / "slo_log.json"

TARGETS = {
    "block_rate_min": 0.05,
    "block_rate_max": 0.12,
    "cost_per_run_usd_p95": 40.0,
}


def _load_log() -> list:
    if SLO_LOG_PATH.exists():
        return json.loads(SLO_LOG_PATH.read_text())
    return []


def record(gate_result: dict, n_cases: int, cost_usd: float = 0.0) -> None:
    log = _load_log()
    log.append({
        "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M"),
        "gate": gate_result["gate"],
        "n_cases": n_cases,
        "cost_usd": round(cost_usd, 4),
        "axes_failed": [ax for ax, d in gate_result.get("axes", {}).items() if d.get("gate") == "fail"],
    })
    SLO_LOG_PATH.write_text(json.dumps(log, indent=2))


def report() -> None:
    log = _load_log()
    if not log:
        print("No SLO history yet. Run evals first.")
        return

    recent = log[-20:]  # last 20 runs
    total = len(recent)
    blocked = sum(1 for r in recent if r["gate"] == "fail")
    block_rate = blocked / total if total else 0.0

    print(f"\n{'='*50}")
    print(f"  SLO Report — last {total} runs")
    print(f"{'='*50}")
    print(f"  Block-rate:     {block_rate:.1%}  (target: 5–12%)")

    if block_rate < TARGETS["block_rate_min"]:
        print(f"  ⚠️  Block-rate too LOW — gate may be too permissive or golden set too easy")
    elif block_rate > TARGETS["block_rate_max"]:
        print(f"  ⚠️  Block-rate too HIGH — tune tolerance or fix judge calibration")
    else:
        print(f"  ✓ Block-rate within target range")

    # axis breakdown
    from collections import Counter
    axis_failures = Counter(ax for r in recent for ax in r.get("axes_failed", []))
    if axis_failures:
        print(f"\n  Most frequently failing axes:")
        for ax, count in axis_failures.most_common():
            print(f"    {ax}: {count} blocks")

    print(f"\n  Run history (last {min(10, total)}):")
    print(f"  {'Date':<18} {'Gate':>6} {'Cases':>6}")
    print(f"  {'-'*32}")
    for r in recent[-10:]:
        icon = "✅" if r["gate"] == "pass" else "❌"
        print(f"  {r['date']:<18} {icon} {r['gate']:>4}  {r['n_cases']:>5}")
    print()


def main():
    parser = argparse.ArgumentParser(description="SLO tracker")
    parser.add_argument("--record", action="store_true", help="Record a run result (used internally)")
    args = parser.parse_args()

    if not args.record:
        report()


if __name__ == "__main__":
    main()
