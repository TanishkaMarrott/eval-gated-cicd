"""
Statistical correction via judgy.
Converts raw judge pass-rates to corrected estimates with confidence intervals.
Falls back to Wilson CI if calibration data is not available.
"""

import json
import math
from pathlib import Path

CALIBRATION_PATH = Path(__file__).parent.parent / "baselines" / "judge_calibration.json"


def _load_calibration() -> dict | None:
    if CALIBRATION_PATH.exists():
        return json.loads(CALIBRATION_PATH.read_text())
    return None


def correct(axis: str, raw_pass_rate: float, n: int, judge_preds: list[int] | None = None) -> dict:
    """
    Returns:
        {
            "axis": str,
            "raw_pass_rate": float,
            "corrected_pass_rate": float,
            "ci_lower": float,
            "ci_upper": float,
            "method": "judgy" | "raw"
        }

    judge_preds: list of 0/1 judge outputs for unlabeled cases (required for judgy correction).
    calibration file must have "test_labels" and "test_preds" arrays (from calibrate_judge.py).
    """
    calibration = _load_calibration()

    if calibration and axis in calibration and judge_preds is not None:
        cal = calibration[axis]
        if "test_labels" in cal and "test_preds" in cal:
            try:
                from judgy import estimate_success_rate
                corrected, ci_lower, ci_upper = estimate_success_rate(
                    test_labels=cal["test_labels"],
                    test_preds=cal["test_preds"],
                    unlabeled_preds=judge_preds,
                )
                return {
                    "axis": axis,
                    "raw_pass_rate": round(raw_pass_rate, 4),
                    "corrected_pass_rate": round(corrected, 4),
                    "ci_lower": round(ci_lower, 4),
                    "ci_upper": round(ci_upper, 4),
                    "method": "judgy",
                }
            except Exception:
                pass

    # fallback — Wilson confidence interval on raw score
    if n == 0:
        return {"axis": axis, "raw_pass_rate": 0.0, "corrected_pass_rate": 0.0,
                "ci_lower": 0.0, "ci_upper": 0.0, "method": "raw"}
    z = 1.96
    p = raw_pass_rate
    margin = z * math.sqrt(p * (1 - p) / n)
    return {
        "axis": axis,
        "raw_pass_rate": round(p, 4),
        "corrected_pass_rate": round(p, 4),
        "ci_lower": round(max(0.0, p - margin), 4),
        "ci_upper": round(min(1.0, p + margin), 4),
        "method": "raw",
    }
