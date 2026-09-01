"""Local-first, human-in-the-loop job search agent (stdlib only)."""
from __future__ import annotations
import argparse, hashlib, json, random, re, signal, sqlite3, sys, time, urllib.parse, urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent
MIN_INTERVAL_SECONDS = 300
STOP_REQUESTED = False

@dataclass(frozen=True)
class Job:
    source: str; external_id: str; title: str; company: str; location: str
    description: str; url: str; salary: str = ""; language: str = ""

DEMO_JOBS = [
 Job("demo","1","Python Backend Developer","Example Labs","Berlin / Remote","Build Python APIs with SQL, Docker and cloud services. English team.","https://example.com/jobs/1","€60,000–€80,000","English"),
 Job("demo","2","Data Analyst","Example Analytics","Munich","Analyze data using SQL and Python. German required.","https://example.com/jobs/2","€55,000–€70,000","German"),
 Job("demo","3","Senior Java Engineer","Example Systems","Hamburg","Distributed Java services. Requires 7+ years.","https://example.com/jobs/3")]

class SourceAdapter(ABC):
    """Extension point for terms-compliant APIs or explicitly permitted feeds."""
    name: str
    @abstractmethod
    def fetch(self, profile: dict, config: dict) -> list[Job]: ...

class DemoAdapter(SourceAdapter):
    name = "demo"
    def fetch(self, profile, config): return DEMO_JOBS

class AdzunaAdapter(SourceAdapter):
    name = "adzuna"
    def fetch(self, profile, config):
        cfg = config.get("sources", {}).get("adzuna", {})
        if not cfg.get("app_id") or not cfg.get("app_key"):
            raise ValueError("config.json 缺少 sources.adzuna.app_id/app_key")
        params = urllib.parse.urlencode({"app_id":cfg["app_id"],"app_key":cfg["app_key"],
          "results_per_page":min(int(cfg.get("results_per_page",30)),50),
          "what":" ".join(profile.get("target_titles",[])),"where":" ".join(profile.get("locations",[])),"content-type":"application/json"})
        country = re.sub(r"[^a-z]","",str(cfg.get("country","de")).lower()) or "de"
        req = urllib.request.Request(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{params}",headers={"User-Agent":"LocalJobAgent/1.0"})
        with urllib.request.urlopen(req,timeout=float(cfg.get("timeout_seconds",20))) as response: payload=json.load(response)
        return [Job(self.name,str(x.get("id") or stable_id(x.get("redirect_url",""))),x.get("title",""),x.get("company",{}).get("display_name",""),x.get("location",{}).get("display_name",""),x.get("description",""),x.get("redirect_url",""),salary_text(x),"") for x in payload.get("results",[])]

ADAPTERS = {x.name:x for x in (DemoAdapter(),AdzunaAdapter())}
def stable_id(value): return hashlib.sha256(value.encode()).hexdigest()[:24]
def salary_text(x):
    low,high=x.get("salary_min"),x.get("salary_max")
    return f"{low:g}–{high:g}" if low is not None and high is not None else ""
def load_json(path, label):
    if not path.exists(): raise SystemExit(f"缺少 {path.name}。请复制对应的 .example.json 文件并编辑。")
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError,OSError) as exc: raise SystemExit(f"无法读取 {label}: {exc}") from exc
def now(): return datetime.now(timezone.utc).isoformat()

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try: return super().__exit__(exc_type, exc_value, traceback)
        finally: self.close()

def connect(path):
    db=sqlite3.connect(path, factory=ClosingConnection); db.row_factory=sqlite3.Row
    db.executescript("""CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,source TEXT NOT NULL,external_id TEXT NOT NULL,title TEXT NOT NULL,company TEXT NOT NULL,location TEXT NOT NULL,description TEXT NOT NULL,url TEXT NOT NULL,salary TEXT NOT NULL,language TEXT NOT NULL DEFAULT '',score INTEGER NOT NULL,reasons TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'new',discovered_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(source,external_id));
CREATE TABLE IF NOT EXISTS job_history(id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',changed_at TEXT NOT NULL,FOREIGN KEY(job_id) REFERENCES jobs(id));
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,source TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,jobs_seen INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '');""")
    cols={r[1] for r in db.execute("PRAGMA table_info(jobs)")}
    for name,ddl in (("language","TEXT NOT NULL DEFAULT ''"),("updated_at","TEXT NOT NULL DEFAULT ''")):
        if name not in cols: db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}")
    db.commit(); return db

def terms(text): return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}|[\u4e00-\u9fff]{2,}",text.lower()))
def salary_numbers(text):
    return [float(n.replace(",",""))*(1000 if k else 1) for n,k in re.findall(r"(\d[\d,.]*)(\s*[kK])?",text)]
def score_job(job, profile):
    full=f"{job.title} {job.description} {job.location} {job.language}".lower(); words=terms(full)
    skills=sorted({str(x).lower() for x in profile.get("skills",[])} & words)
    titles=[str(x).lower() for x in profile.get("target_titles",[]) if str(x).lower() in job.title.lower()]
    locations=[str(x).lower() for x in profile.get("locations",[]) if str(x).lower() in job.location.lower()]
    languages=[str(x).lower() for x in profile.get("languages",[]) if str(x).lower() in full]
    excluded=[str(x).lower() for x in profile.get("exclude_keywords",[]) if str(x).lower() in full]
    score=min(len(skills),5)*8+min(len(titles),1)*30+min(len(locations),1)*15+min(len(languages),1)*10; reasons=[]
    if titles: reasons.append(f"目标职位匹配: {titles[0]}")
    if skills: reasons.append("技能匹配: "+", ".join(skills))
    if locations: reasons.append(f"地点匹配: {locations[0]}")
    if languages: reasons.append(f"语言匹配: {languages[0]}")
    nums=salary_numbers(job.salary); minimum=profile.get("minimum_salary")
    if minimum is not None and nums:
        if max(nums)>=float(minimum): score+=10; reasons.append(f"薪资达到期望: {job.salary}")
        else: score-=20; reasons.append(f"薪资低于期望: {job.salary}")
    if excluded: score-=40*len(excluded); reasons.append("排除项: "+", ".join(excluded))
    return max(0,min(100,score)), reasons or ["没有明显匹配项"]

def save_jobs(path, jobs:Iterable[Job], profile):
    inserted=updated=0; stamp=now()
    with connect(path) as db:
        for job in jobs:
            score,reasons=score_job(job,profile); old=db.execute("SELECT id FROM jobs WHERE source=? AND external_id=?",(job.source,job.external_id)).fetchone()
            db.execute("""INSERT INTO jobs(source,external_id,title,company,location,description,url,salary,language,score,reasons,discovered_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,external_id) DO UPDATE SET title=excluded.title,company=excluded.company,location=excluded.location,description=excluded.description,url=excluded.url,salary=excluded.salary,language=excluded.language,score=excluded.score,reasons=excluded.reasons,updated_at=excluded.updated_at""",(*asdict(job).values(),score,json.dumps(reasons,ensure_ascii=False),stamp,stamp))
            if old: updated+=1
            else:
                inserted+=1; jid=db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute("INSERT INTO job_history(job_id,status,note,changed_at) VALUES(?,?,?,?)",(jid,"new","首次发现",stamp))
    return inserted,updated

def run_source(source,profile,config,path,sleep:Callable[[float],None]=time.sleep):
    if source not in ADAPTERS: raise ValueError(f"未知来源: {source}")
    retry=config.get("retry",{}); maximum=max(1,int(retry.get("max_attempts",3))); base=max(0,float(retry.get("base_delay_seconds",2)))
    with connect(path) as db: rid=db.execute("INSERT INTO runs(source,started_at,status) VALUES(?,?,?)",(source,now(),"running")).lastrowid
    for attempt in range(1,maximum+1):
        try:
            jobs=ADAPTERS[source].fetch(profile,config); result=save_jobs(path,jobs,profile)
            with connect(path) as db: db.execute("UPDATE runs SET finished_at=?,status='success',attempts=?,jobs_seen=? WHERE id=?",(now(),attempt,len(jobs),rid))
            return result
        except Exception as exc:
            if attempt<maximum: sleep(base*2**(attempt-1)+random.uniform(0,min(base,1))); continue
            with connect(path) as db: db.execute("UPDATE runs SET finished_at=?,status='failed',attempts=?,error=? WHERE id=?",(now(),attempt,str(exc)[:1000],rid))
            raise

def parse_interval(value):
    if isinstance(value,(int,float)): seconds=int(value)
    else:
        m=re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*",str(value),re.I)
        if not m: raise ValueError("频率格式应为 30m、2h、300s 或秒数")
        seconds=int(float(m.group(1))*{"":1,"s":1,"m":60,"h":3600,"d":86400}[m.group(2).lower()])
    if seconds<MIN_INTERVAL_SECONDS: raise ValueError("频率不得低于 300 秒（5 分钟）")
    return seconds
def schedule(source,profile,config,path,override):
    global STOP_REQUESTED
    interval=parse_interval(override or config.get("schedule",{}).get("interval","2h")); jitter=max(0,int(config.get("schedule",{}).get("jitter_seconds",60)))
    print(f"持续调度：来源={source}，间隔={interval}s，抖动=0..{jitter}s；Ctrl+C 退出。")
    while not STOP_REQUESTED:
        try: a,b=run_source(source,profile,config,path); print(f"{datetime.now().isoformat(timespec='seconds')} 新增 {a}，更新 {b}")
        except Exception as exc: print(f"本轮失败（已记录，下一轮继续）: {exc}")
        deadline=time.monotonic()+interval+random.uniform(0,jitter)
        while not STOP_REQUESTED and time.monotonic()<deadline: time.sleep(min(1,deadline-time.monotonic()))
    print("已安全停止。")
def print_jobs(path,min_score):
    with connect(path) as db: rows=db.execute("SELECT id,title,company,location,salary,score,status,url FROM jobs WHERE score>=? ORDER BY score DESC,id DESC",(min_score,)).fetchall()
    if not rows: print("没有符合阈值的岗位。先运行 run。")
    for r in rows: print(f"#{r['id']:03} [{r['score']:3}] {r['title']} | {r['company']} | {r['location']} | {r['salary']} | {r['status']}\n  {r['url']}")
def set_status(path,jid,status,note=""):
    allowed={"new","reviewing","drafted","applied","rejected","archived"}
    if status not in allowed: raise SystemExit("状态必须是: "+", ".join(sorted(allowed)))
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM jobs WHERE id=?",(jid,)).fetchone(): raise SystemExit(f"找不到岗位 #{jid}")
        stamp=now(); db.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?",(status,stamp,jid)); db.execute("INSERT INTO job_history(job_id,status,note,changed_at) VALUES(?,?,?,?)",(jid,status,note,stamp))
def draft(path,jid,profile,out):
    with connect(path) as db: row=db.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone()
    if not row: raise SystemExit(f"找不到岗位 #{jid}")
    reasons="；".join(json.loads(row["reasons"])); template=profile.get("cover_letter_template") or "您好，\n\n我希望申请贵公司的 {title} 职位。{reasons}。期待进一步交流。\n\n此致\n{name}\n"
    content=template.format(name=profile.get("name","候选人"),title=row["title"],company=row["company"],reasons=reasons); out.mkdir(parents=True,exist_ok=True)
    safe=re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+","_",f"{row['company']}_{row['title']}").strip("_"); target=out/f"{jid}_{safe}.md"
    target.write_text(f"# 申请草稿：{row['title']} — {row['company']}\n\n> 仅供人工审核；本程序不会自动投递。\n\n岗位链接：{row['url']}\n\n{content}",encoding="utf-8"); set_status(path,jid,"drafted",f"草稿: {target.name}"); return target
def stop(*_):
    global STOP_REQUESTED; STOP_REQUESTED=True
def main():
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(errors="replace")
    p=argparse.ArgumentParser(description="本地优先、人工确认的智能求职 Agent"); p.add_argument("--profile",type=Path,default=ROOT/"profile.json"); p.add_argument("--config",type=Path,default=ROOT/"config.json"); p.add_argument("--db",type=Path)
    sub=p.add_subparsers(dest="command",required=True); run=sub.add_parser("run"); run.add_argument("--source"); watch=sub.add_parser("watch"); watch.add_argument("--source"); watch.add_argument("--interval"); listing=sub.add_parser("list"); listing.add_argument("--min-score",type=int,default=40); drafting=sub.add_parser("draft"); drafting.add_argument("job_id",type=int); status=sub.add_parser("status"); status.add_argument("job_id",type=int); status.add_argument("status"); status.add_argument("--note",default="")
    a=p.parse_args(); profile=load_json(a.profile,"用户画像"); config=load_json(a.config,"运行配置"); path=a.db or ROOT/config.get("database","jobs.db"); source=getattr(a,"source",None) or config.get("default_source","demo"); signal.signal(signal.SIGINT,stop)
    if hasattr(signal,"SIGTERM"): signal.signal(signal.SIGTERM,stop)
    if a.command=="run": x,y=run_source(source,profile,config,path); print(f"完成：新增 {x}，更新 {y}。")
    elif a.command=="watch": schedule(source,profile,config,path,a.interval)
    elif a.command=="list": print_jobs(path,a.min_score)
    elif a.command=="draft": print(f"草稿已生成：{draft(path,a.job_id,profile,ROOT/config.get('draft_directory','drafts'))}（请人工检查后再投递）")
    else: set_status(path,a.job_id,a.status,a.note); print("状态已更新。")
if __name__=="__main__": main()
