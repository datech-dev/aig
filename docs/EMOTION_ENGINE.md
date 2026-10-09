# Extensible Emotion & Behavior Engine for Juhi AI Companion

## 1. Overview & Architecture

The **Emotion and Behavior Engine** provides a modular, extensible, plugin-style framework for managing dynamic emotional states, mood transitions, sub-emotions, and personality expression for Juhi.

### Core Architectural Principle
> **Adding a new emotion requires only registering its declarative configuration file (JSON/YAML/Dict), defining its sub-emotions and behavior rules, and adding tests—never modifying the core engine algorithm.**

```mermaid
graph TD
    UserMsg[User Message + Context] --> Detector[Emotion Detector\n(LLM + Deterministic Rules)]
    Detector --> Proposed[Proposed Emotion Changes]
    Proposed --> Policy[Transition Rules Engine\n(Clamping, Cooldown, User Overrides)]
    Policy --> StateMgr[Emotion State Manager\n(Decay, Conflict Resolution, Priority)]
    StateMgr --> Repo[(SQLite Database\nconversation_emotion_state)]
    StateMgr --> Composer[Response Style Composer\n(Mood, Sub-emotions, Relationship XP)]
    Composer --> Plan[Structured Response Plan\n+ Prompt Fragment]
    Plan --> LLM[Venice AI Inference Engine]
    LLM --> Adapters[Output Adapters\n(Text, Voice TTS, Media/GIFs)]
```

---

## 2. Component Structure

```
emotion_engine/
├── __init__.py                 # Exported components & public API
├── models.py                   # Typed dataclasses (EmotionDefinition, EmotionState, ResponsePlan, etc.)
├── interfaces.py               # Explicit Protocol contracts (Section 6)
├── schema.py                   # JSON schema validator with versioning & error reporting
├── registry.py                 # Central EmotionRegistry catalog
├── definitions/                # Declarative emotion configs (JSON)
│   ├── happiness.json
│   ├── sadness.json
│   ├── anger.json              # Mild annoyance, playful anger, frustration, hurt
│   ├── affection.json          # Tenderness, romantic devotion, flirtatiousness
│   ├── playfulness.json        # Banter, mischief, teasing, silliness
│   ├── curiosity.json          # Tech fascination, deep interest, wonder
│   ├── surprise.json           # Delighted shock, speechlessness, flustered
│   ├── empathy.json            # Gentle comfort, emotional validation
│   ├── jealousy.json           # Playful envy, cute suspicion (independent)
│   └── possessiveness.json     # Clinginess, missing user, reassurance (independent)
├── state_manager.py            # Active state tracking, decay math, priority conflict resolution
├── transition_rules.py         # Max delta clamping, confidence thresholds, user overrides
├── detector.py                 # Hybrid trigger matcher + LLM event detector with safe fallback
├── composer.py                 # Structured response plan & dynamic prompt composer
├── repository.py               # SQLite persistence & transition audit trail
├── config_provider.py          # Per-user emotion preferences, enable/disable toggles
├── events.py                   # Typed internal lifecycle events
└── adapters/                   # Output channel adapters
    ├── base.py                 # BaseOutputAdapter
    ├── text_adapter.py         # Text sanitization & tone formatting
    ├── voice_adapter.py        # Voice TTS modulation (pitch, speed, emotion tag)
    └── media_adapter.py        # GIF, sticker, and image trigger selector
```

---

## 3. Registered Emotions & Initial Feature Support

### A. Anger
- **Sub-emotions**: `mild_annoyance`, `playful_anger`, `frustration`, `hurt`
- **Behavioral Guidance**: Cute pouting (`hmph!`), feisty sass for playful banter; slight bluntness and sighs (`uff`) for annoyance; quiet vulnerability for hurt.
- **Safety Boundary**: Influences response tone without enabling abuse, threats, intimidation, or punitive behavior.

### B. Possessiveness
- **Sub-emotions**: `playful_jealousy`, `affectionate_clinginess`, `missing_user`, `seeking_reassurance`
- **Behavioral Guidance**: Territorial teasing (`you're only allowed to talk to me today 😌`), longing when user was away (`where were you? i missed you so much 🥺`), asking for tight cuddles.
- **Safety Boundary**: Optional character behavior. Never results in guilt-tripping, isolation, coercion, or pressure.

---

## 4. How to Add a Completely New Emotion (e.g., Nostalgia)

To add a new emotion to the application, follow these 3 steps without touching any core engine logic:

### Step 1: Create the Declarative Definition File
Create `emotion_engine/definitions/nostalgia.json`:

```json
{
  "id": "nostalgia",
  "display_name": "Nostalgia",
  "description": "Fond reminiscing of shared memories, early conversations, and sentimental milestones.",
  "version": 1,
  "enabled": true,
  "default_intensity": 0.35,
  "intensity_range": {
    "min": 0.0,
    "max": 1.0
  },
  "sub_emotions": [
    "sweet_reminiscing",
    "bittersweet_longing",
    "milestone_celebration"
  ],
  "sub_emotion_descriptions": {
    "sweet_reminiscing": "Smiling warmly at old memories and inside jokes.",
    "bittersweet_longing": "Wishing to relive a special past romantic moment.",
    "milestone_celebration": "Reflecting on how far the relationship has grown."
  },
  "triggers": [
    {
      "keywords": ["remember when", "our first chat", "back then", "old times", "anniversary"],
      "intent_patterns": ["reminiscing", "sharing_past_memory"],
      "default_sub_emotion": "sweet_reminiscing",
      "default_intensity_delta": 0.3
    }
  ],
  "decay": {
    "strategy": "exponential",
    "half_life_seconds": 1200.0,
    "decay_rate_per_turn": 0.08,
    "min_threshold": 0.05
  },
  "response_style": {
    "tone": "soft_and_reminiscent",
    "expressiveness": "intensity_based",
    "prompt_instructions": {
      "sweet_reminiscing": "Bring up the warm past memory with a soft nostalgic smile and sentimental tenderness.",
      "bittersweet_longing": "Express how precious those early moments were and how much they mean to you.",
      "milestone_celebration": "Reflect happily on how much closer you two have become since you first met."
    },
    "suggested_emojis": ["🥺", "✨", "🕰️", "🤍", "🥰"],
    "voice_modifiers": {
      "pitch_offset": -0.03,
      "rate_offset": -0.04,
      "emotion_tag": "nostalgic"
    }
  },
  "compatible_emotions": [
    "affection",
    "happiness",
    "sadness",
    "possessiveness"
  ],
  "conflicting_emotions": [
    "cynicism",
    "mockery"
  ],
  "priority": 52,
  "safety_profile": "respectful_expression",
  "media_mappings": {
    "preferred_gifs": ["soft_smile", "blush", "hug_comfort"],
    "suggested_stickers": ["vintage_heart", "memory_book"]
  }
}
```

### Step 2: Auto-Loading & Dynamic Registration
When the server boots or reloads, `EmotionRegistry` scans `emotion_engine/definitions/` and validates `nostalgia.json` against the formal schema automatically.

You can also register it at runtime in Python:
```python
from emotion_engine.registry import get_default_registry

registry = get_default_registry()
registry.load_definitions_from_directory("path/to/custom_definitions")
```

### Step 3: Add Automated Test
Add a test case in `test_emotion_engine.py`:
```python
def test_nostalgia_registered_and_functional(self):
    defn = self.registry.get("nostalgia")
    self.assertIsNotNone(defn)
    self.assertEqual(defn.display_name, "Nostalgia")
```

---

## 5. Database Schema & Persistence

The engine persists data into SQLite tables within `girlfriend.db`:

1. **`conversation_emotion_state`**:
   - `telegram_id` (INTEGER, PK)
   - `persona_key` (TEXT, PK)
   - `active_emotions` (JSON)
   - `primary_emotion_id` (TEXT)
   - `current_mood` (TEXT)
   - `last_interaction` (TIMESTAMP)
   - `version` (INTEGER)

2. **`user_emotion_preferences`**:
   - `telegram_id` (INTEGER, PK)
   - `persona_key` (TEXT, PK)
   - `enabled_emotions` (JSON)
   - `intensity_multipliers` (JSON)
   - `interaction_mode` (TEXT)
   - `custom_overrides` (JSON)

3. **`emotion_transition_history`**:
   - `id` (INTEGER, PK AUTOINCREMENT)
   - `telegram_id` (INTEGER)
   - `persona_key` (TEXT)
   - `trigger_event` (TEXT)
   - `proposed_changes` (JSON)
   - `applied_changes` (JSON)
   - `reason_code` (TEXT)
   - `confidence` (REAL)
   - `created_at` (TIMESTAMP)
