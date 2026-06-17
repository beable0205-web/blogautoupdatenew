import sys
import types
import re

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockModels:
    def generate_content(self, model, contents, config=None):
        prompt_str = ""
        for item in contents:
            if isinstance(item, str):
                prompt_str += " " + item
            else:
                prompt_str += f" {str(item)}"
                
        # Simulate timeout/failure for retry test
        if "simulate_timeout" in prompt_str:
            raise Exception("Simulated Gemini API Timeout Error")
            
        # Multimodal OCR
        if "scanned" in prompt_str or "rotated" in prompt_str or "low_res" in prompt_str or "pdf_path" in prompt_str:
            return MockResponse("Mock Scanned PDF Agenda Brief from OCR: Interest rate is 3.50% and GDP growth is 2.1%.")
            
        # Grounding Search (if google_search tool configured)
        if config and 'tools' in config and any('google_search' in tool for tool in config['tools']):
            return MockResponse("Fact checked: Real-time interest rate is 3.50% according to Google search grounding.")
            
        # Fact check failure mismatch (dynamic check)
        if "5.0%" in prompt_str or "4.0%" in prompt_str or ("금리 3.5%" in prompt_str and "금리 5.0%" in prompt_str):
            return MockResponse("결과: Fail\nFact check failed: mismatch found. Draft states incorrect values.")
            
        # AI in Healthcare 2026 check
        if "AI in Healthcare 2026" in prompt_str:
            return MockResponse("<div><h3>Latest Updates on AI in Healthcare 2026</h3><p>Analysis of AI applications in diagnostic imaging and patient care in 2026.</p></div>")
            
        # Dynamic Persona drafts
        keyword_match = re.search(r'키워드:\s*(.*)', prompt_str)
        keyword = keyword_match.group(1).strip() if keyword_match else "경제"
        
        if "health" in prompt_str:
            return MockResponse(f"<div><h3>{keyword} 관련 건강 정보</h3><p>의학 전문가 권고에 의하면 일주일에 3회 운동 시 건강 위험을 15.4% 낮춥니다.</p></div>")
        elif "brandconnect" in prompt_str:
            return MockResponse(f"<div><h3>{keyword} 제품 추천 포스팅</h3><p>브랜드 커넥트 제휴를 통한 신뢰성 높은 추천 글입니다. 만족도 94.2%를 달성했습니다.</p></div>")
        else:
            return MockResponse(f"<div><h3>{keyword} 동향 포스팅</h3><p>전문 금융 분석에 따르면 기준 금리는 3.50%로 유지되고 있습니다. 가계 부채 증가 우려가 있습니다.</p></div>")

class MockClient:
    models = MockModels()
    def __init__(self, *args, **kwargs):
        pass

def patch_gemini():
    try:
        import google.genai
        google.genai.Client = MockClient
    except ImportError:
        google_mod = types.ModuleType("google")
        genai_mod = types.ModuleType("google.genai")
        genai_mod.Client = MockClient
        google_mod.genai = genai_mod
        sys.modules["google"] = google_mod
        sys.modules["google.genai"] = genai_mod
        sys.modules["google.genai.Client"] = MockClient
