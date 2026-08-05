import sys
import logging
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

DUCKDB_PATH = DATA_DIR / "duckdb" / "logdatabase.db"
LOGS_PATH = DATA_DIR / "raw_logs" / "pipeline.log"