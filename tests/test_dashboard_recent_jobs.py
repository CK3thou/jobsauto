import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from applypilot import web
from applypilot.database import close_connection, init_db


class RecentDashboardJobsTests(unittest.TestCase):
    def test_dashboard_only_returns_jobs_posted_within_three_days(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jobs.db"
            conn = init_db(db_path)
            try:
                now = datetime.now(timezone.utc)
                recent = (now - timedelta(days=2)).isoformat()
                old = (now - timedelta(days=3, seconds=1)).isoformat()
                future = (now + timedelta(seconds=1)).isoformat()
                for url, posted_at in (
                    ("https://example.test/recent", recent),
                    ("https://example.test/old", old),
                    ("https://example.test/unknown", None),
                    ("https://example.test/future", future),
                ):
                    conn.execute(
                        "INSERT INTO jobs (url, title, posted_at) VALUES (?, ?, ?)",
                        (url, "Data Analyst", posted_at),
                    )
                conn.commit()

                with patch.object(web, "get_connection", return_value=conn):
                    result = web._dashboard_data()

                self.assertEqual([job["url"] for job in result["jobs"]], ["https://example.test/recent"])
                self.assertEqual(result["stats"]["total"], 1)
            finally:
                close_connection(db_path)


if __name__ == "__main__":
    unittest.main()
