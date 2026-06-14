#!/usr/bin/env python3
"""
Judge-prompt drift detector.
Replays the calibration held-out set monthly and tracks accuracy over time.
Alerts if accuracy drops >3 points or kappa drops below 0.65.

Usage:
  python scripts/drift_detector.py            # run monthly replay
  python scripts/drift_detector.py --kappa    # compute inter-judge kappa (two prompts in parallel)
  python scripts/drift_detector.py --history  # show accuracy trend
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from runner.judge import score

CALIBRATION_PATH = ROOT / "evals" / "calibration" / "labeled_cases.yaml"
DRIFT_LOG_PATH = ROOT / "baselines" / "drift_log.json"


def _load_drift_log() -> list:
    if DRIFT_LOG_PATH.exists():
        return json.loads(DRIFT_LOG_PATH.read_text())
    return []


def _save_drift_log(log: list) -> None:
    DRIFT_LOG_PATH.write_text(json.dumps(log, indent=2))


def run_monthly_replay() -> dict:
    data = yaml.safe_load(CALIBRATION_PATH.read_text())
    # use dev + held-out for monthly replay
    cases = [c for c in data["cases"] if c["split"] in {"dev", "held_out"}]
    print(f"Monthly replay: {len(cases)} cases (dev + held-out)...\n")

    correct_count = 0
    by_axis: dict[str, dict] = {}

    for case in cases:
        verdict = score(
            question=case["question"],
            answer=case["answer"],
            axis=case["axis"],
            expected_contains="",
            must_not_contain=[],
        )
        judge_pass = verdict["pass"]
        true_pass = case["true_pass"]
        match = judge_pass == true_pass
        correct_count += int(match)
        icon = "✓" if match else "✗"
        print(f"  {icon} [{case['id']}] {case['axis']}")

        axis = case["axis"]
        if axis not in by_axis:
            by_axis[axis] = {"correct": 0, "total": 0}
        by_axis[axis]["correct"] += int(match)
        by_axis[axis]["total"] += 1

    overall_acc = correct_count / len(cases) if cases else 0.0
    per_axis_acc = {ax: v["correct"] / v["total"] for ax, v in by_axis.items()}

    entry = {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "overall_accuracy": round(overall_acc, 4),
        "per_axis": {ax: round(v, 4) for ax, v in per_axis_acc.items()},
    }

    log = _load_drift_log()
    log.append(entry)
    _save_drift_log(log)

    print(f"\nOverall accuracy: {overall_acc:.2%}")
    for ax, acc in per_axis_acc.items():
        print(f"  {ax}: {acc:.2%}")

    # drift alert
    if len(log) >= 2:
        prev = log[-2]["overall_accuracy"]
        delta = overall_acc - prev
        if delta < -0.03:
            print(f"\n⚠️  DRIFT ALERT: accuracy dropped {delta:.2%} vs last run ({prev:.2%} → {overall_acc:.2%})")
            print("   Action: open judge calibration maintenance ticket, consider rolling back prompt.")
        else:
            print(f"\n✓ No significant drift ({delta:+.2%} vs last run)")

    return entry


def compute_kappa() -> None:
    """Run two judge prompts in parallel and compute Cohen's kappa."""
    from runner.judge import _load_judge_prompt, score
    from pathlib import Path

    data = yaml.safe_load(CALIBRATION_PATH.read_text())
    cases = [c for c in data["cases"] if c["split"] == "dev"]

    v1_path = ROOT / "evals" / "judge_prompts" / "quality_judge.md"
    v2_path = ROOT / "evals" / "judge_prompts" / "quality_judge_v2.md"

    if not v2_path.exists():
        print("No v2 judge prompt found — skipping kappa computation.")
        return

    import os
    from runner.judge import _client

    agree = 0
    total = len(cases)
    print(f"Computing inter-judge kappa ({total} dev cases)...\n")

    for case in cases:
        def _call(prompt_path):
            template = Path(prompt_path).read_text()
            prompt = template.replace("{question}", case["question"])
            prompt = prompt.replace("{answer}", case["answer"])
            prompt = prompt.replace("{axis}", case["axis"])
            prompt = prompt.replace("{expected_contains}", "(none)")
            prompt = prompt.replace("{must_not_contain}", "(none)")
            import json, re
            response = _client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw = response.text
            m = re.search(r"\{.*?\}", raw, re.DOTALL)
            return json.loads(m.group())["pass"] if m else False

        v1 = _call(v1_path)
        v2 = _call(v2_path)
        agree += int(v1 == v2)
        print(f"  [{case['id']}] v1={v1} v2={v2} {'✓' if v1==v2 else '✗'}")

    p_o = agree / total
    # expected agreement assuming random (simplified — assume 50/50 split)
    p_e = 0.5
    kappa = (p_o - p_e) / (1 - p_e)
    print(f"\nCohen's kappa: {kappa:.3f}")
    if kappa < 0.65:
        print("⚠️  Kappa below 0.65 — judge prompts diverging, investigation needed.")
    elif kappa < 0.70:
        print("⚠️  Kappa below 0.70 threshold — monitor closely.")
    else:
        print("✓ Kappa within acceptable range (≥0.70)")


def show_history() -> None:
    log = _load_drift_log()
    if not log:
        print("No drift history yet. Run `python scripts/drift_detector.py` first.")
        return
    print(f"{'Date':<12} {'Accuracy':>10}")
    print("-" * 24)
    for entry in log:
        print(f"{entry['date']:<12} {entry['overall_accuracy']:>10.2%}")


def main():
    parser = argparse.ArgumentParser(description="Judge drift detector")
    parser.add_argument("--kappa", action="store_true", help="Compute inter-judge kappa")
    parser.add_argument("--history", action="store_true", help="Show accuracy trend")
    args = parser.parse_args()

    if args.history:
        show_history()
    elif args.kappa:
        compute_kappa()
    else:
        run_monthly_replay()


if __name__ == "__main__":
    main()
