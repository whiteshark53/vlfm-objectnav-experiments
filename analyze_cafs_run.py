from pathlib import Path
import re
import csv
from collections import Counter

run_dir = Path("reports/cafs_50ep_20261102_165339")
video_dir = run_dir / "videos"
log_path = run_dir / "run.log"
out_csv = run_dir / "episode_metrics.csv"
out_summary = run_dir / "analysis_summary.txt"

# 1. Метрики из имён видео
rows = []
for path in sorted(video_dir.glob("*.mp4")):
    stem = path.stem
    episode_match = re.search(r"episode[=_-](\d+)", stem)
    if not episode_match:
        print("WARNING: cannot parse episode ID:", path.name)
        continue

    row = {
        "episode_id": episode_match.group(1),
        "video_file": path.name,
    }

    # Поддерживает поля вида success=1, SPL=0.42 и т.п.
    for key, value in re.findall(
        r"([A-Za-z][A-Za-z0-9_]*)=([-+]?\d*\.?\d+)",
        stem
    ):
        row[key] = value

    rows.append(row)

# 2. Категории отказов из run.log
failure_by_episode = {}
if log_path.exists():
    log_text = log_path.read_text(errors="replace")

    # Ищем ID эпизода и текст категории отказа в одной строке
    for line in log_text.splitlines():
        id_match = re.search(r"(?:episode[=_\s-]*)(\d+)", line, re.I)
        if not id_match:
            continue

        cause_match = re.search(
            r"(false_positive|false_negative|bad_stop_true_positive|"
            r"never_saw_target_did_not_travel_stairs_feasible)",
            line,
            re.I
        )
        if cause_match:
            failure_by_episode[id_match.group(1)] = cause_match.group(1)

for row in rows:
    row["failure_cause"] = failure_by_episode.get(
        row["episode_id"], ""
    )

# 3. Единый CSV
fields = sorted({key for row in rows for key in row})
with out_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

# 4. Сводка
summary = []
summary.append(f"Videos parsed: {len(rows)}")
summary.append(f"Failure labels parsed from log: {len(failure_by_episode)}")
summary.append("")

for metric in ("success", "SPL", "SoftSPL",
               "distance_to_goal", "target_detected", "stop_called"):
    values = []
    for row in rows:
        value = row.get(metric)
        if value is not None:
            try:
                values.append(float(value))
            except ValueError:
                pass
    if values:
        summary.append(
            f"{metric}: n={len(values)}, "
            f"mean={sum(values)/len(values):.4f}, "
            f"min={min(values):.4f}, max={max(values):.4f}"
        )

summary.append("")
summary.append("Failure causes:")
for cause, count in Counter(failure_by_episode.values()).most_common():
    summary.append(f"  {cause}: {count}")

summary.append("")
summary.append("Episodes without a parsed failure label:")
summary.extend(
    f"  {row['episode_id']}"
    for row in rows if not row["failure_cause"]
)

out_summary.write_text("\n".join(summary), encoding="utf-8")

print("\n".join(summary))
print(f"\nCSV: {out_csv}")
print(f"Summary: {out_summary}")
