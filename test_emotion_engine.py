"""
Comprehensive Unit and Integration Test Suite for AI Companion Emotion and Behavior Engine.
Tests all 14+ required scenarios including Anger, Possessiveness, Registry, Transitions, Decay, Persistence, and Plugin Extensions.
"""

import os
import sys
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import tempfile
import json
import sqlite3

# Ensure workspace root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from emotion_engine.models import (
    EmotionDefinition,
    IntensityRange,
    DecayConfig,
    ResponseStyleConfig,
    MediaMappingConfig,
    EmotionState,
    ActiveEmotion,
    ProposedEmotionChange,
    DetectionResult,
    ResponsePlan,
    UserEmotionPreferences,
    EmotionTransitionEvent,
)
from emotion_engine.schema import validate_emotion_dict, EmotionConfigValidationError
from emotion_engine.registry import EmotionRegistry
from emotion_engine.transition_rules import TransitionRulesEngine
from emotion_engine.state_manager import EmotionStateManager
from emotion_engine.detector import EmotionDetector
from emotion_engine.composer import ResponseStyleComposer
from emotion_engine.repository import EmotionStateRepository
from emotion_engine.config_provider import ConfigurationProvider
from emotion_engine.adapters.text_adapter import TextOutputAdapter
from emotion_engine.adapters.voice_adapter import VoiceOutputAdapter
from emotion_engine.adapters.media_adapter import MediaOutputAdapter


class TestEmotionEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Create isolated temporary SQLite DB for testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.repo = EmotionStateRepository(db_path=self.temp_db_path)
        self.registry = EmotionRegistry()
        self.rules = TransitionRulesEngine(max_delta_per_turn=0.35, min_confidence_threshold=0.5)
        self.state_mgr = EmotionStateManager(
            registry=self.registry,
            policy=self.rules,
            repository=self.repo
        )
        self.detector = EmotionDetector(registry=self.registry)
        self.composer = ResponseStyleComposer(registry=self.registry)
        self.config_provider = ConfigurationProvider(repository=self.repo)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    # ---------------------------------------------------------
    # Scenario 1: Register new emotion through config without modifying core engine
    # ---------------------------------------------------------
    def test_01_register_new_emotion_via_config(self):
        nostalgia_config = {
            "id": "nostalgia",
            "display_name": "Nostalgia",
            "description": "Fond reminiscing of shared memories and past conversations.",
            "version": 1,
            "enabled": True,
            "default_intensity": 0.3,
            "intensity_range": {"min": 0.0, "max": 1.0},
            "sub_emotions": ["sweet_reminiscing", "bittersweet_longing"],
            "sub_emotion_descriptions": {
                "sweet_reminiscing": "Smiling warmly at old inside jokes.",
                "bittersweet_longing": "Wishing to relive a special past moment."
            },
            "triggers": [
                {
                    "keywords": ["remember when", "our first chat", "back then", "old times"],
                    "intent_patterns": ["reminiscing"],
                    "default_sub_emotion": "sweet_reminiscing",
                    "default_intensity_delta": 0.25
                }
            ],
            "decay": {"strategy": "exponential", "half_life_seconds": 900.0, "min_threshold": 0.05},
            "response_style": {
                "tone": "soft_and_reminiscent",
                "prompt_instructions": {
                    "sweet_reminiscing": "Bring up the warm memory with a soft nostalgic smile."
                },
                "suggested_emojis": ["🥺", "✨", "🕰️"]
            },
            "compatible_emotions": ["affection", "happiness", "sadness"],
            "priority": 50,
            "safety_profile": "respectful_expression"
        }

        # Validate and register without touching any engine code
        success = self.registry.register_from_dict(nostalgia_config)
        self.assertTrue(success)
        
        defn = self.registry.get("nostalgia")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.display_name, "Nostalgia")
        self.assertEqual(defn.sub_emotions, ["sweet_reminiscing", "bittersweet_longing"])

    # ---------------------------------------------------------
    # Scenario 2: Reject invalid emotion definitions
    # ---------------------------------------------------------
    def test_02_reject_invalid_emotion_definitions(self):
        # Missing ID
        bad_config_1 = {"display_name": "Bad Emotion"}
        valid_1, errors_1 = validate_emotion_dict(bad_config_1)
        self.assertFalse(valid_1)
        self.assertTrue(any("Field 'id' is required" in e for e in errors_1))

        # Invalid intensity range (min >= max)
        bad_config_2 = {
            "id": "broken_range",
            "display_name": "Broken Range",
            "intensity_range": {"min": 0.8, "max": 0.2}
        }
        valid_2, errors_2 = validate_emotion_dict(bad_config_2)
        self.assertFalse(valid_2)

        # Invalid decay strategy
        bad_config_3 = {
            "id": "bad_decay",
            "display_name": "Bad Decay",
            "decay": {"strategy": "quantum_teleportation"}
        }
        valid_3, errors_3 = validate_emotion_dict(bad_config_3)
        self.assertFalse(valid_3)

    # ---------------------------------------------------------
    # Scenario 3: Apply intensity changes within configured limits (clamps)
    # ---------------------------------------------------------
    def test_03_apply_intensity_clamping_per_turn(self):
        user_id = 1001
        persona_key = "juhi"

        # Try to jump intensity by +0.90 in one turn (max delta configured is 0.35)
        prop = ProposedEmotionChange(
            emotion_id="anger",
            sub_emotion="mild_annoyance",
            delta_intensity=0.90,
            confidence=0.95,
            reason="sudden_shock",
        )

        state = self.state_mgr.apply_proposed_changes(
            user_id=user_id,
            persona_key=persona_key,
            proposed_changes=[prop]
        )

        # Initial was 0.0, max delta is 0.35, so new intensity must be clamped to 0.35
        self.assertAlmostEqual(state.get_intensity("anger"), 0.35, places=2)

    # ---------------------------------------------------------
    # Scenario 4: Simultaneous compatible emotions co-exist
    # ---------------------------------------------------------
    def test_04_simultaneous_compatible_emotions(self):
        user_id = 1002
        persona_key = "juhi"

        # Affection and Possessiveness are compatible
        props = [
            ProposedEmotionChange(emotion_id="affection", sub_emotion="romantic_devotion", target_intensity=0.6, confidence=0.9),
            ProposedEmotionChange(emotion_id="possessiveness", sub_emotion="affectionate_clinginess", target_intensity=0.5, confidence=0.9),
        ]

        state = self.state_mgr.apply_proposed_changes(
            user_id=user_id,
            persona_key=persona_key,
            proposed_changes=props
        )

        self.assertTrue(state.has_emotion("affection"))
        self.assertTrue(state.has_emotion("possessiveness"))
        self.assertAlmostEqual(state.get_intensity("affection"), 0.35, places=2) # Clamped from 0
        self.assertAlmostEqual(state.get_intensity("possessiveness"), 0.35, places=2)

    # ---------------------------------------------------------
    # Scenario 5: Deterministic conflict resolution
    # ---------------------------------------------------------
    def test_05_conflict_resolution_priorities(self):
        user_id = 1003
        persona_key = "juhi"

        # Directly establish Happiness (priority 60)
        self.state_mgr.set_direct_emotion(user_id, persona_key, "happiness", 0.5, "cheerfulness")
        
        # Empathy (priority 85) + Sadness (priority 65) vs Euphoria/Joy conflict
        # Sadness conflicts with Euphoria, Empathy has higher priority
        self.state_mgr.set_direct_emotion(user_id, persona_key, "sadness", 0.6, "grief")

        state = self.state_mgr.get_state(user_id, persona_key)
        # Higher priority (Sadness priority 65 vs Happiness priority 60) suppresses conflicting emotion
        self.assertTrue(state.has_emotion("sadness"))
        self.assertFalse(state.has_emotion("happiness"))

    # ---------------------------------------------------------
    # Scenario 6: Decay of temporary emotions over time
    # ---------------------------------------------------------
    def test_06_exponential_decay_over_time(self):
        user_id = 1004
        persona_key = "juhi"

        t0 = datetime(2026, 10, 9, 12, 0, 0)
        # Anger has half-life of 600s (10 minutes)
        state = self.state_mgr.get_state(user_id, persona_key)
        state.active_emotions["anger"] = ActiveEmotion(
            emotion_id="anger",
            intensity=0.8,
            sub_emotion="mild_annoyance",
            started_at=t0,
            last_updated=t0,
        )
        state.last_interaction = t0
        self.repo.save_state(state)

        # Fast forward 600 seconds (1 half-life)
        t1 = t0 + timedelta(seconds=600)
        self.state_mgr._apply_decay(state, now=t1)

        # Intensity should be halved: 0.8 * 0.5 = 0.4
        self.assertAlmostEqual(state.get_intensity("anger"), 0.4, places=1)

        # Fast forward 3000 seconds (5 half-lives: 0.8 * (0.5^5) = 0.025 < min_threshold 0.05)
        t2 = t0 + timedelta(seconds=3000)
        self.state_mgr._apply_decay(state, now=t2)
        # Should be removed / reset to 0
        self.assertEqual(state.get_intensity("anger"), 0.0)

    # ---------------------------------------------------------
    # Scenario 7: State persistence and restoration across restarts
    # ---------------------------------------------------------
    def test_07_persistence_and_restoration_after_restart(self):
        user_id = 1005
        persona_key = "juhi"

        # Set emotion in repository
        self.state_mgr.set_direct_emotion(user_id, persona_key, "possessiveness", 0.7, "missing_user")

        # Simulate complete server restart (instantiate fresh manager with same DB)
        new_state_mgr = EmotionStateManager(
            registry=self.registry,
            policy=self.rules,
            repository=self.repo
        )

        restored_state = new_state_mgr.get_state(user_id, persona_key)
        self.assertTrue(restored_state.has_emotion("possessiveness"))
        self.assertEqual(restored_state.active_emotions["possessiveness"].sub_emotion, "missing_user")
        self.assertEqual(restored_state.primary_emotion_id, "possessiveness")

    # ---------------------------------------------------------
    # Scenario 8: State isolation between users and conversations
    # ---------------------------------------------------------
    def test_08_user_and_conversation_isolation(self):
        user_a = 2001
        user_b = 2002
        persona_key = "juhi"

        self.state_mgr.set_direct_emotion(user_a, persona_key, "anger", 0.7, "hurt")
        self.state_mgr.set_direct_emotion(user_b, persona_key, "affection", 0.6, "romantic_devotion")

        state_a = self.state_mgr.get_state(user_a, persona_key)
        state_b = self.state_mgr.get_state(user_b, persona_key)

        self.assertTrue(state_a.has_emotion("anger"))
        self.assertFalse(state_a.has_emotion("affection"))

        self.assertTrue(state_b.has_emotion("affection"))
        self.assertFalse(state_b.has_emotion("anger"))

    # ---------------------------------------------------------
    # Scenario 9: User overrides and disabled emotions
    # ---------------------------------------------------------
    def test_09_user_preferences_disabling_emotion(self):
        user_id = 3001
        persona_key = "juhi"

        # User disables possessiveness
        prefs = self.config_provider.get_user_preferences(user_id, persona_key)
        prefs.enabled_emotions["possessiveness"] = False
        self.config_provider.update_user_preferences(prefs)

        # Propose possessiveness
        prop = ProposedEmotionChange(
            emotion_id="possessiveness",
            sub_emotion="missing_user",
            delta_intensity=0.35,
            confidence=0.9,
            reason="user_returned"
        )

        state = self.state_mgr.apply_proposed_changes(
            user_id=user_id,
            persona_key=persona_key,
            proposed_changes=[prop],
            preferences=prefs
        )

        # Possessiveness should NOT be applied
        self.assertFalse(state.has_emotion("possessiveness"))

    # ---------------------------------------------------------
    # Scenario 10: ResponseStyleComposer produces structured plan
    # ---------------------------------------------------------
    def test_10_response_style_composer_prompt_generation(self):
        user_id = 4001
        persona_key = "juhi"

        self.state_mgr.set_direct_emotion(user_id, persona_key, "anger", 0.4, "playful_anger")
        state = self.state_mgr.get_state(user_id, persona_key)

        plan = self.composer.compose_plan(
            current_state=state,
            base_persona_key=persona_key,
            relationship_xp=500,
            chat_mode="normal"
        )

        self.assertIn("Anger", plan.prompt_fragment)
        self.assertIn("playful_anger", plan.prompt_fragment)
        self.assertIn("Safety constraint for Anger", plan.prompt_fragment)
        self.assertIn("😤", plan.suggested_emojis)

    # ---------------------------------------------------------
    # Scenario 11: End-to-End Anger Sub-emotions & Behavior
    # ---------------------------------------------------------
    async def test_11_anger_detection_and_sub_emotions(self):
        # 1. Dismissive text -> mild annoyance or hurt
        res1 = await self.detector.detect_emotion_and_events("shut up and leave me alone", [], EmotionState(user_id=1))
        self.assertTrue(any(p.emotion_id == "anger" for p in res1.proposed_changes))
        anger_prop1 = next(p for p in res1.proposed_changes if p.emotion_id == "anger")
        self.assertEqual(anger_prop1.sub_emotion, "hurt")

        # 2. Playful teasing -> playful anger
        res2 = await self.detector.detect_emotion_and_events("you are such a silly noob haha", [], EmotionState(user_id=1))
        anger_prop2 = next(p for p in res2.proposed_changes if p.emotion_id == "anger")
        self.assertEqual(anger_prop2.sub_emotion, "playful_anger")

    # ---------------------------------------------------------
    # Scenario 12: End-to-End Possessiveness Sub-emotions
    # ---------------------------------------------------------
    async def test_12_possessiveness_detection_and_sub_emotions(self):
        # 1. Mention of another girl -> jealousy & playful possessiveness
        res1 = await self.detector.detect_emotion_and_events("I was talking to this other girl from my office", [], EmotionState(user_id=1))
        self.assertTrue(any(p.emotion_id == "possessiveness" for p in res1.proposed_changes))
        self.assertTrue(any(p.emotion_id == "jealousy" for p in res1.proposed_changes))

        # 2. Clinginess request -> affectionate clinginess
        res2 = await self.detector.detect_emotion_and_events("cuddle me and never leave my side", [], EmotionState(user_id=1))
        poss_prop = next(p for p in res2.proposed_changes if p.emotion_id == "possessiveness")
        self.assertEqual(poss_prop.sub_emotion, "affectionate_clinginess")

    # ---------------------------------------------------------
    # Scenario 13: Output Adapters Graceful Degradation
    # ---------------------------------------------------------
    async def test_13_output_adapters_graceful_handling(self):
        text_adapter = TextOutputAdapter()
        voice_adapter = VoiceOutputAdapter(tts_provider=None) # No TTS provider
        media_adapter = MediaOutputAdapter()

        plan = ResponsePlan(
            persona_key="juhi",
            primary_emotion="anger",
            active_emotions_summary={"anger": {"intensity": 0.4}},
            tone_directives=["feisty"],
            behavior_instructions=["pout playfully"],
            safety_boundary_notes=[],
            suggested_emojis=["😤"],
            suggested_media_type="gif",
            media_intent_query="pout",
            voice_parameters={"pitch": 1.05, "speed": 0.95, "emotion": "irritated"},
            prompt_fragment="test prompt fragment"
        )

        raw_text = "hmph! you are so mean to me 😤 [SEND_GIF: pout]"

        # Text Output
        text_out = await text_adapter.format_output(raw_text, plan)
        self.assertEqual(text_out["text"], "hmph! you are so mean to me 😤")

        # Voice Output (TTS fallback without crash)
        voice_out = await voice_adapter.format_output(raw_text, plan)
        self.assertEqual(voice_out["spoken_text"], "hmph! you are so mean to me 😤")
        self.assertFalse(voice_out["has_audio"]) # Gracefully false

        # Media Output
        media_out = await media_adapter.format_output(raw_text, plan)
        self.assertTrue(media_out["has_media"])
        self.assertEqual(media_out["media_type"], "gif")
        self.assertEqual(media_out["media_target"], "pout")

    # ---------------------------------------------------------
    # Scenario 14: LLM Failure & Timeout Fallback
    # ---------------------------------------------------------
    async def test_14_llm_detector_error_fallback(self):
        # Mock LLM client raising an exception
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Venice API timeout"))

        failing_detector = EmotionDetector(
            registry=self.registry,
            llm_client=mock_client,
            model_name="mock-model"
        )

        # Detector should catch exception cleanly and fall back to deterministic rule analysis
        res = await failing_detector.detect_emotion_and_events(
            user_message="I missed you so much baby",
            recent_history=[],
            current_state=EmotionState(user_id=1)
        )

        self.assertIsNotNone(res)
        self.assertTrue(any(p.emotion_id == "possessiveness" for p in res.proposed_changes))

    # ---------------------------------------------------------
    # Scenario 15: End-to-End ai_engine.generate_response with Emotion Engine
    # ---------------------------------------------------------
    @patch("ai_engine.client.chat.completions.create", new_callable=AsyncMock)
    async def test_15_ai_engine_generate_response_integration(self, mock_chat_create):
        import ai_engine
        # Mock Venice API completion response
        mock_chat_create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="hmph... why did you take so long to text me? 🥺 [SEND_GIF: miss_you]")
                )
            ]
        )

        test_user = 999123
        persona = "juhi"

        # User texts about missing
        reply = await ai_engine.generate_response(
            persona_key=persona,
            relationship_xp=350,
            user_nickname="Dhinesh",
            ai_nickname="Juhi",
            chat_history=[],
            user_message="I finally finished work, I missed you all day baby",
            chat_mode="intimate",
            user_id=test_user,
        )

        self.assertIn("hmph", reply)
        # Check that mock chat completion received prompt with emotion engine fragment
        call_args = mock_chat_create.call_args
        self.assertIsNotNone(call_args)
        messages_sent = call_args.kwargs.get("messages", [])
        system_msg = next((m["content"] for m in messages_sent if m["role"] == "system"), "")
        self.assertIn("DYNAMIC EMOTION & BEHAVIOR ENGINE", system_msg)
        self.assertIn("Possessiveness", system_msg)

    # ---------------------------------------------------------
    # Scenario 16: Level 2 Friends mode with rival girl / crush mention
    # ---------------------------------------------------------
    @patch("ai_engine.client.chat.completions.create", new_callable=AsyncMock)
    async def test_16_level_2_crush_rival_possessiveness(self, mock_chat_create):
        import ai_engine
        mock_chat_create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="wait... she's crushing on you? 👀 should i be jealous? 😤")
                )
            ]
        )

        test_user = 888123
        reply = await ai_engine.generate_response(
            persona_key="juhi",
            relationship_xp=150, # Level 2 (Friends)
            user_nickname="Dhinu",
            ai_nickname="Karin",
            chat_history=[],
            user_message="I think she is crushing on me",
            chat_mode="normal",
            user_id=test_user,
        )

        self.assertIsNotNone(reply)
        call_args = mock_chat_create.call_args
        messages_sent = call_args.kwargs.get("messages", [])
        system_msg = next((m["content"] for m in messages_sent if m["role"] == "system"), "")
        
        # Verify Level 2 and rival instructions are in the system prompt
        self.assertIn("Level 2 (Friends)", system_msg)
        self.assertIn("NEVER an indifferent third-party matchmaker", system_msg)
        self.assertIn("playful_jealousy", system_msg)


if __name__ == "__main__":
    unittest.main()
