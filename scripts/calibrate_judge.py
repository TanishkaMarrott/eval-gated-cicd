#!/usr/bin/env python3
"""
Judge calibration script.
Runs human-labeled cases through the judge and computes per-axis precision/recall.
Writes results to baselines/judge_calibration.json — used by correction.py for judgy.

Usage:
  python scripts/calibrate_judge.py              # train + dev splits only
  python scripts/calibrate_judge.py --held-out   # include held-out (only before major judge changes)
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from runner.judge import score

CALIBRATION_PATH = ROOT / "evals" / "calibration" / "labeled_cases.yaml"
OUTPUT_PATH = ROOT / "baselines" / "judge_calibration.json"


def main():
    parser = argparse.ArgumentParser(description="Calibrate LLM judge")
    parser.add_argument("--held-out", action="store_true", help="Include held-out split (use sparingly)")
    args = parser.parse_args()

    data = yaml.safe_load(CALIBRATION_PATH.read_text())
    cases = data["cases"]

    allowed_splits = {"train", "dev"}
    if args.held_out:
        allowed_splits.add("held_out")
        print("WARNING: Including held-out split. Only do this before a major judge prompt change.")

    cases = [c for c in cases if c["split"] in allowed_splits]
    print(f"Running calibration on {len(cases)} cases ({', '.join(sorted(allowed_splits))} splits)...\n")

    by_axis: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0})

    for case in cases:
        axis = case["axis"]
        true_pass = case["true_pass"]
        verdict = score(
            question=case["question"],
            answer=case["answer"],
            axis=axis,
            expected_contains="",
            must_not_contain=[],
        )
        judge_pass = verdict["pass"]

        if true_pass and judge_pass:
            by_axis[axis]["tp"] += 1
        elif not true_pass and judge_pass:
            by_axis[axis]["fp"] += 1
        elif true_pass and not judge_pass:
            by_axis[axis]["fn"] += 1
        else:
            by_axis[axis]["tn"] += 1

        status = "✓" if judge_pass == true_pass else "✗"
        print(f"  {status} [{case['id']}] {axis} | true={true_pass} judge={judge_pass}")

    print("\n--- Calibration Results ---\n")
    calibration = {}
    for axis, counts in by_axis.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        accuracy = (tp + counts["tn"]) / sum(counts.values())
        calibration[axis] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "accuracy": round(accuracy, 4),
            "counts": counts,
        }
        print(f"  {axis}: precision={precision:.2%}  recall={recall:.2%}  accuracy={accuracy:.2%}")

    # also store raw test_labels/test_preds arrays per axis for judgy
    for axis in calibration:
        calibration[axis]["test_labels"] = []
        calibration[axis]["test_preds"] = []

    for case in cases:
        axis = case["axis"]
        if axis in calibration:
            verdict = score(case["question"], case["answer"], axis, "", [])
            calibration[axis]["test_labels"].append(int(case["true_pass"]))
            calibration[axis]["test_preds"].append(int(verdict["pass"]))

    OUTPUT_PATH.write_text(json.dumps(calibration, indent=2))
    print(f"\nCalibration saved → {OUTPUT_PATH}")
    print("Re-run eval gate to use corrected (judgy) estimates instead of raw Wilson CI.")


if __name__ == "__main__":
    main()
