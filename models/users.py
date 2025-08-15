def create_users(conn):
    with conn.cursor() as cur:
        cur.execute("""
           CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username TEXT,
    email TEXT UNIQUE NOT NULL,
    password TEXT,  -- allow NULL for Google users
    is_google_user BOOLEAN DEFAULT FALSE,
    google_id TEXT,
    profile_picture TEXT,  -- optional but often useful
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
#         cur.execute("""
# ALTER TABLE users ALTER COLUMN username DROP NOT NULL;
# """)
    conn.commit()



