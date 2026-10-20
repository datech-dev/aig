# Juhi AI Companion Refactor

## Updated runtime files

- ai_engine.py
- config.py
- context_compiler.py
- context_models.py
- response_planner.py
- persona_registry.py
- memory_models.py
- database.py
- safety_engine.py
- proactive_engine.py
- llm_output.py (new)
- test_ai_refactor.py

## Runtime architecture

Safety -> Memory -> Emotion State -> Response Planner -> Context Compiler -> LLM -> Structured Output Validator -> Backend-authorized media compatibility bridge.

## Important compatibility decision

The public `ai_engine.generate_response(...) -> str` interface is preserved. The LLM is asked for structured JSON internally. Validated media requests are converted to the existing `[SEND_GIF: ...]` / `[GENERATE_IMAGE: ...]` markers by backend code only, so existing Telegram/media handling can continue while the model itself cannot directly execute those tags.

## Duplicate snapshots

Files named `ai_engine(1).py`, `config(1).py`, `database(1).py`, and `safety_engine(1).py` were not copied into this clean bundle. They should not be imported at runtime. Compare them with the canonical files if they contain local changes that need to be retained.

## Verification

- Python syntax compilation: PASS for all updated Python files.
- Context compiler smoke test: PASS.
- Database memory TTL smoke test: PASS.
- Full application test suite was not executed because the `emotion_engine` package was not included in the supplied files.
