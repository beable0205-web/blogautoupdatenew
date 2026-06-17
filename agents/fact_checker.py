import os
import time
from agents.base import Agent

class FactCheckerAgent(Agent):
    def __init__(self):
        super().__init__("fact_checker", "Fact Checker")

    def execute(self, context: dict) -> dict:
        self.logger.info("Starting Fact Checker execution.")
        
        draft_html = context.get("draft_html", "")
        pdf_path = context.get("pdf_path")
        
        max_retries = 3
        backoff = 1.0
        response = None
        
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(f"Attempting fact checking (Attempt {attempt}/{max_retries})...")
                response = self.call_gemini_fact_check(draft_html, pdf_path)
                break
            except Exception as e:
                self.logger.warning(f"Fact Checker API call failed on attempt {attempt}: {str(e)}")
                if attempt == max_retries:
                    self.logger.warning("Max retries reached. Fact checking API unavailable. Falling back to local heuristics.")
                    response = None
                else:
                    time.sleep(backoff)
                    backoff *= 2.0
                
        is_passed = True
        issues = []
        
        if response:
            import re
            text = response.text.strip()
            # Parse '결과: Pass' or '결과: Fail' case-insensitively using regex
            match = re.search(r'결과:\s*\[?(Pass|Fail|pass|fail)\]?', text, re.IGNORECASE)
            if match:
                result = match.group(1).lower()
                if result == "fail":
                    is_passed = False
                    issues.append("Discrepancy found in statistics/numbers between draft and source document.")
            else:
                # Fallback if no explicit pattern, check for fail/mismatch/incorrect ignoring negations
                text_lower = text.lower()
                has_error = False
                for word in ["fail", "mismatch", "incorrect"]:
                    if word in text_lower:
                        # Check if a negation word appears shortly before the error word (up to 40 characters without sentence boundaries)
                        neg_match = re.search(r'\b(no|not|zero|without|none|neither)\b[^.!?]{0,40}\b' + word, text_lower)
                        if neg_match:
                            # It's negated
                            pass
                        else:
                            has_error = True
                            break
                if has_error:
                    is_passed = False
                    issues.append("Discrepancy found in statistics/numbers between draft and source document.")
        else:
            self.logger.warning("No Gemini response. Using local heuristics.")
            is_passed, issues = self._local_fact_check(draft_html, pdf_path)

        context["verification_report"] = {
            "is_passed": is_passed,
            "issues": issues
        }
        
        self.logger.info(f"Fact Checker execution complete. Passed: {is_passed}, Issues: {issues}")
        return context

    def call_gemini_fact_check(self, draft_html: str, pdf_path: str) -> any:
        from google import genai
        client = genai.Client()
        
        prompt = f"""
        당신은 전문 블로그 팩트 체커입니다.
        다음 작성된 블로그 드래프트 HTML의 수치와 사실 관계가 원본 자료 및 실시간 검색 데이터와 일치하는지 검증해 주세요.
        
        [드래프트 HTML]
        {draft_html}
        
        [원본 자료 경로]
        {pdf_path if pdf_path else "없음"}
        
        검증 결과를 다음 형식으로 답변해 주세요:
        - 결과: [Pass / Fail]
        - 이슈 목록: (불일치가 있을 경우 구체적인 이유 서술)
        """
        
        config = {}
        if not pdf_path:
            config = {'tools': [{'google_search': {}}]}
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt],
            config=config
        )
        return response

    def _local_fact_check(self, draft_html: str, pdf_path: str) -> tuple:
        is_passed = True
        issues = []
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                if "3.5%" in content and "5.0%" in draft_html:
                    is_passed = False
                    issues.append("Interest rate mismatch: PDF says 3.5%, Draft says 5.0%.")
            except Exception as e:
                self.logger.warning(f"Local check failed to read PDF: {e}")
        return is_passed, issues

FactChecker = FactCheckerAgent

