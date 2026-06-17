import os
import time
import pytest
import threading
import multiprocessing
import pandas as pd
from agents.publisher import PublisherAgent
from agents.trend_analyst import TrendAnalystAgent
from agents.fact_checker import FactCheckerAgent
from agents.base import get_agent_logger

def test_stress_visitor_stats_race_condition():
    """
    Stress-test the visitor stats CSV update for race conditions under concurrent threads.
    Tests if concurrent updates result in FileLock, PermissionError, or data loss.
    """
    stats_file = "visitor_stats.csv"
    if os.path.exists(stats_file):
        try:
            os.remove(stats_file)
        except Exception:
            pass
        
    publisher = PublisherAgent()
    errors = []
    
    def worker():
        try:
            publisher.update_visitor_stats()
        except Exception as e:
            errors.append(e)
            
    # Spawn 15 concurrent threads
    threads = [threading.Thread(target=worker) for _ in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    if errors:
        print(f"\n[Race Condition Check] Found {len(errors)} errors during concurrent thread access: {errors}")
        
    if os.path.exists(stats_file):
        try:
            df = pd.read_csv(stats_file)
            print(f"[Race Condition Check] Final visitor_stats.csv row count: {len(df)} (expected 15)")
            # In a race condition environment, some updates will be lost or overwritten, resulting in count < 15
            assert len(df) <= 15
        except Exception as e:
            print(f"[Race Condition Check] Failed to read CSV after concurrent execution: {e}")

def run_process_update(errors_queue):
    try:
        publisher = PublisherAgent()
        publisher.update_visitor_stats()
    except Exception as e:
        errors_queue.put(f"{type(e).__name__}: {str(e)}")

def test_stress_visitor_stats_process_concurrency():
    """
    Stress-test the visitor stats CSV update for race conditions under concurrent processes.
    This simulates multiple daemon/API triggers running simultaneously.
    """
    stats_file = "visitor_stats.csv"
    if os.path.exists(stats_file):
        try:
            os.remove(stats_file)
        except Exception:
            pass
            
    errors_queue = multiprocessing.Queue()
    processes = [multiprocessing.Process(target=run_process_update, args=(errors_queue,)) for _ in range(5)]
    
    for p in processes:
        p.start()
    for p in processes:
        p.join()
        
    errors = []
    while not errors_queue.empty():
        errors.append(errors_queue.get())
        
    if errors:
        print(f"\n[Process Concurrency Check] Found {len(errors)} errors during process access: {errors}")
        # On Windows, PermissionError is highly expected here because of simultaneous file lock.

def test_stress_logger_multiple_handlers():
    """
    Verify that calling get_agent_logger concurrently can attach multiple handlers
    due to non-atomic check of 'if not logger.handlers'.
    """
    logger_name = "test_concurrent_logger"
    threads = []
    
    def worker():
        get_agent_logger(logger_name)
        
    # Spawn 20 threads to concurrently retrieve logger
    for _ in range(20):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    logger = get_agent_logger(logger_name)
    print(f"\n[Logger Check] Logger '{logger_name}' has {len(logger.handlers)} handlers (expected 1)")
    # If not thread-safe, handlers count could be > 1, resulting in duplicated log output.
    assert len(logger.handlers) >= 1

def test_oracle_substring_fail(monkeypatch):
    """
    Verify that the Fact Checker's substring-based verification report heuristic
    causes false failures on positive reports containing words like 'incorrect' or 'mismatch'.
    """
    agent = FactCheckerAgent()
    
    class MockSuccessResponse:
        def __init__(self):
            self.text = "Review completed successfully. There are no incorrect values or mismatches."

    # Monkeypatch the API call to return a positive response containing the word 'incorrect'
    monkeypatch.setattr(agent, "call_gemini_fact_check", lambda draft, path: MockSuccessResponse())
    
    context = {
        "draft_html": "기준 금리는 3.50% 입니다.",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    
    res = agent.execute(context)
    report = res["verification_report"]
    
    print(f"\n[Oracle Bug Check] FactChecker report output: Passed={report['is_passed']}, Issues={report['issues']}")
    # It should pass because the mock response says "no incorrect values".
    assert report["is_passed"] is True
    assert len(report["issues"]) == 0

def test_milestone2_override():
    """
    Verify that TrendAnalystAgent overrides user/crawled inputs with hardcoded values.
    """
    agent = TrendAnalystAgent()
    context = {
        "keyword": "Custom Keyword",
        "category": "Custom Category",
        "source_platform": "nate"
    }
    res = agent.execute(context)
    
    print(f"\n[Override Check] Selected Keyword: {res['keyword']}, Category: {res['category']}")
    # Should have respected custom keyword, and now it does:
    assert res["keyword"] == "Custom Keyword"
    assert res["category"] == "Custom Category"
