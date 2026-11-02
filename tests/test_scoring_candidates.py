import unittest
from datetime import datetime, timedelta, timezone

from applypilot.discovery.workday import _location_ok
from applypilot.discovery.posting_dates import is_within_days, parse_posted_at
from applypilot.scoring.candidates import is_qualifying_job


class CandidateEligibilityTests(unittest.TestCase):
    def test_emea_support_job_qualifies(self):
        self.assertTrue(is_qualifying_job({
            "title": "Technical Support Specialist",
            "location": "Krakow, Poland",
            "url": "https://example.test/jobs/123",
        }))

    def test_unrestricted_worldwide_remote_job_qualifies(self):
        self.assertTrue(is_qualifying_job({
            "title": "Data Analyst",
            "location": "Remote worldwide",
            "url": "https://example.test/jobs/123",
        }))

    def test_us_remote_job_does_not_qualify_for_target_geography(self):
        self.assertFalse(is_qualifying_job({
            "title": "IT Support Engineer",
            "location": "United States, Remote",
            "url": "https://example.test/jobs/123",
        }))

    def test_unrelated_emea_role_does_not_qualify(self):
        self.assertFalse(is_qualifying_job({
            "title": "Business Development Manager",
            "location": "London, United Kingdom",
            "url": "https://example.test/jobs/123",
        }))

    def test_restricted_remote_location_is_rejected(self):
        self.assertFalse(_location_ok("United States, Remote", ["Poland"], ["United States"]))

    def test_posted_at_within_three_days_is_included(self):
        now = datetime(2026, 11, 2, 20, tzinfo=timezone.utc)
        posted = (now - timedelta(days=2)).isoformat()
        self.assertTrue(is_within_days(posted, days=3, now=now))

    def test_posted_at_older_than_three_days_is_excluded(self):
        now = datetime(2026, 11, 2, 20, tzinfo=timezone.utc)
        posted = (now - timedelta(days=3, seconds=1)).isoformat()
        self.assertFalse(is_within_days(posted, days=3, now=now))

    def test_undated_listing_is_excluded(self):
        self.assertFalse(is_within_days(None, days=3))

    def test_workday_relative_posting_date_is_parsed(self):
        now = datetime(2026, 11, 2, 20, tzinfo=timezone.utc)
        posted = parse_posted_at("Posted 2 Days Ago", now=now)
        self.assertTrue(is_within_days(posted, days=3, now=now))


if __name__ == "__main__":
    unittest.main()
