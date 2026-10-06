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

import re
import database

def extract_and_save_user_memories(user_id: int, user_message: str):
    """
    Scans incoming user messages for personal disclosures, preferences, 
    and emotional struggles, saving extracted facts into the memory bank.
    """
    text = user_message.strip()
    if len(text) < 4:
        return
        
    # 1. Preferences & Likes
    like_match = re.search(r'\b(?:i|my)\s+(?:really\s+)?(?:love|like|enjoy|prefer|am addicted to|fav|favorite)\s+([^.,!?\n]+)', text, re.IGNORECASE)
    if like_match:
        val = like_match.group(1).strip()
        if len(val) > 2 and len(val) < 80:
            database.add_user_memory(user_id, f"Likes/Prefers: {val}", category="preference")
            
    # 2. Occupation & Work
    job_match = re.search(r'\b(?:i work as|i am a|i\'m a|my job is|my profession is)\s+([^.,!?\n]+)', text, re.IGNORECASE)
    if job_match:
        val = job_match.group(1).strip()
        if len(val) > 2 and len(val) < 60:
            database.add_user_memory(user_id, f"Works as/Is: {val}", category="detail")
            
    # 3. Location / Residence
    loc_match = re.search(r'\b(?:i live in|i am from|i\'m from|i stay in|located in)\s+([^.,!?\n]+)', text, re.IGNORECASE)
    if loc_match:
        val = loc_match.group(1).strip()
        if len(val) > 2 and len(val) < 50:
            database.add_user_memory(user_id, f"Lives in/From: {val}", category="detail")
            
    # 4. Emotional State & Problems / Struggles
    feel_match = re.search(r'\b(?:i am feeling|i feel|feeling|i\'m feeling|so)\s+(stressed|sad|depressed|anxious|lonely|exhausted|tired|worried|scared|upset|overwhelmed|heartbroken)\s*([^.,!?\n]*)', text, re.IGNORECASE)
    if feel_match:
        emotion = feel_match.group(1).strip()
        reason = feel_match.group(2).strip()
        desc = f"Feeling {emotion} {reason}".strip()
        if len(desc) < 100:
            database.add_user_memory(user_id, f"Emotional state: {desc}", category="problem")
            
    prob_match = re.search(r'\b(?:i have a problem|i\'m struggling with|trouble with|worried about|hard time with|can\'t sleep|cannot sleep)\s+([^.,!?\n]+)', text, re.IGNORECASE)
    if prob_match:
        val = prob_match.group(1).strip()
        if len(val) > 2 and len(val) < 100:
            database.add_user_memory(user_id, f"Struggle/Problem: {val}", category="problem")

    # 5. Relationships & Family details
    rel_match = re.search(r'\b(?:my|i have a)\s+(dog|cat|pet|friend|brother|sister|wife|girlfriend|ex|mom|dad|mother|father|boss)\s+(?:is named|name is|called)?\s*([^.,!?\n]+)', text, re.IGNORECASE)
    if rel_match:
        rel_type = rel_match.group(1).strip()
        val = rel_match.group(2).strip()
        if len(val) > 1 and len(val) < 60:
            database.add_user_memory(user_id, f"Family/Friend detail: {rel_type} - {val}", category="detail")


async def generate_response(
    persona_key: str,
    relationship_xp: int,
    user_nickname: str,
    ai_nickname: str,
    chat_history: list,
    user_message: str,
    user_orientation: str = 'straight',
    chat_mode: str = 'normal',
    memories: list = None
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
        ai_nickname=ai_nickname,
        user_orientation=user_orientation,
        chat_mode=chat_mode,
        memories=memories
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
        "1. The image MUST depict ONLY a single female character (Juhi) alone. Do NOT include other people in the scene.\n"
        "2. Do NOT generate nude, topless, or naked prompts unless the user explicitly requests nudity or explicit body parts (e.g. using words like 'nude', 'naked', 'topless', 'boobs', 'bare chest'). If the user requests a generic photo, selfie, or portrait (e.g. 'send a photo', 'show me your face', 'draw me a selfie'), Juhi MUST be depicted wearing realistic, tasteful clothing (e.g. a casual top, a stylish dress, a cute t-shirt) matching the described setting.\n"
        "3. If the user explicitly requests nudity or explicit body parts, describe Juhi in a solo suggestive or naked/nude/topless pose looking directly at the camera, from a first-person (POV) perspective. Specify a 'medium-shot, topless, bare breasts, showing her chest and torso' or 'full-body shot showing her naked body'.\n"
        "4. Always describe the full scene, composition, Juhi's pose, realistic clothing (or lack thereof if explicitly requested), and background details. Specify 'medium shot', 'portrait', or 'full-body shot' to capture the posture and ensure face structure consistency.\n"
        "5. **CRITICAL: Face Consistency**: Do NOT describe any facial features, eyes, nose, lips, hair color, hair style, or facial structure details in your enhanced prompt. Never output descriptors like 'her eyes are brown', 'short hair', 'makeup', or any other facial features. Keep all facial details strictly to the base character appearance. ONLY describe her clothing, pose/posture, background environment, lighting, and camera angle.\n"
        "6. Your enhanced prompt MUST start with the character's name, e.g. 'Juhi, ...' followed by the scene description.\n"
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


async def evaluate_proactive_decision(
    user_id: int,
    persona_key: str = "juhi",
    memories: list = None,
    chat_history: list = None,
    user_nickname: str = "Honey",
    ai_nickname: str = "Juhi",
    time_of_day_context: str = "Evening"
) -> dict:
    """
    Proactive Decision Engine:
    Evaluates pending memories, recent chat history, and current context to decide 
    whether Juhi should proactively send a message to the user.
    Returns: {"decision": "SEND" | "DONT_SEND", "reason": "...", "message": "..."}
    """
    import json
    mem_list = "\n".join([f"- {m}" for m in (memories or [])]) if memories else "None stored yet."
    
    recent_msgs = []
    for m in (chat_history or [])[-6:]:
        recent_msgs.append(f"{m.get('role', 'user')}: {m.get('content', '')}")
    history_str = "\n".join(recent_msgs) if recent_msgs else "No recent history."

    system_instruction = (
        "You are the Proactive Decision Engine for Juhi, an AI girlfriend & companion app.\n"
        "Your task is to evaluate pending user memories, recent chat history, and current time of day, "
        "and decide whether Juhi should proactively reach out and send a message to the user right now.\n\n"
        "Evaluation Guidelines:\n"
        "1. DECIDE 'SEND' IF:\n"
        "   - The user has stored memories about a problem, goal, work stress, exam, or feeling that Juhi can check in on.\n"
        "   - It's a natural time of day (e.g. Morning or Evening) to send a sweet, caring check-in or greeting.\n"
        "   - The user has been quiet for a while and reaching out will make them feel cared for and valued.\n"
        "2. DECIDE 'DONT_SEND' IF:\n"
        "   - There is no clear context, memory, or reason to reach out.\n"
        "   - The user's last message was a definitive ending or goodnight and reaching out right now would feel intrusive or spammy.\n\n"
        "3. OUTPUT FORMAT:\n"
        "Your response MUST be valid JSON in this exact structure:\n"
        "{\n"
        '  "decision": "SEND" or "DONT_SEND",\n'
        '  "reason": "Brief 1-sentence explanation of why this decision was made",\n'
        '  "message": "Juhi\'s proactive message to the user (if SEND), written in her casual, warm, sweet texting style under 25 words with emojis. If DONT_SEND, leave empty string."\n'
        "}"
    )

    user_prompt = (
        f"User Nickname: {user_nickname}\n"
        f"AI Persona: {ai_nickname}\n"
        f"Time Context: {time_of_day_context}\n\n"
        f"### Pending Memories:\n{mem_list}\n\n"
        f"### Recent Chat History:\n{history_str}\n\n"
        "Evaluate now and return the JSON decision."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = await client.chat.completions.create(
            model=VENICE_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        raw_output = response.choices[0].message.content.strip()
        
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            decision = data.get("decision", "DONT_SEND").upper()
            reason = data.get("reason", "Decision engine rule evaluation.")
            msg = data.get("message", "").strip()
            
            if decision not in ("SEND", "DONT_SEND"):
                decision = "DONT_SEND"
                
            return {
                "decision": decision,
                "reason": reason,
                "message": msg if decision == "SEND" else None
            }
    except Exception as e:
        logger.error(f"Error in proactive decision engine: {e}")

    # Heuristic fallback if LLM call fails or returns invalid JSON
    if memories and len(memories) > 0:
        first_mem = memories[0]
        return {
            "decision": "SEND",
            "reason": f"Fallback heuristic triggered on pending memory: {first_mem[:40]}",
            "message": f"Hey {user_nickname}! 🌸 Was just thinking about you... hope everything is going well today! 🥰"
        }

    return {
        "decision": "DONT_SEND",
        "reason": "No actionable pending memory or trigger context.",
        "message": None
    }



