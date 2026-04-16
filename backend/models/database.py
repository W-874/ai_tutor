from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'aitutor.db').as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class SkillNode(Base):
    __tablename__ = "skill_nodes"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    parent_ids = Column(JSON)
    doc_id = Column(String, index=True)
    status = Column(String, default="locked")
    mastery = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class LearningProgress(Base):
    __tablename__ = "learning_progress"
    
    id = Column(String, primary_key=True, index=True)
    node_id = Column(String, index=True)
    study_time = Column(Integer, default=0)
    quiz_scores = Column(JSON, default=list)
    last_visit = Column(DateTime, default=datetime.utcnow)
    mastery = Column(Float, default=0.0)

class QuizRecord(Base):
    __tablename__ = "quiz_records"
    
    id = Column(String, primary_key=True, index=True)
    node_id = Column(String, index=True)
    questions = Column(JSON)
    answers = Column(JSON)
    score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
