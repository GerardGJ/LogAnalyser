from typing import Any
from abc import ABC, abstractmethod
from src.engines.base_engine import BaseEngine, require_connection

class RelationalEngine(BaseEngine,ABC):

    @require_connection
    def execute_query(self, query: str, params: tuple | None = None) -> Any:
        return self._execute_query(query, params)

    @require_connection
    def get_schema(self, table_name: str | None = None) -> Any:
        return self._get_schema(table_name)

    @abstractmethod 
    def _execute_query(self, query: str, params: tuple | None = None) -> Any:
        pass

    @abstractmethod
    def _get_schema(self, table_name: str | None = None) -> Any:
        pass