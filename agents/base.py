import os
import json
import logging
import threading
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime

class StructuredJSONFormatter(logging.Formatter):
    def format(self, record):
        traceback = None
        if record.exc_info:
            traceback = self.formatException(record.exc_info)
        
        message = record.getMessage()
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        
        log_name_map = {
            "trendanalyst": "trend_analyst",
            "copywriter": "copywriter",
            "factchecker": "fact_checker",
            "publisher": "publisher",
            "daemon": "daemon"
        }
        agent_name = record.name.lower()
        agent_name = log_name_map.get(agent_name, agent_name)
        
        log_entry = {
            "timestamp": timestamp,
            "agent": agent_name,
            "level": record.levelname,
            "message": message,
            "traceback": traceback
        }
        return json.dumps(log_entry, ensure_ascii=False)

_logger_lock = threading.Lock()

class SafeRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # Gracefully handle lock contention during rollover on Windows
            pass

def get_agent_logger(name: str):
    log_name_map = {
        "TrendAnalyst": "trend_analyst",
        "trend_analyst": "trend_analyst",
        "Copywriter": "copywriter",
        "copywriter": "copywriter",
        "FactChecker": "fact_checker",
        "fact_checker": "fact_checker",
        "Publisher": "publisher",
        "publisher": "publisher",
        "daemon": "daemon",
        "Daemon": "daemon"
    }
    file_name = log_name_map.get(name, name.lower())
    
    # Map for camelcase backward compatibility in test suites
    camel_name_map = {
        "trend_analyst": "TrendAnalyst",
        "copywriter": "Copywriter",
        "fact_checker": "FactChecker",
        "publisher": "Publisher",
        "daemon": "daemon"
    }
    camel_name = camel_name_map.get(file_name, name)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    with _logger_lock:
        if not logger.handlers:
            os.makedirs("outputs", exist_ok=True)
            # Add snake_case log handler
            handler1 = SafeRotatingFileHandler(f"outputs/{file_name}.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
            handler1.setFormatter(StructuredJSONFormatter())
            logger.addHandler(handler1)
            
            # Add camelcase log handler for test suite compatibility if names differ
            name_log = f"{camel_name}.log"
            file_name_log = f"{file_name}.log"
            if name_log.lower() != file_name_log.lower():
                handler2 = SafeRotatingFileHandler(f"outputs/{name_log}", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
                handler2.setFormatter(StructuredJSONFormatter())
                logger.addHandler(handler2)
    return logger


class Agent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.logger = get_agent_logger(name)

    def execute(self, context: dict) -> dict:
        """Executes agent-specific tasks, updating and returning the context dictionary."""
        raise NotImplementedError("Each agent must implement the execute method.")

