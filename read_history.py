import sqlite3
import sys

# Set standard output encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('girlfriend.db')
cursor = conn.cursor()

try:
    cursor.execute('SELECT role, message FROM chat_history ORDER BY id DESC LIMIT 15')
    rows = cursor.fetchall()
    print("Recent Conversation Turns (Latest first):\n")
    for r in rows:
        print(f"[{r[0].upper()}]: {r[1]}")
        print("-" * 40)
except Exception as e:
    print("Error reading table:", e)
finally:
    conn.close()
