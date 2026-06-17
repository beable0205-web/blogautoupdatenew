import requests

original_get = requests.get

class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")

def mock_get(url, *args, **kwargs):
    url_str = str(url)
    if "news.daum.net" in url_str:
        return MockResponse("""
        <html>
            <body>
                <a href="https://v.daum.net/v/1">경영자금 대출 금리 3.5% 동결 소식</a>
                <a href="https://v.daum.net/v/2">최신 가계 금융 시장 동향 보고서</a>
            </body>
        </html>
        """, 200)
    elif "pann.nate.com" in url_str:
        return MockResponse("""
        <html>
            <body>
                <a href="/talk/3">다이어트 식단 조절 15.4% 감량 꿀팁</a>
                <a href="/talk/4">회사 근처 건강 검진 예약 후기</a>
            </body>
        </html>
        """, 200)
    return original_get(url, *args, **kwargs)

def patch_crawler():
    requests.get = mock_get

def unpatch_crawler():
    requests.get = original_get
