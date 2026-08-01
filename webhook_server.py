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
            expiry = database.grant_chat_pass(user_id, hours=3)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"Granted 3 hours chat pass to user {user_id} via Razorpay webhook. Expires: {expiry_str}")
            
            try:
                await tg_app.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Payment Successful!</b>\n\n"
                        f"Thank you for your payment! Your 3-hour unlimited chat pass has been activated.\n"
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
            expiry = database.grant_chat_pass(user_id, hours=3)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"Granted 3 hours chat pass to user {user_id} via Standard Checkout. Expires: {expiry_str}")
            
            if tg_app:
                try:
                    await tg_app.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"✅ <b>Payment Successful!</b>\n\n"
                            f"Thank you for your payment! Your 3-hour unlimited chat pass has been activated.\n"
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
    bot_username = "KarinAIGirlfriendBot"
    if tg_app and tg_app.bot:
        try:
            bot_username = tg_app.bot.username or "KarinAIGirlfriendBot"
        except Exception:
            pass
    return web.json_response({
        "razorpay_key_id": config.RAZORPAY_KEY_ID,
        "bot_username": bot_username
    })

async def start_webhook_server(application, port=8080):
    """
    Starts the aiohttp webhook server on the specified port.
    Shares the same asyncio loop as the telegram bot.
    """
    app = web.Application()
    app.router.add_get('/', handle_home)
    app.router.add_get('/api/config', handle_get_config)
    app.router.add_post('/api/create-order', handle_create_order)
    app.router.add_post('/api/verify-payment', handle_verify_payment)
    app.router.add_post('/webhook/razorpay', handle_razorpay_webhook)
    app.router.add_static('/assets', 'assets')
    
    # Store reference to telegram bot application to allow sending messages in routes
    app['tg_app'] = application
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Razorpay webhook server successfully running on port {port}")
    return runner
