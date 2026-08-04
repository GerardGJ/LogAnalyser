from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field 

class LogLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"
    DEBUG = "DEBUG"

class LogEntry(BaseModel):
    timestamp: datetime = Field(..., description="ISO-8601 UTC timestamp of log event generation")
    level: LogLevel = Field(..., description="Log security level")
    trace_id: str = Field(..., description="Unique correlation ID across distributed services")
    service: str = Field(..., description="Microservice or component emitting the event")
    message: str = Field(..., description="Log payload or stack trace message")

    class Config:
        from_attributes = True