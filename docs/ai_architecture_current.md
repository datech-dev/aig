# Current AI Architecture & Refactor Documentation

## Overview
This document specifies the refactored, production-ready AI layer architecture for the Juhi AI companion application.

### Key Components

1. **Persona Registry (`persona_registry.py`)**:
   - Dynamic filesystem-based persona loader scanning `personas/*.json`.
   - Defaults to base `juhi.json`.
   - Adding new personas in the future requires only placing a new JSON file into `personas/` without any Python code changes.
   - Deprecated scenario personas (`juhi_long_drive`, `juhi_forest_cottage`, `juhi_home`) were removed and cleaned up.

2. **Typed Data Models (`context_models.py` & `memory_models.py`)**:
   - `PersonaConfig`: Typed representation of companion personas.
   - `RelationshipState`: Tracks progression level, XP, chat mode, nicknames, and orientation.
   - `EmotionContext`: Represents active emotions, intensity, and behavioral guidance.
   - `MemoryItem`: Incorporates memory classification (`fact`, `preference`, `detail`, `emotional_state`, `event`) and TTL expiration (`valid_until`).
   - `ResponsePlanContext` & `SafetyDecision`: Formal representation of conversation strategy and safety decisions.

3. **Context & System Prompt Compiler (`context_compiler.py`)**:
   - Authoritative compiler enforcing strict precedence order:
     1. Persona Base Prompt
     2. Physical Appearance Specification
     3. Relationship State & Mode Boundaries (Caring vs Intimate)
     4. Nickname Directives
     5. Filtered & Ranked Memories (Pending events prioritized, expired memories filtered)
     6. Dynamic Emotion Engine Guidance
     7. Texting & Style Constraints (Brief, lowercase, Telegram naturalism)
     8. Tool Triggers (Image generation & reaction GIFs)
   - Eliminates hardcoded unconditional jealousy blocks.

4. **Safety & Boundaries Layer (`safety_engine.py`)**:
   - `scan_input_safety()`: Scans for prompt injection, base64 bypass, and explicit requests.
   - `contains_sexual_intent()`: Detects sexual intent and NSFW requests to hard-gate Caring Best Friend mode.
   - `scan_output_safety()`: Output sanitizer preventing disallowed content leakage.

5. **Emotion Engine Disambiguation (`emotion_engine/detector.py`)**:
   - Refined jealousy detector ensuring professional/coworker and family mentions do not trigger romantic jealousy or hostility.
   - Romantic rivals, external crushes, or dating mentions accurately trigger possessiveness and playful jealousy.

6. **Proactive Decision Engine (`ai_engine.py`)**:
   - Fail-closed safety architecture: returns `DONT_SEND` upon LLM error or timeout, preventing unsolicited or confusing messages.

7. **Database Migrations & Maintenance (`database.py`)**:
   - Added `memory_type` and `valid_until` columns to `user_memories`.
   - Cleaned up orphaned scenario persona rows in `user_settings`.
   - Streamlined `setup_user()` and persona sync operations.
