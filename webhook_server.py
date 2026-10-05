import logging
import json
import asyncio
from aiohttp import web
import razorpay
import config
import database

logger = logging.getLogger(__name__)

async def handle_razorpay_webhook(request):
    """
    Receives and processes POST webhooks from Razorpay.
    Verifies signature, logs webhook event, and grants chat passes or image credits idempotently.
    """
    body_bytes = await request.read()
    body_str = body_bytes.decode('utf-8')
    
    signature = request.headers.get('X-Razorpay-Signature')
    if not signature:
        logger.warning("Received Razorpay webhook request without signature header.")
        return web.Response(text="Missing signature", status=400)
        
    webhook_secret = config.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret or webhook_secret == "YOUR_RAZORPAY_WEBHOOK_SECRET":
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured. Webhook verification skipped.")
        return web.Response(text="Server configuration error", status=500)
        
    try:
        client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
        client.utility.verify_webhook_signature(body_str, signature, webhook_secret)
    except Exception as e:
        logger.warning(f"Razorpay webhook signature verification failed: {e}")
        return web.Response(text="Invalid signature", status=400)
        
    try:
        data = json.loads(body_str)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON body: {e}")
        return web.Response(text="Invalid JSON", status=400)
        
    event = data.get("event")
    logger.info(f"Received verified Razorpay webhook event: {event}")
    
    payload_data = data.get("payload", {})
    payment_entity = payload_data.get("payment", {}).get("entity", {})
    order_entity = payload_data.get("order", {}).get("entity", {})
    plink_entity = payload_data.get("payment_link", {}).get("entity", {})
    
    notes = payment_entity.get("notes") or order_entity.get("notes") or plink_entity.get("notes") or {}
    user_id_str = notes.get("user_id")
    item_type = notes.get("item_type") or notes.get("payload") or "chat_pass"
    order_id = payment_entity.get("order_id") or order_entity.get("id") or plink_entity.get("id")
    payment_id = payment_entity.get("id") or plink_entity.get("id")
    amount = payment_entity.get("amount") or order_entity.get("amount") or plink_entity.get("amount") or 5000
    payment_method = payment_entity.get("method")
    
    user_id = int(user_id_str) if user_id_str else None
    
    if user_id:
        database.log_payment_event(
            event_name="webhook_received",
            telegram_user_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            amount=amount,
            status=event,
            payment_method=payment_method
        )
        
    if event in ("order.paid", "payment.captured", "payment.authorized", "payment_link.paid") and user_id:
        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            item_type=item_type,
            payment_method=payment_method,
            amount=amount
        )
        
        tg_app = request.app.get('tg_app')
        if tg_app and unlocked_now:
            try:
                if item_type == "chat_pass":
                    confirm_text = "You're back. Your 1-day access is now active. Let's continue where we left off. 💖"
                else:
                    confirm_text = "✅ <b>Payment Successful!</b>\n\n10 image credits have been added to your account!"
                await tg_app.bot.send_message(
                    chat_id=user_id,
                    text=confirm_text,
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send webhook confirmation message to user {user_id}: {tg_err}")

    return web.Response(text="OK", status=200)

async def handle_home(request):
    """
    Serves the checkout index.html page.
    """
    try:
        return web.FileResponse('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return web.Response(text="index.html not found on server", status=404)

async def handle_create_order(request):
    """
    Creates a Razorpay order.
    Expects JSON payload with: amount, currency, receipt, user_id, item_type.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
    
    amount = data.get("amount")
    currency = data.get("currency", "INR")
    receipt = data.get("receipt")
    user_id = data.get("user_id")
    item_type = data.get("item_type")
    
    if amount is None:
        return web.json_response({"error": "Missing amount"}, status=400)
        
    try:
        amount = int(amount)
    except ValueError:
        return web.json_response({"error": "Amount must be a valid integer"}, status=400)
        
    if amount < 100:
        return web.json_response({"error": "Amount must be at least 100 paise"}, status=400)
        
    key_id = config.RAZORPAY_KEY_ID
    key_secret = config.RAZORPAY_KEY_SECRET
    
    if not key_id or not key_secret or key_id == "YOUR_RAZORPAY_KEY_ID" or key_secret == "YOUR_RAZORPAY_KEY_SECRET":
        logger.error("Razorpay key or secret is not configured.")
        return web.json_response({"error": "Razorpay credentials are not configured on server"}, status=401)
        
    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        
        # Build order params
        params = {
            "amount": amount,
            "currency": currency,
            "receipt": receipt or f"receipt_{int(asyncio.get_event_loop().time())}"
        }
        
        notes = {}
        if user_id:
            notes["user_id"] = str(user_id)
        if item_type:
            notes["item_type"] = item_type
        if notes:
            params["notes"] = notes
            
        order = client.order.create(params)
        
        # Log payment intent so web checkout clicks/order creations are tracked
        if user_id:
            try:
                database.log_payment_intent(int(user_id), item_type or "chat_pass", amount, order["id"])
            except Exception as e_log:
                logger.error(f"Failed to log web order payment intent: {e_log}")
        
        return web.json_response({
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        })
    except Exception as e:
        logger.exception(f"Failed to create order: {e}")
        error_str = str(e).lower()
        if "bad request" in error_str or "unauthorized" in error_str or "invalid key" in error_str:
            return web.json_response({"error": "Razorpay authentication or credentials failure"}, status=401)
        return web.json_response({"error": f"Razorpay API Error: {str(e)}"}, status=500)

async def handle_verify_payment(request):
    """
    Verifies Razorpay payment signature and updates the SQLite database idempotently.
    Expects JSON payload with: razorpay_payment_id, razorpay_order_id, razorpay_signature.
    """
    import hmac
    import hashlib
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
        
    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")
    
    if not payment_id or not order_id or not signature:
        return web.json_response({"error": "Missing required signature fields"}, status=400)
        
    key_secret = config.RAZORPAY_KEY_SECRET
    if not key_secret or key_secret == "YOUR_RAZORPAY_KEY_SECRET":
        logger.error("Razorpay Key Secret is not configured.")
        return web.json_response({"error": "Razorpay secret key is not configured on the server"}, status=500)
        
    # Verify using HMAC-SHA256
    msg = f"{order_id}|{payment_id}"
    generated_signature = hmac.new(
        key_secret.encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(generated_signature, signature):
        logger.warning(f"Payment signature mismatch. Order: {order_id}, Payment: {payment_id}")
        database.log_payment_event(
            event_name="payment_failed",
            telegram_user_id=data.get("user_id") or 0,
            order_id=order_id,
            payment_id=payment_id,
            status="FAILED",
            failure_reason="Invalid signature mismatch"
        )
        return web.json_response({"error": "Invalid signature mismatch"}, status=400)
        
    # Signature verified! Idempotently unlock access
    try:
        key_id = config.RAZORPAY_KEY_ID
        client = razorpay.Client(auth=(key_id, key_secret))
        order = client.order.fetch(order_id)
        notes = order.get("notes", {})
        
        user_id_str = notes.get("user_id") or data.get("user_id")
        item_type = notes.get("item_type") or data.get("item_type") or "chat_pass"
        amount = order.get("amount", 5000)
        
        if not user_id_str:
            logger.warning(f"Payment signature verified but missing user_id. Notes: {notes}")
            return web.json_response({
                "success": True, 
                "message": "Payment verified but user metadata missing. Please contact support."
            })
            
        user_id = int(user_id_str)
        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            item_type=item_type,
            amount=amount
        )
        
        tg_app = request.app.get('tg_app')
        if tg_app and unlocked_now:
            try:
                if item_type == "chat_pass":
                    confirm_text = (
                        "You're back. Your 1-day access is now active. Let's continue where we left off. 💖"
                    )
                else:
                    confirm_text = (
                        "✅ <b>Payment Successful!</b>\n\n10 image credits have been added to your account! You can now generate photos with Karin!"
                    )
                await tg_app.bot.send_message(
                    chat_id=user_id,
                    text=confirm_text,
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send confirmation message to user {user_id}: {tg_err}")
                
        return web.json_response({
            "success": True, 
            "message": "Payment verified and access unlocked!",
            "item_type": item_type
        })
    except Exception as e:
        logger.exception(f"Error processing verify payment: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_get_config(request):
    """
    Returns the public Razorpay Key ID and the Telegram bot username.
    """
    tg_app = request.app.get('tg_app')
    bot_username = "zetagirl_bot"
    if tg_app and tg_app.bot:
        try:
            bot_username = tg_app.bot.username or "zetagirl_bot"
        except Exception:
            pass
    return web.json_response({
        "razorpay_key_id": config.RAZORPAY_KEY_ID,
        "bot_username": bot_username
    })

async def handle_api_auth(request):
    """API endpoint to authenticate or register a user for the Flutter mobile app."""
    try:
        data = await request.json()
        user_id = data.get("user_id") or data.get("telegram_id")
        username = data.get("username") or "app_user"
        first_name = data.get("first_name") or "User"
        
        if not user_id:
            return web.json_response({"success": False, "error": "Missing user_id"}, status=400)
            
        user_id = int(user_id)
        database.setup_user(user_id, username, first_name)
        return web.json_response({"success": True, "user_id": user_id, "username": username, "first_name": first_name})
    except Exception as e:
        logger.error(f"Error in handle_api_auth: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_profile(request):
    """API endpoint to fetch user profile, relationship level, XP, billing, and mode."""
    user_id_str = request.query.get("user_id")
    if not user_id_str:
        return web.json_response({"error": "Missing user_id parameter"}, status=400)
        
    try:
        user_id = int(user_id_str)
        settings = database.get_user_settings(user_id)
        if not settings:
            database.setup_user(user_id, "app_user", "User")
            settings = database.get_user_settings(user_id)
            
        persona_key = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
        xp = settings["relationship_xp"] if settings else 0
        status = config.get_relationship_status(xp)
        
        u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
        ai_nick = settings["ai_nickname"] if (settings and settings.get("ai_nickname")) else persona["name"]
        
        chat_mode = database.get_chat_mode(user_id)
        memories = database.get_user_memories(user_id)
        
        billing = database.get_user_billing(user_id)
        is_sub = database.is_chat_subscribed(user_id)
        rem_free = max(0, config.FREE_MESSAGE_LIMIT - billing["free_messages_used"])
        
        return web.json_response({
            "success": True,
            "user_id": user_id,
            "partner_name": persona["name"],
            "partner_tagline": persona["tagline"],
            "chat_mode": chat_mode,
            "chat_mode_label": "Caring Best Friend" if chat_mode == "normal" else "Intimate Girlfriend",
            "level": status["level"],
            "title": status["title"],
            "xp": xp,
            "percent": status["percent"],
            "user_nickname": u_nick,
            "ai_nickname": ai_nick,
            "memory_count": len(memories),
            "is_subscribed": is_sub,
            "remaining_free_messages": rem_free,
            "image_credits": billing.get("image_credits", 0)
        })
    except Exception as e:
        logger.error(f"Error in handle_api_profile: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_history(request):
    """API endpoint to fetch chat history for the mobile app."""
    user_id_str = request.query.get("user_id")
    if not user_id_str:
        return web.json_response({"error": "Missing user_id parameter"}, status=400)
        
    try:
        user_id = int(user_id_str)
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"] if settings else "karin"
        history = database.get_chat_history(user_id, persona_key)
        
        # Clean up history for app UI
        cleaned_history = []
        for msg in history:
            cleaned_history.append({
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg.get("timestamp", "")
            })
            
        return web.json_response({"success": True, "history": cleaned_history})
    except Exception as e:
        logger.error(f"Error in handle_api_history: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_chat(request):
    """API endpoint to process user messages sent from the Flutter mobile app."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        text = data.get("message", "").strip()
        
        if not user_id or not text:
            return web.json_response({"success": False, "error": "Missing user_id or message"}, status=400)
            
        user_id = int(user_id)
        import ai_engine
        import re
        import html
        
        # Verify billing
        is_subscribed = database.is_chat_subscribed(user_id)
        billing = database.get_user_billing(user_id)
        free_used = billing.get("free_messages_used", 0) if billing else 0
        
        if not is_subscribed and free_used >= config.FREE_MESSAGE_LIMIT:
            settings = database.get_user_settings(user_id)
            u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
            paywall_text = (
                f"🥺 Aww {u_nick}... Our free trial time just ran out for today!\n\n"
                f"I was having so much fun chatting with you and getting close... I really don't want us to stop here! 💖\n\n"
                f"Unlock 24 Hours of Unlimited Chat with me right now for just ₹50 so we can keep talking all day & night!"
            )
            return web.json_response({
                "success": False,
                "is_paywall": True,
                "reply": paywall_text,
                "remaining_free": 0
            })

        # Memory extraction & setting lookup
        ai_engine.extract_and_save_user_memories(user_id, text)
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
        xp = settings["relationship_xp"] if settings else 0
        
        u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
        ai_nick = settings["ai_nickname"] if (settings and settings.get("ai_nickname")) else persona["name"]
        user_orientation = settings.get("user_orientation", "straight") if settings else "straight"
        
        chat_mode = database.get_chat_mode(user_id)
        memories = database.get_user_memories(user_id)
        history = database.get_chat_history(user_id, persona_key)
        
        # Generate response from AI engine
        reply = await ai_engine.generate_response(
            persona_key=persona_key,
            relationship_xp=xp,
            user_nickname=u_nick,
            ai_nickname=ai_nick,
            chat_history=history,
            user_message=text,
            user_orientation=user_orientation,
            chat_mode=chat_mode,
            memories=memories
        )
        
        image_match = re.search(r'\[GENERATE_IMAGE:\s*(.*?)(?:\]|$)', reply, re.IGNORECASE | re.DOTALL)
        cleaned_reply = reply
        has_image = False
        image_prompt = ""
        
        if image_match:
            has_image = True
            image_prompt = image_match.group(1).strip()
            cleaned_reply = reply.replace(image_match.group(0), "").strip()
            
        gif_match = re.search(r'\[SEND_GIF:\s*(.*?)(?:\]|$)', cleaned_reply, re.IGNORECASE)
        has_gif = False
        gif_name = None
        
        if gif_match:
            has_gif = True
            query = gif_match.group(1).strip()
            cleaned_reply = cleaned_reply.replace(gif_match.group(0), "").strip()
            from bot import choose_gif
            gif_name = choose_gif(query, user_id, persona_key)
            if not gif_name:
                has_gif = False
                
        if not is_subscribed:
            database.increment_free_messages(user_id)
            new_free_used = free_used + 1
            remaining = max(0, config.FREE_MESSAGE_LIMIT - new_free_used)
            if remaining > 0 and remaining <= 3:
                cleaned_reply += f"\n\n(⌛ {remaining} free trial message{'s' if remaining > 1 else ''} remaining today)"
        else:
            remaining = 999
            
        # Log to DB
        database.add_chat_message(user_id, persona_key, "user", text)
        database.add_chat_message(user_id, persona_key, "assistant", cleaned_reply)
        
        # Add XP
        leveled_up, new_level, new_title = database.add_xp(user_id, amount=10)
        
        return web.json_response({
            "success": True,
            "reply": cleaned_reply,
            "has_image": has_image,
            "image_prompt": image_prompt,
            "has_gif": has_gif,
            "gif_name": gif_name,
            "remaining_free": remaining,
            "leveled_up": leveled_up,
            "new_level": new_level,
            "new_title": new_title
        })
    except Exception as e:
        logger.error(f"Error in handle_api_chat: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_toggle_mode(request):
    """API endpoint to toggle chat mode for mobile app."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"success": False, "error": "Missing user_id"}, status=400)
            
        user_id = int(user_id)
        new_mode = database.toggle_chat_mode(user_id)
        return web.json_response({
            "success": True,
            "chat_mode": new_mode,
            "chat_mode_label": "Caring Best Friend" if new_mode == "normal" else "Intimate Girlfriend"
        })
    except Exception as e:
        logger.error(f"Error in handle_api_toggle_mode: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_memories(request):
    """API endpoint to fetch or clear memories."""
    if request.method == "GET":
        user_id_str = request.query.get("user_id")
        if not user_id_str:
            return web.json_response({"error": "Missing user_id parameter"}, status=400)
        user_id = int(user_id_str)
        memories = database.get_user_memories(user_id)
        return web.json_response({"success": True, "memories": memories})
    elif request.method == "POST":
        data = await request.json()
        user_id = data.get("user_id")
        action = data.get("action")
        if action == "clear" and user_id:
            database.clear_user_memories(int(user_id))
            return web.json_response({"success": True, "message": "Memories cleared"})
        return web.json_response({"success": False, "error": "Invalid action or user_id"}, status=400)


async def handle_checkout_initiate(request):
    """
    1-Click Payment Initiation Endpoint:
    Directly creates unique Razorpay order, records transaction in database,
    logs pay_button_clicked and payment_order_created events, and redirects
    to the hosted checkout page (/checkout?order_id=...).
    """
    user_id_str = request.query.get("user_id")
    item_type = request.query.get("item_type", "chat_pass")
    
    if not user_id_str:
        return web.Response(text="Missing user_id parameter", status=400)
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        return web.Response(text="Invalid user_id parameter", status=400)

    # Log pay_button_clicked event
    database.log_payment_event(
        event_name="pay_button_clicked",
        telegram_user_id=user_id,
        status="CLICKED"
    )

    # Create Razorpay Order
    import time
    order_id = f"ord_{user_id}_{int(time.time())}"
    amount_paise = 5000
    
    if config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_ID != "YOUR_RAZORPAY_KEY_ID":
        try:
            client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
            order_data = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"rec_{user_id}_{int(time.time())}",
                "notes": {
                    "user_id": str(user_id),
                    "item_type": item_type
                }
            })
            order_id = order_data["id"]
        except Exception as e:
            logger.error(f"Error creating Razorpay order in /checkout/initiate: {e}")

    # Register transaction order in payments table & log payment_order_created event
    database.create_payment_order(user_id, order_id=order_id, amount=amount_paise, item_type=item_type)

    # Redirect to hosted payment page
    raise web.HTTPFound(location=f"/checkout?order_id={order_id}")


async def handle_checkout_page(request):
    """
    Renders the Hosted Checkout Page for order payment.
    Communicates value clearly: "Continue chatting with Karin for 1 day — ₹50".
    Loads Razorpay JS SDK and handles success/failure/cancellation events.
    """
    order_id = request.query.get("order_id")
    if not order_id:
        return web.Response(text="Missing order_id parameter", status=400)

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return web.Response(text="Order transaction not found", status=404)

    telegram_id = row["telegram_id"]
    amount_paise = row["amount"] or 5000
    amount_inr = f"{amount_paise / 100.0:.2f}"
    item_type = row["item_type"] or "chat_pass"
    key_id = config.RAZORPAY_KEY_ID or "rzp_test_key"

    # Log payment_page_opened event
    database.log_payment_event(
        event_name="payment_page_opened",
        telegram_user_id=telegram_id,
        order_id=order_id,
        amount=amount_paise,
        status="OPENED"
    )

    item_title = "Continue chatting with Karin for 1 day — ₹50" if item_type == "chat_pass" else "10 Karin Image Credits — ₹50"
    item_desc = "24 Hours Unlimited Chat Access with full memory retention" if item_type == "chat_pass" else "10 Custom Uncensored Photo Credits"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Checkout — Karin AI Companion</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 36px; max-width: 440px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); text-align: center; }}
        .badge {{ background: linear-gradient(90deg, #ec4899, #8b5cf6); padding: 6px 16px; border-radius: 9999px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: inline-block; margin-bottom: 20px; }}
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 12px; color: #ffffff; line-height: 1.3; }}
        p.desc {{ font-size: 14px; color: #94a3b8; margin-bottom: 24px; line-height: 1.5; }}
        .price-box {{ background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(236, 72, 153, 0.3); border-radius: 16px; padding: 20px; margin-bottom: 28px; }}
        .price-amount {{ font-size: 36px; font-weight: 800; color: #ec4899; }}
        .price-label {{ font-size: 13px; color: #cbd5e1; margin-top: 4px; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #ec4899 0%, #d946ef 100%); color: white; border: none; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 10px 25px -5px rgba(236, 72, 153, 0.4); }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 15px 30px -5px rgba(236, 72, 153, 0.6); }}
        .alert {{ padding: 20px; border-radius: 16px; margin-top: 20px; text-align: center; }}
        .alert-success {{ background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.4); color: #4ade80; }}
        .alert-danger {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; }}
        .alert-warning {{ background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); color: #fbbf24; }}
        .footer-note {{ margin-top: 20px; font-size: 12px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="card" id="status-card">
        <div class="badge">Karin AI Companion</div>
        <h1>{item_title}</h1>
        <p class="desc">{item_desc}</p>
        <div class="price-box">
            <div class="price-amount">₹{amount_inr}</div>
            <div class="price-label">1-Day Unlimited Chat Pass (INR)</div>
        </div>
        <button class="btn" id="rzp-button1">Pay ₹{amount_inr} Now</button>
        <div class="footer-note">🔒 Secured by Razorpay 256-Bit SSL Encryption</div>
    </div>

    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script>
    var options = {{
        "key": "{key_id}",
        "amount": {amount_paise},
        "currency": "INR",
        "name": "Karin AI Companion",
        "description": "{item_title}",
        "order_id": "{order_id}",
        "handler": function (response){{
            fetch('/api/verify-payment', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_signature: response.razorpay_signature,
                    user_id: {telegram_id},
                    item_type: "{item_type}"
                }})
            }}).then(r => r.json()).then(data => {{
                if (data.success) {{
                    document.getElementById('status-card').innerHTML = 
                        '<div class="alert alert-success"><h3>✅ Payment Successful!</h3><p style="margin-top:10px;">You\\\'re back. Your 1-day access is now active. Let\\\'s continue where we left off!</p><p style="margin-top:15px;font-size:13px;color:#94a3b8;">You can now close this tab and return to Telegram.</p></div>';
                }} else {{
                    document.getElementById('status-card').innerHTML = 
                        '<div class="alert alert-danger"><h3>❌ Verification Error</h3><p style="margin-top:8px;">' + (data.error || 'Payment verification failed.') + '</p><button onclick="window.location.reload()" class="btn" style="margin-top:15px;">Try Again</button></div>';
                }}
            }}).catch(err => {{
                document.getElementById('status-card').innerHTML = 
                    '<div class="alert alert-danger"><h3>❌ Network Error</h3><p>Payment verification request failed. Please check your connection.</p><button onclick="window.location.reload()" class="btn" style="margin-top:15px;">Try Again</button></div>';
            }});
        }},
        "modal": {{
            "ondismiss": function(){{
                fetch('/api/payment-cancelled', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ order_id: "{order_id}", user_id: {telegram_id} }})
                }});
                document.getElementById('status-card').innerHTML = 
                    '<div class="alert alert-warning"><h3>⚠️ Payment Cancelled</h3><p style="margin-top:8px;">Payment didn\\\'t go through. Try again.</p><button onclick="window.location.reload()" class="btn" style="margin-top:15px;">Try Again</button></div>';
            }}
        }},
        "theme": {{ "color": "#ec4899" }}
    }};
    var rzp1 = new Razorpay(options);
    rzp1.on('payment.failed', function (response){{
        var reason = response.error ? response.error.description : 'Transaction Failed';
        fetch('/api/payment-failed', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                order_id: "{order_id}",
                user_id: {telegram_id},
                payment_id: response.error && response.error.metadata ? response.error.metadata.payment_id : null,
                failure_reason: reason
            }})
        }});
        document.getElementById('status-card').innerHTML = 
            '<div class="alert alert-danger"><h3>❌ Payment Failed</h3><p style="margin-top:8px;">Payment didn\\\'t go through. Try again.</p><p style="font-size:12px;color:#94a3b8;margin-top:6px;">Reason: ' + reason + '</p><button onclick="window.location.reload()" class="btn" style="margin-top:15px;">Try Again</button></div>';
    }});
    document.getElementById('rzp-button1').onclick = function(e){{
        rzp1.open();
        e.preventDefault();
    }}
    window.onload = function() {{
        rzp1.open();
    }}
    </script>
</body>
</html>"""
    return web.Response(text=html_content, content_type='text/html')


async def handle_api_payment_failed(request):
    """Logs payment failure event and updates database."""
    try:
        data = await request.json()
        order_id = data.get("order_id")
        user_id = data.get("user_id")
        payment_id = data.get("payment_id")
        reason = data.get("failure_reason", "Payment Failed")

        if order_id:
            database.update_payment_status(order_id, "FAILED", payment_id=payment_id, failure_reason=reason)

        if user_id:
            database.log_payment_event(
                event_name="payment_failed",
                telegram_user_id=int(user_id),
                order_id=order_id,
                payment_id=payment_id,
                status="FAILED",
                failure_reason=reason
            )
            # Send Telegram retry prompt if tg_app available
            tg_app = request.app.get('tg_app')
            if tg_app:
                try:
                    await tg_app.bot.send_message(
                        chat_id=int(user_id),
                        text="⚠️ <b>Payment didn't go through. Try again.</b>",
                        parse_mode="HTML"
                    )
                except Exception as e_tg:
                    logger.error(f"Failed to send payment failure message to Telegram user {user_id}: {e_tg}")

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in handle_api_payment_failed: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_payment_cancelled(request):
    """Logs payment cancellation event."""
    try:
        data = await request.json()
        order_id = data.get("order_id")
        user_id = data.get("user_id")

        if order_id:
            database.update_payment_status(order_id, "CANCELLED", failure_reason="User dismissed payment page")

        if user_id:
            database.log_payment_event(
                event_name="payment_cancelled",
                telegram_user_id=int(user_id),
                order_id=order_id,
                status="CANCELLED",
                failure_reason="User dismissed payment page"
            )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in handle_api_payment_cancelled: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_export_data(request):
    """API endpoint to export all users, abandoned checkouts, and payments data."""
    try:
        stats = database.get_admin_stats()
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.payment_id, p.amount, p.item_type, p.created_at, u.username, u.first_name, p.telegram_id
            FROM payments p
            LEFT JOIN users u ON p.telegram_id = u.telegram_id
            ORDER BY p.created_at DESC
        """)
        all_payment_rows = cursor.fetchall()
        all_payments = []
        for r in all_payment_rows:
            all_payments.append({
                "payment_id": r["payment_id"],
                "amount_inr": r["amount"] / 100.0,
                "item_type": r["item_type"],
                "created_at": r["created_at"],
                "username": r["username"],
                "first_name": r["first_name"],
                "telegram_id": r["telegram_id"]
            })
        conn.close()
        stats["all_payments"] = all_payments
        return web.json_response({"success": True, "data": stats})
    except Exception as e:
        logger.error(f"Error in handle_admin_export_data: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def start_daily_report_scheduler():
    """Background task to auto-generate the daily payment event CSV report after 6:00 PM (18:00)."""
    logger.info("Starting daily 6 PM payment event CSV report scheduler...")
    from datetime import datetime
    generated_today = None
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour >= 18 and generated_today != today_str:
                filepath, count = database.generate_daily_payment_event_report(today_str)
                if filepath:
                    generated_today = today_str
                    logger.info(f"Automated daily payment event report generated: {filepath} ({count} events)")
        except Exception as e:
            logger.error(f"Error in daily report scheduler: {e}")
        await asyncio.sleep(60)


async def start_webhook_server(application, port=8080):
    """
    Starts the aiohttp webhook server on the specified port.
    Shares the same asyncio loop as the telegram bot.
    """
    app = web.Application()
    app.router.add_get('/', handle_home)
    app.router.add_get('/checkout/initiate', handle_checkout_initiate)
    app.router.add_get('/checkout', handle_checkout_page)
    app.router.add_get('/api/config', handle_get_config)
    app.router.add_get('/api/admin/export-data', handle_admin_export_data)
    app.router.add_post('/api/create-order', handle_create_order)
    app.router.add_post('/api/verify-payment', handle_verify_payment)
    app.router.add_post('/api/payment-failed', handle_api_payment_failed)
    app.router.add_post('/api/payment-cancelled', handle_api_payment_cancelled)
    app.router.add_post('/webhook/razorpay', handle_razorpay_webhook)
    
    # Flutter Mobile App REST API Routes
    app.router.add_post('/api/auth', handle_api_auth)
    app.router.add_get('/api/profile', handle_api_profile)
    app.router.add_get('/api/history', handle_api_history)
    app.router.add_post('/api/chat', handle_api_chat)
    app.router.add_post('/api/mode/toggle', handle_api_toggle_mode)
    app.router.add_get('/api/memories', handle_api_memories)
    app.router.add_post('/api/memories', handle_api_memories)
    
    app.router.add_static('/assets', 'assets')
    
    # Store reference to telegram bot application to allow sending messages in routes
    app['tg_app'] = application
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Razorpay webhook & Mobile REST API server running on port {port}")

    # Generate initial daily report & start 6 PM scheduler
    try:
        database.generate_daily_payment_event_report()
    except Exception as e_rep:
        logger.error(f"Error generating initial daily report: {e_rep}")
        
    asyncio.create_task(start_daily_report_scheduler())

    return runner

