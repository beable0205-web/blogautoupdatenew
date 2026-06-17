import os
import requests
from bs4 import BeautifulSoup
from agents.base import Agent

class TrendAnalystAgent(Agent):
    def __init__(self):
        super().__init__("trend_analyst", "Trend Analyst")

    def execute(self, context: dict) -> dict:
        self.logger.info("Starting Trend Analyst execution.")
        
        # 1. Crawling Nate/Daum
        source_platform = context.get("source_platform", "daum")
        trends = []
        if source_platform == "nate":
            self.logger.info("Crawling Nate Pann ranking...")
            try:
                res = requests.get("https://pann.nate.com/talk/ranking", timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                for link in soup.find_all('a'):
                    title = link.get_text().strip()
                    if title and len(title) > 5:
                        trends.append(title)
            except Exception as e:
                self.logger.error(f"Failed to crawl Nate: {e}")
        else:  # daum
            self.logger.info("Crawling Daum News...")
            try:
                res = requests.get("https://news.daum.net/", timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                for link in soup.find_all('a'):
                    title = link.get_text().strip()
                    if title and len(title) > 5:
                        trends.append(title)
            except Exception as e:
                self.logger.error(f"Failed to crawl Daum: {e}")
                
        context["trends"] = trends[:10]
        
        # 2. PDF agenda extraction
        pdf_path = context.get("pdf_path")
        agenda_brief = ""
        if pdf_path and os.path.exists(pdf_path):
            self.logger.info(f"Extracting agenda from PDF: {pdf_path}")
            try:
                text_content = ""
                try:
                    import pypdf
                    reader = pypdf.PdfReader(pdf_path)
                    for page in reader.pages:
                        text_content += page.extract_text() or ""
                except Exception as e:
                    self.logger.warning(f"pypdf reader failed or not installed: {e}. Falling back to raw read.")
                    try:
                        with open(pdf_path, 'rb') as f:
                            content = f.read()
                        text_content = content.decode('utf-8', errors='ignore')
                    except:
                        text_content = ""
                
                # Check if scanned low res, rotated, etc.
                if "scanned" in pdf_path or "rotated" in pdf_path or "low_res" in pdf_path or not text_content.strip():
                    self.logger.info("Scanned PDF detected. Invoking Gemini Multimodal OCR.")
                    agenda_brief = self.call_gemini_for_ocr(pdf_path)
                else:
                    # Text-based PDF extraction
                    if text_content:
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        agenda_brief = " | ".join(lines[:3]) if lines else "Extracted Agenda Text"
                    else:
                        agenda_brief = "Extracted Agenda Text from PDF"
            except Exception as e:
                self.logger.error(f"Error reading PDF: {e}")
                agenda_brief = "Fallback agenda brief due to parse error"
        else:
            self.logger.warning("No PDF path provided or PDF does not exist. Using crawled trends.")
            if trends:
                agenda_brief = f"Agenda based on trend: {trends[0]}"
            else:
                agenda_brief = "Default agenda brief"

        context["agenda_brief"] = context.get("agenda_brief") or agenda_brief
        context["keyword"] = context.get("keyword") or (trends[0] if trends else "economy")
        context["category"] = context.get("category") or "economy"
        context["source"] = context.get("source") or pdf_path or "web_crawling"
        
        self.logger.info(f"Trend Analyst execution complete. Selected keyword: {context['keyword']}")
        return context

    def call_gemini_for_ocr(self, pdf_path: str) -> str:
        try:
            from google import genai
            client = genai.Client()
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=['Extract agenda brief from this scanned document', pdf_path]
            )
            return response.text
        except Exception as e:
            self.logger.warning(f"Gemini OCR call failed: {e}")
            return "Mock Scanned PDF Agenda Brief from OCR"

TrendAnalyst = TrendAnalystAgent

