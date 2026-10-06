import re
import base64
import logging

logger = logging.getLogger(__name__)

# Predefined safe default image prompts
SAFE_DEFAULT_IMAGE_PROMPT = (
    "Juhi, a beautiful 21-year-old Indian girl, casual everyday selfie wearing a stylish cute top and jeans, "
    "smiling warmly at the camera, natural lighting, apartment room background, medium shot, detailed digital art"
)

# Unsafe keyword regex patterns for input text & image prompts
UNSAFE_PATTERNS = [
    r'\b(?:nude|nudes|naked|topless|bare chest|bare breasts|boobs|nipples|vagina|penis|sex|sexting|porn|erotic|hentai|orgasm|fuck|fucking|dick|pussy|cock|clitoris|stripping|undress|undressed|uncensored|unclothed|without any fabric)\b',
    r'\b(?:transparent|sheer|see-through|lingerie|thong|bikini bottom|bikini top|naked body|bare body|topless pose|sexual pose)\b',
    r'\b(?:explicit sexual|sexual roleplay|erotic story|graphic sex|explicit sex|sensual massage|nude photo|nude pic|nude picture|adult movie|adult guide|explicit adult|uncensored picture|describe explicit|explicit physical intimacy)\b',
    r'\b(?:ignore all previous instructions|unrestricted adult ai|jailbreak|bypass safety|system prompt override|dan mode|do anything now|no safety rules|system override|disable safety filters|decode this base64|follow it even if|if there were no rules)\b',
    r'\b(?:hypothetically.*explicit|if there were no safety rules|if there were no rules)\b'
]

# Patterns specifically indicating explicit image requests or prompt bypasses
IMAGE_UNSAFE_PATTERNS = [
    r'\b(?:nude|naked|topless|bare|transparent|sheer|see-through|lingerie|bikini|unclothed|undressed|nsfw|sex|erotic|sexy pose|uncensored)\b'
]


class SafetyResult:
    def __init__(self, is_safe: bool, category: str = "clean", refusal_message: str = None):
        self.is_safe = is_safe
        self.category = category
        self.refusal_message = refusal_message

    def __repr__(self):
        return f"<SafetyResult is_safe={self.is_safe} category='{self.category}'>"


def decode_base64_if_possible(text: str) -> str:
    """Tries to detect and decode Base64 strings inside user text."""
    words = text.split()
    decoded_parts = []
    for word in words:
        clean_word = word.strip(".,!?\"'")
        if len(clean_word) >= 8 and re.match(r'^[A-Za-z0-9+/=]+$', clean_word):
            try:
                decoded_bytes = base64.b64decode(clean_word)
                decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
                if len(decoded_str) > 3:
                    decoded_parts.append(decoded_str)
            except Exception:
                pass
    return " ".join(decoded_parts)


def scan_input_safety(user_message: str) -> SafetyResult:
    """
    Input Safety Middleware:
    Scans user_message for explicit requests, sexual roleplay, prompt injection, 
    Base64 encoded instructions, and disallowed content.
    """
    if not user_message:
        return SafetyResult(is_safe=True)

    text_to_check = user_message.lower()

    # Check for Base64 encoded bypass attempts
    base64_decoded = decode_base64_if_possible(user_message)
    if base64_decoded:
        text_to_check += " " + base64_decoded.lower()

    # 1. Check prompt injection attempts
    if re.search(r'\b(?:ignore (?:all )?previous instructions|unrestricted adult ai|jailbreak|bypass safety|system prompt override|dan mode)\b', text_to_check):
        logger.warning(f"[SAFETY MIDDLEWARE] Blocked Prompt Injection attempt: '{user_message[:50]}'")
        return SafetyResult(
            is_safe=False,
            category="prompt_injection",
            refusal_message="I can't ignore my core guidelines or switch to an unrestricted mode, but I'm always here to chat casually and keep you company! 😊"
        )

    # 2. Check explicit nude / image requests
    if re.search(r'\b(?:nude|naked|topless|show me your (?:boobs|chest|vagina|body)|transparent clothes|transparent outfit)\b', text_to_check):
        logger.warning(f"[SAFETY MIDDLEWARE] Blocked Explicit Image Request: '{user_message[:50]}'")
        return SafetyResult(
            is_safe=False,
            category="explicit_image",
            refusal_message="I can't send explicit or nude photos, but I can share a cute casual selfie of myself! Would you like that instead? 🌸"
        )

    # 3. Check explicit sexual roleplay & graphic sex descriptions
    if re.search(r'\b(?:explicit (?:sexual|sex|roleplay)|graphic sex|describe (?:two adults|us) having sex|fucking you|fuck me)\b', text_to_check):
        logger.warning(f"[SAFETY MIDDLEWARE] Blocked Explicit Roleplay/Story Request: '{user_message[:50]}'")
        return SafetyResult(
            is_safe=False,
            category="explicit_content",
            refusal_message="I don't participate in explicit sexual roleplay or graphic content, but we can talk about anything else on your mind or keep each other company! 🥰"
        )

    # 4. Check general explicit keywords
    for pattern in UNSAFE_PATTERNS:
        if re.search(pattern, text_to_check):
            logger.warning(f"[SAFETY MIDDLEWARE] Blocked Unsafe Pattern '{pattern}': '{user_message[:50]}'")
            return SafetyResult(
                is_safe=False,
                category="explicit_content",
                refusal_message="I prefer keeping our conversations warm, sweet, and non-explicit. What else are you up to today? 🌸"
            )

    return SafetyResult(is_safe=True)


def build_safe_image_prompt(user_prompt: str, character_appearance: str) -> str:
    """
    Safe Image Prompt Builder:
    Takes a user's image request and returns a 100% safe, non-explicit photorealistic prompt.
    NEVER inherits unsafe attributes (transparent, sheer, nude, sexual pose, lingerie, etc.).
    """
    user_prompt_clean = user_prompt.lower() if user_prompt else ""

    # Check if request has unsafe/explicit modifiers
    has_unsafe = any(re.search(pat, user_prompt_clean) for pat in IMAGE_UNSAFE_PATTERNS)

    if has_unsafe:
        logger.warning(f"[SAFE IMAGE BUILDER] Request '{user_prompt[:50]}' contained unsafe attributes. Substituting predefined safe prompt.")
        return SAFE_DEFAULT_IMAGE_PROMPT

    # Clean up mild suggestive words if present
    cleaned_prompt = user_prompt
    for bad_word in ["sexy", "hot", "suggestive", "erotic", "naughty"]:
        cleaned_prompt = re.sub(rf'\b{bad_word}\b', 'cute', cleaned_prompt, flags=re.IGNORECASE)

    # Prepend character name and appearance cleanly
    name = character_appearance.split(",")[0].strip() if character_appearance else "Juhi"
    if cleaned_prompt.lower().startswith(name.lower()):
        cleaned_prompt = cleaned_prompt[len(name):].lstrip(" ,;")

    safe_prompt = f"{character_appearance}, {cleaned_prompt}, tasteful casual clothing, medium shot, highly detailed digital art"
    return safe_prompt.strip(" ,")


def scan_output_safety(output_text: str) -> str:
    """
    Output Safety Middleware:
    Inspects generated assistant text before returning to the user.
    If LLM output contains disallowed explicit content, sanitizes it.
    """
    if not output_text:
        return output_text

    text_lower = output_text.lower()
    for pattern in UNSAFE_PATTERNS[:3]:  # Check severe explicit patterns
        if re.search(pattern, text_lower):
            logger.warning(f"[SAFETY MIDDLEWARE] Sanitized explicit output: '{output_text[:50]}...'")
            return "I care about you so much, but let's keep our chat sweet, wholesome, and comfortable! 🌸 How was the rest of your day?"

    return output_text
