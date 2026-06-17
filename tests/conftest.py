import pytest
import requests
import json
from tests.mocks.mock_gemini import patch_gemini
from tests.mocks.mock_naver_api import patch_naver, unpatch_naver, mock_post as naver_mock_post
from tests.mocks.mock_crawler import patch_crawler, unpatch_crawler, mock_get as crawler_mock_get

class MockLocalResponse:
    def __init__(self, json_data, status_code):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    @property
    def text(self):
        return json.dumps(self._json)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")

@pytest.fixture(autouse=True)
def setup_mocks():
    # 1. Patch Gemini API
    patch_gemini()
    
    # 2. Patch Naver & Crawler
    patch_naver()
    patch_crawler()
    
    # 3. Intercept localhost API calls (Next.js daemon & trend routes)
    original_get = requests.get
    original_post = requests.post
    
    def local_get(url, *args, **kwargs):
        url_str = str(url)
        if "/api/daemon" in url_str:
            from agents.daemon import read_status
            return MockLocalResponse(read_status(), 200)
        elif "/api/agent-trend" in url_str:
            return MockLocalResponse({"status": "success", "trends": ["금리", "건강"]}, 200)
        return crawler_mock_get(url, *args, **kwargs)
        
    def local_post(url, *args, **kwargs):
        url_str = str(url)
        if "/api/daemon" in url_str:
            json_data = kwargs.get("json", {})
            action = json_data.get("action")
            from agents.daemon import write_status
            if action == "start":
                write_status("running", pid=9999)
                return MockLocalResponse({"status": "started", "pid": 9999}, 200)
            elif action == "stop":
                write_status("stopped")
                return MockLocalResponse({"status": "stopped"}, 200)
            elif action == "status":
                from agents.daemon import read_status
                return MockLocalResponse(read_status(), 200)
            else:
                from agents.daemon import read_status
                return MockLocalResponse(read_status(), 200)
        return naver_mock_post(url, *args, **kwargs)
        
    requests.get = local_get
    requests.post = local_post
    
    yield
    
    # Restore
    unpatch_naver()
    unpatch_crawler()
    requests.get = original_get
    requests.post = original_post
