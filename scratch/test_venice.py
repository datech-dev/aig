import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

VENICE_API_KEY = os.getenv("VENICE_API_KEY")
VENICE_MODEL = os.getenv("VENICE_MODEL", "gemma-4-uncensored")

print("Key:", VENICE_API_KEY)
print("Model:", VENICE_MODEL)

client = AsyncOpenAI(
    api_key=VENICE_API_KEY,
    base_url="https://api.venice.ai/api/v1"
)

async def test_chat():
    try:
        response = await client.chat.completions.create(
            model=VENICE_MODEL,
            messages=[
                {"role": "system", "content": "You are Juhi, a sweet AI girlfriend."},
                {"role": "user", "content": "Hey Juhi! How are you?"}
            ]
        )
        print("Success! Response:")
        print(response.choices[0].message.content)
    except Exception as e:
        print("Venice API Error:", e)

if __name__ == "__main__":
    asyncio.run(test_chat())
