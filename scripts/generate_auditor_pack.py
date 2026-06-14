#!/usr/bin/env python3
"""
Quarterly auditor pack generator.
Produces a signed markdown report covering:
  - Methodology (versioned judge prompt)
  - Golden set summary (counts per failure mode)
  - Judge calibration results (precision/recall/kappa history)
  - Block-rate histogram
  - Sample of failing PRs with rationale

Usage:
  python scripts/generate_auditor_pack.py
Output: results/auditor_pack_YYYYQN.md
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

CALIBRATION_PATH = ROOT / "baselines" / "judge_calibration.json"
SLO_LOG_PATH = ROOT / "baselines" / "slo_log.json"
DRIFT_LOG_PATH = ROOT / "baselines" / "drift_log.json"
GOLDEN_SET_PATH = ROOT / "evals" / "golden_sets" / "answer_bot.yaml"
JUDGE_PROMPT_PATH = ROOT / "evals" / "judge_prompts" / "quality_judge.md"
VERSIONING_PATH = ROOT / "evals" / "judge_prompts" / "VERSIONING.md"


def _quarter(dt: datetime) -> str:
    return f"Q{(dt.month - 1) // 3 + 1}"


def main():
    now = datetime.utcnow()
    quarter = _quarter(now)
    pack_name = f"auditor_pack_{now.strftime('%Y')}{quarter}.md"
    out_path = ROOT / "results" / pack_name

    lines = [
        f"# Auditor Pack — {now.strftime('%Y')} {quarter}",
        f"",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
        f"## 1. Methodology",
        f"",
        f"This eval pipeline gates every PR that touches the AI surface against a golden test set.",
        f"Each case is scored by an LLM judge (Gemini 2.5 Flash) on one of five failure-mode axes.",
        f"Raw judge scores are corrected using **judgy** (statistical correction via confusion matrix)",
        f"before comparing against the main-branch baseline.",
        f"",
        f"Judge prompt version history:",
        f"",
    ]

    if VERSIONING_PATH.exists():
        for line in VERSIONING_PATH.read_text().splitlines():
            if line.startswith("| "):
                lines.append(line)
        lines.append("")

    # golden set summary
    lines += [
        f"## 2. Golden Set Summary",
        f"",
    ]
    if GOLDEN_SET_PATH.exists():
        data = yaml.safe_load(GOLDEN_SET_PATH.read_text())
        cases = data.get("cases", [])
        from collections import Counter
        axis_counts = Counter(c["failure_mode"] for c in cases)
        lines.append(f"Total active cases: **{len(cases)}**")
        lines.append(f"")
        lines.append(f"| Axis | Cases |")
        lines.append(f"|------|-------|")
        for ax, count in sorted(axis_counts.items()):
            lines.append(f"| {ax} | {count} |")
        lines.append("")

    # calibration results
    lines += ["## 3. Judge Calibration", ""]
    if CALIBRATION_PATH.exists():
        cal = json.loads(CALIBRATION_PATH.read_text())
        lines.append(f"| Axis | Precision | Recall | Accuracy |")
        lines.append(f"|------|-----------|--------|----------|")
        for ax, vals in cal.items():
            lines.append(
                f"| {ax} | {vals['precision']:.2%} | {vals['recall']:.2%} | {vals['accuracy']:.2%} |"
            )
        lines.append("")
    else:
        lines += ["_No calibration data yet._", ""]

    # drift history
    lines += ["## 4. Judge Drift History", ""]
    if DRIFT_LOG_PATH.exists():
        drift = json.loads(DRIFT_LOG_PATH.read_text())
        lines.append(f"| Date | Overall Accuracy |")
        lines.append(f"|------|-----------------|")
        for entry in drift[-6:]:  # last 6 months
            lines.append(f"| {entry['date']} | {entry['overall_accuracy']:.2%} |")
        lines.append("")
    else:
        lines += ["_No drift history yet. Run `python scripts/drift_detector.py` monthly._", ""]

    # block rate
    lines += ["## 5. Block-Rate Histogram", ""]
    if SLO_LOG_PATH.exists():
        log = json.loads(SLO_LOG_PATH.read_text())
        total = len(log)
        blocked = sum(1 for r in log if r["gate"] == "fail")
        block_rate = blocked / total if total else 0.0
        lines.append(f"Total eval runs: **{total}**  ")
        lines.append(f"PRs blocked: **{blocked}** ({block_rate:.1%})")
        lines.append(f"Target: 5–12%")
        lines.append("")

        from collections import Counter
        axis_failures = Counter(ax for r in log for ax in r.get("axes_failed", []))
        if axis_failures:
            lines.append("Most blocked axes:")
            lines.append("")
            lines.append("| Axis | Blocks |")
            lines.append("|------|--------|")
            for ax, count in axis_failures.most_common():
                lines.append(f"| {ax} | {count} |")
            lines.append("")
    else:
        lines += ["_No SLO data yet._", ""]

    # sample failing cases
    lines += ["## 6. Sample Failing Cases", ""]
    latest_result = ROOT / "baselines" / "main_baseline.json"
    if latest_result.exists():
        result = json.loads(latest_result.read_text())
        shown = 0
        for axis, data in result.get("per_axis", {}).items():
            for case in data.get("cases", []):
                if not case["pass"] and shown < 5:
                    lines.append(f"**{case['id']}** ({axis})")
                    lines.append(f"> {case['question']}")
                    lines.append(f"> Judge: {case['reason']}")
                    lines.append("")
                    shown += 1
        if shown == 0:
            lines += ["_No failures in latest baseline run._", ""]

    lines += [
        "---",
        "",
        f"_Pack generated by eval-gated-cicd · Signed: {now.strftime('%Y-%m-%d')}_",
    ]

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"Auditor pack → {out_path}")


if __name__ == "__main__":
    main()
