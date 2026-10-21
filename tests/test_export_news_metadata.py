import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("exporter", Path(__file__).resolve().parents[1] / "scripts/export_news_metadata.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def test_current_run_only_and_metadata_whitelist(self):
        started = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        now = datetime(2026, 10, 21, 13, tzinfo=timezone.utc)
        row = {"date_scraped": "2026-10-21 12:10:00", "article_url": "https://publisher.example/story?utm_source=x",
               "headline": "Dallas police report theft", "where": "Dallas;Texas", "who": "PRIVATE NAME",
               "content": "PRIVATE BODY", "publication_date": "2026-10-21"}
        result = exporter.build_snapshot([row, {**row, "article_url": "https://publisher.example/story#part"},
            {**row, "date_scraped": "2026-02-24 12:00:00"}, {**row, "date_scraped": "2026-10-22 12:00:00"}], started, now, "abc")
        self.assertEqual(len(result["articles"]), 1)
        self.assertIsNone(result["articles"][0]["publishedAt"])
        self.assertEqual(result["articles"][0]["capturedAt"], "2026-10-21T12:10:00Z")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(result["articles"][0]["articleUrl"], "https://publisher.example/story")

    def test_invalid_rows_empty_freshness_and_caps(self):
        now = datetime(2026, 10, 21, 13, tzinfo=timezone.utc)
        base = {"date_scraped": "2026-10-21 12:10:00", "article_url": "https://publisher.example/story", "headline": "Story", "where": "Dallas"}
        bad = [{**base, "article_url": "https://user:secret@publisher.example/story"}, {**base, "date_scraped": "unknown"}]
        self.assertEqual(exporter.build_snapshot(bad, now, now, "a")["status"], "no_fresh_candidates")
        many = [{**base, "article_url": f"https://publisher.example/{i}"} for i in range(600)]
        result = exporter.build_snapshot(many, now.replace(hour=12), now, "a")
        self.assertEqual(len(result["articles"]), 500)
        self.assertLessEqual(len(json.dumps(result).encode()), 512 * 1024)


if __name__ == "__main__":
    unittest.main()
