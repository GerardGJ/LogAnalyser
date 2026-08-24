from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"
    DEBUG = "DEBUG"

class LogEntry(BaseModel):
    timestamp: datetime = Field(..., description="ISO-8601 UTC timestamp of log event generation")
    level: LogLevel = Field(..., description="Log severity level")
    app: str = Field(..., description="Application or component emitting the event")
    source_file: str = Field(..., description="Source file reported by the log header")
    line_number: int = Field(..., description="Source line number reported by the log header")
    message: str = Field(..., description="Log payload or stack trace message")
