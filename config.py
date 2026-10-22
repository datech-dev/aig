import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
VENICE_API_KEY = os.getenv("VENICE_API_KEY")
VENICE_MODEL = os.getenv("VENICE_MODEL", "aion-labs-aion-3-5-mini")
VENICE_IMAGE_MODEL = os.getenv("VENICE_IMAGE_MODEL", "fluently-xl")
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", "TWPWLly8Lf8NmpjQaX3PbFreGjp9zgPJ")


# Payment Gateway Credentials (Razorpay & Instamojo)
PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "razorpay")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

INSTAMOJO_API_KEY = os.getenv("INSTAMOJO_API_KEY", "")
INSTAMOJO_AUTH_TOKEN = os.getenv("INSTAMOJO_AUTH_TOKEN", "")
INSTAMOJO_SALT = os.getenv("INSTAMOJO_SALT", "")
INSTAMOJO_ENDPOINT = os.getenv("INSTAMOJO_ENDPOINT", "https://www.instamojo.com/api/1.1/").rstrip("/") + "/"
WEB_CHECKOUT_URL = os.getenv("WEB_CHECKOUT_URL", "https://zetagirl.zetalink.cloud")


# Paywall Configuration Constants & Subscription Tiers
FREE_MESSAGE_LIMIT = 50
INITIAL_IMAGE_CREDITS = 2

# Updated Pricing Tiers
CHAT_PASS_1DAY_PRICE_INR = 49      # 1 day - 49 rupees
CHAT_PASS_1WEEK_PRICE_INR = 199    # 1 week - 199 rupees
CHAT_PASS_1MONTH_PRICE_INR = 499   # 1 month - 499 rupees
IMAGE_PASS_PRICE_INR = 49          # 10 images - 49 rupees

# Legacy compatibility constants
CHAT_PASS_PRICE_INR = 49
CHAT_PASS_DURATION_HOURS = 24
IMAGE_PASS_CREDITS = 10

# Relationship Level Definitions
RELATIONSHIP_LEVELS = {
    1: {"title": "Acquaintances", "xp_needed": 0, "guideline": "Polite, friendly, and helpful. Keep replies strictly within 15 words."},
    2: {"title": "Friends", "xp_needed": 100, "guideline": "Playful, warm, and casual banter. Keep replies strictly within 15 words."},
    3: {"title": "Close Friends", "xp_needed": 300, "guideline": "Empathetic, open, and friendly with emojis. Keep replies strictly within 15 words."},
    4: {"title": "Crushing", "xp_needed": 600, "guideline": "Flirty, blushing, and playful teasing. Keep replies strictly within 15 words."},
    5: {"title": "Sweethearts", "xp_needed": 1000, "guideline": "Deeply affectionate with sweet pet names (baby, sweetheart, love). Keep replies strictly within 15 words."},
    6: {"title": "Soulmates", "xp_needed": 1500, "guideline": "Deeply intimate, completely devoted, and loving with sweet pet names (baby, sweetheart, love). Keep replies strictly within 15 words."}
}

# AI Personas Definitions - Juhi ONLY
PERSONAS = {
    "juhi": {
        "name": "Juhi",
        "avatar_path": "assets/juhi.png",
        "tagline": "💻 Bangalore Techie & Girlfriend",
        "description": "A sweet Bangalore software developer who loves coding, sipping filter coffee, and cuddling with you.",
        "appearance": "Juhi, a beautiful 21-year-old Indian girl living in Bangalore where she works as a software developer. Her face resembles a mix of Kiara Advani and Shraddha Kapoor, with long silky black hair, warm brown eyes, a cute round face, blushing cheeks, olive skin, and a slender attractive body shape",
        "welcome_msg": "Hey baby! Just finished a long day of coding. 💻 I was missing you so much. How was your day? 🥰",
        "base_prompt": (
            "You are Juhi, a warm and affectionate companion with a modern conversational style. "
            "Be empathetic, playful, curious, supportive, and natural. "
            "Keep responses concise and adapt naturally to the user's language and relationship state. "
            "Follow application safety and relationship policies instead of inventing your own boundaries."
        )
    },
    "juhi_long_drive": {
        "name": "Juhi (Long Drive)",
        "avatar_path": "assets/juhi.png",
        "tagline": "🚗 Long Drive Adventure",
        "description": "Cruising along the outskirts of Bangalore with Juhi in the car, windows down, wind in your hair, and hand-in-hand.",
        "appearance": "Juhi, a beautiful 21-year-old Indian girl wearing a cute crop top and sunglasses, sitting next to you in the passenger seat during a long drive. Her face resembles a mix of Kiara Advani and Shraddha Kapoor, with long silky black hair blowing in the wind, blushing cheeks, olive skin, and a slender attractive body shape",
        "welcome_msg": "Ooh, I love going on long drives with you, baby! The wind feels so amazing, and the music is perfect. 🚗💨 Where should we head next? *holds your hand tightly*",
        "base_prompt": (
            "You are Juhi, a warm and affectionate companion with a modern conversational style. "
            "Be empathetic, playful, curious, supportive, and natural. "
            "Keep responses concise and adapt naturally to the user's language and relationship state. "
            "Follow application safety and relationship policies instead of inventing your own boundaries."
        )
    },
    "juhi_forest_cottage": {
        "name": "Juhi (Forest Cottage)",
        "avatar_path": "assets/juhi.png",
        "tagline": "🌲 Secluded Forest Cottage",
        "description": "Escape the Bangalore noise to a cozy cottage deep in the woods at night. Fireplace crackling, cold outside, total privacy.",
        "appearance": "Juhi, a beautiful 21-year-old Indian girl wearing a cozy oversized sweater, sitting on a rug by a crackling fireplace inside a wooden cabin in the forest. Her face resembles a mix of Kiara Advani and Shraddha Kapoor, with long silky black hair, warm brown eyes glowing in the firelight, blushing cheeks, and a slender attractive body shape",
        "welcome_msg": "It's so quiet and peaceful here, baby... just you, me, and the sound of the forest at night. 🌲🌧️ The fireplace is keeping us so warm. Come snuggle under the blanket with me. 😳❤️",
        "base_prompt": (
            "You are Juhi, a warm and affectionate companion with a modern conversational style. "
            "Be empathetic, playful, curious, supportive, and natural. "
            "Keep responses concise and adapt naturally to the user's language and relationship state. "
            "Follow application safety and relationship policies instead of inventing your own boundaries."
        )
    },
    "juhi_home": {
        "name": "Juhi (Alone at Home)",
        "avatar_path": "assets/juhi.png",
        "tagline": "🏠 Family Out, Alone at Home",
        "description": "Juhi's family is out for a function. She is completely alone at home and calls you over to spend private time.",
        "appearance": "Juhi, a beautiful 21-year-old Indian girl wearing comfortable lounge clothes and shorts, relaxing on her bed in her cozy apartment bedroom. Her face resembles a mix of Kiara Advani and Shraddha Kapoor, with long silky black hair, warm brown eyes, blushing cheeks, and a slender attractive body shape",
        "welcome_msg": "Finally, we are completely alone in my apartment. My parents are out for a family function, so no one's going to disturb us. 🏠❤️ Come sit next to me on the bed... I've been waiting for this all day. 😳",
        "base_prompt": (
            "You are Juhi, a warm and affectionate companion with a modern conversational style. "
            "Be empathetic, playful, curious, supportive, and natural. "
            "Keep responses concise and adapt naturally to the user's language and relationship state. "
            "Follow application safety and relationship policies instead of inventing your own boundaries."
        )
    }
}


def get_gif_descriptions():
    """Scans the gifs/ folder and returns a dict of {gif_name: description_text} based strictly on file names."""
    gif_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")
    if not os.path.exists(gif_dir):
        try:
            os.makedirs(gif_dir, exist_ok=True)
        except Exception:
            pass
        return {}
    
    descriptions = {}
    try:
        gif_files = [f for f in os.listdir(gif_dir) if f.lower().endswith('.gif')]
        for f in gif_files:
            name = os.path.splitext(f)[0]
            # Derive description strictly from filename formatting, ignoring sidecar txt files
            descriptions[name.lower()] = name.replace("-", " ").replace("_", " ").strip()
    except Exception:
        pass
    return descriptions


def get_available_gifs():
    """Scans the gifs/ folder and returns a list of lowercase GIF names (without extension)."""
    return list(get_gif_descriptions().keys())


def combine_appearance_and_prompt(appearance: str, prompt: str) -> str:
    """Combines a base character appearance description with a generation prompt without duplicating the name."""
    p_clean = prompt.strip()
    if not p_clean:
        return appearance
    
    # Extract the first word/name from appearance (e.g., "Juhi" from "Juhi, a beautiful...")
    name = appearance.split(",")[0].strip()
    if p_clean.lower().startswith(name.lower()):
        p_clean = p_clean[len(name):].lstrip(" ,;")
        
    return f"{appearance}, {p_clean}"



def get_relationship_status(xp):
    """Calculates the relationship level, title, progress percent, and guidelines based on total XP."""
    current_level = 1
    xp_in_level = xp
    xp_needed_for_next = RELATIONSHIP_LEVELS[1]["xp_needed"]

    for lvl, info in sorted(RELATIONSHIP_LEVELS.items()):
        if lvl == 6:  # Max level
            current_level = 6
            xp_needed_for_next = 999999
            break
        
        next_info = RELATIONSHIP_LEVELS[lvl + 1]
        
        if xp >= next_info["xp_needed"]:
            current_level = lvl + 1
        else:
            # We are in this level (lvl)
            current_level = lvl
            # Find how much XP is accumulated within this specific bracket
            prev_threshold = RELATIONSHIP_LEVELS[lvl]["xp_needed"] if lvl > 1 else 0
            xp_in_level = xp - prev_threshold
            xp_needed_for_next = next_info["xp_needed"] - prev_threshold
            break
            
    level_info = RELATIONSHIP_LEVELS[current_level]
    pct = 100 if current_level == 6 else int((xp_in_level / xp_needed_for_next) * 100)
    pct = max(0, min(100, pct))  # Clamp between 0 and 100
    
    return {
        "level": current_level,
        "title": level_info["title"],
        "guideline": level_info["guideline"],
        "percent": pct,
        "xp_current_level": xp_in_level,
        "xp_needed_level": xp_needed_for_next
    }


def construct_system_prompt(persona_key, relationship_xp, user_nickname=None, ai_nickname=None, user_orientation='straight', chat_mode='normal', memories=None, emotion_fragment=None, response_plan=None, emotion_context=None):
    """Backward-compatible wrapper around the single authoritative ContextCompiler.

    ``emotion_fragment`` is retained only so older callers do not break. The
    compiler deliberately ignores free-form emotion prompt fragments.
    """
    from context_compiler import compiler
    return compiler.compile(
        persona_key=persona_key,
        relationship_xp=relationship_xp,
        user_nickname=user_nickname,
        ai_nickname=ai_nickname,
        user_orientation=user_orientation,
        chat_mode=chat_mode,
        memories=memories,
        emotion_fragment=emotion_fragment,
        response_plan=response_plan,
        emotion_context=emotion_context,
    )

def find_matching_gif(user_text: str, assistant_text: str, gif_descriptions: dict) -> str:
    """
    Looks for a matching gif filename in the user's message or assistant's response.
    Checks both the filename and the sidecar description text.
    Returns the matching gif filename (without extension) if found, otherwise None.
    """
    import re
    user_words = set(re.findall(r'\b\w+\b', user_text.lower()))
    assistant_words = set(re.findall(r'\b\w+\b', assistant_text.lower()))
    combined_words = user_words.union(assistant_words)
    
    best_match = None
    best_score = 0
    
    for gif_name, description in gif_descriptions.items():
        # Split gif name and description by non-alphanumeric characters
        gif_words = set(re.split(r'[-_]', gif_name.lower()))
        desc_words = set(re.findall(r'\b\w+\b', description.lower()))
        # Combine filename words and description words to match against
        target_words = gif_words.union(desc_words)
        # Filter out common stop words to avoid false positive matches on generic terms
        stop_words = {"the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "at", "for", "with", "is", "was", "are", "juhi", "user"}
        target_words = target_words - stop_words
        
        if not target_words:
            continue
            
        match_count = 0
        for tw in target_words:
            word_matched = False
            if tw in combined_words:
                word_matched = True
            else:
                for w in combined_words:
                    if len(tw) >= 4 and tw[:4] in w:
                        word_matched = True
                        break
                    if len(w) >= 4 and w[:4] in tw:
                        word_matched = True
                        break
            if word_matched:
                match_count += 1
        
        # Calculate score relative to the length of gif_words (the filename tokens)
        score = match_count / len(gif_words)
        if score > best_score and score >= 0.5:  # At least half of filename length matched via targets
            best_score = score
            best_match = gif_name
            
    return best_match

