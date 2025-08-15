
def create_history_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.chat_history (
                id SERIAL PRIMARY KEY,
                repo_id INTEGER NOT NULL,
                sender_id INTEGER,
                sender_type VARCHAR(10) NOT NULL,
                message_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_order INTEGER NOT NULL
            );
        """)
    conn.commit()
