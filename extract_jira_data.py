import json
import csv
import argparse
from datetime import datetime


def get_date_obj(date_str):
    """
    Convert an ISO date string to a datetime object.
    If the date_str ends with 'Z', it is replaced with '+00:00' for proper parsing.
    Returns None if date_str is None or parsing fails.
    """
    if not date_str:
        return None
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


def format_date(date_obj):
    """Format a datetime object into dd.mm.yyyy format, or return an empty string if None."""
    if date_obj is None:
        return ""
    return date_obj.strftime("%d.%m.%Y")


def main():
    parser = argparse.ArgumentParser(
        description="Extract Jira issues data from multiple JSON files into a single CSV file."
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        help="Path(s) to the input JSON file(s)"
    )
    parser.add_argument(
        "output_file",
        help="Path to the output CSV file"
    )
    parser.add_argument(
        "--omit-outside-sprint",
        action="store_true",
        help="Omit issues that have no sprint information"
    )
    parser.add_argument(
        "--sprint-filter",
        type=str,
        help="Only include issues with a sprint whose name contains this substring (case-insensitive)"
    )
    args = parser.parse_args()

    all_issues = []
    for filename in args.input_files:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            issues = data.get("issues", [])
            all_issues.extend(issues)

    with open(args.output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["issue key", "oldest sprint start date", "resolution date"])

        for issue in all_issues:
            key = issue.get("key", "")
            fields = issue.get("fields", {})

            sprints = fields.get("customfield_10020")
            # If there are sprints and a sprint filter is provided, filter them
            if sprints and isinstance(sprints, list):
                if args.sprint_filter:
                    sprints = [
                        s for s in sprints
                        if s.get("name") and args.sprint_filter.lower() in s.get("name").lower()
                    ]

            # If omit-outside-sprint is active and there are no (or no matching) sprints, skip this issue.
            if args.omit_outside_sprint and not (sprints and len(sprints) > 0):
                continue

            # Determine the oldest sprint's start date among the available sprints.
            oldest_sprint_start = ""
            if sprints and isinstance(sprints, list) and len(sprints) > 0:
                valid_sprints = []
                for sprint in sprints:
                    dt = get_date_obj(sprint.get("startDate"))
                    if dt is not None:
                        valid_sprints.append((dt, sprint))
                if valid_sprints:
                    oldest_sprint = min(valid_sprints, key=lambda x: x[0])
                    oldest_sprint_start = format_date(oldest_sprint[0])

            resolution_date = format_date(get_date_obj(fields.get("resolutiondate")))
            writer.writerow([key, oldest_sprint_start, resolution_date])


if __name__ == "__main__":
    main()
