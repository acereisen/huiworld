import unittest

from job_agent import Job, score_job


class ScoreTests(unittest.TestCase):
    def test_good_match_scores_higher_than_excluded_job(self):
        profile = {
            "target_titles": ["python"], "skills": ["python", "sql"],
            "locations": ["berlin"], "exclude_keywords": ["senior"],
        }
        good = Job("x", "1", "Python Developer", "A", "Berlin", "Python and SQL", "u")
        bad = Job("x", "2", "Senior Java Developer", "B", "Berlin", "Java", "u")
        self.assertGreater(score_job(good, profile)[0], score_job(bad, profile)[0])

    def test_score_is_bounded(self):
        profile = {"target_titles": ["python"], "skills": ["python"] * 20, "locations": ["remote"]}
        job = Job("x", "1", "Python", "A", "Remote", "Python", "u")
        self.assertLessEqual(score_job(job, profile)[0], 100)


if __name__ == "__main__":
    unittest.main()
