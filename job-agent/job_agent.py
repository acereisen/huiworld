"""A safe, local-first job-search agent.

The agent discovers jobs, scores them against a candidate profile, stores results
in SQLite, and creates application drafts. It never submits an application.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "jobs.db"
PROFILE_PATH = ROOT / "profile.json"


@dataclass(frozen=True)
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    salary: str = ""


DEMO_JOBS = [
    Job("demo", "1", "Python Backend Developer", "Example Labs", "Berlin / Remote",
        "Build Python APIs, work with SQL, Docker and cloud services.", "https://example.com/jobs/1", "€60k–€80k"),
    Job("demo", "2", "Data Analyst", "Example Analytics", "Munich",
        "Analyze product data using SQL, Python, dashboards and statistics.", "https://example.com/jobs/2", "€55k–€70k"),
    Job("demo", "3", "Senior Java Engineer", "Example Systems", "Hamburg",
        "Design distributed Java services. Requires 7+ years of experience.", "https://example.com/jobs/3"),
]


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise SystemExit("Missing profile.json. Copy profile.example.json to profile.json and edit it.")
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            url TEXT NOT NULL,
            salary TEXT NOT NULL,
            score INTEGER NOT NULL,
            reasons TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            discovered_at TEXT NOT NULL,
            UNIQUE(source, external_id)
        )
    """)
    return db


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fff]{2,}", text.lower()))


def score_job(job: Job, profile: dict) -> tuple[int, list[str]]:
    haystack = terms(f"{job.title} {job.description} {job.location}")
    wanted = {str(x).lower() for x in profile.get("skills", [])}
    titles = [str(x).lower() for x in profile.get("target_titles", [])]
    locations = [str(x).lower() for x in profile.get("locations", [])]
    excluded = [str(x).lower() for x in profile.get("exclude_keywords", [])]
    full_text = f"{job.title} {job.description} {job.location}".lower()

    skill_hits = sorted(x for x in wanted if x in haystack or x in full_text)
    title_hits = [x for x in titles if x in job.title.lower()]
    location_hits = [x for x in locations if x in job.location.lower()]
    excluded_hits = [x for x in excluded if x in full_text]
    score = min(100, len(skill_hits) * 10 + min(len(title_hits), 1) * 30 + min(len(location_hits), 1) * 15)
    score = max(0, score - len(excluded_hits) * 35)
    reasons = []
    if title_hits:
        reasons.append(f"目标职位匹配: {title_hits[0]}")
    if skill_hits:
        reasons.append("技能匹配: " + ", ".join(skill_hits))
    if location_hits:
        reasons.append(f"地点匹配: {location_hits[0]}")
    if excluded_hits:
        reasons.append("排除项: " + ", ".join(excluded_hits))
    return score, reasons or ["没有明显匹配项"]


def fetch_adzuna(profile: dict) -> list[Job]:
    cfg = profile.get("adzuna", {})
    if not cfg.get("app_id") or not cfg.get("app_key"):
        raise SystemExit("profile.json 中缺少 adzuna.app_id/app_key。")
    country = cfg.get("country", "de")
    params = urllib.parse.urlencode({
        "app_id": cfg["app_id"], "app_key": cfg["app_key"],
        "results_per_page": cfg.get("results_per_page", 30),
        "what": " ".join(profile.get("target_titles", [])),
        "where": " ".join(profile.get("locations", [])),
        "content-type": "application/json",
    })
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{params}"
    with urllib.request.urlopen(url, timeout=20) as response:
        payload = json.load(response)
    return [Job(
        "adzuna", str(item["id"]), item.get("title", ""),
        item.get("company", {}).get("display_name", ""),
        item.get("location", {}).get("display_name", ""),
        item.get("description", ""), item.get("redirect_url", ""),
        _salary(item),
    ) for item in payload.get("results", [])]


def _salary(item: dict) -> str:
    low, high = item.get("salary_min"), item.get("salary_max")
    return f"{low:g}–{high:g}" if low is not None and high is not None else ""


def save_jobs(jobs: Iterable[Job], profile: dict) -> tuple[int, int]:
    inserted = updated = 0
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        for job in jobs:
            score, reasons = score_job(job, profile)
            exists = db.execute("SELECT 1 FROM jobs WHERE source=? AND external_id=?",
                                (job.source, job.external_id)).fetchone()
            db.execute("""
                INSERT INTO jobs(source, external_id, title, company, location, description,
                    url, salary, score, reasons, discovered_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    title=excluded.title, company=excluded.company, location=excluded.location,
                    description=excluded.description, url=excluded.url, salary=excluded.salary,
                    score=excluded.score, reasons=excluded.reasons
            """, (*asdict(job).values(), score, json.dumps(reasons, ensure_ascii=False), now))
            inserted += not bool(exists)
            updated += bool(exists)
    return inserted, updated


def print_jobs(min_score: int) -> None:
    rows = connect().execute(
        "SELECT id,title,company,location,score,status,url FROM jobs WHERE score>=? ORDER BY score DESC,id DESC",
        (min_score,),
    ).fetchall()
    if not rows:
        print("没有符合阈值的岗位。先运行 search。")
        return
    for row in rows:
        print(f"#{row['id']:03} [{row['score']:3}] {row['title']} | {row['company']} | {row['location']} | {row['status']}\n  {row['url']}")


def draft(job_id: int, profile: dict) -> Path:
    row = connect().execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise SystemExit(f"找不到岗位 #{job_id}")
    reasons = "；".join(json.loads(row["reasons"]))
    name = profile.get("name", "候选人")
    template = profile.get("cover_letter_template") or (
        "您好，\n\n我希望申请贵公司的 {title} 职位。{reasons}。"
        "我相信自己的经验可以为团队带来价值，期待进一步交流。\n\n此致\n{name}\n"
    )
    content = template.format(name=name, title=row["title"], company=row["company"], reasons=reasons)
    out_dir = ROOT / "drafts"
    out_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "_", f"{row['company']}_{row['title']}").strip("_")
    path = out_dir / f"{job_id}_{safe_name}.md"
    path.write_text(f"# {row['title']} — {row['company']}\n\n岗位链接：{row['url']}\n\n{content}", encoding="utf-8")
    with connect() as db:
        db.execute("UPDATE jobs SET status='drafted' WHERE id=?", (job_id,))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="本地优先的自动找工作 Agent")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="搜索、评分并保存岗位")
    search.add_argument("--source", choices=["demo", "adzuna"], default="demo")
    listing = sub.add_parser("list", help="列出匹配岗位")
    listing.add_argument("--min-score", type=int, default=40)
    drafting = sub.add_parser("draft", help="为岗位生成申请草稿")
    drafting.add_argument("job_id", type=int)
    args = parser.parse_args()

    profile = load_profile()
    if args.command == "search":
        jobs = DEMO_JOBS if args.source == "demo" else fetch_adzuna(profile)
        inserted, updated = save_jobs(jobs, profile)
        print(f"完成：新增 {inserted}，更新 {updated}。运行 python job_agent.py list 查看结果。")
    elif args.command == "list":
        print_jobs(args.min_score)
    elif args.command == "draft":
        print(f"草稿已生成：{draft(args.job_id, profile)}（请人工检查后再投递）")


if __name__ == "__main__":
    main()
