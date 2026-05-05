import os
from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector

load_dotenv()

with psycopg.connect(os.getenv("DATABASE_URL")) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)

        cur.execute("DROP TABLE IF EXISTS items")
        cur.execute("CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(3))")
        cur.execute("INSERT INTO items (embedding) VALUES (%s::vector), (%s::vector)", ('[1, 2, 3]', '[4, 5, 6]'))

        cur.execute("SELECT id, embedding FROM items ORDER BY embedding <-> %s::vector LIMIT 5", ('[3, 1, 2]',))
        for row in cur.fetchall():
            print(row)

print("Success — pgvector is working from Python")