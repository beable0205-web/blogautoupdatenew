import os
import json
import pytest
import requests
from agents.trend_analyst import TrendAnalyst
from agents.copywriter import Copywriter
from agents.fact_checker import FactChecker
from agents.publisher import Publisher
from agents.pipeline import Pipeline
from agents.daemon import write_status, read_status

def test_tc1301_trend_to_copywriter():
    # 1. TrendAnalyst runs
    ta = TrendAnalyst()
    context = {"source_platform": "daum"}
    context = ta.execute(context)
    assert context["keyword"] != ""
    
    # 2. Copywriter runs on TrendAnalyst's outputs
    cw = Copywriter()
    context = cw.execute(context)
    assert context["draft_html"] != ""
    assert context["keyword"] in context["draft_html"] or "금리" in context["draft_html"]

def test_tc1302_copywriter_to_fact_checker():
    # 1. Copywriter runs
    cw = Copywriter()
    context = {
        "keyword": "금리",
        "category": "economy",
        "agenda_brief": "금리 3.50% 동결",
        "persona": "economy",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    context = cw.execute(context)
    
    # 2. FactChecker runs on draft
    fc = FactChecker()
    context = fc.execute(context)
    # Since draft is generated with correct interest rates, fact checker should pass
    assert "verification_report" in context
    assert context["verification_report"]["is_passed"] is True

def test_tc1303_fact_checker_to_publisher():
    # 1. Setup context with failed fact check
    context = {
        "keyword": "금리",
        "draft_html": "<p>금리가 5.0%로 폭등했습니다.</p>",
        "verification_report": {"is_passed": False, "issues": ["Mismatch: PDF says 3.5%"]}
    }
    
    # 2. Publisher runs and should refuse to post
    pub = Publisher()
    context = pub.execute(context)
    assert context["published_post_id"] == ""
    assert context["published_url"] == ""

def test_tc1304_ocr_pipeline_flow():
    # Full OCR flow
    context = {
        "source_platform": "daum",
        "pdf_path": "tests/resources/scanned_agenda.pdf",
        "persona": "economy"
    }
    
    ta = TrendAnalyst()
    cw = Copywriter()
    fc = FactChecker()
    pub = Publisher()
    
    context = ta.execute(context)
    assert "OCR" in context["agenda_brief"]
    
    context = cw.execute(context)
    context = fc.execute(context)
    assert context["verification_report"]["is_passed"] is True
    
    context = pub.execute(context)
    assert context["published_post_id"] == "naver_post_999"

def test_tc1305_daemon_pipeline_integration():
    # Running full pipeline via Pipeline coordinator class
    pipeline = Pipeline()
    context = {
        "pdf_path": "tests/resources/sample_agenda.pdf",
        "persona": "economy",
        "source_platform": "daum"
    }
    result = pipeline.run(context)
    assert result["published_post_id"] != ""
    assert os.path.exists("outputs/daemon.log")

def test_tc1306_nextjs_api_daemon_integration():
    # Start daemon via mocked API route POST
    res = requests.post("http://localhost:3000/api/daemon", json={"action": "start"})
    assert res.status_code == 200
    assert res.json()["status"] == "started"
    
    # Check status via API route GET
    res_status = requests.get("http://localhost:3000/api/daemon")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "running"
    
    # Stop daemon via API route POST
    res_stop = requests.post("http://localhost:3000/api/daemon", json={"action": "stop"})
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "stopped"
    
    # Check status again
    res_status2 = requests.get("http://localhost:3000/api/daemon")
    assert res_status2.json()["status"] == "stopped"
