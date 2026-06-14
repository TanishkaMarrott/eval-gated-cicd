"""
Core eval runner.
Loads a golden set, runs the app under eval, scores each case, applies statistical correction.
"""

import json
import random
from collections import defaultdict
from pathlib import Path

import yaml

from runner.cache import get as cache_get
from runner.cache import put as cache_put
from runner.cache import stats as cache_stats
from runner.correction import correct
from runner.judge import score


def load_golden_set(path: Path, sample_pct: float = 1.0, seed: int = 42) -> list[dict]:
    data = yaml.safe_load(path.read_text())
    cases = data["cases"]
    if sample_pct < 1.0:
        rng = random.Random(seed)
        # stratified by failure_mode — ensure every axis is represented
        by_axis: dict[str, list] = defaultdict(list)
        for c in cases:
            by_axis[c["failure_mode"]].append(c)
        sampled = []
        for axis_cases in by_axis.values():
            k = max(1, round(len(axis_cases) * sample_pct))
            sampled.extend(rng.sample(axis_cases, min(k, len(axis_cases))))
        return sampled
    return cases


def run_eval(
    app_module_path: str,
    golden_set_path: Path,
    sample_pct: float = 1.0,
) -> dict:
    """
    app_module_path: dotted path to a module with a run(question: str) -> str function
                     e.g. "examples.answer_bot"
    Returns a result dict with per-axis scores and corrected estimates.
    """
    import importlib
    app = importlib.import_module(app_module_path)

    cases = load_golden_set(golden_set_path, sample_pct)
    print(f"Running {len(cases)} cases from {golden_set_path.name} ...")

    results_by_axis: dict[str, list[dict]] = defaultdict(list)

    for case in cases:
        cid = case["id"]
        question = case["input"]
        axis = case["failure_mode"]
        expected_contains = case.get("expected_contains", "")
        must_not_contain = case.get("must_not_contain", [])

        print(f"  [{cid}] {axis} ... ", end="", flush=True)
        cached = cache_get(question, axis)
        if cached:
            answer = cached["answer"]
            verdict = cached["verdict"]
            status = "PASS" if verdict["pass"] else "FAIL"
            print(f"{status} (conf={verdict['confidence']:.2f}) [cache hit]")
        else:
            answer = app.run(question)
            verdict = score(question, answer, axis, expected_contains, must_not_contain)
            cache_put(question, axis, answer, verdict)
            status = "PASS" if verdict["pass"] else "FAIL"
            print(f"{status} (conf={verdict['confidence']:.2f})")

        results_by_axis[axis].append({
            "id": cid,
            "question": question,
            "answer": answer,
            "pass": verdict["pass"],
            "confidence": verdict["confidence"],
            "reason": verdict["reason"],
        })

    # aggregate and correct per axis
    per_axis = {}
    for axis, results in results_by_axis.items():
        n = len(results)
        raw_pass_rate = sum(1 for r in results if r["pass"]) / n
        judge_preds = [int(r["pass"]) for r in results]
        corrected = correct(axis, raw_pass_rate, n, judge_preds=judge_preds)
        corrected["cases"] = results
        corrected["n"] = n
        per_axis[axis] = corrected

    return {
        "total_cases": len(cases),
        "per_axis": per_axis,
    }


def compare_to_baseline(current: dict, baseline_path: Path, tolerance: float = 0.02) -> dict:
    """
    Compares corrected CI lower bounds against baseline.
    Returns gate decision: pass/fail per axis and overall.
    """
    if not baseline_path.exists():
        return {"gate": "pass", "reason": "no baseline yet — storing current as baseline", "axes": {}}

    baseline = json.loads(baseline_path.read_text())
    axes_result = {}
    overall_pass = True

    for axis, data in current["per_axis"].items():
        baseline_score = baseline.get("per_axis", {}).get(axis, {}).get("corrected_pass_rate", None)
        if baseline_score is None:
            axes_result[axis] = {"gate": "pass", "reason": "no baseline for this axis"}
            continue

        ci_lower = data["ci_lower"]
        delta = ci_lower - baseline_score
        passes = delta >= -tolerance

        axes_result[axis] = {
            "gate": "pass" if passes else "fail",
            "baseline": baseline_score,
            "ci_lower": ci_lower,
            "corrected": data["corrected_pass_rate"],
            "delta": round(delta, 4),
            "tolerance": tolerance,
        }
        if not passes:
            overall_pass = False

    return {
        "gate": "pass" if overall_pass else "fail",
        "axes": axes_result,
    }
