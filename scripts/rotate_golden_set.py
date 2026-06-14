#!/usr/bin/env python3
"""
Quarterly golden set rotation.
- Archives 10-15% of oldest cases to evals/golden_sets/archive/
- Flags cases that have never failed (potential dead weight)
- Never deletes — archived cases run nightly, not on every PR

Usage:
  python scripts/rotate_golden_set.py --dry-run   # preview what would be rotated
  python scripts/rotate_golden_set.py              # apply rotation
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

GOLDEN_SET_PATH = ROOT / "evals" / "golden_sets" / "answer_bot.yaml"
ARCHIVE_DIR = ROOT / "evals" / "golden_sets" / "archive"
HISTORY_PATH = ROOT / "baselines" / "case_history.json"
ROTATION_PCT = 0.12  # rotate ~12% per quarter


def _load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return {}


def _save_history(history: dict) -> None:
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def update_history(result_path: Path) -> None:
    """Call after each eval run to record pass/fail history per case."""
    if not result_path.exists():
        return
    import json as _json
    result = _json.loads(result_path.read_text())
    history = _load_history()

    for axis_data in result.get("per_axis", {}).values():
        for case in axis_data.get("cases", []):
            cid = case["id"]
            if cid not in history:
                history[cid] = {"runs": 0, "failures": 0, "last_seen": None}
            history[cid]["runs"] += 1
            if not case["pass"]:
                history[cid]["failures"] += 1
            history[cid]["last_seen"] = datetime.utcnow().strftime("%Y-%m-%d")

    _save_history(history)


def rotate(dry_run: bool = False) -> None:
    data = yaml.safe_load(GOLDEN_SET_PATH.read_text())
    cases = data["cases"]
    history = _load_history()

    n_rotate = max(1, round(len(cases) * ROTATION_PCT))
    print(f"Golden set: {len(cases)} cases — rotating {n_rotate} ({ROTATION_PCT:.0%})\n")

    # score each case: never-failed cases with most runs are candidates for rotation
    scored = []
    for case in cases:
        cid = case["id"]
        h = history.get(cid, {"runs": 0, "failures": 0})
        # prefer to rotate: high run count, zero failures (potentially too easy / stale)
        score = h["runs"] - (h["failures"] * 10)
        scored.append((score, cid, case))

    scored.sort(reverse=True)
    to_rotate = [c for _, _, c in scored[:n_rotate]]
    to_keep = [c for _, _, c in scored[n_rotate:]]

    print("Cases flagged for rotation:")
    for case in to_rotate:
        h = history.get(case["id"], {"runs": 0, "failures": 0})
        print(f"  {case['id']} ({case['failure_mode']}) — {h['runs']} runs, {h['failures']} failures")

    if dry_run:
        print(f"\nDry run — no changes made. Remove --dry-run to apply.")
        return

    # archive rotated cases
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_name = f"archive_{datetime.utcnow().strftime('%Y%m%d')}.yaml"
    archive_path = ARCHIVE_DIR / archive_name
    archive_data = {"rotated_at": datetime.utcnow().isoformat(), "cases": to_rotate}
    archive_path.write_text(yaml.dump(archive_data, default_flow_style=False, allow_unicode=True))
    print(f"\nArchived {len(to_rotate)} cases → {archive_path}")

    # write updated golden set
    data["cases"] = to_keep
    GOLDEN_SET_PATH.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    print(f"Updated golden set: {len(to_keep)} active cases")
    print("\nNext: add fresh cases from production traces, support tickets, or red-team runs.")


def main():
    parser = argparse.ArgumentParser(description="Quarterly golden set rotation")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--update-history", action="store_true", help="Update case history from latest baseline")
    args = parser.parse_args()

    if args.update_history:
        update_history(ROOT / "baselines" / "main_baseline.json")
        print(f"History updated → {HISTORY_PATH}")
        return

    rotate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
