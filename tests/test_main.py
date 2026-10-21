import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import main


class BotTests(unittest.TestCase):
    def test_structured_results_distinguish_empty_from_invalid_page(self):
        envelope = json.dumps({"status": 200, "body": json.dumps({"results": {"items": [], "total": {"value": 0}}})})
        soup = BeautifulSoup('<script type="application/json" data-sveltekit-fetched data-url="/api/search/47">' + envelope + '</script>', "html.parser")
        self.assertEqual(main.results_from(soup)["items"], [])
        with self.assertRaises(ValueError):
            main.results_from(BeautifulSoup("<h1>Maintenance</h1>", "html.parser"))

    def test_detect_active_campaign_and_keep_geographic_bounds(self):
        soup = BeautifulSoup('<a href="/tools/47/search">Cette année</a>', "html.parser")
        with patch.dict(main.os.environ, {}, clear=True), patch.object(main, "soup_at", return_value=soup):
            url = main.search_url(object())
        self.assertIn("/tools/47/search?bounds=" + main.BOUNDS, url)

    def test_only_available_offers_are_reported(self):
        items = [{"id": i, "label": "Studio", "available": available, "residence": {"label": "Résidence"}}
                 for i, available in [(1, True), (2, False), (3, None)]]
        data = {"items": items, "total": {"value": 3}}
        with patch.object(main, "search_url", return_value=main.BASE_URL + "/tools/47/search"), \
             patch.object(main, "soup_at", return_value=BeautifulSoup("", "html.parser")), \
             patch.object(main, "results_from", return_value=data):
            offers = main.collect(object())
        self.assertEqual(list(offers), [main.BASE_URL + "/tools/47/accommodations/1"])

    def test_partial_success_persisted_and_failed_send_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sent.json"
            offers = {"first": "message 1", "second": "message 2"}
            with patch.object(main, "send_telegram", side_effect=[None, RuntimeError("network")]):
                with self.assertRaises(RuntimeError):
                    main.notify(object(), offers, set(), path, "token", "chat")
            self.assertEqual(main.load_state(path), {"first"})
            with patch.object(main, "send_telegram") as send:
                self.assertEqual(main.notify(object(), offers, main.load_state(path), path, "token", "chat"), 1)
                self.assertEqual(send.call_args.args[-1], "message 2")
            self.assertEqual(main.load_state(path), {"first", "second"})

    def test_corrupt_history_stops_instead_of_resending_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sent.json"
            path.write_text('{}', encoding="utf-8")
            with self.assertRaises(ValueError):
                main.load_state(path)


if __name__ == "__main__":
    unittest.main()
