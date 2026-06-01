import argparse
import csv
import math
import os
from collections import Counter, defaultdict
from statistics import mean, median

import matplotlib.pyplot as plt


def _to_float(value):
	if value is None:
		return None
	value = str(value).strip()
	if not value:
		return None
	try:
		return float(value)
	except ValueError:
		return None


def load_rows(csv_path):
	with open(csv_path, "r", encoding="utf-8", newline="") as f:
		reader = csv.DictReader(f)
		return list(reader)


def summarize(rows):
	event_counter = Counter()
	label_counter = Counter()
	task_counter = Counter()
	experience_counter = Counter()

	delta_ms_vals = []
	dist_px_vals = []
	delta_by_event = defaultdict(list)

	for row in rows:
		event_type = (row.get("event_type") or "").strip() or "unknown"
		label = (row.get("label") or "").strip() or "(empty)"
		task = (row.get("task") or "").strip() or "(unset)"
		experience = (row.get("experience") or "").strip() or "(unset)"

		event_counter[event_type] += 1
		task_counter[task] += 1
		experience_counter[experience] += 1

		if event_type != "session_start":
			label_counter[label] += 1

		delta = _to_float(row.get("delta_ms"))
		if delta is not None:
			delta_ms_vals.append(delta)
			delta_by_event[event_type].append(delta)

		dist = _to_float(row.get("cursor_dist_px"))
		if dist is not None:
			dist_px_vals.append(dist)

	return {
		"total_rows": len(rows),
		"event_counter": event_counter,
		"label_counter": label_counter,
		"task_counter": task_counter,
		"experience_counter": experience_counter,
		"delta_ms_vals": delta_ms_vals,
		"dist_px_vals": dist_px_vals,
		"delta_by_event": delta_by_event,
	}


def print_report(summary):
	print("UX Tracker Analysis")
	print("===================")
	print(f"Rows: {summary['total_rows']}")
	print()

	print("Event counts:")
	for event, count in summary["event_counter"].most_common():
		print(f"  - {event}: {count}")
	print()

	print("Top labels:")
	for label, count in summary["label_counter"].most_common(10):
		print(f"  - {label}: {count}")
	print()

	print("Task distribution:")
	for task, count in summary["task_counter"].most_common():
		print(f"  - {task}: {count}")
	print()

	print("Experience distribution:")
	for exp, count in summary["experience_counter"].most_common():
		print(f"  - {exp}: {count}")
	print()

	delta_vals = summary["delta_ms_vals"]
	if delta_vals:
		print("Delta between interactions (ms):")
		print(f"  - mean: {mean(delta_vals):.1f}")
		print(f"  - median: {median(delta_vals):.1f}")
		print(f"  - min: {min(delta_vals):.1f}")
		print(f"  - max: {max(delta_vals):.1f}")
	else:
		print("Delta between interactions (ms): no values yet")
	print()

	dist_vals = summary["dist_px_vals"]
	if dist_vals:
		print("Cursor distance (px):")
		print(f"  - mean: {mean(dist_vals):.1f}")
		print(f"  - median: {median(dist_vals):.1f}")
		print(f"  - min: {min(dist_vals):.1f}")
		print(f"  - max: {max(dist_vals):.1f}")
	else:
		print("Cursor distance (px): no values yet")


def save_plots(summary, out_dir):
	os.makedirs(out_dir, exist_ok=True)

	# Figure 1: event count bar chart + time/distance histograms
	fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

	events = list(summary["event_counter"].keys())
	counts = [summary["event_counter"][e] for e in events]
	axes[0].bar(events, counts)
	axes[0].set_title("Event Counts")
	axes[0].set_ylabel("Count")
	axes[0].tick_params(axis="x", rotation=25)

	delta_vals = summary["delta_ms_vals"]
	if delta_vals:
		bins = min(30, max(5, int(math.sqrt(len(delta_vals)))))
		axes[1].hist(delta_vals, bins=bins)
	axes[1].set_title("Delta Between Interactions (ms)")
	axes[1].set_xlabel("ms")

	dist_vals = summary["dist_px_vals"]
	if dist_vals:
		bins = min(30, max(5, int(math.sqrt(len(dist_vals)))))
		axes[2].hist(dist_vals, bins=bins)
	axes[2].set_title("Cursor Distance (px)")
	axes[2].set_xlabel("px")

	fig.tight_layout()
	overview_path = os.path.join(out_dir, "overview.png")
	fig.savefig(overview_path, dpi=150)
	plt.close(fig)

	# Figure 2: mean delta by event type
	event_names = []
	event_means = []
	for name, vals in summary["delta_by_event"].items():
		if vals:
			event_names.append(name)
			event_means.append(mean(vals))

	if event_names:
		fig2, ax2 = plt.subplots(figsize=(8, 4.8))
		ax2.bar(event_names, event_means)
		ax2.set_title("Mean Delta by Event Type")
		ax2.set_ylabel("Mean delta (ms)")
		ax2.tick_params(axis="x", rotation=25)
		fig2.tight_layout()
		by_event_path = os.path.join(out_dir, "mean_delta_by_event.png")
		fig2.savefig(by_event_path, dpi=150)
		plt.close(fig2)
	else:
		by_event_path = None

	return overview_path, by_event_path


def build_parser():
	parser = argparse.ArgumentParser(description="Analyze UX Tracker CSV data")
	parser.add_argument(
		"--csv",
		default=os.path.join("ux-tracker", "ux_tracker.csv"),
		help="Path to UX tracker CSV",
	)
	parser.add_argument(
		"--out",
		default=os.path.join("analysis_output"),
		help="Output directory for plot images",
	)
	return parser


def main():
	parser = build_parser()
	args = parser.parse_args()

	csv_path = os.path.abspath(args.csv)
	out_dir = os.path.abspath(args.out)

	if not os.path.exists(csv_path):
		raise FileNotFoundError(f"CSV file not found: {csv_path}")

	rows = load_rows(csv_path)
	if not rows:
		print("No rows in CSV yet.")
		return

	summary = summarize(rows)
	print_report(summary)
	overview_path, by_event_path = save_plots(summary, out_dir)

	print()
	print("Plots written:")
	print(f"  - {overview_path}")
	if by_event_path:
		print(f"  - {by_event_path}")


if __name__ == "__main__":
	main()
