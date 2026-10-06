import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import bot
import config
import database

print("Testing bot startup locally...")
print("Bot Token:", config.TELEGRAM_BOT_TOKEN)

async def main():
    database.init_db()
    print("Database initialized.")
    app = bot.Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    await app.initialize()
    await app.start()
    print("Bot initialized and started successfully.")
    
    try:
        updates = await app.bot.get_updates(limit=1)
        print(f"Successfully fetched {len(updates)} pending updates from Telegram!")
        for u in updates:
            print("Update details:", u.to_dict())
    except Exception as e:
        print("Error fetching updates:", e)
        
    await app.stop()
    await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
