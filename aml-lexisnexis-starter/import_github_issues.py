import csv
import requests
import sys

GITHUB_TOKEN = input("Enter your GitHub Personal Access Token: ").strip()
REPO = "Ziggler01/AML-LexisNexis-Anomaly"
API_BASE = f"https://api.github.com/repos/{REPO}"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def get_milestone_map():
    """Fetch all milestones and return a mapping title -> number."""
    milestones = {}
    page = 1
    while True:
        r = requests.get(f"{API_BASE}/milestones?state=all&page={page}", headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        for m in data:
            milestones[m["title"]] = m["number"]
        page += 1
    return milestones

def create_issue(row, milestone_map):
    title = row["Title"]
    body = row.get("Body", "")
    labels = [l.strip() for l in row.get("Labels", "").split(",") if l.strip()]
    milestone_title = row.get("Milestone", "").strip()
    milestone_num = milestone_map.get(milestone_title) if milestone_title else None

    issue = {
        "title": title,
        "body": body,
        "labels": labels,
    }
    if milestone_num:
        issue["milestone"] = milestone_num

    resp = requests.post(f"{API_BASE}/issues", json=issue, headers=HEADERS)
    if resp.status_code == 201:
        print(f"✅ Created: {title}")
    else:
        print(f"❌ Failed: {title} - {resp.status_code} - {resp.text}")

def main():
    milestone_map = get_milestone_map()
    print("Milestone titles found:", milestone_map.keys())

    with open("github_issues_phase1.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            milestone = row.get("Milestone", "").strip()
            if milestone and milestone not in milestone_map:
                print(f"⚠️ Milestone '{milestone}' not found for issue '{row['Title']}'. Issue will be created without a milestone.")
            create_issue(row, milestone_map)

if __name__ == "__main__":
    main()