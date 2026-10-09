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

if __name__ == "__main__":
    unittest.main()
