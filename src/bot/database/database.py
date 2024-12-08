# database.py
import os
from datetime import date, datetime
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import func
from typing import Any, Dict, Generator, Optional

from bot.database.models import Base, User, Session, Message

class DatabaseConnection:
    def __init__(self, url: Optional[str] = None, **engine_kwargs: Dict[str, Any]):
        database_url = url or os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL must be provided either through environment variable or constructor")

        self.engine = create_engine(database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def get_db(self) -> Generator:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

# Create default instance only if DATABASE_URL is set
conn = DatabaseConnection() if os.getenv("DATABASE_URL") else None

def get_user(user_id: int):
    with conn.get_db() as db:
        return db.query(User).filter(User.user_id == user_id).first()

def add_user(user_id: int):
    with conn.get_db() as db:
        if not db.query(User).filter(User.user_id == user_id).first():
            user = User(user_id=user_id, last_reset=date.today())
            db.add(user)
            db.commit()

def reset_daily_tokens(user_id: int):
    with conn.get_db() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.daily_tokens_used = 0
            user.last_reset = date.today()
            db.commit()

def update_tokens(user_id: int, tokens: int):
    with conn.get_db() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.tokens_used += tokens

            if user.last_reset < date.today():
                user.daily_tokens_used = 0
                user.last_reset = date.today()
            
            user.daily_tokens_used += tokens
            db.commit()

def start_new_session(user_id: int) -> int:
    with conn.get_db() as db:
        session = Session(user_id=user_id, start_date=date.today())
        db.add(session)
        db.commit()
        return session.id

def get_current_session_id(user_id: int) -> int:
    with conn.get_db() as db:
        session = db.query(Session).filter(
            Session.user_id == user_id,
            Session.end_date.is_(None)
        ).first()
        
        if session:
            return session.id
        else:
            return start_new_session(user_id)

def save_session_message(user_id: int, session_id: int, role: str, content: str, compute_embedding: bool = True):
    from bot.llm import get_embedding
    with conn.get_db() as db:
        embedding = get_embedding(content) if compute_embedding else None
        message = Message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            embedding=embedding
        )
        db.add(message)
        db.commit()

def get_session_messages(session_id: int, include_system_message: bool = True) -> list[dict]:
    """
    Get all messages for a specific session.
    
    Args:
        session_id: ID of the session to get messages for
        include_system_message: Whether to include system role message at the start
        
    Returns:
        List of message dictionaries with 'role' and 'content' keys
    """
    from bot.bot_messages import get_assistant_role
    
    with conn.get_db() as db:
        messages = db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.id).all()
        
        result = [{"role": msg.role, "content": msg.content} for msg in messages]
        
        if include_system_message:
            result.insert(0, {"role": "system", "content": get_assistant_role()})
            
        return result

def get_current_session_messages(user_id: int) -> list[dict]:
    """
    Get all messages for user's current session.
    Includes system role message at the start.
    
    Args:
        user_id: ID of the user
        
    Returns:
        List of message dictionaries with 'role' and 'content' keys
    """
    session_id = get_current_session_id(user_id)
    return get_session_messages(session_id)

def get_user_messages(user_id: int):
    with conn.get_db() as db:
        messages = db.query(Message).filter(
            Message.user_id == user_id,
            Message.embedding.isnot(None)
        ).all()
        return [(msg.content, msg.embedding) for msg in messages]

def clear_session(session_id: int):
    with conn.get_db() as db:
        db.query(Message).filter(Message.session_id == session_id).delete()
        db.query(Session).filter(Session.id == session_id).delete()
        db.commit()

def close_session(user_id: int):
    with conn.get_db() as db:
        session = db.query(Session).filter(
            Session.user_id == user_id,
            Session.end_date.is_(None)
        ).first()
        if session:
            session.end_date = date.today()
            db.commit()
            return session.id
        return None