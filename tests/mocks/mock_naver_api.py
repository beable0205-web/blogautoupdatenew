import requests

original_post = requests.post

class MockResponse:
    def __init__(self, json_data, status_code):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    @property
    def text(self):
        import json
        return json.dumps(self._json)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")

def mock_post(url, *args, **kwargs):
    if "api.naver.com/blog/write" in url:
        return MockResponse({
            "status": "success",
            "post_id": "naver_post_999",
            "url": "https://blog.naver.com/post/naver_post_999"
        }, 200)
    return original_post(url, *args, **kwargs)

def patch_naver():
    requests.post = mock_post

def unpatch_naver():
    requests.post = original_post
