#!/usr/bin/env python3
"""Analyze saved VLFM per-episode JSON files without running Habitat."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

METRICS = ("success", "spl", "soft_spl", "distance_to_goal")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("episodes_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    files = sorted(args.episodes_dir.glob("*.json"))
    records = []
    for path in files:
        with path.open(encoding="utf-8") as f:
            item = json.load(f)
        records.append(item)

    if not records:
        raise SystemExit(f"No JSON episodes found in {args.episodes_dir}")

    ids = [str(r["episode_id"]) for r in records]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate episode IDs detected")

    n = len(records)
    successes = sum(float(r["success"]) == 1.0 for r in records)
    failures = Counter(r.get("failure_cause", "unknown") for r in records)

    print(f"Episodes: {n}")
    print(f"Unique IDs: {len(set(ids))}")
    print(f"Successes: {successes}/{n}")
    print(f"SR: {successes / n:.4f}")
    for metric in METRICS:
        values = [float(r[metric]) for r in records if r.get(metric) is not None]
        print(f"Mean {metric}: {sum(values) / len(values):.4f}")

    print("\nFailure causes:")
    for cause, count in failures.most_common():
        print(f"  {cause}: {count} ({count / n:.1%})")

    print("\nFailure episodes:")
    for r in sorted(records, key=lambda x: str(x["episode_id"])):
        if float(r["success"]) == 1.0:
            continue
        print(
            f"  {r['episode_id']}: {r.get('target_object', '?')}, "
            f"{r.get('failure_cause', '?')}, "
            f"distance={float(r.get('distance_to_goal', -1)):.3f} m, "
            f"target_detected={r.get('target_detected')}, "
            f"stop_called={r.get('stop_called')}"
        )

    if args.out:
        fields = [
            "episode_id", "scene_id", "target_object", "failure_cause",
            "success", "spl", "soft_spl", "distance_to_goal",
            "target_detected", "stop_called", "gps", "yaw", "start_yaw",
        ]
        with args.out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        print(f"\nSaved CSV: {args.out}")


if __name__ == "__main__":
    main()
