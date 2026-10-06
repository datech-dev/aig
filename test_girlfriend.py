import os
import sys
import unittest
from unittest.mock import patch, AsyncMock

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import config
import database
import ai_engine

class TestGirlfriendApp(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Use isolated test database so production girlfriend.db is never deleted
        database.DB_PATH = "test_girlfriend.db"
        if os.path.exists("test_girlfriend.db"):
            try:
                os.remove("test_girlfriend.db")
            except OSError:
                pass
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = "girlfriend.db"
        if os.path.exists("test_girlfriend.db"):
            try:
                os.remove("test_girlfriend.db")
            except OSError:
                pass
        
    def test_01_config_loading(self):
        """Verify settings and level thresholds are defined correctly."""
        self.assertIsNotNone(config.PERSONAS)
        self.assertIn("juhi", config.PERSONAS)
        self.assertNotIn("sakura", config.PERSONAS)  # Sakura should be removed
        self.assertIsNotNone(config.VENICE_IMAGE_MODEL)
        self.assertEqual(config.VENICE_IMAGE_MODEL, "lustify-v7")
        
        # Test level ranges
        status_l1 = config.get_relationship_status(0)
        self.assertEqual(status_l1["level"], 1)
        self.assertEqual(status_l1["title"], "Acquaintances")
        self.assertEqual(status_l1["percent"], 0)
        
        status_l3 = config.get_relationship_status(450)
        self.assertEqual(status_l3["level"], 3)
        self.assertEqual(status_l3["title"], "Close Friends")
        
        # Max level boundary
        status_max = config.get_relationship_status(5000)
        self.assertEqual(status_max["level"], 6)
        self.assertEqual(status_max["title"], "Soulmates")
        self.assertEqual(status_max["percent"], 100)
        
    def test_02_database_operations(self):
        """Verify DB initialization, Juhi profile updates, XP increments, and history logging."""
        test_id = 999999999
        username = "test_user"
        first_name = "Tester"
        
        # Setup user
        database.setup_user(test_id, username, first_name)
        
        # Verify user settings default to Juhi
        settings = database.get_user_settings(test_id)
        self.assertIsNotNone(settings)
        self.assertEqual(settings["active_persona"], "juhi")
        self.assertEqual(settings["user_nickname"], "Tester")
        self.assertEqual(settings["ai_nickname"], "Juhi")
        self.assertEqual(settings["relationship_xp"], 0)
        self.assertEqual(settings["relationship_level"], 1)
        
        # Test updating nicknames
        database.update_nicknames(test_id, user_nickname="Honey", ai_nickname="Juhi Baby")
        settings = database.get_user_settings(test_id)
        self.assertEqual(settings["user_nickname"], "Honey")
        self.assertEqual(settings["ai_nickname"], "Juhi Baby")
        
        # Test XP increments for Juhi
        leveled_up, level, title = database.add_xp(test_id, amount=120)
        settings = database.get_user_settings(test_id)
        self.assertTrue(leveled_up)
        self.assertEqual(level, 2)
        self.assertEqual(settings["relationship_xp"], 120)
        
        # Test chat messages logging
        database.add_chat_message(test_id, "juhi", "user", "I want you.")
        database.add_chat_message(test_id, "juhi", "assistant", "Hmph, really? 😳")
        
        history = database.get_chat_history(test_id, "juhi")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "I want you.")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Hmph, really? 😳")
        
        # Test clear logs
        database.clear_chat_history(test_id, "juhi")
        history = database.get_chat_history(test_id, "juhi")
        self.assertEqual(len(history), 0)
        
    def test_03_ai_engine_initialization(self):
        """Verify prompt constructs contains image generation triggers and nicknames."""
        test_id = 888888888
        database.setup_user(test_id, "dummy", "Dummy")
        settings = database.get_user_settings(test_id)
        
        # Test system prompt builder (default: Caring Best Friend mode)
        system_prompt = config.construct_system_prompt(
            persona_key=settings["active_persona"],
            relationship_xp=settings["relationship_xp"],
            user_nickname=settings["user_nickname"],
            ai_nickname=settings["ai_nickname"]
        )
        
        self.assertIn("Juhi", system_prompt)
        self.assertIn("caring, warm, supportive", system_prompt)
        self.assertIn("Dummy", system_prompt)
        self.assertIn("GENERATE_IMAGE", system_prompt)  # Ensure tag guidelines are present
        
        # Test intimate mode system prompt builder
        system_prompt_intimate = config.construct_system_prompt(
            persona_key=settings["active_persona"],
            relationship_xp=settings["relationship_xp"],
            user_nickname=settings["user_nickname"],
            ai_nickname=settings["ai_nickname"],
            chat_mode="intimate"
        )
        self.assertIn("loving, sweet girlfriend", system_prompt_intimate)

    def test_04_billing_operations(self):
        """Verify billing db helpers, limits, and blocking checks."""
        test_id = 777777777
        database.setup_user(test_id, "billing_user", "BillingUser")
        
        # Initial check
        billing = database.get_user_billing(test_id)
        self.assertIsNotNone(billing)
        self.assertEqual(billing["free_messages_used"], 0)
        self.assertEqual(billing["image_credits"], 2)
        self.assertIsNone(billing["chat_expires_at"])
        
        # Chat subscription is initially False
        self.assertFalse(database.is_chat_subscribed(test_id))
        
        # Increment free messages
        database.increment_free_messages(test_id)
        billing = database.get_user_billing(test_id)
        self.assertEqual(billing["free_messages_used"], 1)
        
        # Grant chat pass (1 day / 24 hours)
        expiry = database.grant_chat_pass(test_id, hours=config.CHAT_PASS_DURATION_HOURS)
        self.assertIsNotNone(expiry)
        self.assertTrue(database.is_chat_subscribed(test_id))
        
        # Grant image credits
        database.grant_image_credits(test_id, amount=10)
        billing = database.get_user_billing(test_id)
        self.assertEqual(billing["image_credits"], 12)
        
        # Deduct image credit
        success = database.use_image_credit(test_id)
        self.assertTrue(success)
        billing = database.get_user_billing(test_id)
        self.assertEqual(billing["image_credits"], 11)
        
        # Deduct all remaining credits to test boundary
        for _ in range(11):
            database.use_image_credit(test_id)
        billing = database.get_user_billing(test_id)
        self.assertEqual(billing["image_credits"], 0)
        
        # Next deduction should fail
        success = database.use_image_credit(test_id)
        self.assertFalse(success)
        
    def test_05_consistent_face_prompt(self):
        """Verify prompt combination logic avoids duplication and prepends appearance correctly."""
        appearance = "Juhi, a beautiful blonde girl"
        
        # Scenario 1: Prompt starts with character name
        prompt_with_name = "Juhi looking sexy in bedroom"
        full_prompt = config.combine_appearance_and_prompt(appearance, prompt_with_name)
        self.assertEqual(full_prompt, "Juhi, a beautiful blonde girl, looking sexy in bedroom")
        
        # Scenario 2: Prompt doesn't start with character name
        prompt_no_name = "looking naughty, smiling"
        full_prompt_no_name = config.combine_appearance_and_prompt(appearance, prompt_no_name)
        self.assertEqual(full_prompt_no_name, "Juhi, a beautiful blonde girl, looking naughty, smiling")
        
        # Scenario 3: Empty prompt
        full_prompt_empty = config.combine_appearance_and_prompt(appearance, "")
        self.assertEqual(full_prompt_empty, appearance)

    @patch('os.listdir')
    @patch('os.path.exists')
    def test_06_reaction_gifs_logic(self, mock_exists, mock_listdir):
        """Verify GIF scanning based strictly on file names and heuristic matching logic."""
        mock_exists.return_value = True
        mock_listdir.return_value = ["kissing.gif", "holding-hands.gif", "smile.gif"]
        
        gif_descriptions = config.get_gif_descriptions()
        
        # Check description loading
        self.assertIn("kissing", gif_descriptions)
        self.assertEqual(gif_descriptions["kissing"], "kissing")
        
        self.assertIn("holding-hands", gif_descriptions)
        self.assertEqual(gif_descriptions["holding-hands"], "holding hands")
        
        self.assertIn("smile", gif_descriptions)
        self.assertEqual(gif_descriptions["smile"], "smile")
        
        # Match via prefix/fuzzy keyword ("kiss" matches "kissing")
        match1 = config.find_matching_gif("she blew a kiss", "she did?", gif_descriptions)
        self.assertEqual(match1, "kissing")
        
        # Match via fallback name ("hold hands" matches "holding hands")
        match2 = config.find_matching_gif("I want to hold hands with you", "me too", gif_descriptions)
        self.assertEqual(match2, "holding-hands")
        
        # Match via keyword ("smiling" matches "smile")
        match3 = config.find_matching_gif("why are you smiling?", "because I'm happy!", gif_descriptions)
        self.assertEqual(match3, "smile")
        
        # Non-matching test
        match4 = config.find_matching_gif("random text", "hello world", gif_descriptions)
        self.assertIsNone(match4)

    @patch('ai_engine.client.chat.completions.create', new_callable=AsyncMock)
    def test_07_enhance_image_prompt_success(self, mock_chat_create):
        """Verify prompt enhancement formats system instructions and handles API returns."""
        import asyncio
        from unittest.mock import MagicMock
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Juhi, a beautiful blonde girl in a passionate embrace, full body shot, detailed scene"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        mock_chat_create.return_value = mock_response
        
        enhanced = asyncio.run(ai_engine.enhance_image_prompt("send me a photo like I am fucking you", "Juhi, a beautiful blonde girl"))
        self.assertEqual(enhanced, "Juhi, a beautiful blonde girl in a passionate embrace, full body shot, detailed scene")

    @patch('ai_engine.client.chat.completions.create', new_callable=AsyncMock)
    def test_08_enhance_image_prompt_fallback(self, mock_chat_create):
        """Verify prompt enhancement falls back to combine_appearance_and_prompt on error."""
        import asyncio
        mock_chat_create.side_effect = Exception("API Error")
        enhanced = asyncio.run(ai_engine.enhance_image_prompt("some user request", "Juhi, a beautiful blonde girl"))
        self.assertEqual(enhanced, "Juhi, a beautiful blonde girl, some user request")

    def test_09_database_seed_generation(self):
        """Verify that a random persistent seed is generated and preserved in user settings."""
        test_id = 99991111
        database.setup_user(test_id, "seed_user", "SeedUser")
        
        settings = database.get_user_settings(test_id)
        self.assertIsNotNone(settings)
        seed1 = settings.get("seed")
        self.assertIsNotNone(seed1)
        self.assertTrue(1 <= seed1 <= 2147483647)
        
        # Verify it stays consistent on subsequent fetches
        settings_retry = database.get_user_settings(test_id)
        self.assertEqual(settings_retry.get("seed"), seed1)

    def test_10_admin_stats_and_payments(self):
        """Verify tracking of payments and calculations of admin statistics."""
        test_user_id = 88882222
        database.setup_user(test_user_id, "stats_user", "StatsUser")
        
        # Initial stats
        initial_stats = database.get_admin_stats()
        self.assertIn("total_users", initial_stats)
        self.assertIn("paying_users", initial_stats)
        self.assertIn("total_payments", initial_stats)
        self.assertIn("total_revenue_inr", initial_stats)
        
        # Log a payment
        payment_id = "pay_test_123"
        order_id = "order_test_123"
        amount = 5000  # ₹50.00
        item_type = "chat_pass"
        
        database.log_payment(test_user_id, payment_id, order_id, amount, item_type)
        
        # Log a duplicate payment to ensure unique constraint logic/no error
        database.log_payment(test_user_id, payment_id, order_id, amount, item_type)
        
        # Verify stats after payment
        new_stats = database.get_admin_stats()
        self.assertGreater(new_stats["total_users"], 0)
        self.assertEqual(new_stats["total_payments"], initial_stats["total_payments"] + 1)
        self.assertEqual(new_stats["total_revenue_inr"], initial_stats["total_revenue_inr"] + 50.00)
        
        # Check recent payments info
        self.assertTrue(len(new_stats["recent_payments"]) > 0)
        recent = new_stats["recent_payments"][0]
        self.assertEqual(recent["payment_id"], payment_id)
        self.assertEqual(recent["amount_inr"], 50.0)
        self.assertEqual(recent["item_type"], "chat_pass")
        self.assertEqual(recent["username"], "stats_user")

    @patch('config.get_gif_descriptions')
    def test_11_gif_selection_deduplication(self, mock_get_descs):
        """Verify choose_gif selection, de-duplication, and randomness rules."""
        mock_get_descs.return_value = {
            "kiss-1": "juhi kissing cheek",
            "kiss-2": "juhi kissing neck",
            "cuddle": "juhi cuddling with user",
            "smile": "smiling happily"
        }
        test_id = 99993333
        database.setup_user(test_id, "gif_user", "GifUser")
        
        # Test 1: First request for "kiss" matches one of the kiss options
        import bot
        matched_1 = bot.choose_gif("kiss", test_id, "juhi")
        self.assertTrue(matched_1 in ["kiss-1", "kiss-2"])
        
        # Test 2: Next request for "kiss" should select the other kiss option to avoid duplication
        matched_2 = bot.choose_gif("kiss", test_id, "juhi")
        self.assertTrue(matched_2 in ["kiss-1", "kiss-2"])
        self.assertNotEqual(matched_1, matched_2)
        
        # Test 3: Third request - since both have been sent, history filters them out but defaults back to prevent empty result
        matched_3 = bot.choose_gif("kiss", test_id, "juhi")
        self.assertTrue(matched_3 in ["kiss-1", "kiss-2"])

    def test_12_user_orientation_pronouns(self):
        """Verify user_orientation updates and pronoun replacement rules in system prompt."""
        test_id = 99994444
        database.setup_user(test_id, "pronoun_user", "PronounUser")
        
        # Test 1: Default orientation is straight
        settings = database.get_user_settings(test_id)
        self.assertEqual(settings.get("user_orientation"), "straight")
        
        # Test 2: Update orientation to lesbian
        database.update_user_orientation(test_id, "lesbian")
        settings_new = database.get_user_settings(test_id)
        self.assertEqual(settings_new.get("user_orientation"), "lesbian")
        
        # Test 3: Construct prompt with lesbian orientation and verify female pronoun replacement
        system_prompt = config.construct_system_prompt(
            persona_key="juhi",
            relationship_xp=10,
            user_nickname="Girl",
            ai_nickname="Juhi",
            user_orientation="lesbian",
            chat_mode="intimate"
        )
        self.assertIn("You are her loving, sweet girlfriend", system_prompt)
        self.assertNotIn("You are his loving, sweet girlfriend", system_prompt)
        self.assertIn("with her.", system_prompt)

    def test_13_roleplay_and_sync(self):
        """Verify roleplay switching, history isolation, and sync of XP and nicknames."""
        test_id = 99995555
        database.setup_user(test_id, "rp_user", "RPUser")
        
        # Verify initial active persona is 'juhi'
        active = database.get_active_persona_key(test_id)
        self.assertEqual(active, "juhi")
        
        # Add some XP to 'juhi'
        database.add_xp(test_id, amount=100)
        settings_juhi = database.get_user_settings(test_id)
        self.assertEqual(settings_juhi["relationship_xp"], 100)
        
        # Verify settings sync to other Juhi sub-personas (e.g. 'juhi_long_drive')
        database.update_active_persona(test_id, "juhi_long_drive")
        settings_drive = database.get_user_settings(test_id)
        self.assertEqual(settings_drive["relationship_xp"], 100)
        self.assertEqual(settings_drive["user_nickname"], "RPUser")
        
        # Update nickname on 'juhi_long_drive'
        database.update_nicknames(test_id, user_nickname="Darling", ai_nickname="Juhi Baby")
        
        # Verify nickname sync back to 'juhi'
        database.update_active_persona(test_id, "juhi")
        settings_juhi_new = database.get_user_settings(test_id)
        self.assertEqual(settings_juhi_new["user_nickname"], "Darling")
        self.assertEqual(settings_juhi_new["ai_nickname"], "Juhi Baby")
        
        # Verify user orientation sync
        database.update_user_orientation(test_id, "lesbian")
        settings_lesbian = database.get_user_settings(test_id)
        self.assertEqual(settings_lesbian["user_orientation"], "lesbian")
        
        database.update_active_persona(test_id, "juhi_long_drive")
        settings_drive_lesbian = database.get_user_settings(test_id)
        self.assertEqual(settings_drive_lesbian["user_orientation"], "lesbian")
        
        # Verify chat history isolation
        database.add_chat_message(test_id, "juhi", "user", "Hello techie Juhi")
        database.add_chat_message(test_id, "juhi_long_drive", "user", "Hello driver Juhi")
        
        history_juhi = database.get_chat_history(test_id, "juhi")
        history_drive = database.get_chat_history(test_id, "juhi_long_drive")
        
        self.assertEqual(len(history_juhi), 1)
        self.assertEqual(history_juhi[0]["content"], "Hello techie Juhi")
        self.assertEqual(len(history_drive), 1)
        self.assertEqual(history_drive[0]["content"], "Hello driver Juhi")

    @patch("config.get_gif_descriptions")
    def test_14_nsfw_gif_filtering(self, mock_get_descs):
        """Verify that NSFW/explicit GIFs are blocked for users with less than 250 XP (25 messages), but allowed at 250+ XP."""
        mock_get_descs.return_value = {
            "normal_kiss": "juhi kissing cheek",
            "boobs_touching": "juhi touching her boobs",
        }
        
        test_id = 99996666
        database.setup_user(test_id, "nsfw_user", "NsfwUser")
        
        # XP = 0: "boobs_touching" should be filtered.
        import bot
        matched_l1 = bot.choose_gif("touching", test_id, "juhi")
        self.assertIsNone(matched_l1) # "boobs_touching" is filtered out
        
        matched_l1_safe = bot.choose_gif("kiss", test_id, "juhi")
        self.assertEqual(matched_l1_safe, "normal_kiss") # Safe GIF works
        
        # Upgrade user to 240 XP (24 messages) - still filtered
        database.add_xp(test_id, amount=240)
        matched_l24 = bot.choose_gif("touching", test_id, "juhi")
        self.assertIsNone(matched_l24)
        
        # Upgrade user to 250 XP (25 messages) - allowed!
        database.add_xp(test_id, amount=10)
        settings = database.get_user_settings(test_id)
        self.assertEqual(settings["relationship_xp"], 250)
        
        matched_l25 = bot.choose_gif("touching", test_id, "juhi")
        self.assertEqual(matched_l25, "boobs_touching")

    def test_15_user_tracking_and_payment_intents(self):
        """Verify tracking of users trying the app and tracking of users who click Pay 50 and leave after generating link."""
        u1_id = 11110001
        u2_id = 11110002
        
        database.setup_user(u1_id, "trying_user1", "User1")
        database.setup_user(u2_id, "trying_user2", "User2")
        
        # Verify trying users list contains these users
        trying = database.get_trying_users()
        user_ids = [u["telegram_id"] for u in trying]
        self.assertIn(u1_id, user_ids)
        self.assertIn(u2_id, user_ids)
        
        # User 1 clicks Pay 50 (generates payment link plink_1001)
        database.log_payment_intent(u1_id, "chat_pass", 5000, "plink_1001")
        
        # User 2 clicks Pay 50 (generates payment link plink_1002)
        database.log_payment_intent(u2_id, "image_credits", 5000, "plink_1002")
        
        # Check abandoned checkout list (both users generated link and left)
        abandoned = database.get_abandoned_payment_link_users()
        abandoned_link_ids = [ab["payment_link_id"] for ab in abandoned]
        self.assertIn("plink_1001", abandoned_link_ids)
        self.assertIn("plink_1002", abandoned_link_ids)
        
        # User 1 returns and completes payment
        database.log_payment(u1_id, "pay_1001", "order_1001", 5000, "chat_pass")
        
        # Now plink_1001 should be marked completed and removed from abandoned list, while plink_1002 remains abandoned
        abandoned_after = database.get_abandoned_payment_link_users()
        remaining_link_ids = [ab["payment_link_id"] for ab in abandoned_after]
        self.assertNotIn("plink_1001", remaining_link_ids)
        self.assertIn("plink_1002", remaining_link_ids)
        
        # Verify admin stats reflect abandoned checkouts count
        stats = database.get_admin_stats()
        self.assertGreaterEqual(stats["abandoned_checkouts_count"], 1)

    def test_16_chat_mode_and_memory_bank(self):
        """Verify switching chat modes (normal/intimate) and storing/retrieving memories."""
        u_id = 99998888
        database.setup_user(u_id, "mode_user", "ModeUser")
        
        # 1. Test chat mode toggle
        initial_mode = database.get_chat_mode(u_id)
        self.assertEqual(initial_mode, "normal")
        
        toggled_mode = database.toggle_chat_mode(u_id)
        self.assertEqual(toggled_mode, "intimate")
        self.assertEqual(database.get_chat_mode(u_id), "intimate")
        
        toggled_back = database.toggle_chat_mode(u_id)
        self.assertEqual(toggled_back, "normal")
        self.assertEqual(database.get_chat_mode(u_id), "normal")
        
        # 2. Test system prompt construction for normal vs intimate modes
        prompt_normal = config.construct_system_prompt("juhi", 100, user_nickname="Honey", ai_nickname="Juhi", chat_mode="normal")
        self.assertIn("caring, warm, supportive", prompt_normal)
        self.assertIn("Do NOT engage in explicit sexual talk", prompt_normal)
        
        prompt_intimate = config.construct_system_prompt("juhi", 300, user_nickname="Honey", ai_nickname="Juhi", chat_mode="intimate")
        self.assertIn("loving, sweet girlfriend", prompt_intimate)
        
        # 3. Test memory bank operations
        database.add_user_memory(u_id, "Likes/Prefers: South Indian Biryani", category="preference")
        database.add_user_memory(u_id, "Works as: Software Engineer", category="detail")
        database.add_user_memory(u_id, "Emotional state: Feeling stressed about work deadlines", category="problem")
        
        mems = database.get_user_memories(u_id)
        self.assertEqual(len(mems), 3)
        self.assertIn("Likes/Prefers: South Indian Biryani", mems)
        self.assertIn("Works as: Software Engineer", mems)
        
        # Verify duplicate memory prevention
        added_dup = database.add_user_memory(u_id, "Likes/Prefers: South Indian Biryani", category="preference")
        self.assertFalse(added_dup)
        self.assertEqual(len(database.get_user_memories(u_id)), 3)
        
        # Verify prompt memory injection
        prompt_with_mem = config.construct_system_prompt("juhi", 100, memories=mems)
        self.assertIn("THINGS YOU REMEMBER ABOUT THIS USER", prompt_with_mem)
        self.assertIn("Software Engineer", prompt_with_mem)
        
        # Verify memory clearing
        database.clear_user_memories(u_id)
        self.assertEqual(len(database.get_user_memories(u_id)), 0)

    def test_17_payment_page_event_tracking_and_daily_report(self):
        """Verify complete P0 payment event tracking, idempotency, and daily CSV report generation."""
        test_user_id = 77771111
        database.setup_user(test_user_id, "p0_tester", "P0Tester")
        
        # 1. Log payment events across lifecycle
        database.log_payment_event("paywall_shown", test_user_id, status="SHOWN")
        database.log_payment_event("pay_button_clicked", test_user_id, status="CLICKED")
        
        order_id = f"ord_test_p0_{test_user_id}"
        database.create_payment_order(test_user_id, order_id=order_id, amount=5000, item_type="chat_pass")
        database.log_payment_event("payment_page_opened", test_user_id, order_id=order_id, amount=5000, status="OPENED")
        
        # 2. Test idempotent unlock
        unlocked1, exp1, msg1 = database.unlock_paid_access_idempotent(
            telegram_id=test_user_id,
            order_id=order_id,
            payment_id="pay_test_p0_123",
            item_type="chat_pass",
            payment_method="upi",
            amount=5000
        )
        self.assertTrue(unlocked1)
        self.assertEqual(msg1, "Access unlocked successfully")
        
        # Duplicate call with same order/payment
        unlocked2, exp2, msg2 = database.unlock_paid_access_idempotent(
            telegram_id=test_user_id,
            order_id=order_id,
            payment_id="pay_test_p0_123",
            item_type="chat_pass",
            payment_method="upi",
            amount=5000
        )
        self.assertFalse(unlocked2)
        self.assertEqual(msg2, "Already processed")
        
        # 3. Verify user subscription status
        self.assertTrue(database.is_chat_subscribed(test_user_id))
        
        # 4. Generate daily CSV report under assets/
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        report_file, count = database.generate_daily_payment_event_report(today_str)
        self.assertIsNotNone(report_file)
        self.assertTrue(os.path.exists(report_file))
        self.assertGreaterEqual(count, 5) # At least our logged events
        
        # Verify CSV headers & non-sensitive columns
        import csv
        with open(report_file, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertIn("event_name", header)
            self.assertIn("telegram_user_id", header)
            self.assertIn("order_id", header)
            self.assertIn("access_unlocked", header)

    def test_18_proactive_decision_engine(self):
        """Verify Proactive Decision Engine logging, evaluation, and background check workflow."""
        test_user_id = 99998888
        database.setup_user(test_user_id, "proactive_user", "ProactiveUser")
        database.add_user_memory(test_user_id, "Emotional state: Feeling anxious about upcoming interview", category="problem")
        
        # 1. Verify proactive decision logging
        database.log_proactive_decision(test_user_id, "SEND", "Memory trigger: interview anxiety", "Hey Honey! Hope your interview goes great today! 🥰")
        logs = database.get_proactive_logs(test_user_id)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["decision"], "SEND")
        self.assertEqual(logs[0]["message_sent"], "Hey Honey! Hope your interview goes great today! 🥰")
        
        # 2. Verify get_last_proactive_sent_time
        last_sent = database.get_last_proactive_sent_time(test_user_id)
        self.assertIsNotNone(last_sent)
        
        # 3. Test proactive decision engine evaluation via proactive_engine module
        import proactive_engine
        import asyncio
        res = asyncio.run(proactive_engine.evaluate_proactive_for_user(test_user_id, force=True))
        self.assertIn("decision", res)
        self.assertIn(res["decision"], ["SEND", "DONT_SEND"])
        self.assertIn("reason", res)
        
        # 4. Test execute_proactive_check with application=None (dry run execution)
        exec_results = asyncio.run(proactive_engine.execute_proactive_check(application=None, telegram_id=test_user_id, force=True))
        self.assertEqual(len(exec_results), 1)
        self.assertEqual(exec_results[0]["telegram_id"], test_user_id)


if __name__ == "__main__":
    unittest.main()


