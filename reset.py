from models.config import conn

def delete_tables():
    with conn.cursor() as cur:
        cur.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'TRUNCATE TABLE public.' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
            END LOOP;
        END $$;
        """)
    conn.commit()
    print('✅ All tables truncated')

if __name__ == "__main__":
    delete_tables()
