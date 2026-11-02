from collections.abc import Iterator
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings

_database_resources: dict[
    str,
    tuple[Engine, sessionmaker[Session]],
] = {}

_database_resources_lock = Lock()
_database_disposal_failed = False

def get_database_url() -> str:
    return get_settings().database_url

def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)

def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_database_resources(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    with _database_resources_lock:
        if _database_disposal_failed:
            raise RuntimeError(
                "Database resource disposal previously failed; "
                "retry cleanup successfully before requesting database resources"
            )

        if database_url not in _database_resources:
            engine = create_database_engine(database_url)

            try:
                session_factory = create_session_factory(engine)
            except Exception:
                engine.dispose()
                raise

            _database_resources[database_url] = (engine,session_factory)
        return _database_resources[database_url]

def dispose_database_resources() -> None:
    global _database_disposal_failed

    errors: list[BaseException] = []

    with _database_resources_lock:
        for database_url, (engine, _) in list(_database_resources.items()):
            try:
                engine.dispose()
            except BaseException as exc:
                errors.append(exc)
            else:
                del _database_resources[database_url]

        _database_disposal_failed = bool(errors)

    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("Failed to dispose database resources", errors)

def get_db_session() -> Iterator[Session]:
    database_url = get_database_url()
    _, session_factory = get_database_resources(database_url)

    with session_factory() as session:
        yield session
