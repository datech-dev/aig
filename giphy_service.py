"""
giphy_service.py - GIPHY API Integration for Juhi AI
Fetches contextual reaction GIFs from GIPHY with smart mood mapping and local caching
for seamless mobile delivery.
"""

import os
import re
import random
import urllib.request
import urllib.parse
import json
import logging
from typing import Optional, Dict

logger = logging.getLogger("giphy_service")

# Default API key provided for Juhi AI
DEFAULT_GIPHY_API_KEY = "TWPWLly8Lf8NmpjQaX3PbFreGjp9zgPJ"
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", DEFAULT_GIPHY_API_KEY)

GIFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")
os.makedirs(GIFS_DIR, exist_ok=True)

# Smart mood mappings to get high-aesthetic, cute & romantic GIFs
MOOD_MAPPINGS = {
    "kiss": [
        "cute couple kiss",
        "romantic kiss",
        "sweet kiss forehead",
        "lip kiss anime cute",
        "kiss love sweet",
    ],
    "lip lock": [
        "romantic lip kiss couple",
        "passionate sweet kiss",
        "romantic couple kiss",
    ],
    "blush": [
        "cute anime blush",
        "shy blushing cute",
        "flustered blush sweet",
        "blush smile cute",
    ],
    "cuddle": [
        "couple cuddle sweet",
        "warm cuddle hug",
        "cute snuggle love",
        "cozy cuddle couple",
    ],
    "hug": [
        "tight warm hug",
        "cute couple hug",
        "comfort hug sweet",
        "anime cute hug",
    ],
    "love": [
        "i love you cute hearts",
        "flying hearts cute",
        "romantic couple love",
        "sweet love romantic",
    ],
    "wink": [
        "cute flirty wink",
        "playful wink smile",
        "anime cute wink",
    ],
    "tease": [
        "playful teasing cute",
        "silly tongue out cute",
        "smug cute laugh",
    ],
    "laugh": [
        "cute laughing girl",
        "happy giggle cute",
        "burst out laughing cute",
    ],
    "miss you": [
        "missing you cute",
        "thinking of you sweet",
        "pout miss you cute",
    ],
    "good morning": [
        "cute good morning sunshine",
        "wake up stretch cute",
        "sweet morning smile",
    ],
    "good night": [
        "sweet dreams good night cute",
        "sleepy cuddle night",
        "tuck in bed cute",
    ],
    "dance": [
        "happy celebration dance cute",
        "silly happy dance cute",
    ],
}

# Cache of recently served GIPHY IDs per user to avoid repeats
_USER_RECENT_GIPHY: Dict[int, list] = {}


def _clean_query(raw_query: str) -> str:
    """Cleans conversation filler phrases from search queries."""
    q = (raw_query or "").lower().strip()
    filler_patterns = [
        r"^(please\s+|plz\s+)?(can\s+you\s+)?(send|show|give|share)\s+(me\s+)?(a\s+)?(gif\s+of\s+|gif\s+|reaction\s+gif\s+|animation\s+of\s+)?",
        r"\b(gif|reaction gif|animation)\b",
        r"\b(juhi|baby|sweetheart)\b",
    ]
    for pattern in filler_patterns:
        q = re.sub(pattern, "", q, flags=re.IGNORECASE).strip()
    return q or "cute romantic"


def get_search_terms(raw_query: str) -> list:
    """Returns candidate search queries ranked for best visual aesthetics."""
    cleaned = _clean_query(raw_query)
    
    # Check mood mapping matches
    for mood, suggestions in MOOD_MAPPINGS.items():
        if mood in cleaned or cleaned in mood:
            return suggestions
            
    # Fallback to cleaned query + cute modifier
    return [f"{cleaned} cute", f"{cleaned} romantic", cleaned]


def search_and_fetch_gif(query: str, user_id: int = 0) -> Optional[Dict[str, str]]:
    """
    Searches GIPHY API for matching GIFs, caches the selected GIF locally
    for legacy client compatibility, and returns metadata with both local gif_name
    and direct CDN gif_url.
    """
    api_key = os.getenv("GIPHY_API_KEY", DEFAULT_GIPHY_API_KEY)
    if not api_key:
        logger.warning("No GIPHY_API_KEY configured.")
        return None

    candidates = get_search_terms(query)
    chosen_search = random.choice(candidates)
    
    encoded_q = urllib.parse.quote(chosen_search)
    url = f"https://api.giphy.com/v1/gifs/search?api_key={api_key}&q={encoded_q}&limit=10&rating=pg-13&lang=en"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "JuhiAI/2.0 (Mobile Assistant)"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                logger.error(f"GIPHY API returned status {response.status}")
                return None
            data = json.loads(response.read().decode("utf-8"))
            items = data.get("data", [])
            
        if not items:
            logger.info(f"No GIPHY results for query '{chosen_search}'")
            return None

        # Filter recently sent GIPHY IDs for this user
        recent_list = _USER_RECENT_GIPHY.setdefault(user_id, [])
        fresh_items = [it for it in items if it.get("id") not in recent_list]
        selected_item = random.choice(fresh_items if fresh_items else items)
        
        gid = str(selected_item.get("id") or "").lower().strip()
        title = selected_item.get("title", chosen_search)
        
        # Prefer fixed_height (200px height, optimized ~200-400KB for mobile)
        images = selected_item.get("images", {})
        fixed_height = images.get("fixed_height", {})
        cdn_url = fixed_height.get("url") or images.get("original", {}).get("url")
        
        if not cdn_url:
            logger.error("No valid image URL in GIPHY payload")
            return None

        # Track recent
        if user_id:
            recent_list.append(gid)
            if len(recent_list) > 15:
                recent_list.pop(0)

        # Cache locally to gifs/giphy_{gid}.gif for backward compatibility with currently installed app
        local_filename = f"giphy_{gid}"
        local_filepath = os.path.join(GIFS_DIR, f"{local_filename}.gif")
        
        if not os.path.exists(local_filepath):
            try:
                dl_req = urllib.request.Request(
                    cdn_url,
                    headers={"User-Agent": "JuhiAI/2.0"}
                )
                with urllib.request.urlopen(dl_req, timeout=6) as dl_resp:
                    with open(local_filepath, "wb") as f:
                        f.write(dl_resp.read())
                logger.info(f"Cached GIPHY GIF locally: {local_filepath}")
            except Exception as dl_err:
                logger.warning(f"Failed to cache GIF locally: {dl_err}. Falling back to CDN only.")

        return {
            "gif_name": local_filename,
            "gif_url": cdn_url,
            "title": title,
        }

    except Exception as e:
        logger.error(f"GIPHY fetch error for '{query}': {e}")
        return None
