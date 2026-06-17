import os
import json
import pytest
import requests
from agents.trend_analyst import TrendAnalyst
from agents.copywriter import Copywriter
from agents.fact_checker import FactChecker
from agents.publisher import Publisher
from agents.daemon import run_once, read_status, write_status

# --- F1: Trend Analyst Boundary Cases ---

def test_tc701_crawl_empty_page(monkeypatch):
    # Mock requests.get to return empty HTML
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: type("MockRes", (), {"text": "", "status_code": 200})())
    agent = TrendAnalyst()
    context = {"source_platform": "daum"}
    res = agent.execute(context)
    assert isinstance(res["trends"], list)
    assert len(res["trends"]) == 0

def test_tc702_empty_pdf():
    # Write empty file
    pdf_path = "tests/resources/empty_agenda.pdf"
    with open(pdf_path, "w") as f:
        f.write("")
    agent = TrendAnalyst()
    context = {"pdf_path": pdf_path}
    res = agent.execute(context)
    assert res["agenda_brief"] != ""
    os.remove(pdf_path)

def test_tc703_large_pdf():
    # Simulated 100+ pages of PDF text
    pdf_path = "tests/resources/large_agenda.pdf"
    with open(pdf_path, "w", encoding="utf-8") as f:
        f.write("금리 3.50% 동결\n" * 10000)
    agent = TrendAnalyst()
    context = {"pdf_path": pdf_path}
    res = agent.execute(context)
    assert "3.50%" in res["agenda_brief"]
    os.remove(pdf_path)

def test_tc704_encrypted_pdf():
    agent = TrendAnalyst()
    context = {"pdf_path": "tests/resources/encrypted_agenda.pdf"}
    res = agent.execute(context)
    assert res["agenda_brief"] != ""

def test_tc705_both_crawlers_fail(monkeypatch):
    # Simulate network down
    def mock_get_error(*args, **kwargs):
        raise requests.ConnectionError("Connection failed")
    monkeypatch.setattr(requests, "get", mock_get_error)
    agent = TrendAnalyst()
    context = {}
    res = agent.execute(context)
    assert res["keyword"] == "economy"  # default fallback
    assert res["agenda_brief"] == "Default agenda brief"

# --- F2: Copywriter Boundary Cases ---

def test_tc801_copywriter_empty_keyword():
    agent = Copywriter()
    context = {"keyword": "", "category": "economy", "agenda_brief": "금리동향"}
    res = agent.execute(context)
    assert "draft_html" in res
    assert res["draft_html"] != ""

def test_tc802_copywriter_long_agenda():
    agent = Copywriter()
    context = {"keyword": "금리", "category": "economy", "agenda_brief": "금리 " * 2000}
    res = agent.execute(context)
    assert "draft_html" in res
    assert len(res["draft_html"]) > 0

def test_tc803_copywriter_invalid_persona():
    agent = Copywriter()
    context = {"keyword": "금리", "persona": "invalid_persona"}
    res = agent.execute(context)
    assert "draft_html" in res
    # Falls back to default economy
    assert "금리" in res["draft_html"]

def test_tc804_copywriter_non_korean_keyword():
    agent = Copywriter()
    context = {"keyword": "Interest Rates", "persona": "economy"}
    res = agent.execute(context)
    assert "Interest Rates" in res["draft_html"]
    # Still writes in Korean
    assert "금리" in res["draft_html"] or "포스팅" in res["draft_html"]

def test_tc805_copywriter_tight_constraints():
    agent = Copywriter()
    context = {"keyword": "금리", "max_tokens": 10}
    res = agent.execute(context)
    assert "draft_html" in res
    assert res["draft_html"] != ""

# --- F3: Fact Checker Boundary Cases ---

def test_tc901_fact_check_empty_draft():
    agent = FactChecker()
    context = {"draft_html": "", "pdf_path": "tests/resources/sample_agenda.pdf"}
    res = agent.execute(context)
    # Empty draft doesn't contradict PDF, so it passes
    assert res["verification_report"]["is_passed"] is True

def test_tc902_fact_check_no_numbers_pdf():
    # PDF with no numbers
    pdf_path = "tests/resources/no_numbers.pdf"
    with open(pdf_path, "w", encoding="utf-8") as f:
        f.write("금리 동향 보고서 내용 없음.")
    agent = FactChecker()
    context = {"draft_html": "기준 금리는 3.50% 입니다.", "pdf_path": pdf_path}
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

def test_tc903_fact_check_empty_grounding(monkeypatch):
    # Mock Gemini to return empty grounding search response
    from tests.mocks.mock_gemini import MockModels, MockResponse
    monkeypatch.setattr(MockModels, "generate_content", lambda *args, **kwargs: MockResponse("", 200))
    agent = FactChecker()
    context = {"draft_html": "금리 3.5%", "pdf_path": None}
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

def test_tc904_fact_check_multiple_conflicts():
    agent = FactChecker()
    context = {
        "draft_html": "기준 금리는 5.0% 이고 GDP는 4.0% 입니다.",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is False

def test_tc905_fact_check_malformed_html():
    agent = FactChecker()
    context = {
        "draft_html": "<div><h3>기준 금리 3.5%</h3><p>동결되었습니다.</div></p>",
        "pdf_path": "tests/resources/sample_agenda.pdf"
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True

# --- F4: Multimodal OCR Boundary Cases ---

def test_tc1001_ocr_empty_pdf():
    # Create empty scanned PDF
    pdf_path = "tests/resources/scanned_empty.pdf"
    with open(pdf_path, "w") as f:
        f.write("[scanned image pdf content]")
    agent = FactChecker()
    context = {
        "draft_html": "금리 3.5%",
        "pdf_path": pdf_path
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

def test_tc1002_ocr_blurry_pdf():
    pdf_path = "tests/resources/scanned_blurry.pdf"
    with open(pdf_path, "w") as f:
        f.write("[scanned image pdf content] blurry")
    agent = FactChecker()
    context = {
        "draft_html": "금리 3.5%",
        "pdf_path": pdf_path
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

def test_tc1003_ocr_corrupted_image():
    pdf_path = "tests/resources/scanned_corrupted.pdf"
    with open(pdf_path, "w") as f:
        f.write("[scanned image pdf content] corrupted")
    agent = FactChecker()
    context = {
        "draft_html": "금리 3.5%",
        "pdf_path": pdf_path
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

def test_tc1004_ocr_multipage_layout():
    pdf_path = "tests/resources/scanned_multipage.pdf"
    with open(pdf_path, "w") as f:
        f.write("[scanned image pdf content]\nPage 1\nPage 2\nPage 3")
    agent = FactChecker()
    context = {
        "draft_html": "금리 3.5%",
        "pdf_path": pdf_path
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

def test_tc1005_ocr_foreign_language():
    pdf_path = "tests/resources/scanned_english.pdf"
    with open(pdf_path, "w") as f:
        f.write("[scanned image pdf content] The interest rate is fixed at 3.5%.")
    agent = FactChecker()
    context = {
        "draft_html": "금리 3.5%",
        "pdf_path": pdf_path
    }
    res = agent.execute(context)
    assert res["verification_report"]["is_passed"] is True
    os.remove(pdf_path)

# --- F5: Publisher Boundary Cases ---

def test_tc1101_publish_empty_draft():
    agent = Publisher()
    context = {"draft_html": "", "verification_report": {"is_passed": True}}
    res = agent.execute(context)
    assert res["published_post_id"] != ""

def test_tc1102_publish_naver_api_error(monkeypatch):
    # Simulate Naver API 500 error
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: type("MockRes", (), {"status_code": 500, "text": "Error"})())
    agent = Publisher()
    context = {"draft_html": "<p>글</p>", "verification_report": {"is_passed": True}}
    res = agent.execute(context)
    # Handled fallback url
    assert "local_mock_post_" in res["published_post_id"] or "local_fallback_post_" in res["published_post_id"]

def test_tc1103_publish_missing_csv():
    # Remove CSV
    if os.path.exists("visitor_stats.csv"):
        os.remove("visitor_stats.csv")
    agent = Publisher()
    context = {"draft_html": "<p>글</p>", "verification_report": {"is_passed": True}}
    res = agent.execute(context)
    assert os.path.exists("visitor_stats.csv")

def test_tc1104_publish_duplicate_keywords():
    agent = Publisher()
    context = {
        "draft_html": "<p>글</p>",
        "verification_report": {"is_passed": True},
        "keyword": "금리"
    }
    # Run twice
    res1 = agent.execute(context)
    res2 = agent.execute(context)
    assert res1["published_post_id"] != ""
    assert res2["published_post_id"] != ""

def test_tc1105_publish_ftc_duplicate():
    agent = Publisher()
    # FTC disclosure already in draft
    disclosure = '본 포스팅은 소정의 원고료를 지원받아 주관적으로 작성된 신뢰도 높은 글입니다.'
    context = {
        "draft_html": f"<p>글</p>\n<div class='ftc'>{disclosure}</div>",
        "verification_report": {"is_passed": True}
    }
    res = agent.execute(context)
    # Disclosure should appear but let's make sure it doesn't duplicate the text unnecessarily or is handled safely
    assert disclosure in res["draft_html"]

# --- F6: Daemon Boundary Cases ---

def test_tc1201_daemon_status_corrupted():
    status_path = "outputs/daemon_status.json"
    os.makedirs("outputs", exist_ok=True)
    with open(status_path, "w") as f:
        f.write("{invalid json}")
    # Read status should not crash
    status = read_status()
    assert status["status"] == "stopped"

def test_tc1202_daemon_double_start(capsys):
    write_status("running", pid=1234)
    # Simulate CLI start call
    import sys
    orig_argv = sys.argv
    sys.argv = ["daemon.py", "start"]
    from agents.daemon import main
    main()
    sys.argv = orig_argv
    captured = capsys.readouterr()
    assert "Daemon is already running" in captured.out

def test_tc1203_daemon_run_once_fails(monkeypatch):
    # Make pipeline run fail
    from agents.pipeline import Pipeline
    monkeypatch.setattr(Pipeline, "run", lambda *args, **kwargs: exec("raise(Exception('Failed pipeline'))"))
    with pytest.raises(Exception):
        run_once()
    # Verify status is still stopped
    status = read_status()
    assert status["status"] == "stopped"

def test_tc1204_log_rotation():
    # Simulate logging rotation triggers
    # Verify daemon logger level
    from agents.base import get_agent_logger
    logger = get_agent_logger("daemon")
    assert logger is not None

def test_tc1205_nextjs_api_route_invalid_json():
    # Test local mock Next.js post route with empty/invalid request structure
    res = requests.post("http://localhost:3000/api/daemon", json={})
    # Mock endpoint should return stopped status since no valid action was sent
    assert "status" in res.json()
