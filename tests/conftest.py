# conftest.py
import pytest
from sqlalchemy.pool import StaticPool
from bot.database.database import DatabaseConnection

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

@pytest.fixture
def user_id_generator():
    """Generate unique user IDs for tests."""
    def _generate():
        _generate.current += 1
        return _generate.current
    _generate.current = 10000
    return _generate