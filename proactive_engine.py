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


async def evaluate_proactive_for_user(telegram_id: int, force: bool = False, trigger_type: str = "NORMAL", current_time: str = None) -> dict:
    """
    Evaluates a single user for proactive message eligibility using the Decision Engine.
    Supports deterministic current_time injection for evaluation testing.
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
    chat_mode = database.get_chat_mode(telegram_id)

    eval_now = datetime.fromisoformat(current_time) if current_time else datetime.now()

    # Cooldown checks (skip if force=True)
    if not force:
        # Check last proactive message sent to user
        last_proactive = database.get_last_proactive_sent_time(telegram_id)
        if last_proactive:
            try:
                last_p_dt = datetime.fromisoformat(str(last_proactive))
                hours_since_p = (eval_now - last_p_dt).total_seconds() / 3600.0
                if hours_since_p < 6.0:  # Minimum 6h between proactive messages
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"Proactive message sent recently ({hours_since_p:.1f}h ago < 6h cooldown).",
                        "message": None
                    }
            except Exception:
                pass

        # Check last user message timestamp
        last_user_msg = database.get_last_user_message_time(telegram_id)
        if last_user_msg:
            try:
                last_u_dt = datetime.fromisoformat(str(last_user_msg))
                hours_since_u = (eval_now - last_u_dt).total_seconds() / 3600.0
                if hours_since_u < 3.0:  # If user chatted recently (< 3h ago), don't interrupt
                    return {
                        "telegram_id": telegram_id,
                        "decision": "DONT_SEND",
                        "reason": f"User chatted recently ({hours_since_u:.1f}h ago < 3h cooldown).",
                        "message": None
                    }
            except Exception:
                pass

    # Gather context: Pending memories & Chat history
    memories = database.get_user_memories(telegram_id, limit=10)
    chat_history = database.get_chat_history(telegram_id, persona_key=persona_key, limit=8)
    time_context = get_time_of_day_context(eval_now)
    if trigger_type != "NORMAL":
        time_context += f" | Trigger Context: {trigger_type}"

    # Invoke Proactive Decision Engine
    result = await ai_engine.evaluate_proactive_decision(
        user_id=telegram_id,
        persona_key=persona_key,
        memories=memories,
        chat_history=chat_history,
        user_nickname=user_nickname,
        ai_nickname=ai_nickname,
        time_of_day_context=time_context,
        trigger_type=trigger_type,
        current_time=current_time
    )

    result["telegram_id"] = telegram_id
    result["memories_count"] = len(memories)
    result["time_context"] = time_context
    return result


async def execute_proactive_check(application, telegram_id: int = None, force: bool = False) -> list:
    """
    Runs the Proactive Decision Engine for target user or all registered users.
    Dispatches messages on 'SEND' decision and logs evaluations.
    """
    if telegram_id:
        users = [{"telegram_id": telegram_id}]
    else:
        users = database.get_all_registered_users()

    results = []
    for u in users:
        u_id = u["telegram_id"]
        try:
            res = await evaluate_proactive_for_user(u_id, force=force)
            decision = res.get("decision", "DONT_SEND")
            reason = res.get("reason", "")
            message = res.get("message")

            if decision == "SEND" and message and application:
                try:
                    # Send message to Telegram chat
                    await application.bot.send_message(chat_id=u_id, text=message)
                    
                    # Store in chat history
                    settings = database.get_user_settings(u_id)
                    p_key = settings.get("active_persona", "juhi") if settings else "juhi"
                    database.add_chat_message(u_id, p_key, "assistant", message)
                    
                    # Reward user + companion interaction
                    database.add_xp(u_id, amount=5)
                    
                    # Log SEND decision
                    database.log_proactive_decision(u_id, "SEND", reason, message)
                    res["sent_status"] = "DELIVERED"
                    logger.info(f"[PROACTIVE ENGINE] SENT to user {u_id}: '{message}' (Reason: {reason})")
                except Exception as e:
                    logger.error(f"[PROACTIVE ENGINE] Failed sending to user {u_id}: {e}")
                    res["sent_status"] = f"FAILED ({e})"
            else:
                database.log_proactive_decision(u_id, "DONT_SEND", reason, None)
                res["sent_status"] = "SKIPPED"
                logger.info(f"[PROACTIVE ENGINE] DONT_SEND for user {u_id}: {reason}")

            results.append(res)
        except Exception as e:
            logger.error(f"Error evaluating proactive check for user {u_id}: {e}")

    return results


async def proactive_scheduler_loop(application, interval_minutes: int = 30):
    """Background periodic loop to run proactive decision engine checks."""
    logger.info(f"[PROACTIVE SCHEDULER] Started running every {interval_minutes} minutes.")
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            logger.info("[PROACTIVE SCHEDULER] Executing periodic proactive decision engine check...")
            await execute_proactive_check(application, force=False)
        except asyncio.CancelledError:
            logger.info("[PROACTIVE SCHEDULER] Stopped.")
            break
        except Exception as e:
            logger.error(f"[PROACTIVE SCHEDULER] Error during periodic execution: {e}")
