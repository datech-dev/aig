import sqlite3

def cleanup():
    conn = sqlite3.connect('girlfriend.db')
    c = conn.cursor()
    
    tables_with_user_id = ['users', 'user_settings', 'chat_history', 'user_memories', 'user_events', 'proactive_logs', 'user_active_persona', 'user_billing']
    
    for t in tables_with_user_id:
        try:
            c.execute(f"DELETE FROM {t} WHERE telegram_id >= 88880000")
            print(f"Cleaned {c.rowcount} test rows from {t}")
        except Exception as e:
            print(f"Skipped {t}: {e}")
            
    conn.commit()
    conn.close()
    print("Database cleanup finished.")

if __name__ == "__main__":
    cleanup()
