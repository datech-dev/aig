"""
Emotion State Repository: SQLite persistence for emotion states, preferences, and transition history.
"""

from typing import Dict, Any, Optional, List
import sqlite3
import json
import logging
from datetime import datetime
from .models import (
    EmotionState,
    ActiveEmotion,
    UserEmotionPreferences,
    EmotionTransitionEvent,
)
from .interfaces import EmotionStateRepositoryProtocol

logger = logging.getLogger(__name__)


class EmotionStateRepository(EmotionStateRepositoryProtocol):
    """
    Persists emotion state and transition logs to SQLite database.
    Ensures safe restoration after application restarts and isolates state per user/conversation.
    """

    def __init__(self, db_path: str = "girlfriend.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Initializes emotion engine database tables if not existing."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 1. State Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_emotion_state (
                        telegram_id INTEGER,
                        persona_key TEXT,
                        active_emotions TEXT,
                        primary_emotion_id TEXT,
                        current_mood TEXT,
                        last_interaction TIMESTAMP,
                        version INTEGER DEFAULT 1,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (telegram_id, persona_key)
                    )
                """)

                # 2. Preferences Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_emotion_preferences (
                        telegram_id INTEGER,
                        persona_key TEXT,
                        enabled_emotions TEXT,
                        intensity_multipliers TEXT,
                        interaction_mode TEXT DEFAULT 'balanced',
                        custom_overrides TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (telegram_id, persona_key)
                    )
                """)

                # 3. Transition History Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_transition_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER,
                        persona_key TEXT,
                        trigger_event TEXT,
                        proposed_changes TEXT,
                        applied_changes TEXT,
                        reason_code TEXT,
                        confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize emotion tables in {self.db_path}: {e}")

    def get_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        """Loads persistent emotion state from DB or returns initial baseline state."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM conversation_emotion_state WHERE telegram_id = ? AND persona_key = ?",
                    (user_id, persona_key),
                )
                row = cursor.fetchone()
                if row:
                    raw_actives = json.loads(row["active_emotions"]) if row["active_emotions"] else {}
                    actives: Dict[str, ActiveEmotion] = {}
                    for k, v in raw_actives.items():
                        actives[k] = ActiveEmotion.from_dict(v)

                    last_int = row["last_interaction"]
                    if isinstance(last_int, str):
                        try:
                            last_int = datetime.fromisoformat(last_int)
                        except Exception:
                            last_int = datetime.utcnow()
                    elif not isinstance(last_int, datetime):
                        last_int = datetime.utcnow()

                    return EmotionState(
                        user_id=user_id,
                        persona_key=persona_key,
                        active_emotions=actives,
                        primary_emotion_id=row["primary_emotion_id"],
                        current_mood=row["current_mood"] or "content",
                        last_interaction=last_int,
                        version=row["version"] or 1,
                    )
        except Exception as e:
            logger.error(f"Error loading emotion state for user {user_id}: {e}")

        return EmotionState(user_id=user_id, persona_key=persona_key)

    def save_state(self, state: EmotionState) -> bool:
        """Saves current emotion state to SQLite."""
        try:
            raw_actives = json.dumps({k: v.to_dict() for k, v in state.active_emotions.items()})
            last_int_str = state.last_interaction.isoformat() if state.last_interaction else datetime.utcnow().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_emotion_state (
                        telegram_id, persona_key, active_emotions, primary_emotion_id,
                        current_mood, last_interaction, version, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(telegram_id, persona_key) DO UPDATE SET
                        active_emotions = excluded.active_emotions,
                        primary_emotion_id = excluded.primary_emotion_id,
                        current_mood = excluded.current_mood,
                        last_interaction = excluded.last_interaction,
                        version = excluded.version,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    state.user_id,
                    state.persona_key,
                    raw_actives,
                    state.primary_emotion_id,
                    state.current_mood,
                    last_int_str,
                    state.version,
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving emotion state for user {state.user_id}: {e}")
            return False

    def get_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        """Loads user preferences from database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM user_emotion_preferences WHERE telegram_id = ? AND persona_key = ?",
                    (user_id, persona_key),
                )
                row = cursor.fetchone()
                if row:
                    enabled = json.loads(row["enabled_emotions"]) if row["enabled_emotions"] else {}
                    multipliers = json.loads(row["intensity_multipliers"]) if row["intensity_multipliers"] else {}
                    overrides = json.loads(row["custom_overrides"]) if row["custom_overrides"] else {}
                    return UserEmotionPreferences(
                        user_id=user_id,
                        persona_key=persona_key,
                        enabled_emotions=enabled,
                        intensity_multipliers=multipliers,
                        interaction_mode=row["interaction_mode"] or "balanced",
                        custom_overrides=overrides,
                        updated_at=datetime.utcnow(),
                    )
        except Exception as e:
            logger.error(f"Error loading user emotion preferences for {user_id}: {e}")

        # Safe default
        return UserEmotionPreferences(
            user_id=user_id,
            persona_key=persona_key,
            enabled_emotions={"anger": True, "possessiveness": True, "affection": True, "happiness": True},
            intensity_multipliers={"anger": 1.0, "possessiveness": 1.0},
            interaction_mode="balanced",
        )

    def save_preferences(self, preferences: UserEmotionPreferences) -> bool:
        """Saves user emotion preferences to database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_emotion_preferences (
                        telegram_id, persona_key, enabled_emotions, intensity_multipliers,
                        interaction_mode, custom_overrides, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(telegram_id, persona_key) DO UPDATE SET
                        enabled_emotions = excluded.enabled_emotions,
                        intensity_multipliers = excluded.intensity_multipliers,
                        interaction_mode = excluded.interaction_mode,
                        custom_overrides = excluded.custom_overrides,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    preferences.user_id,
                    preferences.persona_key,
                    json.dumps(preferences.enabled_emotions),
                    json.dumps(preferences.intensity_multipliers),
                    preferences.interaction_mode,
                    json.dumps(preferences.custom_overrides),
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving user emotion preferences for {preferences.user_id}: {e}")
            return False

    def log_transition_event(self, event: EmotionTransitionEvent) -> bool:
        """Logs emotion transition audit trail."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO emotion_transition_history (
                        telegram_id, persona_key, trigger_event, proposed_changes,
                        applied_changes, reason_code, confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    event.user_id,
                    event.persona_key,
                    event.trigger_event,
                    json.dumps(event.proposed_changes),
                    json.dumps(event.applied_changes),
                    event.reason_code,
                    event.confidence,
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error logging emotion transition event: {e}")
            return False
