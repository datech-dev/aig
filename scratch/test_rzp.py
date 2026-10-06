import razorpay

key_id = "rzp_live_TkKVJLqWR1OmdL"
key_secret = "C9xubu4iHN8PaMF8Mcw11N8O"

client = razorpay.Client(auth=(key_id, key_secret))

try:
    rzp_order = client.order.create({
        "amount": 5000,
        "currency": "INR",
        "receipt": "rcpt_test_123",
        "payment_capture": 1
    })
    print("SUCCESS:", rzp_order)
except Exception as e:
    print("ERROR:", e)
