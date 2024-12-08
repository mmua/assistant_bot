# migrate.py
import os
import sqlite3
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine
from models import Base

def connect_sqlite():
    sqlite_path = os.getenv("DATABASE_PATH", "./data/bot.db")
    return sqlite3.connect(sqlite_path)

def connect_postgres():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

def migrate_users(sqlite_conn, pg_conn):
    print("Migrating users...")
    cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Get users from SQLite
    cursor.execute("SELECT user_id, token_limit, tokens_used, daily_tokens_used, last_reset FROM users")
    users = cursor.fetchall()
    
    if users:
        execute_values(pg_cursor,
            "INSERT INTO users (user_id, token_limit, tokens_used, daily_tokens_used, last_reset) VALUES %s",
            users
        )
    
    pg_conn.commit()
    print(f"Migrated {len(users)} users")

def migrate_sessions(sqlite_conn, pg_conn):
    print("Migrating sessions...")
    cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    cursor.execute("SELECT rowid, user_id, start_date, end_date FROM sessions")
    sessions = cursor.fetchall()
    
    if sessions:
        execute_values(pg_cursor,
            "INSERT INTO sessions (id, user_id, start_date, end_date) VALUES %s",
            sessions
        )
    
    pg_conn.commit()
    print(f"Migrated {len(sessions)} sessions")

def migrate_messages(sqlite_conn, pg_conn):
    print("Migrating messages...")
    cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    cursor.execute("SELECT id, user_id, session_id, role, content, embedding FROM messages")
    messages = cursor.fetchall()
    
    if messages:
        execute_values(pg_cursor,
            "INSERT INTO messages (id, user_id, session_id, role, content, embedding) VALUES %s",
            messages
        )
    
    # Reset the sequence to the max id
    if messages:
        pg_cursor.execute("""
            SELECT setval('messages_id_seq', (SELECT MAX(id) FROM messages));
        """)
    
    pg_conn.commit()
    print(f"Migrated {len(messages)} messages")

def main():
    # Create PostgreSQL tables
    engine = create_engine(os.getenv("DATABASE_URL"))
    Base.metadata.create_all(engine)
    
    # Connect to both databases
    sqlite_conn = connect_sqlite()
    pg_conn = connect_postgres()
    
    try:
        # Migrate data
        migrate_users(sqlite_conn, pg_conn)
        migrate_sessions(sqlite_conn, pg_conn)
        migrate_messages(sqlite_conn, pg_conn)
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        pg_conn.rollback()
    
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main()