from typing import Optional
from sqlmodel import SQLModel, Field, create_engine
import os


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str
    email: Optional[str] = None


class Preference(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    budget: Optional[str] = None
    destinations: Optional[str] = None  # comma-separated for demo
    activities: Optional[str] = None


def get_engine():
    db_url = os.getenv("DATABASE_URL", "sqlite:///wandergenie.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, echo=False, connect_args=connect_args)


def init_db():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine