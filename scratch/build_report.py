import json
import os

with open('scratch/vps_export.json', encoding='utf-8') as f:
    data = json.load(f)['data']

trying = data['trying_users']
abandoned = data['abandoned_checkout_users']
payments = data['all_payments']

artifact_path = r'C:\Users\dhine\.gemini\antigravity-ide\brain\95b0e4aa-98a4-43b3-8fb1-84fdaa2e2379\vps_user_data_export.md'

lines = []
lines.append('# 📊 Complete VPS User & Transaction Report')
lines.append('')
lines.append('**Extracted Directly from Production VPS Database (`girlfriend.db`)**  ')
lines.append(f'*Total Records Extracted:* **{len(trying)} Users** | **{len(abandoned)} Abandoned Links** | **{len(payments)} Payments**')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 📈 Executive Summary')
lines.append(f'- **Total Registered Users Trying App:** {data["total_users"]}')
lines.append(f'- **Total Paying Users:** {data["paying_users"]}')
lines.append(f'- **Completed Payment Transactions:** {data["total_payments"]}')
lines.append(f'- **Total Revenue Generated:** ₹{data["total_revenue_inr"]:.2f} INR')
lines.append(f'- **Abandoned Payment Links (Clicked Pay ₹50 & Left):** {data["abandoned_checkouts_count"]}')
lines.append(f'- **Conversion Rate:** {(data["paying_users"]/data["total_users"]*100):.2f}%')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 💳 Complete Payments History')
if payments:
    lines.append('| Date & Time | User | Telegram Identifier | Amount | Item Type | Payment ID |')
    lines.append('|---|---|---|---|---|---|')
    for p in payments:
        uname = f"@{p['username']}" if p['username'] else f"ID: {p['telegram_id']}"
        fname = p['first_name'] or "User"
        lines.append(f"| {p['created_at']} | {fname} | {uname} | ₹{p['amount_inr']:.2f} | `{p['item_type']}` | `{p['payment_id']}` |")
else:
    lines.append('*No payments recorded.*')

lines.append('')
lines.append('---')
lines.append('')
lines.append('## ⚠️ Users Clicked Pay ₹50 & Left (Payment Link Generated)')
if abandoned:
    lines.append('| Date & Time | User | Telegram Identifier | Amount | Item Type | Payment Link ID |')
    lines.append('|---|---|---|---|---|---|')
    for ab in abandoned:
        uname = f"@{ab['username']}" if ab['username'] else f"ID: {ab['telegram_id']}"
        fname = ab['first_name'] or "User"
        plink = ab.get('payment_link_id') or 'N/A'
        lines.append(f"| {ab['created_at']} | {fname} | {uname} | ₹{ab['amount_inr']:.0f} | `{ab['item_type']}` | `{plink}` |")
else:
    lines.append('*No abandoned checkout links.*')

lines.append('')
lines.append('---')
lines.append('')
lines.append(f'## 📱 All {len(trying)} Users Trying App')
lines.append('')
lines.append('| # | Name | Telegram ID / Handle | Joined Date & Time | Msgs Used | Status | Credits |')
lines.append('|---|---|---|---|---|---|---|')
for idx, u in enumerate(trying, 1):
    uname = f"@{u['username']}" if u['username'] else f"ID: {u['telegram_id']}"
    fname = (u['first_name'] or "User").replace('|', '\\|')
    sub_status = 'Pass Active ✅' if u['is_chat_subscribed'] else 'Free Trial'
    lines.append(f"| {idx} | {fname} | {uname} | {u['created_at']} | {u['free_messages_used']} | {sub_status} | {u['image_credits']} |")

os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
with open(artifact_path, 'w', encoding='utf-8') as out:
    out.write('\n'.join(lines))

print('Artifact report created successfully at:', artifact_path)
