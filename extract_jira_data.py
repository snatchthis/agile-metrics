import json
import argparse
import csv
from datetime import datetime

def get_date_obj(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(date_str[:23], "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            return None

def format_date(dt, date_format):
    return dt.strftime(date_format) if dt else ""

def extract_actual_commit_dates(sprints, changelog, issue_created_date):
    sprint_id_to_start = {s["id"]: get_date_obj(s.get("startDate")) for s in sprints if s.get("id") and s.get("startDate")}
    sprint_ids = set(sprint_id_to_start.keys())

    commit_dates = []

    if changelog:
        for history in changelog.get("histories", []):
            for item in history.get("items", []):
                if item.get("field") == "Sprint":
                    to_field = item.get("to")
                    if to_field:
                        to_ids = [int(x.strip()) for x in to_field.strip("[]").split(",") if x.strip().isdigit()]
                    else:
                        to_ids = []
                    for sid in to_ids:
                        if sid in sprint_ids:
                            history_dt = get_date_obj(history.get("created"))
                            if history_dt:
                                commit_dates.append((sid, history_dt))

    result_dates = []
    for sid, start_date in sprint_id_to_start.items():
        valid_commit_dates = [cd for s_id, cd in commit_dates if s_id == sid]
        if valid_commit_dates:
            result_dates.append(min(valid_commit_dates))
        elif issue_created_date and start_date and issue_created_date > start_date:
            result_dates.append(issue_created_date)
        else:
            result_dates.append(start_date)

    return result_dates

def extract_status_dates(changelog):
    status_dates = {}
    for history in changelog.get("histories", []):
        for item in history.get("items", []):
            if item.get("field") == "status":
                status = item.get("toString")
                date = get_date_obj(history.get("created"))
                if status and date and status not in status_dates:
                    status_dates[status] = date
    return status_dates

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_files", nargs="+")
    parser.add_argument("output_file")
    parser.add_argument("--omit-outside-sprint", action="store_true")
    parser.add_argument("--sprint-keyword", action="append", help="Keyword to match in sprint names (can be used multiple times)")
    parser.add_argument("--date-format", default="%d-%m-%Y")
    args = parser.parse_args()

    issue_data = []

    for file in args.input_files:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)

        for issue in data.get("issues", []):
            key = issue.get("key")
            fields = issue.get("fields", {})
            changelog = issue.get("changelog", {})
            issuetype = fields.get("issuetype", {}).get("name", "")

            created_dt = get_date_obj(fields.get("created"))
            created_str = format_date(created_dt, args.date_format)
            resolution_dt = get_date_obj(fields.get("resolutiondate"))

            sprints = sorted(fields.get("customfield_10020") or [], key=lambda s: s.get("startDate") or "", reverse=False)

            if args.omit_outside_sprint and not sprints:
                continue
            if args.sprint_keyword and not any(
                any(keyword in s.get("name", "") for keyword in args.sprint_keyword) for s in sprints
            ):
                continue

            status_dates = extract_status_dates(changelog)
            commit_dates = extract_actual_commit_dates(sprints, changelog, created_dt)
            commitment_date = min(commit_dates) if commit_dates else None
            
            # If any status transition date is before the start of the sprint, use the earliest of those as commitment
            if commit_dates:
                sprint_start = min(commit_dates)
                early_status_dates = [dt for dt in status_dates.values() if dt and dt < sprint_start]
                if early_status_dates:
                    commitment_date = min(early_status_dates)

            new_dt = status_dates.get("New")
            todo_dt = status_dates.get("To Do")
            candidates = [d for d in [commitment_date, new_dt, todo_dt] if d]
            commitment_date = max(candidates) if candidates else None

            if resolution_dt and commitment_date and resolution_dt < commitment_date:
                continue

            issue_data.append({
                "key": key,
                "issuetype": issuetype,
                "created": created_str,
                "commitment_date": format_date(commitment_date, args.date_format),
                "statuses": status_dates
            })

    all_statuses = sorted({status for item in issue_data for status in item["statuses"]})
    header = ["Issue Key", "issue type", "Backlog", "To Do"] + all_statuses

    with open(args.output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for item in issue_data:
            row = [
                item["key"],
                item["issuetype"],
                item["created"],
                item["commitment_date"]
            ] + [format_date(item["statuses"].get(status), args.date_format) for status in all_statuses]
            writer.writerow(row)

if __name__ == "__main__":
    main()
