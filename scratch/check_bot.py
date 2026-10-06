import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print("Bot Token:", TOKEN)

async def check_bot():
    url_me = f"https://api.telegram.org/bot{TOKEN}/getMe"
    url_webhook = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url_me) as resp:
            print("--- getMe Response ---")
            print(f"Status: {resp.status}")
            print(await resp.text())
            
        async with session.get(url_webhook) as resp:
            print("\n--- getWebhookInfo Response ---")
            print(f"Status: {resp.status}")
            print(await resp.text())

if __name__ == "__main__":
    asyncio.run(check_bot())
