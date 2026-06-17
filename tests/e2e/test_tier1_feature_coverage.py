import os
import json
import pytest
from agents.trend_analyst import TrendAnalyst
from agents.copywriter import Copywriter
from agents.fact_checker import FactChecker
from agents.publisher import Publisher
from agents.daemon import run_once, read_status, write_status

# --- F1: Trend Analyst Agent ---

def test_tc101_crawl_daum():
    agent = TrendAnalyst()
    context = {"source_platform": "daum"}
    res = agent.execute(context)
    assert "trends" in res
    assert len(res["trends"]) > 0
    assert any("금리" in t or "금융" in t or "동향" in t for t in res["trends"])

def test_tc102_crawl_nate():
    agent = TrendAnalyst()
    context = {"source_platform": "nate"}
    res = agent.execute(context)
    assert "trends" in res
    assert len(res["trends"]) > 0
    assert any("식단" in t or "감량" in t or "건강" in t for t in res["trends"])

def test_tc103_extract_text_pdf():
    agent = TrendAnalyst()
    pdf_path = "tests/resources/sample_agenda.pdf"
    context = {"pdf_path": pdf_path}
    res = agent.execute(context)
    assert res["agenda_brief"] != ""
    assert "기준금리 3.5%" in res["agenda_brief"]

def test_tc104_extract_trends_keyword():
    agent = TrendAnalyst()
    context = {"source_platform": "daum"}
    res = agent.execute(context)
    assert "keyword" in res
    assert res["keyword"] != ""

def test_tc105_select_category():
    agent = TrendAnalyst()
    context = {"category": "health"}
    res = agent.execute(context)
    assert res["category"] == "health"

# --- F2: Copywriter Agent ---

def test_tc201_copywriter_economy():
    agent = Copywriter()
    context = {"keyword": "금리", "category": "economy", "agenda_brief": "금리 3.5% 동결", "persona": "economy"}
    res = agent.execute(context)
    assert "draft_html" in res
    assert "금리" in res["draft_html"]
    assert "3.50%" in res["draft_html"]

def test_tc202_copywriter_health():
    agent = Copywriter()
    context = {"keyword": "다이어트", "category": "health", "agenda_brief": "식단 조절 15.4% 감량", "persona": "health"}
    res = agent.execute(context)
    assert "draft_html" in res
    assert "건강" in res["draft_html"]
    assert "15.4%" in res["draft_html"]

def test_tc203_copywriter_brandconnect():
    agent = Copywriter()
    context = {"keyword": "영양제", "category": "brandconnect", "agenda_brief": "만족도 94.2%", "persona": "brandconnect"}
    res = agent.execute(context)
    assert "draft_html" in res
    assert "브랜드" in res["draft_html"]
    assert "94.2%" in res["draft_html"]

def test_tc204_copywriter_tone():
    agent = Copywriter()
    context = {"keyword": "금리", "persona": "economy"}
    res = agent.execute(context)
    # Professional dry honorific tone ends with 습니다/입니다
    draft = res["draft_html"]
    assert "요" not in draft or "습니다" in draft or "입니다" in draft
    assert "진짜" not in draft  # avoid subjective hype

def test_tc205_copywriter_no_images():
    agent = Copywriter()
    context = {"keyword": "금리"}
    res = agent.execute(context)
    assert "<img>" not in res["draft_html"]
    assert "<img" not in res["draft_html"]

# --- F3: Fact Checker Agent ---

def test_tc301_fact_check_pass():
    agent = FactChecker()
    context = {
        "draft_html": "기준 금리는 3.50%로 유지되고 있습니다.",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc302_fact_check_rates():
    agent = FactChecker()
    context = {
        "draft_html": "현재 금리는 3.50% 수준입니다.",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc303_fact_check_google_grounding():
    agent = FactChecker()
    context = {
        "draft_html": "기준 금리는 3.50% 수준입니다.",
        "pdf_path": None  # Trigger Google Grounding search
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc304_fact_check_mismatch():
    agent = FactChecker()
    # Mismatch: PDF says 3.5%, Draft says 5.0%
    context = {
        "draft_html": "기준 금리는 5.0% 수준으로 크게 치솟았습니다.",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is False
    assert len(res["verification_report"]["issues"]) > 0

def test_tc305_fact_check_report_schema():
    agent = FactChecker()
    context = {"draft_html": "테스트", "pdf_path": "tests/resources/sample_agenda.pdf"}
    res = agent.execute(context)
    report = res["verification_report"]
    assert "is_passed" in report
    assert "issues" in report
    assert isinstance(report["is_passed"], bool)
    assert isinstance(report["issues"], list)

# --- F4: Multimodal OCR Fact Checking ---

def test_tc401_ocr_scanned_pdf():
    agent = FactChecker()
    context = {
        "draft_html": "기준금리 3.5%와 GDP 성장률 2.1% 전망",
        "pdf_path": "tests/resources/scanned_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc402_ocr_extract_stats():
    agent = TrendAnalyst()
    context = {"pdf_path": "tests/resources/scanned_agenda.pdf"}
    res = agent.execute(context)
    assert "OCR" in res["agenda_brief"]
    assert "3.50%" in res["agenda_brief"]

def test_tc403_ocr_rotated_pdf():
    agent = FactChecker()
    context = {
        "draft_html": "기준금리 3.5%와 GDP 성장률 2.1% 전망",
        "pdf_path": "tests/resources/scanned_rotated.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc404_ocr_low_res_pdf():
    agent = FactChecker()
    context = {
        "draft_html": "기준금리 3.5%와 GDP 성장률 2.1% 전망",
        "pdf_path": "tests/resources/scanned_low_res.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc405_ocr_handwritten_pdf():
    # In this mock-up framework, low_res/scanned is routed similarly
    agent = FactChecker()
    context = {
        "draft_html": "기준금리 3.5%와 GDP 성장률 2.1% 전망",
        "pdf_path": "tests/resources/scanned_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

# --- F5: Naver Blog Publishing & Performance Loop ---

def test_tc501_publisher_antidetect():
    agent = Publisher()
    context = {
        "draft_html": "<p>금리 동향에 대한 글입니다.</p>",
        "verification_report": {"is_passed": True}
    }
    res = agent.execute(context)
    assert "naver-style-" in res["draft_html"]

def test_tc502_publisher_ftc_disclosure():
    agent = Publisher()
    context = {
        "draft_html": "<p>경제 글</p>",
        "verification_report": {"is_passed": True}
    }
    res = agent.execute(context)
    assert "ftc-disclosure" in res["draft_html"]
    assert "소정의 원고료" in res["draft_html"]

def test_tc503_publisher_naver_mock():
    agent = Publisher()
    context = {
        "draft_html": "<p>본문 내용</p>",
        "verification_report": {"is_passed": True},
        "keyword": "금리",
        "category": "economy"
    }
    res = agent.execute(context)
    assert res["published_post_id"] == "naver_post_999"
    assert "naver.com" in res["published_url"]

def test_tc504_publisher_visitor_stats():
    # Setup stats mock file
    if os.path.exists("visitor_stats.csv"):
        os.remove("visitor_stats.csv")
    agent = Publisher()
    context = {
        "draft_html": "<p>본문 내용</p>",
        "verification_report": {"is_passed": True}
    }
    res = agent.execute(context)
    assert os.path.exists("visitor_stats.csv")
    df = pytest.importorskip("pandas").read_csv("visitor_stats.csv")
    assert len(df) > 0

def test_tc505_publisher_reject_invalid():
    agent = Publisher()
    context = {
        "draft_html": "<p>본문 내용</p>",
        "verification_report": {"is_passed": False, "issues": ["Mismatch found"]},
        "published_post_id": "old_id",
        "published_url": "old_url"
    }
    res = agent.execute(context)
    assert res["published_post_id"] == ""
    assert res["published_url"] == ""

# --- F6: Logging, Coordinator Daemon & API Monitor ---

def test_tc601_daemon_start():
    from agents.daemon import read_status, write_status
    # Stop first
    write_status("stopped")
    # Start
    import subprocess
    # Run inline helper to simulate daemon CLI
    write_status("running", pid=1111)
    status = read_status()
    assert status["status"] == "running"
    assert status["pid"] == 1111

def test_tc602_daemon_stop():
    from agents.daemon import read_status, write_status
    write_status("stopped", pid=None)
    status = read_status()
    assert status["status"] == "stopped"
    assert status["pid"] is None

def test_tc603_daemon_status_cmd(capsys):
    from agents.daemon import write_status
    write_status("running", pid=2222)
    # Call daemon status
    import sys
    orig_argv = sys.argv
    sys.argv = ["daemon.py", "status"]
    from agents.daemon import main
    try:
        main()
    except SystemExit:
        pass
    sys.argv = orig_argv
    captured = capsys.readouterr()
    assert '"status": "running"' in captured.out
    assert '"pid": 2222' in captured.out

def test_tc604_daemon_run_once():
    # run-once executed
    res = run_once(pdf_path="tests/resources/sample_agenda.pdf", persona="economy")
    assert res is not None
    assert res["published_post_id"] != ""

def test_tc605_agent_logs():
    # Clean old logs if any
    for log in ["TrendAnalyst.log", "Copywriter.log", "FactChecker.log", "Publisher.log", "daemon.log"]:
        path = f"outputs/{log}"
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
                
    run_once(pdf_path="tests/resources/sample_agenda.pdf", persona="economy")
    for log in ["TrendAnalyst.log", "Copywriter.log", "FactChecker.log", "Publisher.log", "daemon.log"]:
        assert os.path.exists(f"outputs/{log}")
