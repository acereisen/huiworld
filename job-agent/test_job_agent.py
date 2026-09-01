import tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
import job_agent
from job_agent import Job, connect, parse_interval, run_source, save_jobs, score_job, set_status

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"test.db"
        self.profile={"target_titles":["python"],"skills":["python","sql"],"locations":["berlin"],"languages":["english"],"minimum_salary":60000,"exclude_keywords":["senior"]}
    def tearDown(self): self.tmp.cleanup()
    def test_matching_uses_all_profile_dimensions(self):
        good=Job("x","1","Python Developer","A","Berlin","Python SQL English","u","€65k","English")
        bad=Job("x","2","Senior Java Developer","B","Berlin","Java","u")
        self.assertGreater(score_job(good,self.profile)[0],score_job(bad,self.profile)[0])
        self.assertLessEqual(score_job(good,self.profile)[0],100)
    def test_interval_and_guard(self):
        self.assertEqual(parse_interval("30m"),1800); self.assertEqual(parse_interval("2h"),7200)
        with self.assertRaises(ValueError): parse_interval("4m")
    def test_dedup_and_status_history(self):
        job=Job("x","same","Python","A","Berlin","Python","u")
        self.assertEqual(save_jobs(self.db,[job],self.profile),(1,0)); self.assertEqual(save_jobs(self.db,[job],self.profile),(0,1)); set_status(self.db,1,"reviewing","人工查看")
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0],1); self.assertEqual(db.execute("SELECT count(*) FROM job_history").fetchone()[0],2)
    def test_retry_and_run_history(self):
        adapter=Mock(); adapter.fetch.side_effect=[OSError("temporary"),[Job("flaky","1","Python","A","Berlin","Python","u")]]
        with patch.dict(job_agent.ADAPTERS,{"flaky":adapter}): result=run_source("flaky",self.profile,{"retry":{"max_attempts":2,"base_delay_seconds":0}},self.db,sleep=lambda _:None)
        self.assertEqual(result,(1,0))
        with connect(self.db) as db: self.assertEqual(tuple(db.execute("SELECT status,attempts FROM runs").fetchone()),("success",2))
if __name__=="__main__": unittest.main()
