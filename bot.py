import sys
import logging
import html
import os
import random
import re
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction

# UTF-8 encoding configuration for Windows system compatibility
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import local modules
import config
import database
import ai_engine

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State dictionary to track if a user is in the middle of renaming
# Structure: {user_id: "AWAITING_USER_NICKNAME" | "AWAITING_AI_NICKNAME"}
USER_STATES = {}

def get_chat_paywall_keyboard(user_id=None):
    base_url = config.WEB_CHECKOUT_URL.rstrip('/')
    if user_id:
        pay_url = f"{base_url}/checkout?user_id={user_id}&item_type=chat_pass"
    else:
        pay_url = f"{base_url}/checkout?item_type=chat_pass"

    keyboard = [
        [
            InlineKeyboardButton("💳 Pay ₹50 inside Telegram", web_app=WebAppInfo(url=pay_url))
        ],
        [
            InlineKeyboardButton("🌐 Open in Browser (Direct UPI / GPay)", url=pay_url)
        ],
        [
            InlineKeyboardButton("🔙 View Profile / Balance", callback_data="profile_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_image_paywall_keyboard(user_id=None):
    base_url = config.WEB_CHECKOUT_URL.rstrip('/')
    if user_id:
        pay_url = f"{base_url}/checkout?user_id={user_id}&item_type=image_credits"
    else:
        pay_url = f"{base_url}/checkout?item_type=image_credits"

    keyboard = [
        [
            InlineKeyboardButton("💳 Pay ₹50 inside Telegram", web_app=WebAppInfo(url=pay_url))
        ],
        [
            InlineKeyboardButton("🌐 Open in Browser (Direct UPI / GPay)", url=pay_url)
        ],
        [
            InlineKeyboardButton("🔙 View Profile / Balance", callback_data="profile_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_progress_bar(percent):
    """Renders a beautiful visual progress bar."""
    filled_blocks = int(percent / 10)
    empty_blocks = 10 - filled_blocks
    return "█" * filled_blocks + "░" * empty_blocks

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and starts the onboarding process (asking for nickname)."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    database.update_active_persona(user.id, "karin")
    
    # Set state to await nickname on start
    USER_STATES[user.id] = "AWAITING_START_NICKNAME"
    
    await update.message.reply_text(
        "👋 Welcome! Before we begin, what should I call you?\n\n"
        "💬 Please type the nickname you want me to call you (e.g. <i>Honey, Darling, master</i>, or your real name):",
        parse_mode="HTML"
    )


def build_profile_view(user_id):
    """Constructs the profile text and reply markup keyboard."""
    settings = database.get_user_settings(user_id)
    persona_key = settings["active_persona"] if settings else "karin"
    persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
    xp = settings["relationship_xp"] if settings else 0
    status = config.get_relationship_status(xp)
    bar = get_progress_bar(status["percent"])
    
    u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else "User"
    ai_nick = settings["ai_nickname"] if (settings and settings.get("ai_nickname")) else persona["name"]
    
    chat_mode = database.get_chat_mode(user_id)
    mode_label = "🌸 <b>Caring Best Friend</b> (Supportive & empathetic)" if chat_mode == "normal" else "🔥 <b>Intimate Girlfriend</b> (Flirty & passionate)"
    mode_btn_text = "🔥 Switch to Intimate Mode" if chat_mode == "normal" else "🌸 Switch to Best Friend Mode"
    
    memories = database.get_user_memories(user_id)
    mem_count = len(memories)
    
    billing = database.get_user_billing(user_id)
    if database.is_chat_subscribed(user_id):
        expiry = datetime.fromisoformat(billing["chat_expires_at"])
        remaining = expiry - datetime.utcnow()
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if remaining.days > 0:
            hours += remaining.days * 24
        chat_status = f"✅ <b>Active</b> (expires in {hours}h {minutes}m)"
    else:
        remaining_free = config.FREE_MESSAGE_LIMIT - billing["free_messages_used"]
        if remaining_free > 0:
            chat_status = f"⏳ <b>Free Trial</b> ({remaining_free}/10 free messages left)"
        else:
            chat_status = "❌ <b>Trial Expired</b> (Purchase ₹50 pass to unlock)"
            
    image_credits = billing["image_credits"]
    image_status = f"📸 <b>{image_credits} Image Credits</b>"
    
    profile_text = (
        f"❤️ <b>YOUR RELATIONSHIP PROFILE</b> ❤️\n\n"
        f"<b>Partner:</b> {persona['name']} ({persona['tagline']})\n"
        f"<b>Chat Mode:</b> {mode_label}\n"
        f"<b>Relationship Level:</b> {status['level']} - <b>{status['title']}</b>\n"
        f"<b>XP Progress:</b> {xp} XP\n"
        f"<code>[{bar}]</code> {status['percent']}%\n\n"
        f"👤 <b>What she calls you:</b> <code>{html.escape(u_nick)}</code>\n"
        f"🤖 <b>What you call her:</b> <code>{html.escape(ai_nick)}</code>\n"
        f"🧠 <b>Memory Bank:</b> <code>{mem_count} details remembered</code>\n\n"
        f"💳 <b>BILLING & SUBSCRIPTION</b> 💳\n"
        f"• <b>Chat Subscription:</b> {chat_status}\n"
        f"• <b>Image Generation:</b> {image_status}\n\n"
        f"<i>Switch between Caring Best Friend and Intimate Girlfriend modes anytime!</i>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(mode_btn_text, callback_data="toggle_chat_mode"),
            InlineKeyboardButton("🧠 Memory Bank", callback_data="view_memories")
        ],
        [
            InlineKeyboardButton("✏️ Edit Nicknames", callback_data="menu_nicknames")
        ],
        [
            InlineKeyboardButton("💬 Buy Chat Pass (₹50)", callback_data="buy_chat_menu"),
            InlineKeyboardButton("📸 Buy 10 Images (₹50)", callback_data="buy_image_menu")
        ],
        [
            InlineKeyboardButton("🔄 Reset Chat History", callback_data="menu_reset_history")
        ]
    ]
    return profile_text, InlineKeyboardMarkup(keyboard)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's relationship progress with Karin, nicknames, mode, and billing info."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    profile_text, reply_markup = build_profile_view(user.id)
    await update.message.reply_text(profile_text, reply_markup=reply_markup, parse_mode="HTML")


async def roleplay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a menu of available roleplays for Karin."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    settings = database.get_user_settings(user.id)
    active_persona = settings["active_persona"] if settings else "karin"
    
    menu_text = (
        "🎭 <b>KARIN ROLEPLAY MANAGER</b> 🎭\n\n"
        "Switch Karin's scenario to explore different stories and intimacy settings. "
        "Each roleplay has its own <b>independent chat history</b> so the scenarios don't get mixed up, "
        "but your <b>relationship XP/level & custom nicknames are shared</b>!\n\n"
        "<b>Current Active Mode:</b>\n"
        f"👉 <b>{config.PERSONAS[active_persona]['name']}</b> - <i>{config.PERSONAS[active_persona]['tagline']}</i>\n\n"
        "Select a scenario to start:"
    )
    
    keyboard = []
    for p_key, p_info in config.PERSONAS.items():
        icon = "💬"
        if "drive" in p_key:
            icon = "🚗"
        elif "cottage" in p_key:
            icon = "🌲"
        elif "home" in p_key:
            icon = "🏠"
            
        btn_text = f"{icon} {p_info['name']}"
        if p_key == active_persona:
            btn_text += " (Active)"
            
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"set_roleplay_{p_key}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(menu_text, reply_markup=reply_markup, parse_mode="HTML")


async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an image of Karin using Venice.ai's 'lustify-v7' model if credits are available."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    # Check image credits before generating
    billing = database.get_user_billing(user.id)
    if billing["image_credits"] <= 0:
        paywall_text = (
            f"📸 <b>IMAGE GENERATION LOCKED</b> 📸\n\n"
            f"You need image credits to generate custom drawings.\n"
            f"Purchase 10 image credits for ₹50 to start drawing again!"
        )
        await update.message.reply_text(
            paywall_text,
            reply_markup=get_image_paywall_keyboard(user.id),
            parse_mode="HTML"
        )
        return
        
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text("💬 Please provide a prompt. Example: <code>/draw Karin, looking naughty, wearing a bikini, blushing</code>", parse_mode="HTML")
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    generation_notice = await update.message.reply_text("🎨 Generating image... please wait a moment.")
    
    try:
        settings = database.get_user_settings(user.id)
        persona_key = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
        appearance = persona.get("appearance", "")
        full_prompt = config.combine_appearance_and_prompt(appearance, prompt)
        seed = settings.get("seed") if settings else None
        
        img_path = await ai_engine.generate_image(full_prompt, seed=seed)
        # Deduct credit
        database.use_image_credit(user.id)
        new_billing = database.get_user_billing(user.id)
        
        caption = (
            f"🎨 Generated: <i>{html.escape(prompt)}</i>\n\n"
            f"🔋 <b>Remaining Balance:</b> {new_billing['image_credits']} credits."
        )
        with open(img_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo, 
                caption=caption, 
                parse_mode="HTML"
            )
        # Clean up files & notices
        os.remove(img_path)
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=generation_notice.message_id)
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        await generation_notice.edit_text(f"❌ Image generation failed: {str(e)[:100]}")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Directly triggers the chat reset verification."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    settings = database.get_user_settings(user.id)
    active_persona = settings["active_persona"] if settings else "karin"
    persona = config.PERSONAS.get(active_persona, config.PERSONAS["karin"])
    
    keyboard = [
        [
            InlineKeyboardButton("❌ Yes, Reset History", callback_data=f"confirm_reset_{active_persona}"),
            InlineKeyboardButton("🔙 Cancel", callback_data="profile_back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"⚠️ Are you sure you want to clear your chat history with <b>{persona['name']}</b>?\n"
        f"This cannot be undone, but your relationship level/XP will remain intact.",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies with list of commands and usage help."""
    help_text = (
        "🤖 <b>Karin Bot - Quick Help</b>\n\n"
        "Here are the commands you can use to control the bot:\n"
        "• /start - Greet Karin and begin chatting.\n"
        "• /profile - Check relationship level, XP, and nicknames.\n"
        "• /roleplay - Switch Karin's roleplay scenario (e.g. Long Drive, Forest Cottage, Alone at Home).\n"
        "• /draw &lt;prompt&gt; - Generate custom images of Karin using Venice lustify-v7.\n"
        "• /reset - Clear conversation history with Karin.\n"
        "• /help - Display this help text.\n\n"
        "<b>💡 Chatting Tips:</b>\n"
        "- Just send normal messages to chat. Each reply from you increases your XP.\n"
        "- You can ask Karin directly to send you a photo, and she will generate it!"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


# --- Callback Query Handler (Button Click Processing) ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes inline keyboard interactions."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Ensure user exists in database
    database.setup_user(user_id, query.from_user.username, query.from_user.first_name)
    
    # Roleplay selection handler
    if data.startswith("set_roleplay_"):
        roleplay_key = data[len("set_roleplay_"):]
        if roleplay_key in config.PERSONAS:
            database.setup_user(user_id, query.from_user.username, query.from_user.first_name)
            database.update_active_persona(user_id, roleplay_key)
            persona = config.PERSONAS[roleplay_key]
            
            welcome_text = persona.get("welcome_msg", "Hey baby! Let's chat. 🥰")
            
            # If empty history, prepopulate with welcome message so context is set
            history = database.get_chat_history(user_id, roleplay_key)
            if not history:
                database.add_chat_message(user_id, roleplay_key, "assistant", welcome_text)
                
            transition_text = (
                f"🎭 <b>Roleplay Scenario Switched!</b>\n"
                f"🌟 <b>{persona['name']}</b> ({persona['tagline']})\n\n"
                f"💬 <b>Karin:</b> {welcome_text}"
            )
            await query.message.edit_text(transition_text, parse_mode="HTML")
        return
        
    # 0. Onboarding Orientation Selection Triggers
    if data in ["set_orientation_straight", "set_orientation_lesbian"]:
        orientation = "straight" if data == "set_orientation_straight" else "lesbian"
        database.update_user_orientation(user_id, orientation)
        USER_STATES.pop(user_id, None)
        
        # Now welcome them!
        settings = database.get_user_settings(user_id)
        u_nick = settings["user_nickname"] if settings and settings["user_nickname"] else "User"
        persona = config.PERSONAS["karin"]
        avatar_path = persona["avatar_path"]
        
        welcome_text = (
            f"⚡ <b>Hello {html.escape(u_nick)}! I'm Karin!</b> ⚡\n\n"
            f"<i>\"{persona['description']}\"</i>\n\n"
            f"I'm your girlfriend now. Let's chat! What do you want to talk about? 😉\n\n"
            f"<i>Tip: You can ask me to send you a picture at any time! You can also use /draw &lt;prompt&gt; to generate custom images.</i>"
        )
        
        try:
            await query.message.delete()
        except Exception:
            pass
            
        if os.path.exists(avatar_path):
            with open(avatar_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=welcome_text,
                    parse_mode="HTML"
                )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=welcome_text,
                parse_mode="HTML"
            )
        return
        
    # 1. Profile Menu: Nicknames Screen
    elif data == "menu_nicknames":
        settings = database.get_user_settings(user_id)
        u_nick = settings["user_nickname"] if settings["user_nickname"] else "User"
        ai_nick = settings["ai_nickname"] if settings["ai_nickname"] else "Karin"
        
        nickname_text = (
            f"✏️ <b>NICKNAME CONFIGURATION</b>\n\n"
            f"Current settings:\n"
            f"• What she calls you: <b>{html.escape(u_nick)}</b>\n"
            f"• What you call her: <b>{html.escape(ai_nick)}</b>\n\n"
            f"Select which nickname you would like to edit:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👤 Change what she calls me", callback_data="rename_user"),
                InlineKeyboardButton("🤖 Change what I call her", callback_data="rename_ai")
            ],
            [
                InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")
            ]
        ]
        await query.message.edit_text(
            nickname_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    # 2. Nickname Triggers
    elif data == "rename_user":
        USER_STATES[user_id] = "AWAITING_USER_NICKNAME"
        await query.message.edit_text(
            "💬 Please type the nickname you want her to use for you (e.g. <i>Darling, Honey, Master</i>, or your name):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="menu_nicknames")]]),
            parse_mode="HTML"
        )
        
    elif data == "rename_ai":
        USER_STATES[user_id] = "AWAITING_AI_NICKNAME"
        await query.message.edit_text(
            "💬 Please type the nickname you want to use for her (e.g. <i>Sweetie, My Princess</i>):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="menu_nicknames")]]),
            parse_mode="HTML"
        )
        
    # 3. Profile Menu: Reset History Prompt
    elif data == "menu_reset_history":
        settings = database.get_user_settings(user_id)
        active_persona = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(active_persona, config.PERSONAS["karin"])
        keyboard = [
            [
                InlineKeyboardButton("❌ Yes, Clear History", callback_data=f"confirm_reset_{active_persona}"),
                InlineKeyboardButton("🔙 Cancel", callback_data="profile_back")
            ]
        ]
        await query.message.edit_text(
            f"⚠️ Are you sure you want to clear your chat history with <b>{persona['name']}</b>?\n"
            f"This cannot be undone, but your relationship level/XP will remain intact.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
    # 4. Confirm Reset (Dynamic)
    elif data.startswith("confirm_reset_"):
        persona_key = data[len("confirm_reset_"):]
        database.clear_chat_history(user_id, persona_key)
        
        persona = config.PERSONAS.get(persona_key)
        if persona and "welcome_msg" in persona:
            database.add_chat_message(user_id, persona_key, "assistant", persona["welcome_msg"])
            
        persona_name = persona.get("name", "Karin") if persona else "Karin"
        await query.message.edit_text(
            f"🔄 Chat history with <b>{persona_name}</b> has been successfully cleared!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]),
            parse_mode="HTML"
        )
        
    # Paywall / Purchase callbacks
    elif data == "buy_chat_menu":
        paywall_text = (
            f"💬 <b>CHAT PASS SUBSCRIPTION</b> 💬\n\n"
            f"Get unlimited messaging with Karin for <b>1 day (24 hours)</b> for only <b>₹50</b>!\n\n"
            f"Click the button below to purchase or simulate payment."
        )
        await query.message.edit_text(
            paywall_text,
            reply_markup=get_chat_paywall_keyboard(user_id),
            parse_mode="HTML"
        )
        
    elif data == "buy_image_menu":
        paywall_text = (
            f"📸 <b>IMAGE GENERATION CREDITS</b> 📸\n\n"
            f"Generate custom images of Karin with her `/draw` command and dynamic selfie reactions!\n\n"
            f"Purchase <b>10 images</b> for only <b>₹50</b>.\n\n"
            f"Click the button below to purchase or simulate payment."
        )
        await query.message.edit_text(
            paywall_text,
            reply_markup=get_image_paywall_keyboard(user_id),
            parse_mode="HTML"
        )
        
    elif data == "pay_chat_pass":
        database.log_payment_event("pay_button_clicked", user_id, status="CLICKED")
        
        order_id = f"ord_{user_id}_{int(asyncio.get_event_loop().time())}"
        if config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_ID != "YOUR_RAZORPAY_KEY_ID":
            try:
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                order_data = client.order.create({
                    "amount": 5000,
                    "currency": "INR",
                    "receipt": f"rec_{user_id}_{int(asyncio.get_event_loop().time())}",
                    "notes": {
                        "user_id": str(user_id),
                        "item_type": "chat_pass"
                    }
                })
                order_id = order_data["id"]
            except Exception as e:
                logger.error(f"Failed to create Razorpay Order: {e}")

        # Register transaction order in payments & log payment_order_created
        database.create_payment_order(user_id, order_id=order_id, amount=5000, item_type="chat_pass")
        
        checkout_base = config.WEB_CHECKOUT_URL.rstrip('/')
        checkout_url = f"{checkout_base}/checkout?order_id={order_id}"
        
        checkout_text = (
            f"💬 <b>UNLIMITED CHAT PASS (24 HOURS)</b>\n\n"
            f"Continue chatting with Karin for 1 day — <b>₹50</b>\n\n"
            f"✨ Keep your full conversation history & memories intact!\n\n"
            f"Click the button below to open your secure hosted payment page and complete your ₹50 purchase via UPI, Card, or NetBanking."
        )
        keyboard = [
            [InlineKeyboardButton("💳 Continue for ₹50 — Open Payment Page", url=checkout_url)],
            [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
        ]
        await query.message.edit_text(checkout_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    elif data == "pay_image_credits":
        database.log_payment_event("pay_button_clicked", user_id, status="CLICKED")
        
        order_id = f"ord_img_{user_id}_{int(asyncio.get_event_loop().time())}"
        if config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_ID != "YOUR_RAZORPAY_KEY_ID":
            try:
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                order_data = client.order.create({
                    "amount": 5000,
                    "currency": "INR",
                    "receipt": f"rec_img_{user_id}_{int(asyncio.get_event_loop().time())}",
                    "notes": {
                        "user_id": str(user_id),
                        "item_type": "image_credits"
                    }
                })
                order_id = order_data["id"]
            except Exception as e:
                logger.error(f"Failed to create Razorpay Image Order: {e}")

        # Register transaction order in payments & log payment_order_created
        database.create_payment_order(user_id, order_id=order_id, amount=5000, item_type="image_credits")
        
        checkout_base = config.WEB_CHECKOUT_URL.rstrip('/')
        checkout_url = f"{checkout_base}/checkout?order_id={order_id}"
        
        checkout_text = (
            f"📸 <b>10 KARIN IMAGE CREDITS</b>\n\n"
            f"10 Custom Photo Credits — <b>₹50</b>\n\n"
            f"Generate custom pictures of Karin using Venice lustify-v7!\n\n"
            f"Click the button below to open your secure payment page and complete your ₹50 purchase."
        )
        keyboard = [
            [InlineKeyboardButton("💳 Continue for ₹50 — Open Payment Page", url=checkout_url)],
            [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
        ]
        await query.message.edit_text(checkout_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    # 5. Back to Profile
    elif data == "profile_back":
        USER_STATES.pop(user_id, None)
        profile_text, reply_markup = build_profile_view(user_id)
        await query.message.edit_text(profile_text, reply_markup=reply_markup, parse_mode="HTML")

    # Mode and Memory Bank Callbacks
    elif data == "toggle_chat_mode":
        new_mode = database.toggle_chat_mode(user_id)
        if new_mode == "normal":
            msg = (
                "🌸 <b>Mode Switched: CARING BEST FRIEND</b> 🌸\n\n"
                "Karin will now talk to you as a sweet, supportive, compassionate best friend! "
                "She will focus on listening to your day, comforting your struggles, and offering warm emotional care."
            )
        else:
            msg = (
                "🔥 <b>Mode Switched: INTIMATE GIRLFRIEND</b> 🔥\n\n"
                "Karin will now talk to you as a flirty, passionate, and deeply intimate girlfriend!"
            )
        keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "view_memories":
        memories = database.get_user_memories(user_id)
        if not memories:
            mem_text = (
                "🧠 <b>KARIN'S MEMORY BANK ABOUT YOU</b>\n\n"
                "<i>I haven't remembered any specific preferences or personal details yet!</i>\n\n"
                "Chat with me and tell me about your job, favorite things, daily life, or feelings, and I'll keep them in mind to support you."
            )
            keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
        else:
            mem_list = "\n".join([f"• <b>{html.escape(m)}</b>" for m in memories])
            mem_text = (
                f"🧠 <b>KARIN'S MEMORY BANK ABOUT YOU</b> 🧠\n\n"
                f"Here are the personal details, preferences, and feelings you've shared with me:\n\n"
                f"{mem_list}\n\n"
                f"<i>I remember these details to understand you better, support your struggles, and care for you deeply!</i>"
            )
            keyboard = [
                [InlineKeyboardButton("🗑️ Clear Memory Bank", callback_data="clear_memories")],
                [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
            ]
        await query.message.edit_text(mem_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "clear_memories":
        database.clear_user_memories(user_id)
        msg = (
            "🗑️ <b>Memory Bank Cleared!</b>\n\n"
            "I have cleared previously stored personal details. As we keep chatting, I'll start fresh in remembering details you share!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    # 6. Visualize Image Request
    elif data == "visualize_image":
        # Remove the button immediately to avoid double clicks
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning(f"Could not remove reply markup: {e}")

        # Check image credits balance
        billing = database.get_user_billing(user_id)
        if billing["image_credits"] <= 0:
            paywall_text = (
                f"📸 <b>IMAGE GENERATION LOCKED</b> 📸\n\n"
                f"You need image credits to visualize Karin.\n"
                f"Purchase 10 image credits for ₹50 to see it!"
            )
            await query.message.reply_text(
                paywall_text,
                reply_markup=get_image_paywall_keyboard(),
                parse_mode="HTML"
            )
            return

        # Retrieve settings and active persona info
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
        appearance = persona.get("appearance", "")

        # Get last user message from chat history
        history = database.get_chat_history(user_id, persona_key)
        user_messages = [msg["content"] for msg in history if msg["role"] == "user"]
        if not user_messages:
            await query.message.reply_text("❌ Could not retrieve your last message to visualize.")
            return
        last_user_message = user_messages[-1]

        # Send loading notification and trigger photo upload action
        loading_msg = await query.message.reply_text("🎨 <i>Enhancing prompt and generating image... please wait a moment.</i>", parse_mode="HTML")
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.UPLOAD_PHOTO)

        try:
            # Enhance prompt using Venice
            enhanced_prompt = await ai_engine.enhance_image_prompt(last_user_message, appearance)
            full_prompt = config.combine_appearance_and_prompt(appearance, enhanced_prompt)

            seed = settings.get("seed") if settings else None
            # Generate the image from Venice
            img_path = await ai_engine.generate_image(full_prompt, seed=seed)

            # Deduct credit
            database.use_image_credit(user_id)
            new_billing = database.get_user_billing(user_id)

            caption = f"🔋 <b>Remaining Balance:</b> {new_billing['image_credits']} image credits."

            with open(img_path, "rb") as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML"
                )
            os.remove(img_path)
            # Delete loading message
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=loading_msg.message_id)
        except Exception as e:
            logger.error(f"Failed to generate dynamic image from callback: {e}")
            await loading_msg.edit_text(f"⚠️ Image generation failed: {str(e)[:100]}")


# --- Text Message Handlers ---

def choose_gif(query: str, telegram_id: int, persona_key: str, user_text: str = "", assistant_text: str = "") -> str:
    """
    Finds the most appropriate GIF to send.
    - Calculates a matching score for all available GIFs.
    - Filters out recently sent GIFs (last 3) to prevent repetition.
    - Randomly picks from the top-scoring matches if multiple options exist.
    - Returns the filename of the selected GIF (without extension), or None.
    """
    gif_descriptions = config.get_gif_descriptions()
    if not gif_descriptions:
        return None
        
    # Check relationship XP to restrict NSFW/explicit GIFs (unlocks after 25 messages / 250 XP)
    xp = 0
    try:
        settings = database.get_user_settings(telegram_id)
        if settings:
            xp = settings.get("relationship_xp", 0)
    except Exception as e:
        logger.error(f"Error fetching relationship XP in choose_gif: {e}")
        
    def is_nsfw(name: str) -> bool:
        nsfw_keywords = ["boob", "nipple", "nude", "hentai", "fingering", "naked", "breast", "teasing"]
        name_lower = name.lower()
        return any(k in name_lower for k in nsfw_keywords)

    import re
    # Tokenize input texts
    stop_words = {"the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "at", "for", "with", "is", "was", "are", "karin", "user"}
    
    if query:
        # Explicit tag query: match query against name & description
        query_words = set(re.findall(r'\b\w+\b', query.lower())) - stop_words
        if not query_words:
            query_words = set(re.split(r'[-_ ]', query.lower()))
    else:
        # Heuristic fallback: match user + assistant message texts
        user_words = set(re.findall(r'\b\w+\b', user_text.lower()))
        assistant_words = set(re.findall(r'\b\w+\b', assistant_text.lower()))
        query_words = user_words.union(assistant_words) - stop_words

    if not query_words:
        return None

    # Calculate match scores for all GIFs
    candidates = []
    for gif_name, description in gif_descriptions.items():
        # Restrict explicit GIFs to 25+ messages (250+ XP)
        if xp < 250 and is_nsfw(gif_name):
            continue
            
        gif_words = set(re.split(r'[-_]', gif_name.lower()))
        desc_words = set(re.findall(r'\b\w+\b', description.lower()))
        target_words = gif_words.union(desc_words) - stop_words
        
        if not target_words:
            continue
            
        match_count = 0
        for tw in target_words:
            word_matched = False
            if tw in query_words:
                word_matched = True
            else:
                for qw in query_words:
                    if len(tw) >= 4 and tw[:4] in qw:
                        word_matched = True
                        break
                    if len(qw) >= 4 and qw[:4] in tw:
                        word_matched = True
                        break
            if word_matched:
                match_count += 1
                
        score = match_count / len(gif_words)
        
        if query:
            if score > 0:
                candidates.append((gif_name, score))
        else:
            if score >= 0.5:
                candidates.append((gif_name, score))

    if not candidates:
        if query:
            query_clean = query.lower().strip()
            for gif_name in gif_descriptions.keys():
                if xp < 250 and is_nsfw(gif_name):
                    continue
                if query_clean in gif_name.lower() or gif_name.lower() in query_clean:
                    candidates.append((gif_name, 1.0))
        
        if not candidates:
            return None

    # Fetch recently sent history
    recent_gifs = database.get_user_recent_gifs(telegram_id, persona_key)
    
    # Filter candidates to avoid recently sent ones
    filtered_candidates = [c for c in candidates if c[0] not in recent_gifs]
    
    # If all matches were recently sent, fall back to the original list to ensure we can still send one
    if not filtered_candidates:
        filtered_candidates = candidates
        
    # Find the maximum score among remaining candidates
    max_score = max(c[1] for c in filtered_candidates)
    
    # Keep only the candidates sharing the highest score
    best_candidates = [c[0] for c in filtered_candidates if c[1] == max_score]
    
    # Randomly select one to ensure variety
    selected_gif = random.choice(best_candidates)
    
    # Update recently sent list
    database.add_user_recent_gif(telegram_id, persona_key, selected_gif)
    
    return selected_gif


async def safe_send_reply(update: Update, text: str, reply_markup=None, parse_mode="HTML"):
    """
    Sends a text reply to update.message.
    Falls back to sending plain text if Telegram fails to parse HTML formatting.
    """
    try:
        return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        err_str = str(e)[:100]
        logger.warning(f"Failed to send formatted message: {err_str}. Retrying as plain text.")
        try:
            return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"Failed to send plain text message fallback: {str(e2)[:100]}")
            raise e2


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes all regular text messages, checking for paywall and image-generation triggers."""
    user = update.effective_user
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    
    try:
        # Initialize user settings in case
        database.setup_user(user.id, user.username, user.first_name)
        
        # 1. State Machine Check: Onboarding or Nickname Settings
        if user.id in USER_STATES:
            state = USER_STATES[user.id]
            
            if state == "AWAITING_START_NICKNAME":
                database.update_nicknames(user.id, user_nickname=text)
                USER_STATES[user.id] = "AWAITING_START_ORIENTATION"
                keyboard = [
                    [
                        InlineKeyboardButton("Straight (Boyfriend ♂️)", callback_data="set_orientation_straight"),
                        InlineKeyboardButton("Lesbian (Girlfriend ♀️)", callback_data="set_orientation_lesbian")
                    ]
                ]
                await safe_send_reply(
                    update,
                    f"Great! I will call you <b>{html.escape(text)}</b>. 🥰\n\n"
                    "Next, please select your relationship style using the buttons below, or simply send your next message to begin!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
                return
                
            elif state == "AWAITING_START_ORIENTATION":
                # User sent a text message instead of clicking orientation button. Default to straight and proceed to chat!
                USER_STATES.pop(user.id, None)
                database.update_user_orientation(user.id, "straight")
                
            elif state == "AWAITING_USER_NICKNAME":
                database.update_nicknames(user.id, user_nickname=text)
                USER_STATES.pop(user.id, None)
                await safe_send_reply(
                    update,
                    f"✅ Nickname updated! I will now call you <b>{html.escape(text)}</b>.",
                    parse_mode="HTML"
                )
                return
                
            elif state == "AWAITING_AI_NICKNAME":
                database.update_nicknames(user.id, ai_nickname=text)
                USER_STATES.pop(user.id, None)
                await safe_send_reply(
                    update,
                    f"✅ Nickname updated! I will refer to myself as <b>{html.escape(text)}</b>.",
                    parse_mode="HTML"
                )
                return

        # 2. Billing Check: Verify chat subscription or free trial messages
        is_subscribed = database.is_chat_subscribed(user.id)
        billing = database.get_user_billing(user.id)
        free_used = billing.get("free_messages_used", 0) if billing else 0
        
        if not is_subscribed:
            if free_used >= config.FREE_MESSAGE_LIMIT:
                database.log_payment_event("paywall_shown", user.id, status="SHOWN")
                settings = database.get_user_settings(user.id)
                u_nick = settings["user_nickname"] if (settings and settings.get("user_nickname")) else user.first_name
                paywall_text = (
                    f"🥺 <b>Aww {html.escape(u_nick)}... Our free trial time just ran out for today!</b>\n\n"
                    f"I was having so much fun chatting with you and getting close... I really don't want us to stop here! 💖\n\n"
                    f"<b>Continue chatting with Karin for 1 day — ₹50</b> 👇"
                )
                await safe_send_reply(
                    update,
                    paywall_text,
                    reply_markup=get_chat_paywall_keyboard(user.id),
                    parse_mode="HTML"
                )
                return

        # 3. Regular Conversation Flow
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
        settings = database.get_user_settings(user.id)
        persona_key = settings["active_persona"] if settings else "karin"
        persona = config.PERSONAS.get(persona_key, config.PERSONAS["karin"])
        xp = settings["relationship_xp"] if settings else 0
        
        u_nick = settings["user_nickname"] if (settings and settings["user_nickname"]) else user.first_name
        ai_nick = settings["ai_nickname"] if (settings and settings["ai_nickname"]) else persona["name"]
        user_orientation = settings.get("user_orientation", "straight") if settings else "straight"
        
        # Extract & store personal details/memories from user message
        ai_engine.extract_and_save_user_memories(user.id, text)
        
        chat_mode = database.get_chat_mode(user.id)
        memories = database.get_user_memories(user.id)
        
        # Get chat history for Karin
        history = database.get_chat_history(user.id, persona_key)
        
        # Generate response from Venice AI
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
        
        # Check if the AI's reply contains an image generation tag [GENERATE_IMAGE: prompt]
        image_match = re.search(r'\[GENERATE_IMAGE:\s*(.*?)(?:\]|$)', reply, re.IGNORECASE | re.DOTALL)
        
        cleaned_reply = reply
        has_image = False
        image_prompt = ""
        
        if image_match:
            has_image = True
            image_prompt = image_match.group(1).strip()
            cleaned_reply = reply.replace(image_match.group(0), "").strip()
            
        # Check if the AI's reply contains a GIF reaction tag [SEND_GIF: name]
        gif_match = re.search(r'\[SEND_GIF:\s*(.*?)(?:\]|$)', cleaned_reply, re.IGNORECASE)
        has_gif = False
        gif_name = None
        
        if gif_match:
            has_gif = True
            query = gif_match.group(1).strip()
            cleaned_reply = cleaned_reply.replace(gif_match.group(0), "").strip()
            gif_name = choose_gif(query, user.id, persona_key)
            if not gif_name:
                has_gif = False
        else:
            if random.random() < 0.10:
                gif_name = choose_gif(None, user.id, persona_key, user_text=text, assistant_text=cleaned_reply)
                if gif_name:
                    has_gif = True
                    
        if not cleaned_reply and (has_image or has_gif):
            cleaned_reply = "Here is something for you... 😉"
            
        # Increment free messages used if user is not subscribed
        if not is_subscribed:
            database.increment_free_messages(user.id)
            new_free_used = free_used + 1
            remaining = config.FREE_MESSAGE_LIMIT - new_free_used
            if remaining > 0 and remaining <= 3:
                cleaned_reply += f"\n\n<i>(⌛ {remaining} free trial message{'s' if remaining > 1 else ''} remaining today)</i>"
            
        # Save conversation log to SQLite DB
        database.add_chat_message(user.id, persona_key, "user", text)
        database.add_chat_message(user.id, persona_key, "assistant", cleaned_reply)
        
        # Increment relationship XP
        leveled_up, new_level, new_title = database.add_xp(user.id, amount=10)
        
        # Resolve GIF path if matched
        gif_path = None
        if has_gif and gif_name:
            gif_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")
            if os.path.exists(gif_dir):
                try:
                    possible_files = [f for f in os.listdir(gif_dir) if os.path.splitext(f)[0].lower() == gif_name.lower() and f.lower().endswith('.gif')]
                    if possible_files:
                        gif_path = os.path.join(gif_dir, possible_files[0])
                except Exception as e:
                    logger.error(f"Error listing gifs directory: {e}")
                    
        if has_image:
            keyboard = [[InlineKeyboardButton("Visualize it? 🎨", callback_data="visualize_image")]]
            await safe_send_reply(
                update,
                cleaned_reply,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        elif not is_subscribed and free_used + 1 == 5:
            # Highlight visual generator hook around message 5 to boost engagement
            keyboard = [[InlineKeyboardButton("📸 Imagine what I look like right now... 🎨", callback_data="visualize_image")]]
            if gif_path and os.path.exists(gif_path):
                try:
                    with open(gif_path, "rb") as gif_file:
                        await update.message.reply_animation(
                            animation=gif_file,
                            caption=cleaned_reply,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except Exception as e:
                    logger.error(f"Failed to send reaction GIF: {e}")
                    await safe_send_reply(update, cleaned_reply, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await safe_send_reply(update, cleaned_reply, reply_markup=InlineKeyboardMarkup(keyboard))
        elif gif_path and os.path.exists(gif_path):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
            try:
                with open(gif_path, "rb") as gif_file:
                    await update.message.reply_animation(
                        animation=gif_file,
                        caption=cleaned_reply
                    )
            except Exception as e:
                logger.error(f"Failed to send reaction GIF: {e}")
                await safe_send_reply(update, cleaned_reply)
        else:
            await safe_send_reply(update, cleaned_reply)
            
        # Trigger level up banner if they crossed a threshold
        if leveled_up:
            level_up_card = (
                f"🎉 <b>CONGRATULATIONS! LEVEL UP!</b> 🎉\n\n"
                f"Your bond with {ai_nick} has grown stronger!\n"
                f"You have reached <b>Level {new_level}</b>: <b>{new_title}</b>!\n\n"
                f"<i>New topics and dialogues are now unlocked in her personality matrix.</i>"
            )
            await safe_send_reply(update, level_up_card, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in handle_message for user {user.id}: {e}", exc_info=True)
        err_msg = f"⚠️ Karin Connection Error ({type(e).__name__}): {str(e)[:150]}"
        await safe_send_reply(
            update,
            err_msg
        )


def is_admin_user(user) -> bool:
    """Helper to check if a Telegram user has admin authorization."""
    if not user:
        return False
    if config.ADMIN_TELEGRAM_ID and str(user.id).strip() == str(config.ADMIN_TELEGRAM_ID).strip():
        return True
    if user.username:
        u_name = user.username.lstrip('@').lower()
        if u_name in ["dhinesh_rajam", "dhineshrajam"]:
            return True
    return False


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to view detailed usage, user list, payment link abandonment, and revenue statistics."""
    user = update.effective_user
    if not is_admin_user(user):
        await update.message.reply_text(
            f"❌ <b>Admin Permission Required</b>\n\n"
            f"You do not have permission to view stats.\n"
            f"<i>Your Telegram ID is:</i> <code>{user.id}</code>\n\n"
            f"To enable admin access, add this to your <code>.env</code> file:\n"
            f"<code>ADMIN_TELEGRAM_ID={user.id}</code>",
            parse_mode="HTML"
        )
        return
        
    try:
        stats = database.get_admin_stats()
        
        conversion_rate = 0.0
        if stats["total_users"] > 0:
            conversion_rate = (stats["paying_users"] / stats["total_users"]) * 100.0
            
        # 1. Recent Payments
        recent_text = ""
        if stats["recent_payments"]:
            recent_text = "\n📈 <b>Recent Payments:</b>\n"
            for p in stats["recent_payments"]:
                username_str = f"@{html.escape(str(p['username']))}" if p['username'] else f"ID: {p['telegram_id']}"
                first_name_str = html.escape(str(p['first_name'])) if p['first_name'] else "User"
                item_str = html.escape(str(p['item_type']))
                recent_text += (
                    f"• {p['created_at'][:19]} - {first_name_str} ({username_str}) paid "
                    f"<b>₹{p['amount_inr']:.2f}</b> for <code>{item_str}</code>\n"
                )
        else:
            recent_text = "\n<i>No completed payments yet.</i>\n"

        # 2. Tracked Users Trying the App
        trying_text = "\n📱 <b>Users Trying App:</b>\n"
        if stats.get("trying_users"):
            for u in stats["trying_users"][:10]: # show top 10 recent
                u_str = f"@{html.escape(str(u['username']))}" if u['username'] else f"ID: {u['telegram_id']}"
                name = html.escape(str(u['first_name'] or "User"))
                sub_status = "Pass Active" if u['is_chat_subscribed'] else f"{u['free_messages_used']} msgs used"
                trying_text += f"• {name} ({u_str}) - Joined: {u['created_at'][:10]} [{sub_status}]\n"
            if len(stats["trying_users"]) > 10:
                trying_text += f"  <i>...and {len(stats['trying_users']) - 10} more users.</i>\n"
        else:
            trying_text += "<i>No registered users yet.</i>\n"

        # 3. Tracked Users Clicking Pay 50 and Leaving
        abandoned_text = "\n⚠️ <b>Users Clicked Pay ₹50 & Left (Payment Link Generated):</b>\n"
        if stats.get("abandoned_checkout_users"):
            for ab in stats["abandoned_checkout_users"][:10]: # show top 10
                u_str = f"@{html.escape(str(ab['username']))}" if ab['username'] else f"ID: {ab['telegram_id']}"
                name = html.escape(str(ab['first_name'] or "User"))
                item = html.escape(str(ab['item_type'] or "chat_pass"))
                date_str = ab['created_at'][:19] if ab['created_at'] else "Recently"
                abandoned_text += f"• {date_str} - {name} ({u_str}) generated ₹{ab['amount_inr']:.0f} link for <code>{item}</code> & left\n"
            if len(stats["abandoned_checkout_users"]) > 10:
                abandoned_text += f"  <i>...and {len(stats['abandoned_checkout_users']) - 10} more left link checkout.</i>\n"
        else:
            abandoned_text += "<i>No abandoned payment links recorded.</i>\n"
            
        stats_card = (
            f"📊 <b>Karin AI - Admin Statistics</b>\n\n"
            f"👥 <b>Total Users Trying App:</b> {stats['total_users']}\n"
            f"⚠️ <b>Users Clicked Pay 50 & Left:</b> {stats['abandoned_checkouts_count']}\n"
            f"💳 <b>Total Paying Users:</b> {stats['paying_users']}\n"
            f"💰 <b>Completed Payments:</b> {stats['total_payments']}\n"
            f"💵 <b>Total Revenue:</b> ₹{stats['total_revenue_inr']:.2f} INR\n"
            f"🔄 <b>Conversion Rate:</b> {conversion_rate:.2f}%\n"
            f"{trying_text}"
            f"{abandoned_text}"
            f"{recent_text}"
        )
        await update.message.reply_text(stats_card, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        await update.message.reply_text(f"❌ Failed to retrieve stats: {e}")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to export all users as a CSV file."""
    user = update.effective_user
    if not is_admin_user(user):
        await update.message.reply_text(
            f"❌ <b>Admin Permission Required</b>\n\n"
            f"You do not have permission to export user data.\n"
            f"<i>Your Telegram ID is:</i> <code>{user.id}</code>\n\n"
            f"To enable admin access, add this to your <code>.env</code> file:\n"
            f"<code>ADMIN_TELEGRAM_ID={user.id}</code>",
            parse_mode="HTML"
        )
        return

    try:
        trying_users = database.get_trying_users()
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Telegram ID", "Username", "First Name", "Joined Date", "Free Msgs Used", "Chat Pass Active", "Image Credits"])
        for u in trying_users:
            writer.writerow([
                u["telegram_id"],
                u["username"] or "",
                u["first_name"] or "",
                u["created_at"],
                u["free_messages_used"],
                "YES" if u["is_chat_subscribed"] else "NO",
                u["image_credits"]
            ])
        output.seek(0)
        file_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
        file_bytes.name = "vps_all_users.csv"
        await update.message.reply_document(
            document=file_bytes,
            filename="vps_all_users.csv",
            caption=f"📊 <b>Complete User Export</b> ({len(trying_users)} users)",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await update.message.reply_text(f"❌ Failed to export user data: {e}")



async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows user to toggle between Caring Best Friend and Intimate Girlfriend modes."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    new_mode = database.toggle_chat_mode(user.id)
    if new_mode == "normal":
        msg = (
            "🌸 <b>Mode Switched: CARING BEST FRIEND</b> 🌸\n\n"
            "Karin will now talk to you as a sweet, supportive, compassionate best friend! "
            "She will focus on listening to your day, comforting your struggles, and offering warm emotional care without NSFW/explicit talk."
        )
    else:
        msg = (
            "🔥 <b>Mode Switched: INTIMATE GIRLFRIEND</b> 🔥\n\n"
            "Karin will now talk to you as a flirty, passionate, and deeply intimate girlfriend!"
        )
    
    keyboard = [[InlineKeyboardButton("🔙 View Profile", callback_data="profile_back")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def memories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays stored user memories and personal details."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    
    memories = database.get_user_memories(user.id)
    if not memories:
        mem_text = (
            "🧠 <b>KARIN'S MEMORY BANK ABOUT YOU</b>\n\n"
            "<i>I haven't remembered any specific preferences or personal details yet!</i>\n\n"
            "Chat with me and tell me about your job, favorite things, daily life, or feelings, and I'll keep them in mind to support you."
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
    else:
        mem_list = "\n".join([f"• <b>{html.escape(m)}</b>" for m in memories])
        mem_text = (
            f"🧠 <b>KARIN'S MEMORY BANK ABOUT YOU</b> 🧠\n\n"
            f"Here are the personal details, preferences, and feelings you've shared with me:\n\n"
            f"{mem_list}\n\n"
            f"<i>I remember these details to understand you better, support your struggles, and care for you deeply!</i>"
        )
        keyboard = [
            [InlineKeyboardButton("🗑️ Clear Memory Bank", callback_data="clear_memories")],
            [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
        ]
    await update.message.reply_text(mem_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- Main Application Boot ---

async def post_init(application: Application):
    """Starts the async webhook receiver server and sets official bot commands on Telegram."""
    from webhook_server import start_webhook_server
    # Start Razorpay webhook server on port 8080 (shares the telegram event loop)
    asyncio.create_task(start_webhook_server(application, port=8080))
    
    # Overwrite & update official bot command list in Telegram to remove old third-party menus
    commands = [
        BotCommand("start", "Start chatting with Karin"),
        BotCommand("profile", "View profile, relationship level & status"),
        BotCommand("roleplay", "Switch companion persona"),
        BotCommand("mode", "Toggle Normal vs Intimate chat mode"),
        BotCommand("memories", "View stored memory bank"),
        BotCommand("draw", "Generate custom AI image"),
        BotCommand("reset", "Reset chat history"),
        BotCommand("help", "View help & commands guide"),
        BotCommand("stats", "Admin stats & usage overview"),
        BotCommand("export", "Export user data CSV")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Successfully updated official bot commands in Telegram.")
    except Exception as e:
        logger.error(f"Failed to set Telegram bot commands: {e}")


def main():
    """Initializes the bot application."""
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("TELEGRAM_BOT_TOKEN environment variable is missing! Bot cannot start.")
        print("\n[ERROR] Telegram Bot Token is missing. Configure it in .env file and try again.")
        return

    # Build client with webhook receiver initialization
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Add Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("roleplay", roleplay_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("memories", memories_command))
    application.add_handler(CommandHandler("draw", draw_command))
    application.add_handler(CommandHandler("image", draw_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("export_users", export_command))
    
    # Add Inline Button Handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Add Message Handler for general text conversation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Launch bot
    print("AI Girlfriend Telegram bot starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
