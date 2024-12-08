from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import date

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True)
    token_limit = Column(Integer)
    tokens_used = Column(Integer, default=0)
    daily_tokens_used = Column(Integer, default=0)
    last_reset = Column(Date)

    sessions = relationship("Session", back_populates="user")
    messages = relationship("Message", back_populates="user")

class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    session_id = Column(Integer, ForeignKey('sessions.id'))
    role = Column(String)
    content = Column(Text)
    embedding = Column(Text, nullable=True)

    user = relationship("User", back_populates="messages")
    session = relationship("Session", back_populates="messages")