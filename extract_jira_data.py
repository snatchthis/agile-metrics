import json
import csv
import argparse
from datetime import datetime

def get_date_obj(date_str):
    if not date_str:
        return None
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return None

def format_date(date_obj):
    return date_obj.strftime("%d.%m.%Y") if date_obj else ""

def extract_actual_commit_dates(sprints, changelog):
    """
    For each sprint, determine the actual commitment date.
    If the issue was added after the sprint started, use the changelog timestamp.
    Otherwise, use the sprint start date.
    """
    commit_dates = []
    sprint_id_to_start = {
        s.get("id"): get_date_obj(s.get("startDate"))
        for s in sprints if s.get("id") and s.get("startDate")
    }

    # Map sprint ID -> list of commit timestamps (from changelog)
    sprint_commits = {}
    if changelog:
        for entry in changelog.get("histories", []):
            created = get_date_obj(entry.get("created"))
            for item in entry.get("items", []):
                if item.get("field") == "Sprint":
                    added_ids = []
                    to = item.get("toString", "")
                    if to:
                        # Handle format like "[123, 456]" or "DEVOPS Sprint 17"
                        if to.startswith("[") and to.endswith("]"):
                            try:
                                added_ids = [int(x.strip()) for x in to[1:-1].split(",") if x.strip().isdigit()]
                            except:
                                continue
                    for sid in added_ids:
                        if sid in sprint_id_to_start:
                            sprint_commits.setdefault(sid, []).append(created)

    for sid, start_date in sprint_id_to_start.items():
        changelog_dates = sprint_commits.get(sid, [])
        if changelog_dates:
            # Only keep those changelog additions that happened after sprint start
            valid_commit_dates = [d for d in changelog_dates if d and d >= start_date]
            if valid_commit_dates:
                commit_dates.append(min(valid_commit_dates))
                continue
        # Otherwise fall back to sprint start date
        commit_dates.append(start_date)

    return commit_dates

def main():
    parser = argparse.ArgumentParser(
        description="Extract Jira issues data from multiple JSON files into a single CSV file."
    )
    parser.add_argument("input_files", nargs="+", help="Path(s) to the input JSON file(s)")
    parser.add_argument("output_file", help="Path to the output CSV file")
    parser.add_argument("--omit-outside-sprint", action="store_true", help="Omit issues that have no sprint information")
    parser.add_argument("--sprint-filter", type=str, help="Only include issues with a sprint whose name contains this substring (case-insensitive)")
    args = parser.parse_args()

    all_issues = []
    for filename in args.input_files:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_issues.extend(data.get("issues", []))

    with open(args.output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["issue key", "commitment date", "resolution date"])

        for issue in all_issues:
            key = issue.get("key", "")
            fields = issue.get("fields", {})
            changelog = issue.get("changelog", {})

            sprints = fields.get("customfield_10020") or []
            if args.sprint_filter:
                sprints = [s for s in sprints if s.get("name") and args.sprint_filter.lower() in s.get("name").lower()]

            if args.omit_outside_sprint and not sprints:
                continue

            commit_dates = extract_actual_commit_dates(sprints, changelog)
            commitment_date = min(commit_dates) if commit_dates else None

            resolution_dt = get_date_obj(fields.get("resolutiondate"))
            if commitment_date and resolution_dt and resolution_dt < commitment_date:
                continue

            writer.writerow([
                key,
                format_date(commitment_date),
                format_date(resolution_dt)
            ])

if __name__ == "__main__":
    main()
