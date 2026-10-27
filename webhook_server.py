import re
import os
import time
import shutil
import logging
import json
import asyncio
import urllib.parse
from datetime import datetime, timedelta
import aiohttp
from aiohttp import web
import config
import database

logger = logging.getLogger(__name__)


def get_payment_confirmation_text(item_type: str, expiry_dt=None) -> str:
    """Builds a clear, informative confirmation message including expiry date and time in IST."""
    norm = (item_type or "").lower().strip()
    exp_str = ""
    if expiry_dt:
        if isinstance(expiry_dt, str):
            try:
                expiry_dt = datetime.fromisoformat(expiry_dt)
            except Exception:
                pass
        if isinstance(expiry_dt, datetime):
            ist_dt = expiry_dt + timedelta(hours=5, minutes=30)
            exp_str = f"\n\n📅 <b>Valid Until:</b> {ist_dt.strftime('%d %b %Y, %I:%M %p')} IST"

    if norm in ("chat_pass_1month", "1month", "month", "monthly", "chat_pass_month", "chat_pass_30days"):
        return f"🎉 <b>1-Month Unlimited Pass Activated!</b> 💎\n\nWelcome to 30 days of unlimited chats, deep memories, and roleplays with Juhi!{exp_str}\n\nLet's continue our conversation! 💖"
    elif norm in ("chat_pass_1week", "1week", "week", "weekly", "chat_pass_week"):
        return f"🎉 <b>1-Week Unlimited Pass Activated!</b> 🚀\n\nWelcome to 7 days of unlimited chats and intimate roleplays with Juhi!{exp_str}\n\nLet's continue where we left off! 💖"
    elif norm in ("image_credits", "10_images", "images", "photos"):
        return "✅ <b>Payment Successful!</b> 📸\n\n10 image generation credits have been added to your account! Type /draw to create photos of Juhi."
    else:
        return f"🎉 <b>1-Day Unlimited Pass Activated!</b> ⚡\n\nYour 24-hour access is active!{exp_str}\n\nLet's continue chatting! 💖"


async def create_instamojo_payment_request(user_id: int, item_type: str = "chat_pass", amount_inr: float = 49.0):
    """
    Calls Instamojo REST API to create a Payment Request.
    Returns tuple: (payment_request_id, longurl, error_message)
    """
    endpoint = config.INSTAMOJO_ENDPOINT.rstrip("/") + "/payment-requests/"
    api_key = (config.INSTAMOJO_API_KEY or "").strip()
    auth_token = (config.INSTAMOJO_AUTH_TOKEN or "").strip()
    base_url = (config.WEB_CHECKOUT_URL or "https://zetagirl.zetalink.cloud").rstrip("/")
    
    norm_type = (item_type or "").lower().strip()
    if norm_type in ("chat_pass_1month", "1month", "month", "monthly"):
        purpose = "Juhi AI 1-Month Chat Pass"
        amount_inr = 499.0
    elif norm_type in ("chat_pass_1week", "1week", "week", "weekly"):
        purpose = "Juhi AI 1-Week Chat Pass"
        amount_inr = 199.0
    elif norm_type in ("image_credits", "10_images"):
        purpose = "Juhi AI 10 Image Credits"
        amount_inr = 49.0
    else:
        purpose = "Juhi AI 1-Day Chat Pass"
        amount_inr = 49.0

    if not api_key or not auth_token or api_key == "YOUR_INSTAMOJO_API_KEY" or auth_token == "YOUR_INSTAMOJO_AUTH_TOKEN":
        import time
        mock_id = f"PR_mock_{user_id}_{int(time.time())}"
        mock_url = f"{base_url}/checkout/instamojo/mock_ui?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
        return mock_id, mock_url, "Missing live Instamojo credentials"

    headers = {
        "X-Api-Key": api_key,
        "X-Auth-Token": auth_token
    }
    
    redirect_url = f"{base_url}/checkout/instamojo/callback?user_id={user_id}"
    webhook_url = f"{base_url}/webhook/instamojo"
    
    data = {
        "purpose": purpose[:30],
        "amount": f"{amount_inr:.2f}",
        "buyer_name": f"User {user_id}",
        "email": f"user_{user_id}@juhi.ai",
        "redirect_url": redirect_url,
        "webhook": webhook_url,
        "allow_repeated_payments": "False",
        "send_email": "False",
        "send_sms": "False"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, headers=headers, data=data) as resp:
                resp_text = await resp.text()
                try:
                    resp_data = json.loads(resp_text)
                except Exception:
                    logger.error(f"Instamojo API non-JSON response ({resp.status}): {resp_text[:200]}")
                    return None, None, f"Instamojo API HTTP Error {resp.status}"

                if resp.status in (200, 201) and resp_data.get("success"):
                    pr = resp_data.get("payment_request", {})
                    longurl = pr.get("longurl")
                    if not longurl:
                        import time
                        mock_id = f"PR_mock_{user_id}_{int(time.time())}"
                        longurl = f"{base_url}/checkout/instamojo/mock_ui?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
                    return pr.get("id"), longurl, None
                else:
                    err_msg = resp_data.get("message") or resp_data.get("error") or str(resp_data)
                    logger.error(f"Instamojo API Error creating payment request: {err_msg}")
                    return None, None, f"Instamojo API Error: {err_msg}"
    except Exception as e:
        logger.error(f"HTTP exception during Instamojo API call: {e}")
        return None, None, str(e)


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
        
    try:
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
                    confirm_text = get_payment_confirmation_text(item_type, expiry)
                    await tg_app.bot.send_message(
                        chat_id=telegram_id,
                        text=confirm_text,
                        parse_mode="HTML"
                    )
                except Exception as tg_err:
                    logger.error(f"Failed to send webhook confirmation message to user {telegram_id}: {tg_err}")
    except Exception as e_wh:
        logger.error(f"Error executing Instamojo webhook unlock: {e_wh}")

    return web.Response(text="OK", status=200)

async def handle_razorpay_webhook(request):
    """
    Webhook handler for Razorpay server-to-server notifications.
    Processes 'payment.captured' and 'order.paid' events idempotently.
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Razorpay webhook payload: {e}")
        return web.Response(text="Invalid JSON", status=400)

    event = data.get("event")
    logger.info(f"Received Razorpay webhook event: {event}")

    payload = data.get("payload", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    order_entity = payload.get("order", {}).get("entity", {})

    payment_id = payment_entity.get("id")
    order_id = payment_entity.get("order_id") or order_entity.get("id")
    amount = payment_entity.get("amount") or order_entity.get("amount") or 5000
    currency = payment_entity.get("currency") or "INR"

    notes = payment_entity.get("notes") or order_entity.get("notes") or {}
    user_id_val = notes.get("user_id")
    item_type = notes.get("item_type") or notes.get("plan_type", "chat_pass")

    user_id = None
    if user_id_val:
        try:
            user_id = int(user_id_val)
        except ValueError:
            pass

    if not user_id and order_id:
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, item_type, amount FROM payments WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            user_id = row["telegram_id"]
            if row["item_type"]:
                item_type = row["item_type"]
            if row["amount"]:
                amount = row["amount"]

    if not user_id:
        logger.warning(f"Razorpay webhook: Could not identify user_id for order={order_id}, payment={payment_id}")
        return web.Response(text="OK", status=200)

    amt_val = float(amount or 0)
    if amt_val in (19900, 199, 199.0):
        item_type = "chat_pass_1week"
    elif amt_val in (49900, 499, 499.0):
        item_type = "chat_pass_1month"

    if event in ("payment.captured", "order.paid"):
        try:
            unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
                telegram_id=user_id,
                order_id=order_id,
                payment_id=payment_id,
                item_type=item_type,
                gateway="razorpay",
                amount=amount,
                currency=currency
            )
            logger.info(f"Razorpay webhook unlocked user={user_id}, plan={item_type}, expiry={expiry}")
        except Exception as e_unlock:
            logger.error(f"Error unlocking access from Razorpay webhook: {e_unlock}")

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

def _is_valid_cred(val: str) -> bool:
    if not val:
        return False
    val = val.strip()
    return bool(val and "xxxx" not in val.lower() and "YOUR_" not in val and len(val) >= 8)


async def handle_create_order(request):
    """
    Creates a Payment Order (Razorpay or Instamojo).
    Expects JSON payload with: amount, currency, user_id, item_type.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
    
    amount = data.get("amount")
    user_id = data.get("user_id")
    item_type = data.get("item_type") or data.get("plan_type", "chat_pass")
    gateway_type = data.get("gateway") or config.PAYMENT_GATEWAY
    
    if not user_id:
        return web.json_response({"error": "Missing user_id"}, status=400)
        
    try:
        user_id = int(user_id)
        if item_type in ("chat_pass_1week", "1week"):
            amount_inr = 199.0
        elif item_type in ("chat_pass_1month", "1month"):
            amount_inr = 499.0
        elif item_type in ("image_credits", "10_images"):
            amount_inr = 49.0
        elif item_type in ("chat_pass_1day", "1day", "chat_pass"):
            amount_inr = 49.0
        else:
            amount_inr = float(amount) / 100.0 if amount and float(amount) >= 100 else 49.0
        amount_paise = int(amount_inr * 100)
    except ValueError:
        return web.json_response({"error": "Invalid user_id or amount"}, status=400)

    # 1. Primary: Razorpay
    rzp_key_id = (config.RAZORPAY_KEY_ID or "").strip()
    rzp_key_secret = (config.RAZORPAY_KEY_SECRET or "").strip()
    
    if gateway_type == "razorpay" or _is_valid_cred(rzp_key_id):
        if not _is_valid_cred(rzp_key_id) or not _is_valid_cred(rzp_key_secret):
            return web.json_response({"error": "Razorpay API Keys are missing or invalid in .env configuration."}, status=400)
            
        try:
            import razorpay
            import time
            client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
            receipt_str = f"rcpt_{user_id}_{int(time.time())}"[:40]
            rzp_order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt_str,
                "payment_capture": 1,
                "notes": {
                    "user_id": str(user_id),
                    "item_type": item_type
                }
            })
            order_id = rzp_order["id"]
            database.create_payment_order(user_id, order_id=order_id, amount=amount_paise, item_type=item_type, payment_gateway="razorpay")
            database.log_payment_event(
                event_name="payment_order_created",
                telegram_user_id=user_id,
                order_id=order_id,
                amount=amount_paise,
                status="PENDING",
                payment_gateway="razorpay"
            )
            return web.json_response({
                "order_id": order_id,
                "amount": amount_paise,
                "currency": "INR",
                "key": rzp_key_id,
                "gateway": "razorpay"
            })
        except Exception as rzp_err:
            logger.error(f"Razorpay order creation error: {rzp_err}")
            return web.json_response({"error": f"Razorpay API Error: {str(rzp_err)}"}, status=400)

    # 2. Secondary: Instamojo
    order_id, pay_url, err = await create_instamojo_payment_request(user_id, item_type, amount_inr=amount_inr)
    
    if not pay_url:
        return web.json_response({"error": err or "Failed to create Instamojo payment request"}, status=400)
        
    database.create_payment_order(user_id, order_id=order_id, amount=amount_paise, item_type=item_type, payment_gateway="instamojo")
    
    return web.json_response({
        "order_id": order_id,
        "pay_url": pay_url,
        "amount": amount_paise,
        "currency": "INR",
        "gateway": "instamojo"
    })

async def handle_verify_payment(request):
    """
    Verifies Razorpay or Instamojo payment and updates the SQLite database idempotently.
    Expects JSON payload with: razorpay_signature (or payment_request_id/order_id), payment_id, user_id.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)
        
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")
    
    order_id = razorpay_order_id or data.get("payment_request_id") or data.get("order_id")
    payment_id = razorpay_payment_id or data.get("payment_id") or f"verify_{order_id}"
    user_id = data.get("user_id")
    item_type = data.get("item_type") or data.get("plan_type", "chat_pass")
    
    if not order_id or not user_id:
        return web.json_response({"error": "Missing required fields"}, status=400)
        
    try:
        user_id = int(user_id)
        gateway_used = "razorpay" if razorpay_signature else "instamojo"
        
        if razorpay_signature and config.RAZORPAY_KEY_SECRET:
            try:
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                client.utility.verify_payment_signature({
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature
                })
            except Exception as sig_err:
                logger.error(f"Razorpay signature verification failed: {sig_err}")
                return web.json_response({"error": "Payment signature verification failed"}, status=400)

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT item_type, amount FROM payments WHERE order_id = ? OR payment_id = ?", (order_id, payment_id))
        p_row = cursor.fetchone()
        conn.close()
        
        actual_item_type = item_type
        actual_amount = 5000
        if p_row:
            if p_row["amount"]:
                actual_amount = p_row["amount"]
            if p_row["item_type"]:
                if actual_item_type in (None, "", "chat_pass", "chat_pass_1day") or p_row["item_type"] in ("chat_pass_1week", "chat_pass_1month", "image_credits"):
                    actual_item_type = p_row["item_type"]

        # Fetch authoritative details directly from Razorpay if available
        if razorpay_payment_id and config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET:
            try:
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                rzp_pay_data = client.payment.fetch(razorpay_payment_id)
                if rzp_pay_data:
                    rzp_amt = rzp_pay_data.get("amount")
                    if rzp_amt:
                        actual_amount = int(rzp_amt)
                    rzp_notes = rzp_pay_data.get("notes") or {}
                    rzp_item = rzp_notes.get("item_type") or rzp_notes.get("plan_type")
                    if rzp_item:
                        actual_item_type = rzp_item
            except Exception as fetch_err:
                logger.warning(f"Could not fetch payment from Razorpay: {fetch_err}")

        # Enforce plan based on verified amount
        if actual_amount in (19900, 199, 199.0):
            actual_item_type = "chat_pass_1week"
        elif actual_amount in (49900, 499, 499.0):
            actual_item_type = "chat_pass_1month"

        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            item_type=actual_item_type,
            gateway=gateway_used,
            amount=actual_amount
        )
        
        tg_app = request.app.get('tg_app')
        if tg_app and unlocked_now:
            try:
                confirm_text = get_payment_confirmation_text(actual_item_type, expiry)
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


async def handle_api_analytics_event(request):
    """API endpoint to record client-side user behavior events from Android app (single or batch)."""
    try:
        data = await request.json()
        # Support batch payload if "events" list is supplied
        if "events" in data and isinstance(data["events"], list):
            success = database.log_user_analytics_events_batch(data["events"])
            return web.json_response({"success": bool(success), "count": len(data["events"])})

        user_id = data.get("user_id")
        event_name = data.get("event_name")
        event_category = data.get("event_category", "engagement")
        platform = data.get("platform", "android_app")
        metadata = data.get("metadata") or {}
        
        if not user_id or not event_name:
            return web.json_response({"success": False, "error": "Missing user_id or event_name"}, status=400)
            
        success = database.log_user_analytics_event(
            user_id=int(user_id),
            event_name=str(event_name),
            event_category=str(event_category),
            platform=str(platform),
            metadata=metadata
        )
        return web.json_response({"success": bool(success)})
    except Exception as e:
        logger.error(f"Error in handle_api_analytics_event: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_analytics_batch(request):
    """Dedicated API endpoint to record batch of events efficiently."""
    try:
        data = await request.json()
        events = data.get("events") if isinstance(data, dict) else (data if isinstance(data, list) else None)
        if not events or not isinstance(events, list):
            return web.json_response({"success": False, "error": "Expected a list of events"}, status=400)
            
        success = database.log_user_analytics_events_batch(events)
        return web.json_response({"success": bool(success), "received": len(events)})
    except Exception as e:
        logger.error(f"Error in handle_api_analytics_batch: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_analytics_overview(request):
    """API endpoint returning overview metrics and paywall conversion funnel."""
    try:
        overview = database.get_user_behavior_analytics_overview()
        return web.json_response({"success": True, "data": overview})
    except Exception as e:
        logger.error(f"Error in handle_admin_analytics_overview: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_analytics_users(request):
    """API endpoint returning list of users with behavior stats."""
    try:
        limit = int(request.query.get("limit", 100))
        offset = int(request.query.get("offset", 0))
        users = database.get_user_behavior_list(limit=limit, offset=offset)
        return web.json_response({"success": True, "users": users, "count": len(users)})
    except Exception as e:
        logger.error(f"Error in handle_admin_analytics_users: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_analytics_user_journey(request):
    """API endpoint returning complete journey, messages, replies, and events for a user."""
    try:
        user_id_str = request.match_info.get("user_id") or request.query.get("user_id")
        if not user_id_str:
            return web.json_response({"error": "Missing user_id"}, status=400)
        journey = database.get_user_full_journey(int(user_id_str))
        return web.json_response({"success": True, "journey": journey})
    except Exception as e:
        logger.error(f"Error in handle_admin_analytics_user_journey: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_analytics_live_feed(request):
    """API endpoint returning live stream of events with pagination, category filter, and search."""
    try:
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        user_id = request.query.get("user_id")
        event_name = request.query.get("event_name")
        event_category = request.query.get("event_category")
        search = request.query.get("search")
        
        feed = database.get_live_analytics_events(
            limit=limit,
            offset=offset,
            user_id=int(user_id) if user_id else None,
            event_name=event_name,
            event_category=event_category,
            search=search
        )
        return web.json_response({"success": True, "data": feed})
    except Exception as e:
        logger.error(f"Error in handle_admin_analytics_live_feed: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_admin_export_users_csv(request):
    """Downloads CSV report of all user behaviors and message stats."""
    try:
        filepath, count = database.export_user_behavior_csv()
        import os
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return web.Response(
                text=content,
                content_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"'}
            )
        return web.json_response({"error": "File not found"}, status=404)
    except Exception as e:
        logger.error(f"Error exporting user behavior data: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_admin_export_events_csv(request):
    """Downloads CSV report of all raw user behavior events."""
    try:
        filepath, count = database.export_user_analytics_events_csv()
        import os
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return web.Response(
                text=content,
                content_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"'}
            )
        return web.json_response({"error": "File not found"}, status=404)
    except Exception as e:
        logger.error(f"Error exporting events data: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_admin_analytics_dashboard(request):
    """Serves the rich user behavior tracking dashboard webpage."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, 'analytics.html')
        if os.path.exists(html_path):
            return web.FileResponse(html_path)
        return web.Response(text="<h1>Analytics dashboard template (analytics.html) not found.</h1>", status=404, content_type="text/html")
    except Exception as e:
        logger.error(f"Error serving analytics dashboard: {e}")
        return web.Response(text=f"<h1>Error loading analytics: {e}</h1>", status=500, content_type="text/html")



async def handle_get_config(request):
    """
    Returns payment configuration and the Telegram bot username.
    """
    tg_app = request.app.get('tg_app')
    bot_username = "JuhiAICompanionBot"
    if tg_app and tg_app.bot:
        try:
            bot_username = tg_app.bot.username or "JuhiAICompanionBot"
        except Exception:
            pass
    return web.json_response({
        "payment_gateway": config.PAYMENT_GATEWAY,
        "razorpay_key_id": config.RAZORPAY_KEY_ID,
        "bot_username": bot_username,
        "free_message_limit": config.FREE_MESSAGE_LIMIT
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
            
        persona_key = settings["active_persona"] if settings else "juhi"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["juhi"])
        xp = settings["relationship_xp"] if settings else 0
        status = config.get_relationship_status(xp)
        
        u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
        ai_nick = settings["ai_nickname"] if (settings and settings.get("ai_nickname")) else persona["name"]
        
        chat_mode = database.get_chat_mode(user_id)
        memories = database.get_user_memories(user_id)
        
        sub_info = database.get_subscription_info(user_id)
        
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
            "is_subscribed": sub_info["is_subscribed"],
            "remaining_free_messages": sub_info["free_messages_remaining"],
            "image_credits": sub_info["image_credits"],
            "chat_expires_at": sub_info["chat_expires_at"],
            "expires_at_ist": sub_info["expires_at_ist"],
            "expiry_date_str": sub_info["expiry_date_str"],
            "expiry_time_str": sub_info["expiry_time_str"],
            "subscription_remaining_text": sub_info["remaining_text"],
            "subscription_plan": sub_info["plan_name"]
        })
    except Exception as e:
        logger.error(f"Error in handle_api_profile: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_set_relationship_level(request):
    """API endpoint to manually select the relationship level (1 to 6) from mobile app or web."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        level = data.get("level")
        if not user_id or level is None:
            return web.json_response({"error": "Missing user_id or level"}, status=400)
            
        user_id = int(user_id)
        level = int(level)
        if level < 1 or level > 6:
            return web.json_response({"error": "Level must be between 1 and 6"}, status=400)
            
        database.setup_user(user_id, "app_user", "User")
        _, new_lvl, title, new_xp = database.set_relationship_level(user_id, level)
        level_info = config.RELATIONSHIP_LEVELS[new_lvl]
        status = config.get_relationship_status(new_xp)
        return web.json_response({
            "success": True,
            "user_id": user_id,
            "level": new_lvl,
            "title": title,
            "xp": new_xp,
            "percent": status["percent"],
            "guideline": level_info["guideline"]
        })
    except Exception as e:
        logger.error(f"Error in handle_api_set_relationship_level: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_api_history(request):
    """API endpoint to fetch chat history for the mobile app."""
    user_id_str = request.query.get("user_id")
    if not user_id_str:
        return web.json_response({"error": "Missing user_id parameter"}, status=400)
        
    try:
        user_id = int(user_id_str)
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"] if settings else "juhi"
        history = database.get_chat_history(user_id, persona_key)
        
        # Clean up history for app UI
        cleaned_history = []
        for msg in history:
            content = msg.get("content") or ""
            img_match = re.search(r'\[IMAGE:\s*(.*?)(?:\]|$)', content)
            has_img = False
            img_url = None
            if img_match:
                has_img = True
                img_url = img_match.group(1).strip()
                content = content.replace(img_match.group(0), "").strip()

            gif_match = re.search(r'\[GIF:\s*(.*?)(?:\]|$)', content)
            has_gif = False
            gif_name = None
            if gif_match:
                has_gif = True
                gif_name = gif_match.group(1).strip()
                content = content.replace(gif_match.group(0), "").strip()

            cleaned_history.append({
                "role": msg["role"],
                "content": content,
                "has_image": has_img,
                "image_url": img_url,
                "has_gif": has_gif,
                "gif_name": gif_name,
                "timestamp": msg.get("timestamp", "")
            })
            
        return web.json_response({"success": True, "history": cleaned_history})
    except Exception as e:
        logger.error(f"Error in handle_api_history: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_clear_history(request):
    """API endpoint to clear chat history for the mobile app without deleting memories."""
    try:
        user_id = None
        persona_key = None
        if request.method == "POST":
            data = await request.json()
            user_id = data.get("user_id")
            persona_key = data.get("persona_key")
        elif request.method in ("DELETE", "GET"):
            user_id = request.query.get("user_id")
            persona_key = request.query.get("persona_key")
            
        if not user_id:
            return web.json_response({"success": False, "error": "Missing user_id parameter"}, status=400)
            
        user_id = int(user_id)
        # Clear chat history only - user_memories is completely preserved
        # If persona_key is None, clear all companion chat history for this user
        database.clear_chat_history(user_id, persona_key=persona_key)
        
        # Log analytics event
        try:
            database.log_user_analytics_event(user_id, "chat_history_cleared", "chat", "android_app", {
                "persona_key": persona_key
            })
        except Exception:
            pass
            
        logger.info(f"[REST API] Chat history cleared for user {user_id} (persona: {persona_key}). Memory vault intact.")
        return web.json_response({
            "success": True, 
            "message": "Chat history cleared successfully. Memory vault preserved."
        })
    except Exception as e:
        logger.error(f"Error in handle_api_clear_history: {e}")
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
            database.log_user_analytics_event(user_id, "paywall_hit", "monetization", "android_app", {"free_messages_used": free_used, "limit": config.FREE_MESSAGE_LIMIT})
            settings = database.get_user_settings(user_id)
            u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
            paywall_text = (
                f"🥺 Aww {u_nick}... Our {config.FREE_MESSAGE_LIMIT} free trial messages just ran out for today!\n\n"
                f"I was having so much fun chatting with you and getting close... I really don't want us to stop here! 💖\n\n"
                f"Unlock 24 Hours of Unlimited Chat with me right now for just ₹49 so we can keep talking all day & night!"
            )
            return web.json_response({
                "success": False,
                "is_paywall": True,
                "reply": paywall_text,
                "remaining_free": 0
            })

        # Log incoming user message analytics event
        database.log_user_analytics_event(user_id, "message_sent", "chat", "android_app", {
            "text_length": len(text),
            "free_messages_used": free_used
        })

        # Memory extraction & setting lookup
        ai_engine.extract_and_save_user_memories(user_id, text)
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"] if settings else "juhi"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["juhi"])
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
            memories=memories,
            user_id=user_id
        )
        
        import os, time, shutil, safety_engine

        image_match = re.search(r'\[(?:GENERATE_IMAGE|IMAGE):\s*(.*?)(?:\]|$)', reply, re.IGNORECASE | re.DOTALL)
        cleaned_reply = reply
        has_image = False
        image_prompt = ""
        image_url = None
        
        user_wants_photo = any(
            phrase in text.lower()
            for phrase in ("selfie", "photo", "picture", "pic", "pics", "show yourself", "what you look like")
        ) and any(
            act in text.lower()
            for act in ("send", "show", "give", "share", "take", "click", "see", "your", "ur", "a", "can i", "plz", "please")
        )
        
        if image_match or user_wants_photo:
            has_image = True
            image_prompt = image_match.group(1).strip() if image_match else "Juhi casual selfie smiling warmly"
            if image_match:
                cleaned_reply = reply.replace(image_match.group(0), "").strip()

            character_appearance = persona.get(
                "appearance",
                "Juhi, a young Indian software developer living in Bangalore, stylish top, smiling warmly, casual apartment background"
            )
            safe_prompt = safety_engine.build_safe_image_prompt(image_prompt, character_appearance)
            
            # Check image credits
            has_credit = database.use_image_credit(user_id)
            if not has_credit and not is_subscribed:
                has_image = False
                cleaned_reply += f"\n\n📸 Aww {u_nick}, you're out of selfie photo credits! 💕 Unlock 10 more in the Store so I can keep sending you photos!"
            else:
                try:
                    seed = user_id + int(time.time())
                    temp_img_path = await ai_engine.generate_image(safe_prompt, seed=seed)
                    gen_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "generated")
                    os.makedirs(gen_dir, exist_ok=True)
                    filename = f"selfie_{user_id}_{int(time.time())}.png"
                    dest_path = os.path.join(gen_dir, filename)
                    shutil.copyfile(temp_img_path, dest_path)
                    image_url = f"/assets/generated/{filename}"
                    logger.info(f"[IMAGE GEN] Generated selfie for user {user_id} saved to {dest_path}")
                except Exception as img_err:
                    logger.error(f"Failed generating selfie image for user {user_id}: {img_err}")
                    has_image = False
            
        text_lower = text.lower()
        conversational_gif_query = None
        if any(w in text_lower for w in ["love you", "i love you", "adore you", "my girl", "marry me"]):
            conversational_gif_query = "romantic love hearts"
        elif any(w in text_lower for w in [
            "other girl", "another girl", "cute girl", "pretty girl", "crush on me", "crushes on me",
            "she likes me", "likes me", "talking to a girl", "talked to a girl", "asked me out"
        ]):
            conversational_gif_query = "jealous pout"
        elif any(w in text_lower for w in ["promoted", "passed exam", "got the job", "won"]):
            conversational_gif_query = "celebrate"

        user_wants_gif = (
            any(phrase in text_lower for phrase in ("gif", "reaction gif", "send a gif", "send gif"))
            or any(phrase in text_lower for phrase in ("kiss", "mwah", "blush", "lip lock", "cuddle"))
            or bool(conversational_gif_query)
        )

        gif_match = re.search(r'\[(?:SEND_GIF|GIF):\s*(.*?)(?:\]|$)', cleaned_reply, re.IGNORECASE)
        has_gif = False
        gif_name = None
        gif_url = None
        
        if gif_match or user_wants_gif:
            has_gif = True
            if gif_match:
                query = gif_match.group(1).strip()
                cleaned_reply = cleaned_reply.replace(gif_match.group(0), "").strip()
            elif conversational_gif_query:
                query = conversational_gif_query
            else:
                query = text

            # First priority: Try dynamic GIPHY API search & local cache
            try:
                import giphy_service
                giphy_res = giphy_service.search_and_fetch_gif(query, user_id=user_id)
                if giphy_res:
                    gif_name = giphy_res.get("gif_name")
                    gif_url = giphy_res.get("gif_url")
            except Exception as g_err:
                logger.warning(f"GIPHY search failed: {g_err}")

            # Second priority fallback: Curated local GIFs
            if not gif_name:
                from bot import choose_gif
                gif_name = choose_gif(query, user_id, persona_key)

            if not gif_name:
                has_gif = False
            else:
                gif_name = gif_name.lower().strip()
                
        if not is_subscribed:
            database.increment_free_messages(user_id)
            new_free_used = free_used + 1
            remaining = max(0, config.FREE_MESSAGE_LIMIT - new_free_used)
            if remaining > 0 and remaining <= 5:
                cleaned_reply += f"\n\n(⌛ {remaining} free trial message{'s' if remaining > 1 else ''} remaining today)"
        else:
            remaining = 999
            
        # Log to DB (include image/gif tags so history displays media upon re-opening)
        msg_to_save = cleaned_reply
        if has_image and image_url:
            msg_to_save = f"{msg_to_save}\n[IMAGE: {image_url}]"
        if has_gif and gif_name:
            msg_to_save = f"{msg_to_save}\n[GIF: {gif_name}]"

        database.add_chat_message(user_id, persona_key, "user", text)
        database.add_chat_message(user_id, persona_key, "assistant", msg_to_save)
        
        # Log AI reply analytics event
        database.log_user_analytics_event(user_id, "ai_reply_sent", "chat", "android_app", {
            "reply_length": len(cleaned_reply),
            "has_image": has_image,
            "has_gif": has_gif,
            "remaining_free": remaining
        })
        
        # Add XP
        leveled_up, new_level, new_title = database.add_xp(user_id, amount=10)
        
        return web.json_response({
            "success": True,
            "reply": cleaned_reply,
            "has_image": has_image,
            "image_prompt": image_prompt,
            "image_url": image_url,
            "has_gif": has_gif,
            "gif_name": gif_name,
            "gif_url": gif_url,
            "remaining_free": remaining,
            "leveled_up": leveled_up,
            "new_level": new_level,
            "new_title": new_title
        })
    except Exception as e:
        logger.error(f"Error in handle_api_chat: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_voice_call_turn(request):
    """
    Handles a full conversational voice call turn:
    1. Receives recorded user speech (multipart form or base64 JSON).
    2. Transcribes speech using Sarvam Saaras v4.
    3. Generates context-aware emotional response via Juhi AI companion engine.
    4. Synthesizes voice audio using Sarvam Bulbul v4.
    5. Returns user transcript, AI text reply, and base64 audio.
    """
    try:
        import voice_service
        user_id = None
        audio_bytes = None

        filename = "voice_input.wav"
        content_type = "audio/wav"

        if request.content_type.startswith("multipart/"):
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name == "user_id":
                    user_id = int((await part.text()).strip())
                elif part.name in ("audio", "file"):
                    if part.filename:
                        filename = part.filename
                    if part.headers.get("Content-Type"):
                        content_type = part.headers.get("Content-Type")
                    audio_bytes = await part.read()
        else:
            data = await request.json()
            user_id = data.get("user_id")
            if user_id:
                user_id = int(user_id)
            audio_b64 = data.get("audio_base64") or data.get("audio")
            if audio_b64:
                import base64
                audio_bytes = base64.b64decode(audio_b64)

        if not user_id or not audio_bytes:
            return web.json_response({
                "success": False,
                "error": "Missing user_id or audio content"
            }, status=400)

        # Check paywall
        is_subscribed = database.is_chat_subscribed(user_id)
        billing = database.get_user_billing(user_id)
        free_used = billing.get("free_messages_used", 0) if billing else 0
        
        if not is_subscribed and free_used >= config.FREE_MESSAGE_LIMIT:
            paywall_text = "Aww sweetie, our daily free minutes just ran out! Unlock unlimited calls with me in the VIP lounge so we can keep talking."
            audio_b64, audio_fmt = await voice_service.text_to_speech(paywall_text)
            return web.json_response({
                "success": False,
                "is_paywall": True,
                "user_transcript": "",
                "ai_reply": paywall_text,
                "audio_base64": audio_b64,
                "audio_format": audio_fmt,
                "remaining_free": 0
            })

        result = await voice_service.process_voice_call_turn(
            user_id=user_id,
            audio_bytes=audio_bytes,
            filename=filename,
            mime_type=content_type,
            platform="android_app"
        )
        return web.json_response(result)
    except Exception as e:
        logger.error(f"Error in handle_api_voice_call_turn: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_voice_stt(request):
    """Standalone STT endpoint using Sarvam Saaras v4."""
    try:
        import voice_service
        audio_bytes = None
        if request.content_type.startswith("multipart/"):
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name in ("audio", "file"):
                    audio_bytes = await part.read()
        else:
            data = await request.json()
            audio_b64 = data.get("audio_base64") or data.get("audio")
            if audio_b64:
                import base64
                audio_bytes = base64.b64decode(audio_b64)

        if not audio_bytes:
            return web.json_response({"success": False, "error": "Missing audio"}, status=400)

        transcript = await voice_service.speech_to_text(audio_bytes)
        return web.json_response({"success": True, "transcript": transcript})
    except Exception as e:
        logger.error(f"Error in handle_api_voice_stt: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_voice_tts(request):
    """Standalone TTS endpoint using Sarvam Bulbul v4."""
    try:
        import voice_service
        data = await request.json()
        text = data.get("text", "").strip()
        speaker = data.get("speaker")
        target_lang = data.get("language_code", "en-IN")

        if not text:
            return web.json_response({"success": False, "error": "Missing text"}, status=400)

        audio_b64, audio_fmt = await voice_service.text_to_speech(
            text=text,
            target_language_code=target_lang,
            speaker=speaker
        )
        return web.json_response({
            "success": True,
            "audio_base64": audio_b64,
            "audio_format": audio_fmt
        })
    except Exception as e:
        logger.error(f"Error in handle_api_voice_tts: {e}")
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
    """API endpoint to fetch, backfill, or clear memories."""
    if request.method == "GET":
        user_id_str = request.query.get("user_id")
        if not user_id_str:
            return web.json_response({"error": "Missing user_id parameter"}, status=400)
        user_id = int(user_id_str)
        memories = database.get_user_memories(user_id)
        if not memories:
            # Auto-backfill if user has past chat history
            await ai_engine.backfill_user_memories_from_history(user_id)
            memories = database.get_user_memories(user_id)
        return web.json_response({"success": True, "memories": memories})
    elif request.method == "POST":
        data = await request.json()
        user_id = data.get("user_id")
        action = data.get("action")
        if action == "clear" and user_id:
            database.clear_user_memories(int(user_id))
            return web.json_response({"success": True, "message": "Memories cleared"})
        elif action == "backfill" and user_id:
            count = await ai_engine.backfill_user_memories_from_history(int(user_id))
            memories = database.get_user_memories(int(user_id))
            return web.json_response({"success": True, "memories": memories, "extracted": count})
        return web.json_response({"success": False, "error": "Invalid action or user_id"}, status=400)


async def handle_api_device_token(request):
    """API endpoint to save mobile push notification device token."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        device_token = data.get("device_token")
        enabled = data.get("enabled", True)
        device_type = data.get("device_type", "android")
        
        if not user_id or not device_token:
            return web.json_response({"success": False, "error": "Missing user_id or device_token"}, status=400)
            
        database.save_device_token(int(user_id), device_token, device_type=device_type, notifications_enabled=1 if enabled else 0)
        return web.json_response({"success": True, "message": "Device token registered"})
    except Exception as e:
        logger.error(f"Error in handle_api_device_token: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_test_notification(request):
    """API endpoint to trigger a sample proactive message for the user."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id:
            return web.json_response({"success": False, "error": "Missing user_id"}, status=400)
            
        settings = database.get_user_settings(int(user_id))
        user_nickname = (settings.get("user_nickname") if settings else None) or "Sweetheart"
        ai_nickname = (settings.get("ai_nickname") if settings else None) or "Juhi"
        
        message = f"Hey {user_nickname}! Just thinking of you while taking a coffee break... how has your day been so far? 💕"
        return web.json_response({
            "success": True,
            "title": f"{ai_nickname} 💕",
            "message": message
        })
    except Exception as e:
        logger.error(f"Error in handle_api_test_notification: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_api_proactive_check(request):
    """
    API endpoint for mobile app to check or trigger proactive companion messages.
    Supports GET /api/proactive/check?user_id=...&force=... and POST /api/proactive/check.
    If a proactive message is decided, it is automatically saved to chat_history so it
    appears directly in the user's conversation.
    """
    try:
        user_id = None
        force = False
        if request.method == "POST":
            try:
                data = await request.json()
                user_id = data.get("user_id")
                force = bool(data.get("force", False))
            except Exception:
                pass
        if not user_id:
            user_id = request.query.get("user_id")
            force = request.query.get("force", "false").lower() in ("true", "1", "yes")

        if not user_id:
            return web.json_response({"success": False, "error": "Missing user_id"}, status=400)

        user_id = int(user_id)
        from proactive_engine import evaluate_proactive_for_user

        eval_res = await evaluate_proactive_for_user(user_id, force=force)
        decision = str(eval_res.get("decision", "DONT_SEND")).upper()
        reason = eval_res.get("reason", "")
        message = eval_res.get("message")

        settings = database.get_user_settings(user_id)
        p_key = (settings.get("active_persona", "juhi") if settings else "juhi")
        persona = config.PERSONAS.get(p_key, config.PERSONAS["juhi"])
        ai_nickname = (settings.get("ai_nickname") if settings else None) or persona.get("name", "Juhi")

        if decision == "SEND" and message:
            # Save directly to user chat history
            database.add_chat_message(user_id, p_key, "assistant", message)
            database.log_proactive_decision(user_id, "SEND", reason, message)
            database.add_xp(user_id, amount=5)

            logger.info(f"[API PROACTIVE] Triggered and delivered for user {user_id}: '{message}' (Reason: {reason})")
            return web.json_response({
                "success": True,
                "has_proactive": True,
                "title": f"{ai_nickname} 💕",
                "message": message,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
        else:
            database.log_proactive_decision(user_id, "DONT_SEND", reason, None)
            return web.json_response({
                "success": True,
                "has_proactive": False,
                "reason": reason
            })
    except Exception as e:
        logger.error(f"Error in handle_api_proactive_check: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


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

    try:
        # Log pay_button_clicked event
        database.log_payment_event(
            event_name="pay_button_clicked",
            telegram_user_id=user_id,
            status="CLICKED",
            payment_gateway="instamojo"
        )

        norm_type = (item_type or "").lower().strip()
        if norm_type in ("chat_pass_1month", "1month", "month", "monthly"):
            amount_inr = 499.0
        elif norm_type in ("chat_pass_1week", "1week", "week", "weekly"):
            amount_inr = 199.0
        else:
            amount_inr = 49.0
        amount_paise = int(amount_inr * 100)

        # Create Instamojo Payment Request
        order_id, pay_url, err = await create_instamojo_payment_request(user_id, item_type, amount_inr=amount_inr)

        # Register transaction order in payments table & log payment_order_created event
        database.create_payment_order(user_id, order_id=order_id, amount=amount_paise, item_type=item_type, payment_gateway="instamojo")

        database.log_payment_event(
            event_name="payment_page_opened",
            telegram_user_id=user_id,
            order_id=order_id,
            amount=amount_paise,
            status="OPENED",
            payment_gateway="instamojo"
        )

        if not pay_url:
            base_url = (config.WEB_CHECKOUT_URL or "http://zetagirl.zetalink.cloud:8080").rstrip("/")
            pay_url = f"{base_url}/checkout/instamojo/mock?order_id={order_id}&user_id={user_id}&item_type={item_type}"

        # Redirect to Instamojo hosted checkout page
        raise web.HTTPFound(location=pay_url)
    except web.HTTPFound:
        raise
    except Exception as e:
        logger.exception(f"Error initiating payment in /checkout/initiate: {e}")
        return web.Response(text=f"Payment Initiation Error: {str(e)}", status=500)


async def handle_checkout_page(request):
    """
    Renders the native Telegram WebApp Checkout Page.
    Receives user_id & item_type via query params or Telegram WebApp initData.
    Auto-initiates payment or displays a sleek checkout card with Instamojo gateway redirect.
    """
    user_id_str = request.query.get("user_id", "")
    item_type = request.query.get("item_type", "chat_pass")
    
    ITEM_CONFIGS = {
        "chat_pass": {"title": "1-Day Unlimited Chat Pass", "desc": "Unlimited instant messages & roleplays with Juhi for 24 hours.", "price": 49},
        "chat_pass_1day": {"title": "1-Day Unlimited Chat Pass", "desc": "Unlimited instant messages & roleplays with Juhi for 24 hours.", "price": 49},
        "chat_pass_1week": {"title": "1-Week Unlimited Chat Pass", "desc": "Unlimited instant messages & roleplays with Juhi for 7 days.", "price": 199},
        "chat_pass_1month": {"title": "1-Month Unlimited Chat Pass", "desc": "Unlimited instant messages & roleplays with Juhi for 30 days.", "price": 499},
        "image_credits": {"title": "10 Image Generation Credits", "desc": "Generate 10 custom photos of Juhi.", "price": 49},
        "10_images": {"title": "10 Image Generation Credits", "desc": "Generate 10 custom photos of Juhi.", "price": 49},
    }
    cfg = ITEM_CONFIGS.get(item_type, ITEM_CONFIGS["chat_pass"])
    title = cfg["title"]
    desc = cfg["desc"]
    price_inr = cfg["price"]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Juhi AI Checkout</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; }}
        body {{ background: linear-gradient(135deg, #0a0712 0%, #150d22 50%, #06040a 100%); color: #f3f4f6; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; }}
        .checkout-card {{ background: rgba(255, 255, 255, 0.04); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 28px 24px; width: 100%; max-width: 400px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6); text-align: center; position: relative; overflow: hidden; }}
        .checkout-card::before {{ content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(255, 74, 118, 0.12) 0%, transparent 60%); pointer-events: none; }}
        .avatar-wrap {{ width: 80px; height: 80px; margin: 0 auto 16px auto; border-radius: 50%; border: 2px solid #ff4a76; padding: 3px; background: rgba(255, 74, 118, 0.1); box-shadow: 0 0 20px rgba(255, 74, 118, 0.4); }}
        .avatar-wrap img {{ width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }}
        .title {{ font-size: 20px; font-weight: 700; color: #ffffff; margin-bottom: 6px; }}
        .subtitle {{ font-size: 13px; color: #9ca3af; margin-bottom: 20px; line-height: 1.4; }}
        .price-badge {{ background: rgba(255, 74, 118, 0.15); border: 1px solid rgba(255, 74, 118, 0.3); border-radius: 16px; padding: 14px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
        .price-label {{ font-size: 14px; color: #d1d5db; font-weight: 500; }}
        .price-val {{ font-size: 24px; font-weight: 800; color: #ff4a76; }}
        .pay-btn {{ width: 100%; background: linear-gradient(135deg, #ff4a76 0%, #e03b62 100%); color: white; border: none; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 8px 25px rgba(255, 74, 118, 0.4); display: flex; align-items: center; justify-content: center; gap: 8px; }}
        .pay-btn:active {{ transform: scale(0.98); opacity: 0.9; }}
        .pay-btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
        .spinner {{ display: none; width: 20px; height: 20px; border: 3px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 0.8s linear infinite; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .secure-note {{ font-size: 12px; color: #6b7280; margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 6px; }}
        .error-box {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; font-size: 13px; padding: 10px; border-radius: 10px; margin-bottom: 16px; display: none; text-align: left; }}
    </style>
</head>
<body>
    <div class="checkout-card">
        <div class="avatar-wrap">
            <img src="/assets/juhi.png" onerror="this.src='https://raw.githubusercontent.com/telegramdesktop/tdesktop/dev/Telegram/Resources/art/bg.png'" alt="Juhi">
        </div>
        <h1 class="title">{title}</h1>
        <p class="subtitle">{desc}</p>
        
        <div class="price-badge">
            <span class="price-label">Total Amount</span>
            <span class="price-val">₹{price_inr}</span>
        </div>

        <div id="error-box" class="error-box"></div>

        <button id="pay-btn" onclick="startPayment()" class="pay-btn">
            <div id="spinner" class="spinner"></div>
            <span id="btn-text">Pay ₹{price_inr} with Razorpay</span>
        </button>

        <a id="sandbox-btn" style="display:none; width: 100%; background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.4); color: #fde047; padding: 14px; border-radius: 14px; font-size: 14px; font-weight: 600; text-decoration: none; margin-top: 12px; box-sizing: border-box;" href="#">🧪 Test in Sandbox Mode</a>

        <div class="secure-note">
            🔒 256-bit Encrypted SSL Gateway (UPI / Cards / NetBanking)
        </div>
    </div>

    <script>
        let tgUserId = "{user_id_str}";
        let itemType = "{item_type}";
        let priceInr = {price_inr};

        // Initialize Telegram WebApp API
        if (window.Telegram && window.Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
            if (!tgUserId && Telegram.WebApp.initDataUnsafe && Telegram.WebApp.initDataUnsafe.user) {{
                tgUserId = Telegram.WebApp.initDataUnsafe.user.id;
            }}
        }}

        async function startPayment() {{
            const errBox = document.getElementById('error-box');
            const sandboxBtn = document.getElementById('sandbox-btn');
            const payBtn = document.getElementById('pay-btn');
            const spinner = document.getElementById('spinner');
            const btnText = document.getElementById('btn-text');

            errBox.style.display = 'none';
            sandboxBtn.style.display = 'none';

            if (!tgUserId) {{
                errBox.innerText = "Telegram User ID missing. Please open checkout from Telegram bot.";
                errBox.style.display = 'block';
                return;
            }}

            payBtn.disabled = true;
            spinner.style.display = 'block';
            btnText.innerText = 'Connecting to Gateway...';

            try {{
                const res = await fetch('/api/create-order', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        amount: priceInr * 100,
                        currency: 'INR',
                        user_id: tgUserId,
                        item_type: itemType
                    }})
                }});
                
                const data = await res.json();
                
                if (data.gateway === 'razorpay' && data.key) {{
                    spinner.style.display = 'none';
                    btnText.innerText = `Pay ₹${{priceInr}} with Razorpay`;
                    payBtn.disabled = false;
                    
                    const options = {{
                        key: data.key,
                        amount: data.amount,
                        currency: data.currency || 'INR',
                        name: "Juhi AI Companion",
                        description: "{title}",
                        order_id: data.order_id,
                        prefill: {{
                            name: "User " + tgUserId,
                            email: "user_" + tgUserId + "@juhi.ai",
                            contact: "9999999999"
                        }},
                        notes: {{
                            user_id: tgUserId,
                            item_type: itemType
                        }},
                        theme: {{ color: "#ff4a76" }},
                        handler: async function (paymentResponse) {{
                            payBtn.disabled = true;
                            spinner.style.display = 'block';
                            btnText.innerText = 'Verifying Payment...';
                            
                            try {{
                                const vRes = await fetch('/api/verify-payment', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/json' }},
                                    body: JSON.stringify({{
                                        razorpay_payment_id: paymentResponse.razorpay_payment_id,
                                        razorpay_order_id: paymentResponse.razorpay_order_id,
                                        razorpay_signature: paymentResponse.razorpay_signature,
                                        user_id: tgUserId,
                                        item_type: itemType
                                    }})
                                }});
                                const vData = await vRes.json();
                                if (vData.success) {{
                                    document.body.innerHTML = `
                                        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px;">
                                            <div style="background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 24px; padding: 36px; max-width: 420px; width: 100%; text-align: center;">
                                                <div style="font-size: 56px; margin-bottom: 16px;">💖</div>
                                                <h1 style="font-size: 24px; font-weight: 700; margin-bottom: 12px; color: #4ade80;">Payment Successful!</h1>
                                                <p style="font-size: 15px; color: #cbd5e1; margin-bottom: 24px;">Your access has been activated! Return to Telegram to chat with Juhi.</p>
                                                <button onclick="if(window.Telegram && window.Telegram.WebApp){{Telegram.WebApp.close();}}else{{window.location.href='https://t.me/JuhiAICompanionBot';}}" style="width: 100%; background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color: white; border: none; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; cursor: pointer;">Return to Telegram Chat</button>
                                            </div>
                                        </div>
                                    `;
                                }} else {{
                                    throw new Error(vData.error || "Payment verification failed.");
                                }}
                             }} catch (vErr) {{
                                payBtn.disabled = false;
                                spinner.style.display = 'none';
                                btnText.innerText = `Pay ₹${{priceInr}} with Razorpay`;
                                errBox.innerText = vErr.message;
                                errBox.style.display = 'block';
                            }}
                        }},
                        modal: {{
                            ondismiss: function () {{
                                payBtn.disabled = false;
                                spinner.style.display = 'none';
                                btnText.innerText = `Pay ₹${{priceInr}} with Razorpay`;
                                fetch('/api/payment-cancelled', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/json' }},
                                    body: JSON.stringify({{ order_id: data.order_id, user_id: tgUserId }})
                                }}).catch(function(){{}});
                            }},
                            escape: true,
                            backdropclose: false
                        }}
                    }};
                    const rzp = new Razorpay(options);
                    rzp.open();
                }} else if (data.pay_url) {{
                    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink && data.pay_url.startsWith('http') && !data.pay_url.includes(window.location.hostname)) {{
                        Telegram.WebApp.openLink(data.pay_url);
                        payBtn.disabled = false;
                        spinner.style.display = 'none';
                        btnText.innerText = `Pay ₹${{priceInr}} via Instamojo`;
                    }} else {{
                        window.location.href = data.pay_url;
                    }}
                }} else if (data.error) {{
                    throw new Error(data.error);
                }} else {{
                    throw new Error("Server failed to generate payment gateway link.");
                }}
            }} catch (err) {{
                payBtn.disabled = false;
                spinner.style.display = 'none';
                btnText.innerText = `Pay ₹${{priceInr}}`;
                errBox.innerText = err.message || "Failed to initiate payment gateway.";
                errBox.style.display = 'block';
                
                sandboxBtn.href = `/checkout/instamojo/mock_ui?user_id=${{tgUserId}}&item_type=${{itemType}}`;
                sandboxBtn.style.display = 'inline-block';
            }}
        }}
    </script>
</body>
</html>"""
    return web.Response(text=html_content, content_type="text/html")


async def handle_instamojo_callback(request):
    """
    Handles user redirect back from Instamojo after payment attempt.
    Query parameters: payment_id, payment_status, payment_request_id, user_id.
    Renders styled Telegram WebApp confirmation card with Telegram.WebApp.close().
    """
    try:
        payment_id = request.query.get("payment_id") or ""
        payment_status = request.query.get("payment_status") or ""
        payment_request_id = request.query.get("payment_request_id") or ""
        user_id_param = request.query.get("user_id") or ""
        
        logger.info(f"Instamojo callback: payment_id={payment_id}, status={payment_status}, request_id={payment_request_id}, user_id_param={user_id_param}")

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE order_id = ?", (payment_request_id,))
        row = cursor.fetchone()
        conn.close()

        telegram_id = row["telegram_id"] if row else 0
        if not telegram_id and user_id_param:
            try:
                telegram_id = int(user_id_param)
            except ValueError:
                pass
                
        if not telegram_id:
            import re
            m = re.search(r'(\d{7,12})', payment_id + payment_request_id)
            if m:
                telegram_id = int(m.group(1))

        item_type = row["item_type"] if row else "chat_pass"
        amount = row["amount"] if row else 5000

        tg_app = request.app.get('tg_app')
        bot_username = "JuhiAICompanionBot"
        if tg_app and tg_app.bot:
            try:
                bot_username = tg_app.bot.username or bot_username
            except Exception:
                pass
                
        bot_link = f"https://t.me/{bot_username}"

        if payment_status in ("Credit", "SUCCESS", "completed", "paid"):
            unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
                telegram_id=telegram_id if telegram_id else 0,
                order_id=payment_request_id,
                payment_id=payment_id,
                item_type=item_type,
                gateway="instamojo",
                amount=amount
            )
            
            if tg_app and unlocked_now and telegram_id > 0:
                try:
                    confirm_text = get_payment_confirmation_text(item_type, expiry)
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
    <title>Payment Successful — Juhi AI</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 24px; padding: 36px; max-width: 420px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); text-align: center; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; display: inline-block; }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; color: #4ade80; }}
        p {{ font-size: 15px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color: white; border: none; outline: none; cursor: pointer; display: block; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; transition: all 0.2s ease; box-shadow: 0 10px 25px -5px rgba(34, 197, 94, 0.4); text-decoration: none; }}
        .btn:hover {{ transform: translateY(-2px); box-shadow: 0 15px 30px -5px rgba(34, 197, 94, 0.6); }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">💖</div>
        <h1>Payment Successful!</h1>
        <p>You're back! Your access has been activated. Tap below to return to your chat with Juhi.</p>
        <button onclick="closeWebApp()" class="btn">Return to Telegram Chat</button>
    </div>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
        }}
        function closeWebApp() {{
            if (window.Telegram && window.Telegram.WebApp) {{
                Telegram.WebApp.close();
            }} else {{
                window.location.href = "{bot_link}";
            }}
        }}
    </script>
</body>
</html>"""
            return web.Response(text=html_content, content_type="text/html")
        else:
            if telegram_id:
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
    <title>Payment Incomplete — Juhi AI</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 24px; padding: 36px; max-width: 420px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); text-align: center; }}
        .icon {{ font-size: 56px; margin-bottom: 16px; display: inline-block; }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; color: #f87171; }}
        p {{ font-size: 15px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #ec4899 0%, #d946ef 100%); color: white; border: none; outline: none; cursor: pointer; display: block; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; transition: all 0.2s ease; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">⚠️</div>
        <h1>Payment Incomplete</h1>
        <p>Your payment was not completed. You can try again whenever you're ready.</p>
        <button onclick="closeWebApp()" class="btn">Return to Telegram Bot</button>
    </div>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
        }}
        function closeWebApp() {{
            if (window.Telegram && window.Telegram.WebApp) {{
                Telegram.WebApp.close();
            }} else {{
                window.location.href = "{bot_link}";
            }}
        }}
    </script>
</body>
</html>"""
            return web.Response(text=html_content, content_type="text/html")
    except Exception as err_cb:
        logger.error(f"Error in handle_instamojo_callback: {err_cb}")
        bot_username = "JuhiAICompanionBot"
        bot_link = f"https://t.me/{bot_username}"
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Received — Juhi AI</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.9); backdrop-filter: blur(16px); border: 1px solid rgba(255, 74, 118, 0.3); border-radius: 24px; padding: 36px; max-width: 420px; width: 100%; text-align: center; }}
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 12px; color: #ff4a76; }}
        p {{ font-size: 15px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn {{ width: 100%; background: linear-gradient(90deg, #ff4a76 0%, #e03b62 100%); color: white; border: none; outline: none; display: block; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; cursor: pointer; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size: 48px; margin-bottom: 12px;">💖</div>
        <h1>Payment Callback Received</h1>
        <p>Your payment request was received. Tap below to return to your chat with Juhi.</p>
        <button onclick="if(window.Telegram && window.Telegram.WebApp){{Telegram.WebApp.close();}}else{{window.location.href='{bot_link}';}}" class="btn">Return to Telegram</button>
    </div>
</body>
</html>"""
        return web.Response(text=html_content, content_type="text/html", status=200)

async def handle_instamojo_mock(request):
    """Mock payment redirection endpoint for local/testing environments."""
    order_id = request.query.get("order_id", "PR_mock_0")
    user_id = request.query.get("user_id", "0")
    item_type = request.query.get("item_type", "chat_pass")
    callback_url = f"/checkout/instamojo/callback?payment_id=MOJO_mock_{user_id}&payment_status=Credit&payment_request_id={order_id}&user_id={user_id}"
    raise web.HTTPFound(location=callback_url)


async def handle_instamojo_mock_ui(request):
    """
    Renders an interactive Test Sandbox screen when live Instamojo API keys are not yet configured in .env.
    """
    order_id = request.query.get("order_id", "PR_mock_0")
    user_id = request.query.get("user_id", "0")
    item_type = request.query.get("item_type", "chat_pass")
    
    success_url = f"/checkout/instamojo/callback?payment_id=MOJO_mock_{user_id}&payment_status=Credit&payment_request_id={order_id}&user_id={user_id}"
    fail_url = f"/checkout/instamojo/callback?payment_id=MOJO_mock_{user_id}&payment_status=Failed&payment_request_id={order_id}&user_id={user_id}"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instamojo Test Gateway</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: linear-gradient(135deg, #0a0712 0%, #1e1b4b 100%); color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .card {{ background: rgba(30, 41, 59, 0.9); backdrop-filter: blur(16px); border: 1px solid rgba(255, 74, 118, 0.3); border-radius: 24px; padding: 32px 24px; max-width: 420px; width: 100%; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }}
        .badge {{ display: inline-block; background: rgba(234, 179, 8, 0.15); border: 1px solid rgba(234, 179, 8, 0.4); color: #fde047; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 16px; }}
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; color: #ffffff; }}
        p {{ font-size: 14px; color: #cbd5e1; margin-bottom: 24px; line-height: 1.5; }}
        .btn-success {{ width: 100%; background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%); color: white; border: none; padding: 16px; border-radius: 14px; font-size: 16px; font-weight: 700; cursor: pointer; margin-bottom: 12px; display: block; text-decoration: none; }}
        .btn-fail {{ width: 100%; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: #9ca3af; padding: 14px; border-radius: 14px; font-size: 14px; font-weight: 600; cursor: pointer; display: block; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">🧪 Test Sandbox Mode</div>
        <h1>Instamojo Payment Gateway</h1>
        <p>Live API credentials are not yet set in <code>.env</code>.<br>You are testing payment flow in Sandbox Mode.</p>
        
        <a href="{success_url}" class="btn-success">✅ Simulate Successful Payment (₹50)</a>
        <a href="{fail_url}" class="btn-fail">❌ Simulate Cancelled Payment</a>
    </div>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {{
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
        }}
    </script>
</body>
</html>"""
    return web.Response(text=html_content, content_type="text/html")


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
    app.router.add_get('/checkout/instamojo/mock_ui', handle_instamojo_mock_ui)
    app.router.add_get('/checkout', handle_checkout_page)
    # Admin Analytics & User Behavior Tracking Routes
    app.router.add_get('/analytics', handle_admin_analytics_dashboard)
    app.router.add_get('/admin/analytics', handle_admin_analytics_dashboard)
    app.router.add_get('/records', handle_admin_analytics_dashboard)
    app.router.add_get('/api/admin/analytics/overview', handle_admin_analytics_overview)
    app.router.add_get('/api/admin/analytics/users', handle_admin_analytics_users)
    app.router.add_get('/api/admin/analytics/user/{user_id}', handle_admin_analytics_user_journey)
    app.router.add_get('/api/admin/analytics/live-feed', handle_admin_analytics_live_feed)
    app.router.add_get('/api/admin/analytics/export-users-csv', handle_admin_export_users_csv)
    app.router.add_get('/api/admin/analytics/export-events', handle_admin_export_events_csv)
    app.router.add_get('/api/admin/export-data', handle_admin_export_data)
    app.router.add_post('/api/analytics/event', handle_api_analytics_event)
    app.router.add_post('/api/analytics/events/batch', handle_api_analytics_batch)
    
    app.router.add_post('/api/create-order', handle_create_order)
    app.router.add_post('/api/verify-payment', handle_verify_payment)
    app.router.add_post('/api/payment-failed', handle_api_payment_failed)
    app.router.add_post('/api/payment-cancelled', handle_api_payment_cancelled)
    app.router.add_post('/webhook/instamojo', handle_instamojo_webhook)
    app.router.add_post('/webhook/razorpay', handle_razorpay_webhook)
    
    # Flutter Mobile App REST API Routes
    app.router.add_post('/api/auth', handle_api_auth)
    app.router.add_get('/api/profile', handle_api_profile)
    app.router.add_get('/api/history', handle_api_history)
    app.router.add_post('/api/history/clear', handle_api_clear_history)
    app.router.add_delete('/api/history', handle_api_clear_history)
    app.router.add_post('/api/chat', handle_api_chat)
    app.router.add_post('/api/mode/toggle', handle_api_toggle_mode)
    app.router.add_post('/api/relationship/level', handle_api_set_relationship_level)
    app.router.add_get('/api/memories', handle_api_memories)
    app.router.add_post('/api/memories', handle_api_memories)
    app.router.add_post('/api/device-token', handle_api_device_token)
    app.router.add_post('/api/notifications/test', handle_api_test_notification)
    app.router.add_get('/api/proactive/check', handle_api_proactive_check)
    app.router.add_post('/api/proactive/check', handle_api_proactive_check)
    
    # Voice Call Endpoints (Sarvam Saaras v4 STT & Bulbul v4 TTS)
    app.router.add_post('/api/voice/call-turn', handle_api_voice_call_turn)
    app.router.add_post('/api/voice/stt', handle_api_voice_stt)
    app.router.add_post('/api/voice/tts', handle_api_voice_tts)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, 'assets')
    gifs_dir = os.path.join(base_dir, 'gifs')
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(gifs_dir, exist_ok=True)
    app.router.add_static('/assets', assets_dir)
    app.router.add_static('/gifs', gifs_dir)
    
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

    # Start proactive companion background scheduler loop
    try:
        from proactive_engine import proactive_scheduler_loop
        asyncio.create_task(proactive_scheduler_loop(application=application, interval_minutes=120))
        logger.info("[PROACTIVE SCHEDULER] Periodic background loop initialized.")
    except Exception as e_pro:
        logger.error(f"Error starting proactive scheduler loop: {e_pro}")

    return runner


if __name__ == "__main__":
    async def main():
        runner = await start_webhook_server(application=None, port=8080)
        logger.info("REST API and Webhook server started on http://0.0.0.0:8080")
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await runner.cleanup()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")
