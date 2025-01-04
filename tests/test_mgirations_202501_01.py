# tests/test_migrations.py
import pytest
from datetime import datetime, date
from sqlalchemy import inspect, text
from bot.database.models import (
    User, Session, Message, Task, DailyAnalysis,
    AnalysisInsight, StrategicPoint, SessionTopic, AnalysisTopic,
    MessageSentiment, TaskStatus, TaskPriority
)

@pytest.fixture
def user(db_session, user_id_generator):
    """Create a test user."""
    user = User(
        user_id=user_id_generator(),
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
def daily_analysis(db_session, user):
     """Create a test daily analysis."""
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


class TestMigrations:
    def test_tables_exist(self, db_session):
        """Test that all expected tables are created"""
        inspector = inspect(db_session.bind)
        existing_tables = inspector.get_table_names()
        
        expected_tables = {
            'users',
            'sessions',
            'messages',
            'daily_analyses',
            'tasks',
            'analysis_insights',
            'strategic_points',
            'session_topics',
            'analysis_topics',
            'message_sentiments'
        }
        
        for table in expected_tables:
            assert table in existing_tables, f"Table {table} not found in database"

    def test_table_columns(self, db_session):
        """Test that tables have the correct columns"""
        inspector = inspect(db_session.bind)
        
        # Test DailyAnalysis columns
        columns = {col['name'] for col in inspector.get_columns('daily_analyses')}
        expected_columns = {
            'id', 'user_id', 'date', 'total_messages', 'total_sessions',
            'average_sentiment', 'generated_at', 'morning_brief_sent',
            'morning_brief_content'
        }
        assert expected_columns.issubset(columns)
        
        # Test Task columns
        columns = {col['name'] for col in inspector.get_columns('tasks')}
        expected_columns = {
            'id', 'user_id', 'analysis_id', 'title', 'description',
            'status', 'priority', 'due_date', 'created_at', 'completed_at',
            'is_strategic'
        }
        assert expected_columns.issubset(columns)

    def test_foreign_keys(self, db_session):
        """Test that foreign key constraints are properly set up"""
        inspector = inspect(db_session.bind)
        
        # Test Task foreign keys
        fks = inspector.get_foreign_keys('tasks')
        fk_cols = {fk['constrained_columns'][0] for fk in fks}
        assert 'user_id' in fk_cols
        assert 'analysis_id' in fk_cols
        
        # Test DailyAnalysis foreign keys
        fks = inspector.get_foreign_keys('daily_analyses')
        fk_cols = {fk['constrained_columns'][0] for fk in fks}
        assert 'user_id' in fk_cols

    def test_indexes(self, db_session):
        """Test that expected indexes are created"""
        inspector = inspect(db_session.bind)

        # Verify tables exist first
        existing_tables = inspector.get_table_names()
        assert 'daily_analyses' in existing_tables, "daily_analyses table not found"
        assert 'tasks' in existing_tables, "tasks table not found"

        # Test DailyAnalysis indexes
        indexes = {idx['name']: idx for idx in inspector.get_indexes('daily_analyses')}
        assert 'ix_daily_analyses_user_id_date' in indexes
        
        # Test Task indexes
        indexes = {idx['name']: idx for idx in inspector.get_indexes('tasks')}
        assert 'ix_tasks_user_id' in indexes
        assert 'ix_tasks_due_date' in indexes

    def test_cascade_delete(self, db_session, user_id_generator):
        """Test that CASCADE DELETE constraints work properly"""
        # Create test user
        user = User(
            user_id=user_id_generator(),
            token_limit=1000,
            tokens_used=0,
            daily_tokens_used=0,
            last_reset=date.today()
        )
        db_session.add(user)
        db_session.commit()

        # Create analysis
        analysis = DailyAnalysis(
            user_id=user.user_id,
            date=date.today(),
            generated_at=datetime.now()
        )
        db_session.add(analysis)
        db_session.commit()

        # Create dependent records
        insight = AnalysisInsight(
            analysis_id=analysis.id,
            category="test",
            insight="Test insight",
            importance_score=0.5
        )
        db_session.add(insight)
        db_session.commit()

        # Delete analysis
        db_session.delete(analysis)
        db_session.commit()

        # Verify cascade delete worked
        assert db_session.query(AnalysisInsight).count() == 0

    def test_enums(self, db_session, user_id_generator, daily_analysis):
        """Test that enum types work correctly"""
        task = Task(
            user_id=daily_analysis.user_id,
            analysis_id=daily_analysis.id,
            title="Test Task",
            created_at=datetime.now(),
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH
        )
        db_session.add(task)
        db_session.commit()

        fetched_task = db_session.query(Task).filter_by(id=task.id).first()
        assert fetched_task.status == TaskStatus.PENDING
        assert fetched_task.priority == TaskPriority.HIGH

    def test_json_columns(self, db_session, daily_analysis):
        """Test that JSON columns work correctly"""
        point = StrategicPoint(
            analysis_id=daily_analysis.id,
            timeframe="short_term",
            point="Test point",
            priority=1,
            metrics={"completion": 50, "effort": "medium"}
        )
        db_session.add(point)
        db_session.commit()

        fetched_point = db_session.query(StrategicPoint).filter_by(id=point.id).first()
        assert fetched_point.metrics["completion"] == 50
        assert fetched_point.metrics["effort"] == "medium"

    def test_nullable_constraints(self, db_session, daily_analysis):
        """Test that nullable constraints are enforced"""
        with pytest.raises(Exception):
            task = Task(
                user_id=daily_analysis.user_id,
                analysis_id=daily_analysis.id,
                title=None,  # This should fail as title is non-nullable
                created_at=datetime.now()
            )
            db_session.add(task)
            db_session.commit()

    @pytest.mark.skip("Run only when testing downgrades")
    def test_downgrade(self, db_session):
        """Test the downgrade migration path"""
        # This would depend on your migration framework
        # If using alembic:
        # alembic.command.downgrade('base')
        
        inspector = inspect(db_session.bind)
        assert 'daily_analyses' not in inspector.get_table_names()
        assert 'tasks' not in inspector.get_table_names()