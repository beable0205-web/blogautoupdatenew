import os
import json
import pytest
import requests
import time
from agents.pipeline import Pipeline
from agents.daemon import write_status, read_status, run_once

# TC1401: Scenario A - Standard Finance Analysis
def test_tc1401_scenario_a_standard_finance():
    pipeline = Pipeline()
    context = {
        "pdf_path": "tests/resources/sample_agenda.pdf",
        "persona": "economy",
        "source_platform": "daum"
    }
    result = pipeline.run(context)
    
    assert result["published_post_id"] == "naver_post_999"
    assert result["verification_report"]["is_passed"] is True
    
    # Verify individual logs
    for log_name in ["TrendAnalyst", "Copywriter", "FactChecker", "Publisher", "daemon"]:
        assert os.path.exists(f"outputs/{log_name}.log")

# TC1402: Scenario B - Scanned Image Report Processing
def test_tc1402_scenario_b_scanned_report():
    pipeline = Pipeline()
    context = {
        "pdf_path": "tests/resources/scanned_agenda.pdf",
        "persona": "economy",
        "source_platform": "daum"
    }
    result = pipeline.run(context)
    
    assert result["published_post_id"] == "naver_post_999"
    assert "OCR" in result["agenda_brief"]
    assert os.path.exists("visitor_stats.csv")

# TC1403: Scenario C - Trending Topic Reaction
def test_tc1403_scenario_c_trending_reaction():
    pipeline = Pipeline()
    context = {
        "source_platform": "daum",
        "pdf_path": None,  # No PDF, trigger grounding search
        "persona": "economy"
    }
    result = pipeline.run(context)
    
    assert result["published_post_id"] == "naver_post_999"
    assert result["verification_report"]["is_passed"] is True

# TC1404: Scenario D - System Resilience & Self-Healing
def test_tc1404_scenario_d_resilience(monkeypatch):
    # Set up simulated timeout in Gemini Mock
    # We want it to raise Exception on the first call, and then succeed on retry.
    call_count = 0
    fact_check_call_count = 0
    from tests.mocks.mock_gemini import MockModels, MockResponse
    
    original_generate_content = MockModels.generate_content
    
    def mock_generate_with_timeout(self, model, contents, config=None):
        nonlocal call_count, fact_check_call_count
        call_count += 1
        
        prompt_str = ""
        for item in contents:
            if isinstance(item, str):
                prompt_str += " " + item
            else:
                prompt_str += f" {str(item)}"
                
        if "Pass / Fail" in prompt_str:
            fact_check_call_count += 1
            if fact_check_call_count == 1:
                raise Exception("Simulated Gemini API Timeout Error")
                
        return original_generate_content(self, model, contents, config=config)
        
    monkeypatch.setattr(MockModels, "generate_content", mock_generate_with_timeout)
    
    pipeline = Pipeline()
    context = {
        "pdf_path": "tests/resources/sample_agenda.pdf",
        "persona": "economy",
        "source_platform": "daum"
    }
    result = pipeline.run(context)
    
    assert call_count > 1  # Verify it retried
    assert result["published_post_id"] == "naver_post_999"
    assert result["verification_report"]["is_passed"] is True
    
    # Check logs for warning/retry traces
    with open("outputs/FactChecker.log", "r", encoding="utf-8") as f:
        log_content = f.read()
    assert "Attempt 1" in log_content or "failed on attempt 1" in log_content
    assert "Attempt 2" in log_content

# TC1405: Scenario E - Multi-day Daemon Monitoring
def test_tc1405_scenario_e_multi_day_daemon():
    # 1. Daemon started in background
    write_status("running", pid=8888)
    
    # 2. Update visitor stats CSV
    stats_file = "visitor_stats.csv"
    if os.path.exists(stats_file):
        os.remove(stats_file)
        
    import pandas as pd
    df = pd.DataFrame({
        "timestamp": ["2026-06-16 10:00"],
        "blog_id": ["jjangdol0205"],
        "today_visitors": [5],
        "total_visitors": [100]
    })
    df.to_csv(stats_file, index=False)
    
    # 3. Daemon runs scheduler (run-once simulation)
    run_once(pdf_path="tests/resources/sample_agenda.pdf", persona="economy")
    
    # 4. Dashboard endpoints queried
    res_daemon = requests.get("http://localhost:3000/api/daemon")
    res_trend = requests.get("http://localhost:3000/api/agent-trend")
    
    assert res_daemon.status_code == 200
    assert "status" in res_daemon.json()
    assert res_trend.status_code == 200
    assert "trends" in res_trend.json()
