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
    Verifies signature and grants chat passes or image credits.
    """
    # Read raw body
    body_bytes = await request.read()
    body_str = body_bytes.decode('utf-8')
    
    # Verify signature
    signature = request.headers.get('X-Razorpay-Signature')
    if not signature:
        logger.warning("Received Razorpay webhook request without signature header.")
        return web.Response(text="Missing signature", status=400)
        
    webhook_secret = config.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret or webhook_secret == "YOUR_RAZORPAY_WEBHOOK_SECRET":
        # Fallback/warning if not configured
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured. Webhook verification skipped.")
        return web.Response(text="Server configuration error", status=500)
        
    # Verify using Razorpay client utilities
    try:
        client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
        # This will raise SignatureVerificationError if verification fails
        client.utility.verify_webhook_signature(body_str, signature, webhook_secret)
    except Exception as e:
        logger.warning(f"Razorpay webhook signature verification failed: {e}")
        return web.Response(text="Invalid signature", status=400)
        
    # Signature is valid. Parse payload.
    try:
        data = json.loads(body_str)
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON body: {e}")
        return web.Response(text="Invalid JSON", status=400)
        
    event = data.get("event")
    logger.info(f"Received verified Razorpay event: {event}")
    
    if event == "payment_link.paid":
        payload_data = data.get("payload", {})
        plink = payload_data.get("payment_link", {}).get("entity", {})
        notes = plink.get("notes", {})
        
        user_id_str = notes.get("user_id")
        item_type = notes.get("payload")
        
        if not user_id_str or not item_type:
            logger.warning(f"Webhook payment_link.paid missing user_id or payload in notes. Notes: {notes}")
            return web.Response(text="Missing notes data", status=200) # Still return 200 to acknowledge webhook
            
        try:
            user_id = int(user_id_str)
            # Log successful payment link payment
            database.log_payment(
                telegram_id=user_id,
                payment_id=plink.get("id"),
                order_id=None,
                amount=plink.get("amount", 0),
                item_type=item_type
            )
        except ValueError:
            logger.error(f"Invalid user_id in notes: {user_id_str}")
            return web.Response(text="Invalid user_id", status=200)
            
        # Get telegram app instance from web application context
        tg_app = request.app.get('tg_app')
        if not tg_app:
            logger.error("Telegram Application instance not found in web app context.")
            return web.Response(text="Internal server error", status=500)
            
        if item_type == "chat_pass":
            expiry = database.grant_chat_pass(user_id, hours=config.CHAT_PASS_DURATION_HOURS)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"Granted 1 day chat pass to user {user_id} via Razorpay webhook. Expires: {expiry_str}")
            
            try:
                await tg_app.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"Thank you for your payment! Your 1-day unlimited chat pass has been activated.\n"
                        f"• <b>Expires at:</b> <code>{expiry_str}</code>\n\n"
                        f"You can now continue chatting with Karin!"
                    ),
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send confirmation message to user {user_id}: {tg_err}")
                
        elif item_type == "image_credits":
            database.grant_image_credits(user_id, amount=10)
            billing = database.get_user_billing(user_id)
            logger.info(f"Granted 10 image credits to user {user_id} via Razorpay webhook. Balance: {billing['image_credits']}")
            
            try:
                await tg_app.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"Thank you for your payment! 10 image credits have been added to your account.\n"
                        f"• <b>Total Image Balance:</b> <code>{billing['image_credits']}</code> credits.\n\n"
                        f"You can now generate pictures of Karin!"
                    ),
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send confirmation message to user {user_id}: {tg_err}")
        else:
            logger.warning(f"Unknown item type in webhook notes payload: {item_type}")
            
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
    Verifies Razorpay payment signature and updates the SQLite database.
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
        return web.json_response({"error": "Invalid signature mismatch"}, status=400)
        
    # Successfully verified! Update database
    try:
        key_id = config.RAZORPAY_KEY_ID
        client = razorpay.Client(auth=(key_id, key_secret))
        order = client.order.fetch(order_id)
        notes = order.get("notes", {})
        
        user_id_str = notes.get("user_id")
        item_type = notes.get("item_type")
        
        # Fallbacks from frontend payload in case notes are missing from Order object
        if not user_id_str:
            user_id_str = data.get("user_id")
        if not item_type:
            item_type = data.get("item_type")
            
        if not user_id_str or not item_type:
            logger.warning(f"Payment signature verified but missing user_id or item_type. Notes: {notes}")
            return web.json_response({
                "success": True, 
                "message": "Payment verified but user metadata missing. Please contact support."
            })
            
        user_id = int(user_id_str)
        # Log successful standard checkout payment
        database.log_payment(
            telegram_id=user_id,
            payment_id=payment_id,
            order_id=order_id,
            amount=order.get("amount", 0),
            item_type=item_type
        )
        tg_app = request.app.get('tg_app')
        
        if item_type == "chat_pass":
            expiry = database.grant_chat_pass(user_id, hours=config.CHAT_PASS_DURATION_HOURS)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"Granted 1 day chat pass to user {user_id} via Standard Checkout. Expires: {expiry_str}")
            
            if tg_app:
                try:
                    await tg_app.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"✅ <b>Payment Successful!</b>\n\n"
                            f"Thank you for your payment! Your 1-day unlimited chat pass has been activated.\n"
                            f"• <b>Expires at:</b> <code>{expiry_str}</code>\n\n"
                            f"You can now continue chatting with Karin!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as tg_err:
                    logger.error(f"Failed to send confirmation message to user {user_id}: {tg_err}")
                     
            return web.json_response({
                "success": True, 
                "message": "Payment verified and Chat Pass granted!",
                "item_type": "chat_pass",
                "details": f"Expires at {expiry_str}"
            })
            
        elif item_type == "image_credits":
            database.grant_image_credits(user_id, amount=10)
            billing = database.get_user_billing(user_id)
            new_balance = billing.get("image_credits", 0)
            logger.info(f"Granted 10 image credits to user {user_id} via Standard Checkout. Balance: {new_balance}")
            
            if tg_app:
                try:
                    await tg_app.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"✅ <b>Payment Successful!</b>\n\n"
                            f"Thank you for your payment! 10 image credits have been added to your account.\n"
                            f"• <b>Total Image Balance:</b> <code>{new_balance}</code> credits.\n\n"
                            f"You can now generate pictures of Karin!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as tg_err:
                    logger.error(f"Failed to send confirmation message to user {user_id}: {tg_err}")
                    
            return web.json_response({
                "success": True, 
                "message": "Payment verified and 10 Image Credits granted!",
                "item_type": "image_credits",
                "details": f"Total balance: {new_balance} credits"
            })
        else:
            logger.warning(f"Unknown item_type verified: {item_type}")
            return web.json_response({"success": True, "message": f"Payment verified but item type '{item_type}' not recognized."})
             
    except Exception as e:
        logger.exception(f"Error handling verified payment callbacks: {e}")
        return web.json_response({
            "success": False, 
            "error": f"Payment verified but database update failed: {str(e)}"
        }, status=500)

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


async def start_webhook_server(application, port=8080):
    """
    Starts the aiohttp webhook server on the specified port.
    Shares the same asyncio loop as the telegram bot.
    """
    app = web.Application()
    app.router.add_get('/', handle_home)
    app.router.add_get('/api/config', handle_get_config)
    app.router.add_get('/api/admin/export-data', handle_admin_export_data)
    app.router.add_post('/api/create-order', handle_create_order)
    app.router.add_post('/api/verify-payment', handle_verify_payment)
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
    return runner
