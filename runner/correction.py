"""
Statistical correction via judgy.
Converts raw judge pass-rates to corrected estimates with confidence intervals.
Falls back to raw rates if judgy is not calibrated yet (no confusion matrix file).
"""

import json
from pathlib import Path

CALIBRATION_PATH = Path(__file__).parent.parent / "baselines" / "judge_calibration.json"


def _load_calibration() -> dict | None:
    if CALIBRATION_PATH.exists():
        return json.loads(CALIBRATION_PATH.read_text())
    return None


def correct(axis: str, raw_pass_rate: float, n: int) -> dict:
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
    """
    calibration = _load_calibration()

    if calibration and axis in calibration:
        try:
            from judgy import correct_pass_rate
            precision = calibration[axis]["precision"]
            recall = calibration[axis]["recall"]
            corrected, (ci_lower, ci_upper) = correct_pass_rate(
                raw_pass_rate=raw_pass_rate,
                n=n,
                precision=precision,
                recall=recall,
            )
            return {
                "axis": axis,
                "raw_pass_rate": raw_pass_rate,
                "corrected_pass_rate": round(corrected, 4),
                "ci_lower": round(ci_lower, 4),
                "ci_upper": round(ci_upper, 4),
                "method": "judgy",
            }
        except Exception:
            pass

    # no calibration yet — return raw rates with wide CI (naive Wilson interval)
    import math
    z = 1.96
    if n == 0:
        return {"axis": axis, "raw_pass_rate": 0.0, "corrected_pass_rate": 0.0,
                "ci_lower": 0.0, "ci_upper": 0.0, "method": "raw"}
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
