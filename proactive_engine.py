import asyncio
import logging
from datetime import datetime
import database
import ai_engine

logger = logging.getLogger(__name__)

def get_time_of_day_context(now=None):
    """Returns a human-readable time of day context based on current local or injected time."""
    if now is None:
        now = datetime.now()
    hour = now.hour
    time_str = now.strftime("%I:%M %p")
    if 5 <= hour < 12:
        return f"Morning ({time_str})"
    elif 12 <= hour < 17:
        return f"Afternoon ({time_str})"
    elif 17 <= hour < 22:
        return f"Evening ({time_str})"
    else:
        return f"Late Night ({time_str})"


# Budget & Safety Constants (Guaranteeing < 30 INR / month total LLM spend)
MAX_GLOBAL_PROACTIVE_DAILY = 10      # Max 10 messages/day across platform (~15 INR / month maximum)
MAX_USER_PROACTIVE_DAILY = 1        # Max 1 proactive message per active user per day
MIN_PROACTIVE_INTERVAL_HOURS = 20.0 # Strict 20-hour cooldown between proactive messages to the same user
MIN_USER_INACTIVITY_HOURS = 4.0     # Don't message if user chatted in the last 4 hours
MAX_USER_INACTIVITY_HOURS = 48.0    # Don't waste tokens on dormant users inactive for > 48 hours


async def evaluate_proactive_for_user(telegram_id: int, force: bool = False, trigger_type: str = "NORMAL", current_time: str = None) -> dict:
    """
    Evaluates a single user for proactive message eligibility using the Decision Engine.
    Employs a zero-token rule gate to ensure 0 LLM tokens are wasted on DONT_SEND decisions.
    """
    settings = database.get_user_settings(telegram_id)
    if not settings:
        return {
            "telegram_id": telegram_id,
            "decision": "DONT_SEND",
            "reason": "User settings not found.",
            "message": None
        }

    persona_key = settings.get("active_persona", "juhi")
    user_nickname = settings.get("user_nickname") or "Honey"
    ai_nickname = settings.get("ai_nickname") or "Juhi"
    eval_now = datetime.fromisoformat(current_time) if current_time else datetime.now()

    # Skip synthetic evaluation test users during periodic background runs
    if telegram_id >= 88880000 and not force:
        return {
            "telegram_id": telegram_id,
            "decision": "DONT_SEND",
            "reason": "Synthetic evaluation user skipped during background loop.",
            "message": None
        }

    # Zero-token rule gate (skips LLM entirely when conditions are not met)
    if not force:
        # 1. Global Daily Budget Cap: Never exceed 10 proactive messages/day (~15 INR/mo ceiling)
        today_sends = database.get_proactive_sends_today()
        if today_sends >= MAX_GLOBAL_PROACTIVE_DAILY:
            return {
                "telegram_id": telegram_id,
                "decision": "DONT_SEND",
                "reason": f"Global daily proactive budget cap reached ({today_sends}/{MAX_GLOBAL_PROACTIVE_DAILY} today).",
                "message": None
            }

        # 2. Per-User Daily Limit: Max 1 proactive reachout per user per day
        user_sends = database.get_user_proactive_sends_today(telegram_id)
        if user_sends >= MAX_USER_PROACTIVE_DAILY:
            return {
                "telegram_id": telegram_id,
                "decision": "DONT_SEND",
                "reason": f"User daily proactive limit reached ({user_sends}/{MAX_USER_PROACTIVE_DAILY} today).",
                "message": None
            }

        # 3. Quiet hours check: never call LLM between 10 PM and 8 AM
        hour = eval_now.hour
        if hour >= 22 or hour < 8:
            return {
                "telegram_id": telegram_id,
                "decision": "DONT_SEND",
                "reason": "Quiet hours (10 PM - 8 AM). Let user rest without interruption.",
                "message": None
            }

        # 4. Check last proactive message sent to user (min 20h between messages)
        last_proactive = database.get_last_proactive_sent_time(telegram_id)
        if last_proactive:
            try:
                last_p_dt = datetime.fromisoformat(str(last_proactive))
                hours_since_p = (eval_now - last_p_dt).total_seconds() / 3600.0
                if hours_since_p < MIN_PROACTIVE_INTERVAL_HOURS:
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"Proactive message sent recently ({hours_since_p:.1f}h ago < {MIN_PROACTIVE_INTERVAL_HOURS}h cooldown).",
                        "message": None
                    }
            except Exception:
                pass

        # 5. Check last evaluation timestamp (prevent re-evaluating on DONT_SEND)
        last_eval = database.get_last_proactive_evaluation_time(telegram_id)
        if last_eval:
            try:
                last_eval_dt = datetime.fromisoformat(str(last_eval))
                hours_since_eval = (eval_now - last_eval_dt).total_seconds() / 3600.0
                if hours_since_eval < 6.0:  # Minimum 6 hours between LLM evaluations
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"Evaluated recently ({hours_since_eval:.1f}h ago < 6h evaluation cooldown).",
                        "message": None
                    }
            except Exception:
                pass

        # 6. Check last user message timestamp (Must be between 4h and 48h)
        last_user_msg = database.get_last_user_message_time(telegram_id)
        if last_user_msg:
            try:
                last_u_dt = datetime.fromisoformat(str(last_user_msg))
                hours_since_u = (eval_now - last_u_dt).total_seconds() / 3600.0
                if hours_since_u < MIN_USER_INACTIVITY_HOURS:
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"User chatted recently ({hours_since_u:.1f}h ago < {MIN_USER_INACTIVITY_HOURS}h cooldown).",
                        "message": None
                    }
                elif hours_since_u > MAX_USER_INACTIVITY_HOURS:
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"User inactive for {hours_since_u:.1f}h (> {MAX_USER_INACTIVITY_HOURS}h). Skipping dormant account to save budget.",
                        "message": None
                    }
            except Exception:
                pass
        elif trigger_type == "NORMAL":
            # No user message on record and not an explicit trigger
            return {
                "telegram_id": telegram_id,
                "decision": "DONT_SEND",
                "reason": "No user message history on record. Skipping unverified account.",
                "message": None
            }

    # Fetch compact context for evaluation
    chat_history = database.get_chat_history(telegram_id, persona_key=persona_key, limit=4)

    # 7. Double-Texting Gate (0 tokens):
    # If the last message in chat was sent by Juhi, she is already waiting for a reply!
    if not force and chat_history and chat_history[-1].get("role") == "assistant":
        return {
            "telegram_id": telegram_id,
            "decision": "DONT_SEND",
            "reason": "Juhi already sent the last message and is awaiting user response. Double-texting prevented.",
            "message": None
        }

    # 8. Dispatch Window Check:
    # Only send in morning window (8-10 AM) or evening window (7-9 PM) or when a scheduled event is due
    is_morning_window = 8 <= eval_now.hour <= 10
    is_evening_window = 19 <= eval_now.hour <= 21
    has_due_event = any(ev.get("status") == "FOLLOW_UP_DUE" for ev in database.get_user_events(telegram_id))
    has_no_history = not chat_history

    if not force and trigger_type == "NORMAL":
        if not (is_morning_window or is_evening_window or has_due_event or has_no_history):
            database.log_proactive_decision(telegram_id, "DONT_SEND", "Outside reach-out windows (8-10 AM, 7-9 PM) and no due events", None)
            return {
                "telegram_id": telegram_id,
                "decision": "DONT_SEND",
                "reason": "Outside proactive reach-out windows and no pending life events.",
                "message": None
            }

    # Gather lean memories (top 3)
    memories = database.get_user_memories(telegram_id, limit=3)
    time_context = get_time_of_day_context(eval_now)
    if trigger_type != "NORMAL":
        time_context += f" | Trigger Context: {trigger_type}"

    # If no chat history exists, trigger FIRST_CONVERSATION to start the chat
    effective_trigger = trigger_type
    if not chat_history and trigger_type == "NORMAL":
        effective_trigger = "FIRST_CONVERSATION"

    # Invoke Proactive Decision Engine (only called when all rules pass)
    result = await ai_engine.evaluate_proactive_decision(
        user_id=telegram_id,
        persona_key=persona_key,
        memories=memories,
        chat_history=chat_history,
        user_nickname=user_nickname,
        ai_nickname=ai_nickname,
        time_of_day_context=time_context,
        trigger_type=effective_trigger,
        current_time=current_time
    )

    result["telegram_id"] = telegram_id
    result["memories_count"] = len(memories)
    result["time_context"] = time_context
    return result


async def execute_proactive_check(application=None, telegram_id: int = None, force: bool = False) -> list:
    """
    Runs the Proactive Decision Engine for target user or active registered users.
    Saves message directly to user chat history and logs evaluations.
    """
    # Enforce global daily cap before doing any work
    if not force and database.get_proactive_sends_today() >= MAX_GLOBAL_PROACTIVE_DAILY:
        logger.info(f"[PROACTIVE ENGINE] Global daily budget safety cap ({MAX_GLOBAL_PROACTIVE_DAILY} sends) reached. Skipping.")
        return []

    if telegram_id:
        users = [{"telegram_id": telegram_id}]
    else:
        # Strictly target active users who messaged within the last 48 hours to protect budget
        users = database.get_active_users_for_proactive(within_hours=48)

    if not users:
        logger.debug("[PROACTIVE ENGINE] No active users eligible for proactive check.")
        return []

    results = []
    for u in users:
        u_id = u["telegram_id"]
        try:
            res = await evaluate_proactive_for_user(u_id, force=force)
            decision = str(res.get("decision", "DONT_SEND")).upper()
            reason = res.get("reason", "")
            message = res.get("message")

            if decision not in {"SEND", "DONT_SEND"} or (decision == "SEND" and not message):
                decision = "DONT_SEND"
                message = None
                reason = reason or "Malformed proactive decision; normalized to DONT_SEND."

            if decision == "SEND" and message:
                try:
                    # Store in companion chat history so Android app sees it immediately
                    settings = database.get_user_settings(u_id)
                    p_key = settings.get("active_persona", "juhi") if settings else "juhi"
                    database.add_chat_message(u_id, p_key, "assistant", message)
                    
                    # Reward user + companion interaction
                    database.add_xp(u_id, amount=5)
                    
                    # Log SEND decision
                    database.log_proactive_decision(u_id, "SEND", reason, message)
                    res["sent_status"] = "DELIVERED"
                    logger.info(f"[PROACTIVE ENGINE] SENT to user {u_id}: '{message}' (Reason: {reason})")

                    # If Telegram bot application is provided, forward to Telegram
                    if application and hasattr(application, "bot"):
                        try:
                            await application.bot.send_message(chat_id=u_id, text=message)
                        except Exception as tg_err:
                            logger.debug(f"[PROACTIVE ENGINE] Telegram forward skipped for user {u_id}: {tg_err}")
                except Exception as e:
                    logger.error(f"[PROACTIVE ENGINE] Failed delivering to user {u_id}: {e}")
                    res["sent_status"] = f"FAILED ({e})"
            else:
                database.log_proactive_decision(u_id, "DONT_SEND", reason, None)
                res["sent_status"] = "SKIPPED"
                logger.debug(f"[PROACTIVE ENGINE] DONT_SEND for user {u_id}: {reason}")

            results.append(res)
        except Exception as e:
            logger.error(f"Error evaluating proactive check for user {u_id}: {e}")

    return results


async def proactive_scheduler_loop(application=None, interval_minutes: int = 60):
    """
    Background periodic loop to run proactive decision engine checks.
    Only executes during morning (8-10 AM) and evening (7-9 PM) windows.
    """
    logger.info(f"[PROACTIVE SCHEDULER] Started running every {interval_minutes} minutes.")
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            now = datetime.now()
            # Only trigger proactive evaluation during morning window (8-10 AM) or evening window (7-9 PM)
            is_morning_slot = (8 <= now.hour <= 10)
            is_evening_slot = (19 <= now.hour <= 21)
            if not is_morning_slot and not is_evening_slot:
                logger.debug(f"[PROACTIVE SCHEDULER] Hour {now.hour} is outside dispatch windows (8-10 AM, 7-9 PM). Sleeping.")
                continue

            logger.info("[PROACTIVE SCHEDULER] Active dispatch window reached. Checking active users...")
            await execute_proactive_check(application, force=False)
        except asyncio.CancelledError:
            logger.info("[PROACTIVE SCHEDULER] Stopped.")
            break
        except Exception as e:
            logger.error(f"[PROACTIVE SCHEDULER] Error during periodic execution: {e}")
