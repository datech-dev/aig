import logging
import base64
import httpx
import tempfile
from io import BytesIO
from PIL import Image
from openai import AsyncOpenAI
from config import VENICE_API_KEY, VENICE_MODEL, construct_system_prompt, VENICE_IMAGE_MODEL


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Venice AI client (OpenAI compatible)
# Base URL: https://api.venice.ai/api/v1
# If VENICE_API_KEY is not set, we'll log a warning.
if not VENICE_API_KEY or VENICE_API_KEY == "YOUR_VENICE_API_KEY":
    logger.warning("VENICE_API_KEY is not set or is using the default placeholder. API requests will fail.")

client = AsyncOpenAI(
    api_key=VENICE_API_KEY if VENICE_API_KEY else "dummy_key",
    base_url="https://api.venice.ai/api/v1"
)

async def generate_response(
    persona_key: str,
    relationship_xp: int,
    user_nickname: str,
    ai_nickname: str,
    chat_history: list,
    user_message: str
) -> str:
    """
    Sends the conversation history, user input, and dynamic system prompt to Venice.ai
    and returns the generated response.
    """
    if not VENICE_API_KEY or VENICE_API_KEY == "YOUR_VENICE_API_KEY":
        return (
            "⚠️ Venice.ai API key is missing! Please configure the `VENICE_API_KEY` "
            "variable in the `.env` file of this project to start chatting."
        )

    # 1. Construct the system prompt instructions
    system_instruction = construct_system_prompt(
        persona_key=persona_key,
        relationship_xp=relationship_xp,
        user_nickname=user_nickname,
        ai_nickname=ai_nickname
    )
    
    # 2. Build the message list for Venice API
    messages = [{"role": "system", "content": system_instruction}]
    
    # Add recent history (up to recent 8 messages to optimize token count and save credits)
    for msg in chat_history[-8:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
        
    # Append the new user message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    try:
        # Call the Venice API chat completion
        response = await client.chat.completions.create(
            model=VENICE_MODEL,
            messages=messages,
            temperature=0.85,
            max_tokens=150
        )

        
        # Extract and return response content
        ai_reply = response.choices[0].message.content.strip()
        return ai_reply


    except Exception as e:
        logger.error(f"Error calling Venice AI API: {e}")
        return (
            f"❌ My thoughts are a bit scrambled right now... (API Error: {str(e)[:100]}). "
            "Please check if your Venice.ai API Key is valid or try again in a bit!"
        )


async def generate_image(prompt: str, seed: int = None) -> str:
    """
    Calls the Venice AI image generation API with the configured model.
    Returns the absolute file path to the generated image saved locally.
    """
    if not VENICE_API_KEY or VENICE_API_KEY == "YOUR_VENICE_API_KEY" or VENICE_API_KEY.startswith("VENICE_INFERENCE_KEY_") is False:
        # A simple fallback for dry run testing
        if VENICE_API_KEY == "dummy_key":
            raise ValueError("DUMMY_KEY is active. Image generation skipped.")
        raise ValueError("VENICE_API_KEY is not configured or is invalid.")
        
    url = "https://api.venice.ai/api/v1/image/generate"
    headers = {
        "Authorization": f"Bearer {VENICE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": VENICE_IMAGE_MODEL,
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "negative_prompt": "cartoon, anime, 3d render, drawing, painting, illustration, sketch, low quality, bad anatomy, deformed face, deformed eyes, extra limbs, ugly, unrealistic",
        "return_binary": False,
        "safe_mode": False
    }
    if seed is not None:
        payload["seed"] = (int(seed) % 999999999) + 1

    
    async with httpx.AsyncClient() as httpx_client:
        response = await httpx_client.post(url, headers=headers, json=payload, timeout=60.0)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                error_json = response.json()
                error_msg = error_json.get("error", {}).get("message", error_json.get("error", str(e)))
                logger.error(f"Venice.ai API Error response payload: {error_json}")
            except Exception:
                error_msg = response.text or str(e)
                logger.error(f"Venice.ai API raw error response: {error_msg}")
            raise ValueError(f"Venice.ai: {error_msg}")
        data = response.json()
        
        images = data.get("images", [])
        if not images:
            raise ValueError("No images returned from Venice API.")
            
        base64_str = images[0]
        # Decode base64
        image_data = base64.b64decode(base64_str)
        
        # Load image via Pillow and save as a true PNG to resolve container rendering bugs on Telegram clients
        try:
            image = Image.open(BytesIO(image_data))
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            image.save(temp_file.name, format="PNG")
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Failed to process and convert image to PNG using Pillow: {e}")
            # Fallback to direct write if Pillow fails
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_file.write(image_data)
            temp_file.close()
            return temp_file.name


async def enhance_image_prompt(user_message: str, appearance: str) -> str:
    """
    Uses the Venice AI LLM to expand the user's raw message requesting an image
    into a detailed, explicit, and high-quality prompt suitable for Venice's image model.
    It ensures the prompt specifies the full scene, composition, poses, clothing, and background,
    avoiding just close-up face shots.
    """
    if not VENICE_API_KEY or VENICE_API_KEY == "YOUR_VENICE_API_KEY":
        # Safe fallback
        return f"{appearance}, {user_message}"

    system_instruction = (
        "You are an expert prompt generator for a text-to-image generator (specifically Venice's lustify-v7).\n"
        "Your task is to take a user's raw request for an image and enhance it into a detailed, high-quality, photorealistic prompt.\n\n"
        "Guidelines:\n"
        "1. The image MUST depict ONLY a single female character (Karin) alone. Do NOT include other people in the scene.\n"
        "2. Do NOT generate nude, topless, or naked prompts unless the user explicitly requests nudity or explicit body parts (e.g. using words like 'nude', 'naked', 'topless', 'boobs', 'bare chest'). If the user requests a generic photo, selfie, or portrait (e.g. 'send a photo', 'show me your face', 'draw me a selfie'), Karin MUST be depicted wearing realistic, tasteful clothing (e.g. a casual top, a stylish dress, a cute t-shirt) matching the described setting.\n"
        "3. If the user explicitly requests nudity or explicit body parts, describe Karin in a solo suggestive or naked/nude/topless pose looking directly at the camera, from a first-person (POV) perspective. Specify a 'medium-shot, topless, bare breasts, showing her chest and torso' or 'full-body shot showing her naked body'.\n"
        "4. Always describe the full scene, composition, Karin's pose, realistic clothing (or lack thereof if explicitly requested), and background details. Specify 'medium shot', 'portrait', or 'full-body shot' to capture the posture and ensure face structure consistency.\n"
        "5. Incorporate the character's appearance details naturally and consistently: " + appearance + "\n"
        "6. Your enhanced prompt MUST start with the character's name, e.g. 'Karin, ...' followed by the scene description.\n"
        "7. Output ONLY the final enhanced prompt. Do NOT include any intro, outro, explanations, conversational text, quotes, or markdown code blocks."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"User's request to visualize: '{user_message}'"}
    ]

    try:
        response = await client.chat.completions.create(
            model=VENICE_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=150
        )
        enhanced_prompt = response.choices[0].message.content.strip()

        # Clean up any quotes or code blocks the model might have returned
        if enhanced_prompt.startswith("```") and enhanced_prompt.endswith("```"):
            enhanced_prompt = enhanced_prompt.strip("`").strip()
        enhanced_prompt = enhanced_prompt.replace("Prompt:", "").strip()

        logger.info(f"Enhanced prompt from user message '{user_message}': '{enhanced_prompt}'")
        return enhanced_prompt
    except Exception as e:
        logger.error(f"Error enhancing image prompt: {e}")
        # Fallback to combining the user message directly
        from config import combine_appearance_and_prompt
        return combine_appearance_and_prompt(appearance, user_message)


