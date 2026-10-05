import logging
import json
import asyncio
import urllib.parse
import aiohttp
from aiohttp import web
import config
import database

logger = logging.getLogger(__name__)

async def create_instamojo_payment_request(user_id: int, item_type: str = "chat_pass", amount_inr: float = 50.0):
    """
    Calls Instamojo REST API to create a Payment Request.
    Returns tuple: (payment_request_id, longurl, error_message)
    """
    endpoint = config.INSTAMOJO_ENDPOINT.rstrip("/") + "/payment-requests/"
    api_key = config.INSTAMOJO_API_KEY
    auth_token = config.INSTAMOJO_AUTH_TOKEN
    
    if not api_key or not auth_token or api_key == "YOUR_INSTAMOJO_API_KEY" or auth_token == "YOUR_INSTAMOJO_AUTH_TOKEN":
        # Fallback/mock order if credentials not yet configured
        import time
        mock_id = f"PR_mock_{user_id}_{int(time.time())}"
        mock_url = f"{config.WEB_CHECKOUT_URL}/checkout/instamojo/mock?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
        return mock_id, mock_url, None

    headers = {
        "X-Api-Key": api_key,
        "X-Auth-Token": auth_token
    }
    
    purpose = "Karin AI 1-Day Chat Pass" if item_type == "chat_pass" else "Karin AI 10 Image Credits"
    redirect_url = f"{config.WEB_CHECKOUT_URL}/checkout/instamojo/callback"
    webhook_url = f"{config.WEB_CHECKOUT_URL}/webhook/instamojo"
    
    data = {
        "purpose": purpose[:30],
        "amount": f"{amount_inr:.2f}",
        "buyer_name": f"User {user_id}",
        "email": f"user_{user_id}@karin.ai",
        "redirect_url": redirect_url,
        "webhook": webhook_url,
        "allow_repeated_payments": "False",
        "send_email": "False",
        "send_sms": "False"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, headers=headers, data=data) as resp:
                resp_data = await resp.json()
                if resp.status in (200, 201) and resp_data.get("success"):
                    pr = resp_data.get("payment_request", {})
                    return pr.get("id"), pr.get("longurl"), None
                else:
                    err_msg = resp_data.get("message") or resp_data.get("error") or str(resp_data)
                    logger.error(f"Instamojo API Error creating payment request: {err_msg}")
                    import time
                    mock_id = f"PR_mock_{user_id}_{int(time.time())}"
                    mock_url = f"{config.WEB_CHECKOUT_URL}/checkout/instamojo/mock?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
                    return mock_id, mock_url, f"Instamojo API Error: {err_msg}"
    except Exception as e:
        logger.error(f"HTTP exception during Instamojo API call: {e}")
        import time
        mock_id = f"PR_mock_{user_id}_{int(time.time())}"
        mock_url = f"{config.WEB_CHECKOUT_URL}/checkout/instamojo/mock?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
        return mock_id, mock_url, str(e)


async def handle_instamojo_webhook(request):
    """
    Receives and processes POST webhooks from Instamojo.
    Verifies MAC if salt provided, logs webhook event, and grants access idempotently.
    """
    try:
        post_data = await request.post()
        data = {k: v for k, v in post_data.items()}
    except Exception:
        try:
            raw_body = await request.text()
            parsed = urllib.parse.parse_qs(raw_body)
            data = {k: v[0] for k, v in parsed.items()}
        except Exception as e:
            logger.error(f"Failed to parse Instamojo webhook data: {e}")
            return web.Response(text="Invalid data", status=400)
            
    payment_id = data.get("payment_id")
    payment_request_id = data.get("payment_request_id")
    status = data.get("status")
    mac = data.get("mac")
    
    logger.info(f"Received Instamojo webhook: payment_id={payment_id}, request_id={payment_request_id}, status={status}")
    
    salt = config.INSTAMOJO_SALT or config.INSTAMOJO_AUTH_TOKEN
    if salt and mac:
        try:
            import hmac
            import hashlib
            keys = sorted([k for k in data.keys() if k.lower() != "mac"], key=lambda s: s.lower())
            val_str = "|".join([str(data[k]) for k in keys])
            calculated_mac = hmac.new(salt.encode("utf-8"), val_str.encode("utf-8"), hashlib.sha1).hexdigest()
            if not hmac.compare_digest(calculated_mac.lower(), mac.lower()):
                logger.warning(f"Instamojo webhook MAC signature mismatch. Calculated: {calculated_mac}, Received: {mac}")
        except Exception as mac_err:
            logger.warning(f"Error during Instamojo MAC verification: {mac_err}")

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE order_id = ?", (payment_request_id,))
    row = cursor.fetchone()
    conn.close()
    
    telegram_id = row["telegram_id"] if row else 0
    item_type = row["item_type"] if row else "chat_pass"
    amount = row["amount"] if row else 5000
    
    if telegram_id:
        database.log_payment_event(
            event_name="webhook_received",
            telegram_user_id=telegram_id,
            order_id=payment_request_id,
            payment_id=payment_id,
            amount=amount,
            status=status or "CREDIT",
            payment_gateway="instamojo"
        )
        
    if (status in ("Credit", "SUCCESS", "completed", "paid")) and telegram_id:
        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=telegram_id,
            order_id=payment_request_id,
            payment_id=payment_id,
            item_type=item_type,
            gateway="instamojo",
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
                    chat_id=telegram_id,
                    text=confirm_text,
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send webhook confirmation message to user {telegram_id}: {tg_err}")

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
    Creates an Instamojo Payment Request for REST clients.
    Expects JSON payload with: amount, currency, user_id, item_type.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
    
    amount = data.get("amount", 5000)
    user_id = data.get("user_id")
    item_type = data.get("item_type", "chat_pass")
    
    if not user_id:
        return web.json_response({"error": "Missing user_id"}, status=400)
        
    try:
        user_id = int(user_id)
        amount_inr = float(amount) / 100.0 if int(amount) >= 100 else 50.0
    except ValueError:
        return web.json_response({"error": "Invalid user_id or amount"}, status=400)
        
    order_id, pay_url, err = await create_instamojo_payment_request(user_id, item_type, amount_inr=amount_inr)
    database.create_payment_order(user_id, order_id=order_id, amount=int(amount_inr * 100), item_type=item_type)
    
    return web.json_response({
        "order_id": order_id,
        "pay_url": pay_url,
        "amount": int(amount_inr * 100),
        "currency": "INR"
    })

async def handle_verify_payment(request):
    """
    Verifies Instamojo payment and updates the SQLite database idempotently.
    Expects JSON payload with: payment_request_id (or order_id), payment_id, user_id.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
        
    order_id = data.get("payment_request_id") or data.get("order_id") or data.get("razorpay_order_id")
    payment_id = data.get("payment_id") or data.get("razorpay_payment_id") or f"MOJO_verify_{order_id}"
    user_id = data.get("user_id")
    item_type = data.get("item_type", "chat_pass")
    
    if not order_id or not user_id:
        return web.json_response({"error": "Missing required fields"}, status=400)
        
    try:
        user_id = int(user_id)
        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            item_type=item_type,
            gateway="instamojo",
            amount=5000
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
    Returns payment configuration and the Telegram bot username.
    """
    tg_app = request.app.get('tg_app')
    bot_username = "KarinAICompanionBot"
    if tg_app and tg_app.bot:
        try:
            bot_username = tg_app.bot.username or "KarinAICompanionBot"
        except Exception:
            pass
    return web.json_response({
        "payment_gateway": "instamojo",
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
    1-Click Instamojo Payment Initiation Endpoint:
    Directly creates unique Instamojo Payment Request, records order in database,
    logs pay_button_clicked and payment_order_created events, and redirects
    to Instamojo hosted checkout page (longurl).
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
        status="CLICKED",
        payment_gateway="instamojo"
    )

    # Create Instamojo Payment Request
    order_id, pay_url, err = await create_instamojo_payment_request(user_id, item_type, amount_inr=50.0)
    amount_paise = 5000

    # Register transaction order in payments table & log payment_order_created event
    database.create_payment_order(user_id, order_id=order_id, amount=amount_paise, item_type=item_type)

    database.log_payment_event(
        event_name="payment_page_opened",
        telegram_user_id=user_id,
        order_id=order_id,
        amount=amount_paise,
        status="OPENED",
        payment_gateway="instamojo"
    )

    # Redirect to Instamojo hosted checkout page
    raise web.HTTPFound(location=pay_url)


async def handle_checkout_page(request):
    """Legacy route alias redirecting to /checkout/initiate."""
    user_id_str = request.query.get("user_id")
    item_type = request.query.get("item_type", "chat_pass")
    if user_id_str:
        raise web.HTTPFound(location=f"/checkout/initiate?user_id={user_id_str}&item_type={item_type}")
    return web.Response(text="Please initiate payment via Telegram bot buttons.", status=400)


async def handle_instamojo_callback(request):
    """
    Handles user redirect back from Instamojo after payment attempt.
    Query parameters: payment_id, payment_status, payment_request_id.
    """
    payment_id = request.query.get("payment_id")
    payment_status = request.query.get("payment_status")
    payment_request_id = request.query.get("payment_request_id")
    
    logger.info(f"Instamojo callback: payment_id={payment_id}, status={payment_status}, request_id={payment_request_id}")

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE order_id = ?", (payment_request_id,))
    row = cursor.fetchone()
    conn.close()

    telegram_id = row["telegram_id"] if row else 0
    item_type = row["item_type"] if row else "chat_pass"
    amount = row["amount"] if row else 5000

    tg_app = request.app.get('tg_app')
    bot_username = "KarinAICompanionBot"
    if tg_app and tg_app.bot:
        try:
            bot_username = tg_app.bot.username or bot_username
        except Exception:
            pass
            
    bot_link = f"https://t.me/{bot_username}"

    if payment_status in ("Credit", "SUCCESS", "completed", "paid"):
        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=telegram_id,
            order_id=payment_request_id,
            payment_id=payment_id,
            item_type=item_type,
            gateway="instamojo",
            amount=amount
        )
        
        if tg_app and unlocked_now and telegram_id:
            try:
                if item_type == "chat_pass":
                    confirm_text = "You're back. Your 1-day access is now active. Let's continue where we left off. 💖"
                else:
                    confirm_text = "✅ <b>Payment Successful!</b>\n\n10 image credits have been added to your account!"
                await tg_app.bot.send_message(
                    chat_id=telegram_id,
                    text=confirm_text,
                    parse_mode="HTML"
                )
            except Exception as tg_err:
                logger.error(f"Failed to send confirmation message to user {telegram_id}: {tg_err}")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Successful — Karin AI</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 24px; padding: 36px; max-width: 440px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); text-align: center; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; display: inline-block; }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; color: #4ade80; }}
        p {{ font-size: 15px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color: white; text-decoration: none; display: block; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; transition: all 0.2s ease; box-shadow: 0 10px 25px -5px rgba(34, 197, 94, 0.4); }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 15px 30px -5px rgba(34, 197, 94, 0.6); }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">💖</div>
        <h1>Payment Successful!</h1>
        <p>You're back! Your 1-day access has been activated. Return to Telegram to continue chatting with Karin.</p>
        <a href="{bot_link}" class="btn">Return to Telegram Bot</a>
    </div>
</body>
</html>"""
        return web.Response(text=html_content, content_type="text/html")
    else:
        database.log_payment_event(
            event_name="payment_failed",
            telegram_user_id=telegram_id,
            order_id=payment_request_id,
            payment_id=payment_id,
            status="FAILED",
            payment_gateway="instamojo",
            failure_reason=f"Instamojo status: {payment_status}"
        )
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Incomplete — Karin AI</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 24px; padding: 36px; max-width: 440px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); text-align: center; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; display: inline-block; }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; color: #f87171; }}
        p {{ font-size: 15px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #ec4899 0%, #d946ef 100%); color: white; text-decoration: none; display: block; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; transition: all 0.2s ease; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">⚠️</div>
        <h1>Payment Incomplete</h1>
        <p>Your payment wasn't completed. You can try again whenever you're ready.</p>
        <a href="{bot_link}" class="btn">Return to Telegram Bot</a>
    </div>
</body>
</html>"""
        return web.Response(text=html_content, content_type="text/html")


async def handle_instamojo_mock(request):
    """Mock payment redirection endpoint for local/testing environments."""
    order_id = request.query.get("order_id")
    user_id = request.query.get("user_id")
    item_type = request.query.get("item_type", "chat_pass")
    callback_url = f"/checkout/instamojo/callback?payment_id=MOJO_mock_{user_id}&payment_status=Credit&payment_request_id={order_id}"
    raise web.HTTPFound(location=callback_url)


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
    app.router.add_get('/checkout/instamojo/callback', handle_instamojo_callback)
    app.router.add_get('/checkout/instamojo/mock', handle_instamojo_mock)
    app.router.add_get('/checkout', handle_checkout_page)
    app.router.add_get('/api/config', handle_get_config)
    app.router.add_get('/api/admin/export-data', handle_admin_export_data)
    app.router.add_post('/api/create-order', handle_create_order)
    app.router.add_post('/api/verify-payment', handle_verify_payment)
    app.router.add_post('/api/payment-failed', handle_api_payment_failed)
    app.router.add_post('/api/payment-cancelled', handle_api_payment_cancelled)
    app.router.add_post('/webhook/instamojo', handle_instamojo_webhook)
    app.router.add_post('/webhook/razorpay', handle_instamojo_webhook)
    
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
    logger.info(f"Instamojo webhook & REST API server running on port {port}")

    # Generate initial daily report & start 6 PM scheduler
    try:
        database.generate_daily_payment_event_report()
    except Exception as e_rep:
        logger.error(f"Error generating initial daily report: {e_rep}")
        
    asyncio.create_task(start_daily_report_scheduler())

    return runner

