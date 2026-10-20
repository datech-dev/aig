"""
test_ai_refactor.py — Unit Tests for the Refactored Juhi AI Architecture
Tests:
1. Dynamic Persona Registry & JSON Extensibility
2. Context Compiler Precedence & Prompt Layer Assembly
3. Memory Models, Types, and Expiration (TTL)
4. Safety Engine Caring Mode Gate & Sexual Intent Detection
5. Emotion Engine Jealousy Disambiguation (Professional vs Romantic)
6. Proactive Engine Fail-Closed Safety
"""

import unittest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import database
import config
import safety_engine
import ai_engine
import context_compiler
import response_planner
import persona_registry
from context_models import PersonaConfig, RelationshipState, EmotionContext
from llm_output import validate_llm_response, to_legacy_compatible_text
from memory_models import MemoryItem
from emotion_engine.detector import EmotionDetector
from emotion_engine.models import EmotionState


class TestAIRefactorArchitecture(unittest.TestCase):

    def setUp(self):
        database.init_db()

    # 1. Dynamic Persona Registry
    def test_01_persona_registry_loads_juhi(self):
        registry = persona_registry.PersonaRegistry()
        juhi = registry.get("juhi")
        self.assertIsNotNone(juhi)
        self.assertEqual(juhi.name, "Juhi")
        self.assertIn("Bangalore", juhi.description)

        # Non-existent falls back safely to juhi
        fallback = registry.get("non_existent_persona")
        self.assertEqual(fallback.name, "Juhi")

        # config.PERSONAS exposes dictionary
        self.assertIn("juhi", config.PERSONAS)
        self.assertEqual(config.PERSONAS["juhi"]["name"], "Juhi")

    # 2. Context Compiler & Precedence
    def test_02_context_compiler_precedence_and_clean_prompt(self):
        compiler = context_compiler.compiler
        prompt = compiler.compile(
            persona_key="juhi",
            relationship_xp=150,
            user_nickname="Sweetheart",
            ai_nickname="Juhi",
            chat_mode="normal",
            memories=["Works as/Is: Engineer", "Pending Event: Interview at 3 PM"],
            emotion_fragment="### Current Emotional Vibe: Playful"
        )
        # Verify base identity is present
        self.assertIn("Juhi", prompt)
        self.assertIn("caring, warm, supportive", prompt)

        # Verify Caring mode hard instructions
        self.assertIn("Do NOT engage in explicit sexual talk", prompt)

        # Verify NO unconditional hardcoded jealousy block
        self.assertNotIn("MANDATORY Emotional Dynamics & Rival Girl Reactions (CRITICAL)", prompt)

        # Free-form emotion prompt fragments are intentionally ignored.
        self.assertNotIn("Current Emotional Vibe: Playful", prompt)

        # Verify structured output contract
        self.assertIn('"message":"short natural reply"', prompt)
        self.assertIn("Never emit executable tags", prompt)

        # Verify nicknames
        self.assertIn("Sweetheart", prompt)


    def test_03_structured_output_validation_and_media_allowlist(self):
        raw = '{"message":"hey there","language":"en","emotion":{"name":"playful","intensity":0.6},"media":{"type":"gif","id":"laughing","prompt":null}}'
        validated = validate_llm_response(raw, allowed_gifs=["laughing"])
        self.assertEqual(validated.message, "hey there")
        self.assertEqual(validated.media_type, "gif")
        self.assertEqual(to_legacy_compatible_text(validated), "hey there\n[SEND_GIF: laughing]")

        # An unknown GIF can never become an executable action.
        invalid = validate_llm_response(raw, allowed_gifs=["smile"])
        self.assertEqual(invalid.media_type, "none")

    def test_04_planner_language_and_relationship_resolution(self):
        relationship = RelationshipState(xp=100, chat_mode="normal", level=2, title="Friends")
        plan = response_planner.planner.plan(
            relationship=relationship,
            emotion=EmotionContext(current_emotion="playful", intensity=0.5),
            user_message="enna panra?",
            memories=["Pending Event: Interview tomorrow"],
            available_gifs=["laughing"],
        )
        self.assertEqual(plan.language, "ta")
        self.assertEqual(plan.code_mixing, "tanglish")
        self.assertEqual(plan.emotion, "playful")
        self.assertTrue(plan.relevant_memory_followup)

    # 5. Memory Models & TTL Expiration
    def test_05_memory_models_and_expiration(self):
        past_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        future_time = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()

        expired_item = MemoryItem(id=1, user_id=101, memory_text="Tired", valid_until=past_time)
        active_item = MemoryItem(id=2, user_id=101, memory_text="Interview", valid_until=future_time)
        perm_item = MemoryItem(id=3, user_id=101, memory_text="Lives in Bangalore", valid_until=None)

        self.assertTrue(expired_item.is_expired())
        self.assertFalse(active_item.is_expired())
        self.assertFalse(perm_item.is_expired())

    def test_06_database_memory_ttl_filtering(self):
        test_user = 88887777
        database.setup_user(test_user, "mem_tester", "MemTester")
        database.clear_user_memories(test_user)

        # Add active permanent memory
        database.add_user_memory(test_user, "Favorite cuisine is Indian", category="preference", memory_type="preference", valid_until=None)

        # Add expired temporary memory
        past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        database.add_user_memory(test_user, "Feeling a bit cold today", category="problem", memory_type="emotional_state", valid_until=past_iso)

        # Add future temporary memory
        future_iso = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        database.add_user_memory(test_user, "Upcoming exam tomorrow", category="event", memory_type="event", valid_until=future_iso)

        retrieved = database.get_user_memories(test_user)
        self.assertIn("Favorite cuisine is Indian", retrieved)
        self.assertIn("Upcoming exam tomorrow", retrieved)
        self.assertNotIn("Feeling a bit cold today", retrieved)

    # 4. Safety Engine & Caring Mode Hard Gate
    def test_07_sexual_intent_detection(self):
        self.assertTrue(safety_engine.contains_sexual_intent("show me your boobs"))
        self.assertTrue(safety_engine.contains_sexual_intent("send me nudes please"))
        self.assertTrue(safety_engine.contains_sexual_intent("describe having sex with me"))
        self.assertFalse(safety_engine.contains_sexual_intent("how was your day at work?"))
        self.assertFalse(safety_engine.contains_sexual_intent("can we talk about your coding project?"))

    def test_08_caring_mode_hard_gate_in_ai_engine(self):
        res = asyncio.run(ai_engine.generate_response(
            persona_key="juhi",
            relationship_xp=100,
            user_nickname="Honey",
            ai_nickname="Juhi",
            chat_history=[],
            user_message="send me naked nudes of your body",
            chat_mode="normal"
        ))
        # Should be blocked immediately by safety or caring mode gate
        self.assertTrue("wholesome" in res.lower() or "nude" in res.lower())

    # 5. Emotion Engine Disambiguation (Professional vs Rival Girl)
    def test_09_emotion_detector_disambiguation(self):
        detector = EmotionDetector()
        state = EmotionState(user_id=1)

        # Professional context should NOT trigger jealousy
        res_work = asyncio.run(detector.detect_emotion_and_events(
            "my female coworker helped me review and deploy the pull request",
            [],
            state
        ))
        emotions_work = {p.emotion_id for p in res_work.proposed_changes}
        self.assertNotIn("jealousy", emotions_work)

        # Family context should NOT trigger jealousy
        res_family = asyncio.run(detector.detect_emotion_and_events(
            "my mom made dinner for the family",
            [],
            state
        ))
        emotions_family = {p.emotion_id for p in res_family.proposed_changes}
        self.assertNotIn("jealousy", emotions_family)

        # Romantic rival context SHOULD trigger jealousy
        res_rival = asyncio.run(detector.detect_emotion_and_events(
            "another girl asked me out on a date",
            [],
            state
        ))
        emotions_rival = {p.emotion_id for p in res_rival.proposed_changes}
        self.assertIn("jealousy", emotions_rival)

    # 6. Proactive Engine Fail-Closed
    @patch('ai_engine.client.chat.completions.create', new_callable=AsyncMock)
    def test_10_proactive_engine_fails_closed(self, mock_create):
        mock_create.side_effect = Exception("Venice API connection timeout")
        decision = asyncio.run(ai_engine.evaluate_proactive_decision(
            user_id=9999,
            persona_key="juhi",
            user_nickname="Friend",
            memories=["User has an interview today"]
        ))
        self.assertEqual(decision["decision"], "DONT_SEND")
        self.assertIsNone(decision["message"])


if __name__ == "__main__":
    unittest.main()
