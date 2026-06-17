import os
import sys
import threading
import random
import time
import json
import pandas as pd
import re
import pytest

# Add project root to python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.trend_analyst import TrendAnalystAgent
from agents.publisher import PublisherAgent
from agents.pipeline import Pipeline
from agents.base import get_agent_logger
from agents.validation import create_default_context

def test_antidetect_styling_newline_and_casing():
    """
    Stress test HTML antidetect styling.
    Vulnerability: The regex r'<p[^>]*>(.*?)</p>' doesn't match newlines or uppercase tags.
    """
    agent = PublisherAgent()
    
    # 1. Paragraph with newline
    html_with_newline = "<p>\nLine 1\nLine 2\n</p>"
    result_newline = agent.apply_antidetect_styling(html_with_newline)
    # If the regex fails to match, the string remains unchanged
    assert "naver-style-" in result_newline, "Failed to apply antidetect styling to paragraph with newline"

    # 2. Paragraph with uppercase tags
    html_uppercase = "<P>This is uppercase</P>"
    result_uppercase = agent.apply_antidetect_styling(html_uppercase)
    assert "naver-style-" in result_uppercase, "Failed to apply antidetect styling to uppercase tags"


def test_visitor_stats_concurrency():
    """
    Stress test concurrency and race conditions on visitor_stats.csv.
    Spawns multiple threads trying to update visitor_stats.csv simultaneously.
    """
    stats_file = "visitor_stats.csv"
    if os.path.exists(stats_file):
        os.remove(stats_file)
        
    agent = PublisherAgent()
    
    errors = []
    def run_update():
        try:
            # Simulate publisher execution which updates stats
            agent.update_visitor_stats()
        except Exception as e:
            errors.append(e)
            
    threads = [threading.Thread(target=run_update) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    # Check if file exists and has correct number of rows
    assert os.path.exists(stats_file), "visitor_stats.csv was not created"
    
    df = pd.read_csv(stats_file)
    expected_rows = 20
    actual_rows = len(df)
    
    # Check if there were any errors or if updates were lost
    print(f"Stats Concurrency Test: Expected {expected_rows} rows, got {actual_rows} rows. Errors: {len(errors)}")
    
    # Clean up
    if os.path.exists(stats_file):
        os.remove(stats_file)
        
    assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrent visitor stats update: {errors}"
    assert actual_rows == expected_rows, f"Race condition led to data loss: expected {expected_rows} rows, got {actual_rows}"


def test_trend_analyst_hardcoded_override():
    """
    Vulnerability: TrendAnalystAgent completely overrides user inputs.
    """
    agent = TrendAnalystAgent()
    custom_keyword = "Custom Crypto Trend"
    custom_category = "Economy"
    custom_brief = "This is a custom agenda brief"
    
    context = {
        "keyword": custom_keyword,
        "category": custom_category,
        "agenda_brief": custom_brief,
        "source_platform": "daum"
    }
    
    res = agent.execute(context)
    
    assert res["keyword"] == custom_keyword, f"Keyword was overridden: expected {custom_keyword}, got {res['keyword']}"
    assert res["agenda_brief"] == custom_brief, f"Agenda brief was overridden: expected {custom_brief}, got {res['agenda_brief']}"


def test_pipeline_traceback_logging():
    """
    Vulnerability: The pipeline logs error messages but omits exc_info=True,
    causing StructuredJSONFormatter to output 'traceback': null in JSON logs.
    """
    log_file = "outputs/daemon.log"
    if os.path.exists(log_file):
        os.remove(log_file)
        
    pipeline = Pipeline()
    
    # Register an agent that crashes
    class CrashingAgent:
        name = "crashing_agent"
        role = "Crasher"
        def execute(self, ctx):
            raise RuntimeError("Database connection timed out")
            
    pipeline.register(CrashingAgent())
    
    try:
        pipeline.run(create_default_context())
    except RuntimeError:
        pass
        
    assert os.path.exists(log_file), "Daemon log file was not created"
    
    with open(log_file, "r", encoding="utf-8") as f:
        log_lines = f.readlines()
        
    error_log_found = False
    traceback_found = False
    
    for line in log_lines:
        entry = json.loads(line)
        if entry["level"] == "ERROR" and "Database connection timed out" in entry["message"]:
            error_log_found = True
            if entry["traceback"] is not None:
                traceback_found = True
                
    assert error_log_found, "ERROR log entry not found in daemon.log"
    assert traceback_found, "Traceback field was null in JSON logs, hindering debugging"


if __name__ == "__main__":
    print("Running stress tests statically...")
    # Execute manually for quick local diagnostic output if run directly
    try:
        test_antidetect_styling_newline_and_casing()
        print("[PASS] Antidetect styling test")
    except AssertionError as e:
        print(f"[FAIL] Antidetect styling test: {e}")
        
    try:
        test_visitor_stats_concurrency()
        print("[PASS] Visitor stats concurrency test")
    except AssertionError as e:
        print(f"[FAIL] Visitor stats concurrency test: {e}")
        
    try:
        test_trend_analyst_hardcoded_override()
        print("[PASS] Trend Analyst override test")
    except AssertionError as e:
        print(f"[FAIL] Trend Analyst override test: {e}")
        
    try:
        test_pipeline_traceback_logging()
        print("[PASS] Pipeline traceback logging test")
    except AssertionError as e:
        print(f"[FAIL] Pipeline traceback logging test: {e}")
