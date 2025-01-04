# conftest.py
import pytest
from datetime import datetime, date
from sqlalchemy.pool import StaticPool
from bot.database.database import DatabaseConnection
from bot.database.models import User


@pytest.fixture(scope="session", autouse=True)
def test_db():
    """Create and configure the test database."""
    test_db = DatabaseConnection(
        url="sqlite:///:memory:",
        connect_args={
            "check_same_thread": False
        },
        poolclass=StaticPool
    )
    
    # Create tables
    test_db.create_tables()
    
    # Make this database connection the global instance
    import bot.database.database as db_module
    db_module.conn = test_db
    
    return test_db

@pytest.fixture
def db_session(test_db):
    """Provides a clean database session for each test."""
    with test_db.get_db() as session:
        session.begin()  # Create a savepoint
        yield session
        session.rollback()  # Rollback to the savepoint
        session.close()  # Clear session cache

class UniqueIdGenerator:
    def __init__(self):
        self._current = 10000
        
    def __call__(self):
        self._current += 1
        return self._current

@pytest.fixture(scope="session")
def user_id_generator():
    """Generate unique user IDs for tests."""
    return UniqueIdGenerator()