# ============================================================================
# DATABASE CONNECTOR - SQLAlchemy ORM & Database Models
# ============================================================================

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Float, Boolean, ForeignKey, JSON, inspect
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Database Setup
Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./vault_v5.db')

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(Base):
    """User account model for authentication."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default='User')
    scan_progress = Column(Integer, default=0)
    scan_status = Column(String, default='Idle')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Hub(Base):
    """Code repository/project hub model."""
    __tablename__ = 'hubs'
    
    id = Column(Integer, primary_key=True)
    hash_key = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    repo_url = Column(String)
    code_snippet = Column(Text)
    embedding_vector = Column(JSON)  # Store embedding as JSON
    complexity_score = Column(Float, default=0.0)
    indexed_at = Column(DateTime, default=datetime.now)

class ChatMessage(Base):
    """Chat conversation history model."""
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

class SearchHistory(Base):
    """Query/search history for analytics."""
    __tablename__ = 'search_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    query = Column(String)
    results_count = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.now)

class FileMetadata(Base):
    """Uploaded file metadata."""
    __tablename__ = 'file_metadata'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    filename = Column(String)
    file_type = Column(String)
    size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.now)

class Satellite(Base):
    """Code metrics and complexity analysis."""
    __tablename__ = 'satellites'
    
    id = Column(Integer, primary_key=True)
    hub_hash = Column(String, ForeignKey('hubs.hash_key'))
    metrics = Column(JSON)  # Store metrics as JSON

class KeyPool(Base):
    """Global API credentials management."""
    __tablename__ = 'key_pool'
    
    id = Column(Integer, primary_key=True)
    provider = Column(String)  # 'GROQ', 'OPENROUTER', etc.
    key_value = Column(String)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

# ============================================================================
# DATABASE INITIALIZATION & MIGRATION
# ============================================================================

def get_engine():
    """Create and return database engine."""
    if DATABASE_URL.startswith('sqlite'):
        engine = create_engine(
            DATABASE_URL,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return engine

def init_db():
    """Initialize database and create all tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine

def get_session():
    """Get a database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def run_migrations():
    """Run database migrations."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

def get_schema_diagnostics(engine):
    """Get database schema diagnostics."""
    try:
        # Check if database file exists
        if 'sqlite' in DATABASE_URL:
            db_file = DATABASE_URL.replace('sqlite:///', '')
            file_exists = os.path.exists(db_file)
        else:
            file_exists = True
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        return {
            'file_exists': file_exists,
            'file_path': DATABASE_URL,
            'tables_created': True,
            'tables': tables
        }
    except Exception as e:
        return {
            'file_exists': False,
            'file_path': DATABASE_URL,
            'error': str(e)
        }
