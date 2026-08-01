import logging
import html
import os
import random
import re
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
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

# --- Paywall Keyboard Helpers ---

def get_chat_paywall_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💳 Pay ₹50 for 3 Hours Chat", callback_data="pay_chat_pass")
        ],
        [
            InlineKeyboardButton("🔙 View Profile / Balance", callback_data="profile_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_image_paywall_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💳 Pay ₹50 for 10 Images", callback_data="pay_image_credits")
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


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's relationship progress with Karin, nicknames, and billing info."""
    user = update.effective_user
    database.setup_user(user.id, user.username, user.first_name)
    settings = database.get_user_settings(user.id)
    
    if not settings:
        await update.message.reply_text("Error loading profile. Try running /start first.")
        return
        
    persona_key = settings["active_persona"]
    persona = config.PERSONAS[persona_key]
    xp = settings["relationship_xp"]
    
    status = config.get_relationship_status(xp)
    bar = get_progress_bar(status["percent"])
    
    u_nick = settings["user_nickname"] if settings["user_nickname"] else "User"
    ai_nick = settings["ai_nickname"] if settings["ai_nickname"] else persona["name"]
    
    # Billing Info
    billing = database.get_user_billing(user.id)
    if database.is_chat_subscribed(user.id):
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
            chat_status = f"⏳ <b>Free Trial</b> ({remaining_free} messages left)"
        else:
            chat_status = "❌ <b>Expired</b> (Purchase required to chat)"
            
    image_credits = billing["image_credits"]
    image_status = f"📸 <b>{image_credits} Image Credits</b>"
    
    profile_text = (
        f"❤️ <b>YOUR RELATIONSHIP PROFILE</b> ❤️\n\n"
        f"<b>Partner:</b> {persona['name']} ({persona['tagline']})\n"
        f"<b>Relationship Level:</b> {status['level']} - <b>{status['title']}</b>\n"
        f"<b>XP Progress:</b> {xp} XP\n"
        f"<code>[{bar}]</code> {status['percent']}%\n\n"
        f"👤 <b>What she calls you:</b> <code>{html.escape(u_nick)}</code>\n"
        f"🤖 <b>What you call her:</b> <code>{html.escape(ai_nick)}</code>\n\n"
        f"💳 <b>BILLING & SUBSCRIPTION</b> 💳\n"
        f"• <b>Chat Subscription:</b> {chat_status}\n"
        f"• <b>Image Generation:</b> {image_status}\n\n"
        f"<i>Chat with her to gain more XP and unlock new levels of intimacy!</i>"
    )
    
    keyboard = [
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
    
    reply_markup = InlineKeyboardMarkup(keyboard)
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
            reply_markup=get_image_paywall_keyboard(),
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
            f"Get unlimited messaging with Karin for <b>3 hours</b> for only <b>₹50</b>!\n\n"
            f"Click the button below to purchase or simulate payment."
        )
        await query.message.edit_text(
            paywall_text,
            reply_markup=get_chat_paywall_keyboard(),
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
            reply_markup=get_image_paywall_keyboard(),
            parse_mode="HTML"
        )
        
    elif data == "pay_chat_pass":
        if not config.RAZORPAY_KEY_ID or config.RAZORPAY_KEY_ID == "YOUR_RAZORPAY_KEY_ID":
            # Fall back to simulated payment
            await query.message.edit_text("⚠️ <i>Razorpay API Key is missing in .env. Simulating successful checkout...</i>", parse_mode="HTML")
            await asyncio.sleep(1.0)
            expiry = database.grant_chat_pass(user_id, hours=3)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S UTC")
            success_text = (
                f"✅ <b>Payment Successful (Simulated)!</b>\n\n"
                f"Thank you! Your 3-hour unlimited chat pass has been activated.\n"
                f"• <b>Expires at:</b> <code>{expiry_str}</code>\n\n"
                f"You can now continue chatting with Karin!"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
            await query.message.edit_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            try:
                await query.message.edit_text("🔄 <i>Generating Razorpay payment link...</i>", parse_mode="HTML")
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username
                
                # Create payment link (₹50 in paisa = 5000)
                payment_link = client.payment_link.create({
                    "amount": 5000,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": "3 Hours Karin Chat Pass",
                    "customer": {
                        "name": query.from_user.first_name,
                    },
                    "notify": {
                        "sms": False,
                        "email": False
                    },
                    "reminder_enable": False,
                    "notes": {
                        "user_id": str(user_id),
                        "payload": "chat_pass"
                    },
                    "callback_url": f"https://t.me/{bot_username}",
                    "callback_method": "get"
                })
                
                short_url = payment_link["short_url"]
                
                checkout_text = (
                    f"💳 <b>Razorpay Checkout</b>\n\n"
                    f"Click the button below to pay <b>₹50</b> via UPI, Card, or Netbanking to activate your 3-Hour Chat Pass."
                )
                keyboard = [
                    [InlineKeyboardButton("🔗 Pay ₹50 via Razorpay", url=short_url)],
                    [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
                ]
                await query.message.edit_text(checkout_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to generate Razorpay chat pass link: {e}")
                await query.message.edit_text(f"❌ Failed to initiate checkout: {str(e)}")
        
    elif data == "pay_image_credits":
        if not config.RAZORPAY_KEY_ID or config.RAZORPAY_KEY_ID == "YOUR_RAZORPAY_KEY_ID":
            # Fall back to simulated payment
            await query.message.edit_text("⚠️ <i>Razorpay API Key is missing in .env. Simulating successful checkout...</i>", parse_mode="HTML")
            await asyncio.sleep(1.0)
            database.grant_image_credits(user_id, amount=10)
            billing = database.get_user_billing(user_id)
            success_text = (
                f"✅ <b>Payment Successful (Simulated)!</b>\n\n"
                f"Thank you! 10 image credits have been added to your account.\n"
                f"• <b>Total Image Balance:</b> <code>{billing['image_credits']}</code> credits.\n\n"
                f"You can now generate pictures of Karin!"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]]
            await query.message.edit_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        else:
            try:
                await query.message.edit_text("🔄 <i>Generating Razorpay payment link...</i>", parse_mode="HTML")
                import razorpay
                client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
                
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username
                
                # Create payment link (₹50 in paisa = 5000)
                payment_link = client.payment_link.create({
                    "amount": 5000,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": "10 Karin Image Credits",
                    "customer": {
                        "name": query.from_user.first_name,
                    },
                    "notify": {
                        "sms": False,
                        "email": False
                    },
                    "reminder_enable": False,
                    "notes": {
                        "user_id": str(user_id),
                        "payload": "image_credits"
                    },
                    "callback_url": f"https://t.me/{bot_username}",
                    "callback_method": "get"
                })
                
                short_url = payment_link["short_url"]
                
                checkout_text = (
                    f"💳 <b>Razorpay Checkout</b>\n\n"
                    f"Click the button below to pay <b>₹50</b> via UPI, Card, or Netbanking to purchase 10 image credits."
                )
                keyboard = [
                    [InlineKeyboardButton("🔗 Pay ₹50 via Razorpay", url=short_url)],
                    [InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")]
                ]
                await query.message.edit_text(checkout_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to generate Razorpay image credits link: {e}")
                await query.message.edit_text(f"❌ Failed to initiate checkout: {str(e)}")
        
    # 5. Back to Profile
    elif data == "profile_back":
        USER_STATES.pop(user_id, None)
        
        settings = database.get_user_settings(user_id)
        persona_key = settings["active_persona"]
        persona = config.PERSONAS[persona_key]
        xp = settings["relationship_xp"]
        status = config.get_relationship_status(xp)
        bar = get_progress_bar(status["percent"])
        
        u_nick = settings["user_nickname"] if settings["user_nickname"] else "User"
        ai_nick = settings["ai_nickname"] if settings["ai_nickname"] else persona["name"]
        
        # Billing Info
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
                chat_status = f"⏳ <b>Free Trial</b> ({remaining_free} messages left)"
            else:
                chat_status = "❌ <b>Expired</b> (Purchase required to chat)"
                
        image_credits = billing["image_credits"]
        image_status = f"📸 <b>{image_credits} Image Credits</b>"
        
        profile_text = (
            f"❤️ <b>YOUR RELATIONSHIP PROFILE</b> ❤️\n\n"
            f"<b>Partner:</b> {persona['name']} ({persona['tagline']})\n"
            f"<b>Relationship Level:</b> {status['level']} - <b>{status['title']}</b>\n"
            f"<b>XP Progress:</b> {xp} XP\n"
            f"<code>[{bar}]</code> {status['percent']}%\n\n"
            f"👤 <b>What she calls you:</b> <code>{html.escape(u_nick)}</code>\n"
            f"🤖 <b>What you call her:</b> <code>{html.escape(ai_nick)}</code>\n\n"
            f"💳 <b>BILLING & SUBSCRIPTION</b> 💳\n"
            f"• <b>Chat Subscription:</b> {chat_status}\n"
            f"• <b>Image Generation:</b> {image_status}\n\n"
            f"<i>Chat with her to gain more XP and unlock new levels of intimacy!</i>"
        )
        
        keyboard = [
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
        
        await query.message.edit_text(
            profile_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes all regular text messages, checking for paywall and image-generation triggers."""
    user = update.effective_user
    text = update.message.text
    
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
            await update.message.reply_text(
                f"Great! I will call you <b>{html.escape(text)}</b>. 🥰\n\n"
                "Next, please select your relationship style:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return
            
        elif state == "AWAITING_START_ORIENTATION":
            await update.message.reply_text(
                "⚠️ Please select your relationship style using the buttons above before we begin!"
            )
            return
            
        elif state == "AWAITING_USER_NICKNAME":
            database.update_nicknames(user.id, user_nickname=text)
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Nickname updated! I will now call you <b>{html.escape(text)}</b>.",
                parse_mode="HTML"
            )
            return
            
        elif state == "AWAITING_AI_NICKNAME":
            database.update_nicknames(user.id, ai_nickname=text)
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"✅ Nickname updated! I will refer to myself as <b>{html.escape(text)}</b>.",
                parse_mode="HTML"
            )
            return

    # 2. Billing Check: Verify chat subscription or free trial messages
    is_subscribed = database.is_chat_subscribed(user.id)
    billing = database.get_user_billing(user.id)
    
    if not is_subscribed:
        if billing["free_messages_used"] >= config.FREE_MESSAGE_LIMIT:
            paywall_text = (
                f"💸 <b>FREE TRIAL EXPIRED</b> 💸\n\n"
                f"You have used all your {config.FREE_MESSAGE_LIMIT} free messages.\n"
                f"To unlock unlimited messaging for 3 hours, purchase a chat pass for just ₹50."
            )
            await update.message.reply_text(
                paywall_text,
                reply_markup=get_chat_paywall_keyboard(),
                parse_mode="HTML"
            )
            return

    # 3. Regular Conversation Flow
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    settings = database.get_user_settings(user.id)
    persona_key = settings["active_persona"]
    persona = config.PERSONAS[persona_key]
    xp = settings["relationship_xp"]
    
    u_nick = settings["user_nickname"] if settings["user_nickname"] else user.first_name
    ai_nick = settings["ai_nickname"] if settings["ai_nickname"] else persona["name"]
    
    # Get chat history for Karin
    history = database.get_chat_history(user.id, persona_key)
    
    # Generate response from Venice AI
    reply = await ai_engine.generate_response(
        persona_key=persona_key,
        relationship_xp=xp,
        user_nickname=u_nick,
        ai_nickname=ai_nick,
        chat_history=history,
        user_message=text
    )
    
    # Check if the AI's reply contains an image generation tag [GENERATE_IMAGE: prompt]
    # We use a pattern that matches even if the closing bracket ']' was truncated at the end of the text.
    image_match = re.search(r'\[GENERATE_IMAGE:\s*(.*?)(?:\]|$)', reply, re.IGNORECASE | re.DOTALL)

    
    cleaned_reply = reply
    has_image = False
    image_prompt = ""
    
    if image_match:
        has_image = True
        image_prompt = image_match.group(1).strip()
        # Remove the tag from the text response
        cleaned_reply = reply.replace(image_match.group(0), "").strip()
        
    # Check if the AI's reply contains a GIF reaction tag [SEND_GIF: name]
    gif_match = re.search(r'\[SEND_GIF:\s*(.*?)(?:\]|$)', cleaned_reply, re.IGNORECASE)
    has_gif = False
    gif_name = None
    
    if gif_match:
        has_gif = True
        query = gif_match.group(1).strip()
        cleaned_reply = cleaned_reply.replace(gif_match.group(0), "").strip()
        # Resolve the best matching GIF for the explicit tag query
        gif_name = choose_gif(query, user.id, persona_key)
        if not gif_name:
            has_gif = False
    else:
        # Heuristic fallback matching (triggered only 10% of the time to avoid over-sending)
        if random.random() < 0.10:
            gif_name = choose_gif(None, user.id, persona_key, user_text=text, assistant_text=cleaned_reply)
            if gif_name:
                has_gif = True
                
    # If LLM produces an empty text after stripping tag, give it a baseline response
    if not cleaned_reply and (has_image or has_gif):
        cleaned_reply = "Here is something for you... 😉"
        
    # Increment free messages used if user is not subscribed
    if not is_subscribed:
        database.increment_free_messages(user.id)
        
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
        await update.message.reply_text(
            cleaned_reply,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    elif gif_path and os.path.exists(gif_path):
        # Send GIF reaction (free)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
        try:
            with open(gif_path, "rb") as gif_file:
                await update.message.reply_animation(
                    animation=gif_file,
                    caption=cleaned_reply
                )
        except Exception as e:
            logger.error(f"Failed to send reaction GIF: {e}")
            await update.message.reply_text(cleaned_reply)
    else:
        # Send text response normally
        await update.message.reply_text(cleaned_reply)
        
    # Trigger level up banner if they crossed a threshold
    if leveled_up:
        level_up_card = (
            f"🎉 <b>CONGRATULATIONS! LEVEL UP!</b> 🎉\n\n"
            f"Your bond with {ai_nick} has grown stronger!\n"
            f"You have reached <b>Level {new_level}</b>: <b>{new_title}</b>!\n\n"
            f"<i>New topics and dialogues are now unlocked in her personality matrix.</i>"
        )
        await update.message.reply_text(level_up_card, parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only command to view usage and payment statistics."""
    user = update.effective_user
    is_admin = False
    if config.ADMIN_TELEGRAM_ID and str(user.id) == str(config.ADMIN_TELEGRAM_ID):
        is_admin = True
    if user.username and user.username.lower() == "dhinesh_rajam":
        is_admin = True
        
    if not is_admin:
        await update.message.reply_text("❌ You do not have permission to view stats.")
        return
        
    try:
        stats = database.get_admin_stats()
        
        conversion_rate = 0.0
        if stats["total_users"] > 0:
            conversion_rate = (stats["paying_users"] / stats["total_users"]) * 100.0
            
        recent_text = ""
        if stats["recent_payments"]:
            recent_text = "\n📈 <b>Recent Payments:</b>\n"
            for p in stats["recent_payments"]:
                username_str = f"@{p['username']}" if p['username'] else f"ID: {p['telegram_id']}"
                first_name_str = p['first_name'] if p['first_name'] else "User"
                recent_text += (
                    f"• {p['created_at'][:19]} - {first_name_str} ({username_str}) paid "
                    f"<b>₹{p['amount_inr']:.2f}</b> for <code>{p['item_type']}</code>\n"
                )
        else:
            recent_text = "\n<i>No payments recorded yet.</i>\n"
            
        stats_card = (
            f"📊 <b>Karin AI - Admin Statistics</b>\n\n"
            f"👥 <b>Total Users trying bot:</b> {stats['total_users']}\n"
            f"💳 <b>Total Paying Users:</b> {stats['paying_users']}\n"
            f"💰 <b>Total Payments count:</b> {stats['total_payments']}\n"
            f"💵 <b>Total Revenue:</b> ₹{stats['total_revenue_inr']:.2f} INR\n"
            f"🔄 <b>Conversion Rate:</b> {conversion_rate:.2f}%\n"
            f"{recent_text}"
        )
        await update.message.reply_text(stats_card, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        await update.message.reply_text(f"❌ Failed to retrieve stats: {e}")


# --- Main Application Boot ---

async def post_init(application: Application):
    """Starts the async webhook receiver server after the telegram application starts."""
    from webhook_server import start_webhook_server
    # Start Razorpay webhook server on port 8080 (shares the telegram event loop)
    asyncio.create_task(start_webhook_server(application, port=8080))


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
    application.add_handler(CommandHandler("mode", roleplay_command))
    application.add_handler(CommandHandler("draw", draw_command))
    application.add_handler(CommandHandler("image", draw_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add Inline Button Handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Add Message Handler for general text conversation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Launch bot
    print("AI Girlfriend Telegram bot starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
