import enum
from sqlalchemy import (
    Column, Index, Integer, String, Date, ForeignKey, Text,
    DateTime, JSON, Enum, Float, Boolean
)
from sqlalchemy.orm import declarative_base, relationship


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
    analyses = relationship("DailyAnalysis", back_populates="user")
    tasks = relationship("Task", back_populates="user")

class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    topics = relationship("SessionTopic", back_populates="session")


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
    sentiment = relationship("MessageSentiment", back_populates="message", uselist=False)


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)
    analysis_id = Column(Integer, ForeignKey('daily_analyses.id', ondelete='CASCADE'))
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    due_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    is_strategic = Column(Boolean, default=False)

    user = relationship("User", back_populates="tasks")
    analysis = relationship("DailyAnalysis", back_populates="tasks")


class DailyAnalysis(Base):
    __tablename__ = 'daily_analyses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)
    date = Column(Date, nullable=False, index=True)
    total_messages = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    average_sentiment = Column(Float)
    generated_at = Column(DateTime, nullable=False)
    morning_brief_sent = Column(Boolean, default=False)
    morning_brief_content = Column(Text, nullable=True)

    user = relationship("User", back_populates="analyses")
    insights = relationship("AnalysisInsight", back_populates="analysis", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="analysis", cascade="all, delete-orphan")
    topics = relationship("AnalysisTopic", back_populates="analysis", cascade="all, delete-orphan")
    strategic_points = relationship("StrategicPoint", back_populates="analysis", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_daily_analyses_user_id_date', 'user_id', 'date'),
    )


class AnalysisInsight(Base):
    __tablename__ = 'analysis_insights'
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey('daily_analyses.id', ondelete='CASCADE'))
    category = Column(String, nullable=False)
    insight = Column(Text, nullable=False)
    importance_score = Column(Float)
    requires_action = Column(Boolean, default=False)

    analysis = relationship("DailyAnalysis", back_populates="insights")

class StrategicPoint(Base):
    __tablename__ = 'strategic_points'
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey('daily_analyses.id', ondelete='CASCADE'))
    timeframe = Column(String)  # 'short_term', 'medium_term', 'long_term'
    point = Column(Text, nullable=False)
    priority = Column(Integer)
    status = Column(String, default='pending')
    metrics = Column(JSON)

    analysis = relationship("DailyAnalysis", back_populates="strategic_points")

class SessionTopic(Base):
    __tablename__ = 'session_topics'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'))
    topic = Column(String, nullable=False)
    confidence_score = Column(Float)
    mention_count = Column(Integer, default=1)

    session = relationship("Session", back_populates="topics")

class AnalysisTopic(Base):
    __tablename__ = 'analysis_topics'
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(Integer, ForeignKey('daily_analyses.id', ondelete='CASCADE'))
    topic = Column(String, nullable=False)
    frequency = Column(Integer)
    importance_score = Column(Float)
    is_trending = Column(Boolean, default=False)

    analysis = relationship("DailyAnalysis", back_populates="topics")

class MessageSentiment(Base):
    __tablename__ = 'message_sentiments'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'))
    sentiment_score = Column(Float)  # -1 to 1
    emotion_labels = Column(JSON)  # e.g., {"joy": 0.8, "frustration": 0.2}
    confidence = Column(Float)

    message = relationship("Message", back_populates="sentiment")