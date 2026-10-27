import unittest
import os
import json
import sqlite3

import config
import database

class TestAnalyticsAndLimit(unittest.TestCase):
    def setUp(self):
        database.init_db()

    def test_01_free_message_limit_is_50(self):
        self.assertEqual(config.FREE_MESSAGE_LIMIT, 50)

    def test_02_log_user_analytics_event(self):
        test_user_id = 99999901
        success = database.log_user_analytics_event(
            user_id=test_user_id,
            event_name="screen_view",
            event_category="navigation",
            platform="android_app",
            metadata={"screen_name": "chat_screen"}
        )
        self.assertTrue(success)

        journey = database.get_user_full_journey(test_user_id)
        events = journey.get("analytics_events", [])
        self.assertTrue(len(events) >= 1)
        found = any(e['event_name'] == 'screen_view' and 'chat_screen' in (e.get('metadata') or '') for e in events)
        self.assertTrue(found)

    def test_03_get_user_behavior_analytics_overview(self):
        overview = database.get_user_behavior_analytics_overview()
        self.assertIn("total_users", overview)
        self.assertIn("funnel", overview)
        self.assertIn("free_message_limit", overview)
        self.assertEqual(overview["free_message_limit"], 50)

    def test_04_get_user_full_journey(self):
        test_user_id = 99999902
        # register or save user
        database.setup_user(test_user_id, "test_analytics_user", "Dhinesh")
        database.add_chat_message(test_user_id, "juhi", "user", "Hey Juhi!")
        database.add_chat_message(test_user_id, "juhi", "assistant", "Hey Dhinesh! I missed you.")
        database.log_user_analytics_event(test_user_id, "paywall_hit", "conversion", metadata={"messages_count": 50})

        journey = database.get_user_full_journey(test_user_id)
        self.assertEqual(journey["user_info"].get("telegram_id"), test_user_id)
        self.assertTrue(len(journey["chat_history"]) >= 2)
        self.assertTrue(len(journey["analytics_events"]) >= 1)
        self.assertTrue(journey["stats"]["total_messages"] >= 1)

    def test_05_export_user_behavior_csv(self):
        filepath, count = database.export_user_behavior_csv()
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(count >= 0)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("user_id", content)
            self.assertIn("messages_sent", content)
            self.assertIn("tried_to_pay", content)

    def test_06_batch_event_logging_and_live_feed(self):
        test_uid = 99999903
        database.setup_user(test_uid, "batch_user", "BatchTester")
        
        events = [
            {"user_id": test_uid, "event_name": "app_open", "event_category": "lifecycle", "metadata": {"session_id": "sess_1"}},
            {"user_id": test_uid, "event_name": "screen_view", "event_category": "navigation", "metadata": {"screen_name": "chat_screen"}},
            {"user_id": test_uid, "event_name": "mode_toggled", "event_category": "companion", "metadata": {"chat_mode": "intimate"}},
            {"user_id": test_uid, "event_name": "plan_selected", "event_category": "monetization", "metadata": {"plan_type": "chat_pass_1week", "amount": 199}},
        ]
        ok = database.log_user_analytics_events_batch(events)
        self.assertTrue(ok)

        feed = database.get_live_analytics_events(limit=10, user_id=test_uid)
        self.assertGreaterEqual(feed["total_count"], 4)
        event_names = [e["event_name"] for e in feed["events"]]
        self.assertIn("app_open", event_names)
        self.assertIn("mode_toggled", event_names)
        self.assertIn("plan_selected", event_names)

        # Category filter test
        nav_feed = database.get_live_analytics_events(limit=10, user_id=test_uid, event_category="navigation")
        self.assertTrue(all(e["event_category"] == "navigation" for e in nav_feed["events"]))

        # Search test
        search_feed = database.get_live_analytics_events(limit=10, user_id=test_uid, search="intimate")
        self.assertGreaterEqual(search_feed["total_count"], 1)

    def test_07_export_raw_events_csv(self):
        filepath, count = database.export_user_analytics_events_csv()
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(count >= 0)
        with open(filepath, "r", encoding="utf-8") as f:
            header = f.readline()
            self.assertIn("event_name", header)
            self.assertIn("event_category", header)

if __name__ == "__main__":
    unittest.main()

