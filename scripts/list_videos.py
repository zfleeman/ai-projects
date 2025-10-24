import csv
from datetime import datetime

import pytz
from openai import OpenAI

from scripts.api_keys import api_keys

API_KEY = api_keys["B4NG AI"]

client = OpenAI(api_key=API_KEY)

videos_list = client.videos.list().data


def format_timestamp(ts):
    if not ts:
        return ""
    tz = pytz.timezone("America/Denver")
    dt = datetime.fromtimestamp(ts, tz)
    return dt.strftime("%A - %Y-%m-%d %I:%M%p")


def format_duration(start, end):
    if not start or not end:
        return ""
    seconds = int(end - start)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


# Get current run timestamp
run_tz = pytz.timezone("America/Denver")
run_at = datetime.now(run_tz)
run_at_str = run_at.strftime("%Y-%m-%d %H:%M:%S %Z")
FILENAME = f"videos_{run_at.strftime('%Y%m%d_%H%M%S')}.csv"

headers = ["ID", "Status", "Created At", "Completed At", "Duration", "Progress"]

with open(FILENAME, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(headers)
    for v in videos_list:
        created = getattr(v, "created_at", None)
        completed = getattr(v, "completed_at", None)
        row = [
            getattr(v, "id", ""),
            getattr(v, "status", ""),
            format_timestamp(created),
            format_timestamp(completed),
            format_duration(created, completed),
            f"{getattr(v, 'progress', 0)}%",
        ]
        writer.writerow(row)

print(f"Wrote {len(videos_list)} videos to {FILENAME}")
