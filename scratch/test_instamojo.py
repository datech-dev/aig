import asyncio
import aiohttp
import json

API_KEY = "332e5911d54ec9867fde77142437f9ec"
AUTH_TOKEN = "8889bed7747e1bab37df435e6e003421"

headers = {
    "X-Api-Key": API_KEY,
    "X-Auth-Token": AUTH_TOKEN,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

async def test_form():
    url = "https://www.instamojo.com/api/1.1/payment-requests/"
    data = aiohttp.FormData()
    data.add_field("purpose", "Juhi AI Pass")
    data.add_field("amount", "50")
    data.add_field("buyer_name", "User")
    data.add_field("email", "user@juhi.ai")
    data.add_field("redirect_url", "https://zetagirl.zetalink.cloud/checkout/instamojo/callback")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as resp:
            print("Status:", resp.status)
            print("Response:", await resp.text())

if __name__ == "__main__":
    asyncio.run(test_form())
