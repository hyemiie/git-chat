def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.repo_names (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                repo_name TEXT NOT NULL,
                repo_link TEXT NOT NULL,
                date_created TEXT
            );
        """)
    conn.commit()
