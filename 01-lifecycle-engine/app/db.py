from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    url = get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    return sessionmaker(engine, expire_on_commit=True)


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
