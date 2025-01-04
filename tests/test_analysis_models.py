# tests/test_analysis_models.py
import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import text
from bot.database.models import (
    User, Session, Message, Task, DailyAnalysis,
    AnalysisInsight, StrategicPoint, SessionTopic, AnalysisTopic,
    MessageSentiment, TaskStatus, TaskPriority
)

def clean_table(session, table):
    """Helper to clean a specific table"""
    session.execute(text(f'DELETE FROM {table}'))


def clean_all_tables(session):
    """Clean all tables in correct order"""
    # Define table order for clean deletion
    tables = [
        'message_sentiments',
        'analysis_insights',
        'analysis_topics',
        'strategic_points',
        'tasks',
        'daily_analyses',
        'messages',
        'sessions',
        'users'
    ]
    for table in tables:
        clean_table(session, table)
    session.commit()


@pytest.fixture(autouse=True)
def setup_cleanup(db_session):
    """Setup and cleanup for each test"""
    clean_all_tables(db_session)
    yield
    clean_all_tables(db_session)


@pytest.fixture
def user(db_session, user_id_generator):
    """Create a test user with a unique ID."""
    # First ensure no user exists with this ID
    user_id = user_id_generator()
    existing = db_session.query(User).filter_by(user_id=user_id).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
    
    user = User(
        user_id=user_id,
        token_limit=1000,
        tokens_used=0,
        daily_tokens_used=0,
        last_reset=date.today()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def chat_session(db_session, user):
    session = Session(
        user_id=user.user_id,
        start_date=date.today(),
        end_date=None
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session

@pytest.fixture
def message(db_session, user, chat_session):
    message = Message(
        user_id=user.user_id,
        session_id=chat_session.id,
        role="user",
        content="Test message content"
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message

@pytest.fixture
def daily_analysis(db_session, user):
    analysis = DailyAnalysis(
        user_id=user.user_id,
        date=date.today(),
        total_messages=10,
        total_sessions=2,
        average_sentiment=0.75,
        generated_at=datetime.now(),
        morning_brief_sent=False
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis


class TestAnalysisModels:
    def test_task_creation(self, db_session, user, daily_analysis):
        task = Task(
            user_id=user.user_id,
            analysis_id=daily_analysis.id,
            title="Implement new feature",
            description="Create user authentication system",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            due_date=datetime.now() + timedelta(days=1),
            created_at=datetime.now(),
            is_strategic=True
        )
        db_session.add(task)
        db_session.commit()

        fetched_task = db_session.query(Task).filter_by(id=task.id).first()
        assert fetched_task.title == "Implement new feature"
        assert fetched_task.status == TaskStatus.PENDING
        assert fetched_task.priority == TaskPriority.HIGH
        assert fetched_task.is_strategic is True
        assert fetched_task.user_id == user.user_id

    def test_daily_analysis_creation(self, db_session, user):
        analysis = DailyAnalysis(
            user_id=user.user_id,
            date=date.today(),
            total_messages=5,
            total_sessions=1,
            average_sentiment=0.6,
            generated_at=datetime.now(),
            morning_brief_sent=False,
            morning_brief_content="Today's summary..."
        )
        db_session.add(analysis)
        db_session.commit()

        fetched_analysis = db_session.query(DailyAnalysis).filter_by(id=analysis.id).first()
        assert fetched_analysis.total_messages == 5
        assert fetched_analysis.average_sentiment == 0.6
        assert not fetched_analysis.morning_brief_sent

    def test_analysis_insight_creation(self, db_session, daily_analysis):
        insight = AnalysisInsight(
            analysis_id=daily_analysis.id,
            category="productivity",
            insight="Consistent pattern of deep work in mornings",
            importance_score=0.85,
            requires_action=True
        )
        db_session.add(insight)
        db_session.commit()

        fetched_insight = db_session.query(AnalysisInsight).filter_by(id=insight.id).first()
        assert fetched_insight.category == "productivity"
        assert fetched_insight.importance_score == 0.85
        assert fetched_insight.requires_action is True

    def test_strategic_point_creation(self, db_session, daily_analysis):
        strategic_point = StrategicPoint(
            analysis_id=daily_analysis.id,
            timeframe="medium_term",
            point="Develop expertise in system design",
            priority=2,
            status="in_progress",
            metrics={"completion_rate": 35, "study_hours": 12}
        )
        db_session.add(strategic_point)
        db_session.commit()

        fetched_point = db_session.query(StrategicPoint).filter_by(id=strategic_point.id).first()
        assert fetched_point.timeframe == "medium_term"
        assert fetched_point.priority == 2
        assert fetched_point.metrics["completion_rate"] == 35

    def test_message_sentiment_creation(self, db_session, message):
        sentiment = MessageSentiment(
            message_id=message.id,
            sentiment_score=0.75,
            emotion_labels={"joy": 0.8, "confidence": 0.7},
            confidence=0.9
        )
        db_session.add(sentiment)
        db_session.commit()

        fetched_sentiment = db_session.query(MessageSentiment).filter_by(id=sentiment.id).first()
        assert fetched_sentiment.sentiment_score == 0.75
        assert fetched_sentiment.emotion_labels["joy"] == 0.8
        assert fetched_sentiment.confidence == 0.9

    def test_session_topic_creation(self, db_session, chat_session):
        topic = SessionTopic(
            session_id=chat_session.id,
            topic="machine_learning",
            confidence_score=0.92,
            mention_count=3
        )
        db_session.add(topic)
        db_session.commit()

        fetched_topic = db_session.query(SessionTopic).filter_by(id=topic.id).first()
        assert fetched_topic.topic == "machine_learning"
        assert fetched_topic.confidence_score == 0.92
        assert fetched_topic.mention_count == 3

    def test_analysis_topic_creation(self, db_session, daily_analysis):
        topic = AnalysisTopic(
            analysis_id=daily_analysis.id,
            topic="productivity_tools",
            frequency=7,
            importance_score=0.8,
            is_trending=True
        )
        db_session.add(topic)
        db_session.commit()

        fetched_topic = db_session.query(AnalysisTopic).filter_by(id=topic.id).first()
        assert fetched_topic.topic == "productivity_tools"
        assert fetched_topic.frequency == 7
        assert fetched_topic.is_trending is True

class TestRelationships:
    def test_user_analysis_relationship(self, db_session, user):
        analysis = DailyAnalysis(
            user_id=user.user_id,
            date=date.today(),
            total_messages=3,
            total_sessions=1,
            average_sentiment=0.5,
            generated_at=datetime.now()
        )
        db_session.add(analysis)
        db_session.commit()

        assert len(user.analyses) == 1
        assert user.analyses[0].total_messages == 3

    def test_analysis_insights_relationship(self, db_session, daily_analysis):
        insights = [
            AnalysisInsight(
                analysis_id=daily_analysis.id,
                category="productivity",
                insight=f"Insight {i}",
                importance_score=0.7 + (i/10)
            )
            for i in range(3)
        ]
        db_session.add_all(insights)
        db_session.commit()

        assert len(daily_analysis.insights) == 3
        assert all(isinstance(insight, AnalysisInsight) for insight in daily_analysis.insights)

    def test_message_sentiment_relationship(self, db_session, message):
        sentiment = MessageSentiment(
            message_id=message.id,
            sentiment_score=0.8,
            emotion_labels={"excitement": 0.9},
            confidence=0.85
        )
        db_session.add(sentiment)
        db_session.commit()

        assert message.sentiment is not None
        assert message.sentiment.sentiment_score == 0.8

    def test_cascade_delete(self, db_session, daily_analysis):
        # Add related objects
        insight = AnalysisInsight(
            analysis_id=daily_analysis.id,
            category="test",
            insight="Test insight",
            importance_score=0.5
        )
        topic = AnalysisTopic(
            analysis_id=daily_analysis.id,
            topic="test_topic",
            frequency=1,
            importance_score=0.5
        )
        db_session.add_all([insight, topic])
        db_session.commit()
        db_session.refresh(daily_analysis)
        db_session.refresh(insight)
        db_session.refresh(topic)

        # Delete the analysis
        db_session.delete(daily_analysis)
        db_session.commit()

        # Verify cascading delete
        assert db_session.query(AnalysisInsight).count() == 0
        assert db_session.query(AnalysisTopic).count() == 0