import argparse
import csv
import os
from collections import Counter
from datetime import datetime

import matplotlib.pyplot as plt


def load_rows(csv_path):
	with open(csv_path, "r", encoding="utf-8", newline="") as f:
		reader = csv.DictReader(f)
		return list(reader)


def _parse_timestamp(raw):
	try:
		return datetime.fromisoformat(raw)
	except (TypeError, ValueError):
		return None


def summarize(rows):
	toolbar_counter = Counter()
	action_counter = Counter()
	hour_counter = Counter()
	valid_ts = 0

	for row in rows:
		toolbar = (row.get("toolbar") or "").strip() or "(unknown toolbar)"
		action = (row.get("action_label") or "").strip() or "(empty action)"
		timestamp = _parse_timestamp(row.get("timestamp"))

		toolbar_counter[toolbar] += 1
		action_counter[action] += 1

		if timestamp is not None:
			valid_ts += 1
			hour_counter[timestamp.hour] += 1

	return {
		"total_rows": len(rows),
		"toolbar_counter": toolbar_counter,
		"action_counter": action_counter,
		"hour_counter": hour_counter,
		"valid_ts": valid_ts,
	}


def print_report(summary):
	print("UX Tracker Analysis")
	print("===================")
	print(f"Rows: {summary['total_rows']}")
	print(f"Valid timestamps: {summary['valid_ts']}")
	print()

	print("Toolbar counts:")
	for toolbar, count in summary["toolbar_counter"].most_common():
		print(f"  - {toolbar}: {count}")
	print()

	print("Top actions:")
	for action, count in summary["action_counter"].most_common(10):
		print(f"  - {action}: {count}")
	print()

	if summary["hour_counter"]:
		print("Clicks by hour:")
		for hour in sorted(summary["hour_counter"]):
			print(f"  - {hour:02d}:00: {summary['hour_counter'][hour]}")


def save_plots(summary, out_dir):
	os.makedirs(out_dir, exist_ok=True)

	# Figure 1: toolbar counts + top action counts + clicks by hour
	fig, axes = plt.subplots(1, 3, figsize=(18, 5.2))

	toolbars = [name for name, _ in summary["toolbar_counter"].most_common(10)]
	toolbar_counts = [summary["toolbar_counter"][name] for name in toolbars]
	axes[0].bar(toolbars, toolbar_counts)
	axes[0].set_title("Top Toolbars")
	axes[0].set_ylabel("Clicks")
	axes[0].tick_params(axis="x", rotation=35)

	actions = [name for name, _ in summary["action_counter"].most_common(10)]
	action_counts = [summary["action_counter"][name] for name in actions]
	axes[1].bar(actions, action_counts)
	axes[1].set_title("Top Actions")
	axes[1].set_ylabel("Clicks")
	axes[1].tick_params(axis="x", rotation=35)

	hours = list(range(24))
	hour_counts = [summary["hour_counter"].get(h, 0) for h in hours]
	axes[2].bar(hours, hour_counts)
	axes[2].set_title("Clicks by Hour")
	axes[2].set_xlabel("Hour of day")
	axes[2].set_ylabel("Clicks")
	axes[2].set_xticks([0, 4, 8, 12, 16, 20, 23])

	fig.tight_layout()
	overview_path = os.path.join(out_dir, "overview.png")
	fig.savefig(overview_path, dpi=150)
	plt.close(fig)

	return overview_path


def build_parser():
	parser = argparse.ArgumentParser(description="Analyze UX Tracker CSV data")
	parser.add_argument(
		"--csv",
		default=os.path.join("ux-tracker", "data", "ux_tracker.csv"),
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
	overview_path = save_plots(summary, out_dir)

	print()
	print("Plots written:")
	print(f"  - {overview_path}")


if __name__ == "__main__":
	main()
