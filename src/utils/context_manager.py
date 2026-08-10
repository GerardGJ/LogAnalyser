import logging
from contextlib import contextmanager
from typing import Generator, TypeVar
from src.engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)

# Generic type constrained to subclasses of BaseEngine
E = TypeVar("E", bound=BaseEngine)


class EngineContext:
    """
    Context manager wrapper for managing lifecycle and automatic resource
    cleanup for any engine inheriting from BaseEngine.
    """

    def __init__(self, engine: E) -> None:
        self.engine = engine

    def __enter__(self) -> E:
        if not self.engine.is_connected:
            logger.debug(f"Connecting engine: {self.engine.__class__.__name__}")
            self.engine.connect()
        return self.engine

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.engine.is_connected:
            logger.debug(f"Disconnecting engine: {self.engine.__class__.__name__}")
            self.engine.disconnect()

        if exc_type is not None:
            logger.error(
                f"Exception encountered during {self.engine.__class__.__name__} context execution: {exc_val}"
            )
        # Return False to allow standard Python exception propagation
        return False


@contextmanager
def managed_engine(engine: E) -> Generator[E, None, None]:
    """
    Functional generator context manager for engines.
    
    Usage:
        with managed_engine(DuckDBEngine(path)) as db:
            db.execute_query(...)
    """
    try:
        if not engine.is_connected:
            engine.connect()
        yield engine
    finally:
        if engine.is_connected:
            engine.disconnect()