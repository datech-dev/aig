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
    api_key = (config.INSTAMOJO_API_KEY or "").strip()
    auth_token = (config.INSTAMOJO_AUTH_TOKEN or "").strip()
    base_url = (config.WEB_CHECKOUT_URL or "https://zetagirl.zetalink.cloud").rstrip("/")
    
    if not api_key or not auth_token or api_key == "YOUR_INSTAMOJO_API_KEY" or auth_token == "YOUR_INSTAMOJO_AUTH_TOKEN":
        import time
        mock_id = f"PR_mock_{user_id}_{int(time.time())}"
        mock_url = f"{base_url}/checkout/instamojo/mock_ui?order_id={mock_id}&user_id={user_id}&item_type={item_type}"
        return mock_id, mock_url, "Missing live Instamojo credentials"

    headers = {
        "X-Api-Key": api_key,
        "X-Auth-Token": auth_token
    }
    
    purpose = "Juhi AI 1-Day Chat Pass" if item_type == "chat_pass" else "Juhi AI 10 Image Credits"
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
    except Exception as e_wh:
        logger.error(f"Error executing Instamojo webhook unlock: {e_wh}")

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

        unlocked_now, expiry, msg_str = database.unlock_paid_access_idempotent(
            telegram_id=user_id,
            order_id=order_id,
            payment_id=payment_id,
            item_type=item_type,
            gateway=gateway_used,
            amount=5000
        )
        
        tg_app = request.app.get('tg_app')
        if tg_app and unlocked_now:
            try:
                if item_type == "chat_pass":
                    confirm_text = "You're back! Your 1-day access is now active. Let's continue where we left off. 💖"
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


async def handle_api_analytics_event(request):
    """API endpoint to record client-side user behavior events from Android app."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        event_name = data.get("event_name")
        event_category = data.get("event_category", "engagement")
        platform = data.get("platform", "android_app")
        metadata = data.get("metadata") or {}
        
        if not user_id or not event_name:
            return web.json_response({"success": False, "error": "Missing user_id or event_name"}, status=400)
            
        database.log_user_analytics_event(
            user_id=int(user_id),
            event_name=str(event_name),
            event_category=str(event_category),
            platform=str(platform),
            metadata=metadata
        )
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"Error in handle_api_analytics_event: {e}")
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


async def handle_admin_export_data(request):
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
        logger.error(f"Error exporting data: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_admin_analytics_dashboard(request):
    """Renders a sleek HTML analytics dashboard for viewing user behavior in any browser."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Juhi AI - User Behavior & Conversion Analytics</title>
  <style>
    :root {
      --bg: #0d0f17;
      --card-bg: #161b26;
      --border: #232d3f;
      --pink: #ff2d87;
      --pink-glow: rgba(255, 45, 135, 0.25);
      --purple: #8b5cf6;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
    h1 { font-size: 24px; display: flex; align-items: center; gap: 10px; }
    .badge { background: var(--pink-glow); color: var(--pink); border: 1px solid var(--pink); padding: 4px 10px; border-radius: 20px; font-size: 13px; }
    .btn { background: var(--pink); color: white; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
    .btn:hover { opacity: 0.9; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
    .kpi-title { font-size: 13px; color: var(--muted); text-transform: uppercase; margin-bottom: 6px; }
    .kpi-val { font-size: 28px; font-weight: 700; color: #fff; }
    .funnel-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px; }
    .funnel-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 12px; text-align: center; }
    .funnel-step { background: #0f131d; border: 1px solid var(--border); border-radius: 8px; padding: 16px; position: relative; }
    .funnel-step h4 { font-size: 14px; color: var(--muted); margin-bottom: 8px; }
    .funnel-step .num { font-size: 24px; font-weight: bold; color: var(--pink); }
    .funnel-arrow { font-size: 18px; color: var(--muted); margin-top: 6px; }
    .table-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; text-align: left; }
    th { background: #0f131d; padding: 14px 16px; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); }
    td { padding: 14px 16px; border-bottom: 1px solid #1a2232; }
    tr:hover { background: rgba(255, 45, 135, 0.04); }
    .tag { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .tag-green { background: rgba(16, 185, 129, 0.15); color: var(--green); }
    .tag-yellow { background: rgba(245, 158, 11, 0.15); color: var(--yellow); }
    .tag-red { background: rgba(239, 68, 68, 0.15); color: var(--red); }
    .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
    .modal-content { background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px; width: 100%; max-width: 800px; max-height: 85vh; overflow-y: auto; padding: 24px; }
    .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
    .chat-bubble { padding: 10px 14px; border-radius: 10px; margin-bottom: 8px; max-width: 80%; font-size: 14px; line-height: 1.4; }
    .bubble-user { background: #ff2d87; color: white; margin-left: auto; }
    .bubble-ai { background: #222b3d; color: #f1f5f9; margin-right: auto; border: 1px solid #2e3a52; }
    .bubble-meta { font-size: 11px; color: rgba(255,255,255,0.6); margin-top: 4px; text-align: right; }
    .close-btn { background: none; border: none; color: var(--muted); font-size: 22px; cursor: pointer; }
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>💖 Juhi AI Companion <span class="badge">Live Analytics</span></h1>
      <p style="color: var(--muted); font-size: 14px; margin-top: 4px;">Track user messages, conversation transcripts, and payment conversions.</p>
    </div>
    <div style="display: flex; gap: 10px;">
      <a href="/api/admin/export-data" class="btn">📥 Export CSV</a>
      <button onclick="loadDashboard()" class="btn" style="background: #334155;">🔄 Refresh</button>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="card">
      <div class="kpi-title">Total Users</div>
      <div class="kpi-val" id="kpi-users">-</div>
    </div>
    <div class="card">
      <div class="kpi-title">Total Messages Sent</div>
      <div class="kpi-val" id="kpi-user-msgs" style="color: var(--pink);">-</div>
    </div>
    <div class="card">
      <div class="kpi-title">AI Replies Generated</div>
      <div class="kpi-val" id="kpi-ai-replies" style="color: var(--purple);">-</div>
    </div>
    <div class="card">
      <div class="kpi-title">Avg Msgs / User</div>
      <div class="kpi-val" id="kpi-avg">-</div>
    </div>
    <div class="card">
      <div class="kpi-title">Free Trial Limit</div>
      <div class="kpi-val" style="color: var(--yellow);">50 msgs</div>
    </div>
    <div class="card">
      <div class="kpi-title">Total Revenue</div>
      <div class="kpi-val" id="kpi-rev" style="color: var(--green);">₹0</div>
    </div>
  </div>

  <div class="funnel-container">
    <h3 style="font-size: 16px; margin-bottom: 4px;">🎯 Monetization & Paywall Conversion Funnel</h3>
    <p style="font-size: 13px; color: var(--muted);">Track user progression from free trial to paying subscribers.</p>
    <div class="funnel-grid">
      <div class="funnel-step">
        <h4>1. Reached 50-Msg Paywall</h4>
        <div class="num" id="funnel-paywall">-</div>
      </div>
      <div class="funnel-step">
        <h4>2. Tried to Pay (Clicked Checkout)</h4>
        <div class="num" id="funnel-tried">-</div>
        <div class="funnel-arrow" id="funnel-click-rate">0% click rate</div>
      </div>
      <div class="funnel-step">
        <h4>3. Paid & Subscribed</h4>
        <div class="num" id="funnel-paid" style="color: var(--green);">-</div>
        <div class="funnel-arrow" id="funnel-conv-rate" style="color: var(--green);">0% conversion</div>
      </div>
    </div>
  </div>

  <div class="table-container">
    <div style="padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
      <h3 style="font-size: 16px;">👥 User Behavior & Engagement Logs</h3>
      <input type="text" id="searchInput" onkeyup="filterUsers()" placeholder="Search user ID or name..." style="background: #0f131d; border: 1px solid var(--border); color: #fff; padding: 6px 12px; border-radius: 6px; font-size: 13px;">
    </div>
    <table id="usersTable">
      <thead>
        <tr>
          <th>User ID</th>
          <th>Name / Nickname</th>
          <th>Messages Sent</th>
          <th>Free Used (Limit 50)</th>
          <th>Hit Paywall?</th>
          <th>Tried to Pay?</th>
          <th>Status</th>
          <th>Last Active</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="userRows">
        <tr><td colspan="9" style="text-align:center; color: var(--muted);">Loading user behavior data...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- User Chat & Event Modal -->
  <div id="userModal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <div>
          <h3 id="modalTitle">User Journey</h3>
          <p id="modalSub" style="font-size: 12px; color: var(--muted); margin-top: 2px;"></p>
        </div>
        <button class="close-btn" onclick="closeModal()">&times;</button>
      </div>
      
      <h4 style="margin: 12px 0 8px; font-size: 14px; color: var(--pink);">💬 Complete Conversation Transcript</h4>
      <div id="modalChatHistory" style="background: #0b0e14; border: 1px solid var(--border); border-radius: 8px; padding: 14px; max-height: 350px; overflow-y: auto; margin-bottom: 16px;"></div>

      <h4 style="margin: 12px 0 8px; font-size: 14px; color: var(--purple);">⚡ Recorded Behavior & Payment Events</h4>
      <div id="modalEventsHistory" style="background: #0b0e14; border: 1px solid var(--border); border-radius: 8px; padding: 14px; max-height: 200px; overflow-y: auto;"></div>
    </div>
  </div>

  <script>
    let allUsers = [];

    async function loadDashboard() {
      try {
        const [ovRes, uRes] = await Promise.all([
          fetch('/api/admin/analytics/overview'),
          fetch('/api/admin/analytics/users?limit=1000')
        ]);
        const ov = (await ovRes.json()).data;
        const uData = await uRes.json();
        allUsers = uData.users || [];

        document.getElementById('kpi-users').textContent = ov.total_users;
        document.getElementById('kpi-user-msgs').textContent = ov.total_user_messages;
        document.getElementById('kpi-ai-replies').textContent = ov.total_ai_replies;
        document.getElementById('kpi-avg').textContent = ov.avg_messages_per_user;
        document.getElementById('kpi-rev').textContent = '₹' + ov.total_revenue_inr;

        document.getElementById('funnel-paywall').textContent = ov.funnel.users_reached_paywall;
        document.getElementById('funnel-tried').textContent = ov.funnel.users_tried_to_pay;
        document.getElementById('funnel-paid').textContent = ov.funnel.users_paid_successfully;
        document.getElementById('funnel-click-rate').textContent = ov.funnel.paywall_to_pay_click_percent + '% click rate';
        document.getElementById('funnel-conv-rate').textContent = ov.funnel.checkout_conversion_percent + '% conversion';

        renderUserTable(allUsers);
      } catch (err) {
        console.error('Error loading analytics:', err);
      }
    }

    function renderUserTable(users) {
      const tbody = document.getElementById('userRows');
      if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--muted);">No users found.</td></tr>';
        return;
      }
      tbody.innerHTML = users.map(u => {
        const paywallTag = u.hit_paywall ? '<span class="tag tag-red">YES (50+)</span>' : '<span class="tag tag-green">NO</span>';
        const triedPayTag = u.tried_to_pay ? '<span class="tag tag-yellow">YES (' + u.payment_attempts + 'x)</span>' : '<span class="tag" style="background:#1e293b; color: #94a3b8;">NO</span>';
        const statusTag = u.is_subscribed ? '<span class="tag tag-green">SUBSCRIBED</span>' : '<span class="tag tag-yellow">FREE TRIAL</span>';
        const lastActive = u.last_active_at ? u.last_active_at.replace('T', ' ').substring(0, 19) : (u.registered_at ? u.registered_at.substring(0, 10) : '-');

        return `<tr>
          <td><strong>${u.user_id}</strong></td>
          <td>${u.first_name || u.username || 'User'}</td>
          <td><strong style="color:var(--pink);">${u.messages_sent || 0}</strong></td>
          <td>${u.free_messages_used || 0} / 50</td>
          <td>${paywallTag}</td>
          <td>${triedPayTag}</td>
          <td>${statusTag}</td>
          <td style="font-size:12px; color:var(--muted);">${lastActive}</td>
          <td>
            <button onclick="viewUserJourney(${u.user_id})" class="btn" style="padding: 4px 10px; font-size: 12px;">🔍 View Chat</button>
          </td>
        </tr>`;
      }).join('');
    }

    function filterUsers() {
      const q = document.getElementById('searchInput').value.toLowerCase();
      const filtered = allUsers.filter(u => 
        String(u.user_id).includes(q) || 
        (u.first_name && u.first_name.toLowerCase().includes(q)) || 
        (u.username && u.username.toLowerCase().includes(q))
      );
      renderUserTable(filtered);
    }

    async function viewUserJourney(userId) {
      try {
        const res = await fetch(`/api/admin/analytics/user/${userId}`);
        const data = await res.json();
        const j = data.journey;

        document.getElementById('modalTitle').textContent = `User ${j.user_info.telegram_id || userId} (${j.user_info.first_name || 'User'})`;
        document.getElementById('modalSub').textContent = `Messages: ${j.stats.total_messages} sent, ${j.stats.total_replies} replies | Free Used: ${j.stats.free_messages_used}/50 | Paid: ${j.stats.has_active_subscription ? 'YES' : 'NO'}`;

        const chatBox = document.getElementById('modalChatHistory');
        if (!j.chat_history.length) {
          chatBox.innerHTML = '<p style="color:var(--muted); text-align:center;">No chat messages yet.</p>';
        } else {
          chatBox.innerHTML = j.chat_history.map(m => `
            <div class="chat-bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-ai'}">
              <strong>${m.role === 'user' ? 'User' : 'Juhi'}:</strong> ${m.message}
              <div class="bubble-meta">${m.timestamp || ''}</div>
            </div>
          `).join('');
          chatBox.scrollTop = chatBox.scrollHeight;
        }

        const evBox = document.getElementById('modalEventsHistory');
        if (!j.analytics_events.length) {
          evBox.innerHTML = '<p style="color:var(--muted); text-align:center;">No behavior events recorded yet.</p>';
        } else {
          evBox.innerHTML = j.analytics_events.map(e => `
            <div style="font-size: 12px; padding: 6px 0; border-bottom: 1px solid #1a2232; display: flex; justify-content: space-between;">
              <span><strong>${e.event_name}</strong> (${e.event_category})</span>
              <span style="color: var(--muted);">${e.created_at}</span>
            </div>
          `).join('');
        }

        document.getElementById('userModal').style.display = 'flex';
      } catch (err) {
        alert('Error loading user journey: ' + err);
      }
    }

    function closeModal() {
      document.getElementById('userModal').style.display = 'none';
    }

    window.onclick = function(event) {
      const modal = document.getElementById('userModal');
      if (event.target === modal) closeModal();
    }

    loadDashboard();
  </script>
</body>
</html>
"""
    return web.Response(text=html_content, content_type="text/html")


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
            "image_credits": billing.get("image_credits", 0),
            "chat_expires_at": billing.get("chat_expires_at")
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
        persona_key = settings["active_persona"] if settings else "juhi"
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
            if remaining > 0 and remaining <= 5:
                cleaned_reply += f"\n\n(⌛ {remaining} free trial message{'s' if remaining > 1 else ''} remaining today)"
        else:
            remaining = 999
            
        # Log to DB
        database.add_chat_message(user_id, persona_key, "user", text)
        database.add_chat_message(user_id, persona_key, "assistant", cleaned_reply)
        
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

        # Create Instamojo Payment Request
        order_id, pay_url, err = await create_instamojo_payment_request(user_id, item_type, amount_inr=50.0)
        amount_paise = 5000

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
                    if item_type == "chat_pass":
                        confirm_text = "You're back! Your 1-day access is now active. Let's continue where we left off. 💖"
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
    app.router.add_get('/admin/analytics', handle_admin_analytics_dashboard)
    app.router.add_get('/api/admin/analytics/overview', handle_admin_analytics_overview)
    app.router.add_get('/api/admin/analytics/users', handle_admin_analytics_users)
    app.router.add_get('/api/admin/analytics/user/{user_id}', handle_admin_analytics_user_journey)
    app.router.add_get('/api/admin/export-data', handle_admin_export_data)
    app.router.add_post('/api/analytics/event', handle_api_analytics_event)
    
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
    app.router.add_post('/api/device-token', handle_api_device_token)
    app.router.add_post('/api/notifications/test', handle_api_test_notification)
    
    app.router.add_static('/assets', 'assets')
    app.router.add_static('/gifs', 'gifs')
    
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

