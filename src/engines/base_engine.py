from abc import ABC, abstractmethod
from functools import wraps
from typing import Callable, Any

class EngineConnectionError(Exception):
    """Raised when an engine operation is called while disconnected."""
    pass

def require_connection(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to ensure the engine is connected before executing a method.
    Checks `self.is_connected` or `self._is_connected`.
    """
    @wraps(func)
    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        # Checks the public property or fallback internal attribute
        is_connected = getattr(self, "is_connected", getattr(self, "_is_connected", False))
        
        # Handle cases where is_connected might be a callable method
        if callable(is_connected):
            is_connected = is_connected()

        if not is_connected:
            raise EngineConnectionError(
                f"Cannot execute '{func.__name__}': {self.__class__.__name__} is not connected. "
                "Call 'connect()' first."
            )
        
        return func(self, *args, **kwargs)
    
    return wrapper

class BaseEngine(ABC):
    def __init__(self):
        self._is_connected: bool = False

    @property
    def is_connected(self) -> bool:
        """Base implementation returning connection status flag."""
        return self._is_connected

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    # --- Template Methods (Public API with enforced connection check) ---

    @require_connection
    def insert(self,  data: Any) -> Any:
        return self._insert(data)

    @require_connection
    def delete_record(self, record_id:str) -> Any:
        return self._delete_record(record_id)

    @require_connection
    def delete_filter(self, filter:str) -> Any:
        return self._delete_filter(filter)

    @require_connection
    def get_by_id(self, record_id:str) -> Any:
        return self._get_by_id(record_id)

    # --- Internal Abstract Hooks (Overridden by concrete backends) --- 
    
    @abstractmethod
    def _insert(self, data: Any) -> Any:
        pass

    @abstractmethod
    def _delete_record(self, record_id:str) -> Any:
        pass

    @abstractmethod
    def _delete_filter(self, filter:str) -> Any:
        pass

    @abstractmethod
    def _get_by_id(self, record_id:str) -> Any:
        pass

    # --- Context Manager Protocol ---

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()

