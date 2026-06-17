import os
import sys
import unittest
import json
import requests

# Add project root to python path to ensure package is importable
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.pipeline import Pipeline
from agents.validation import create_default_context, validate_context
from agents.trend_analyst import TrendAnalystAgent
from agents.copywriter import CopywriterAgent
from agents.fact_checker import FactCheckerAgent
from agents.publisher import PublisherAgent
from tests.mocks.mock_gemini import patch_gemini
from tests.mocks.mock_naver_api import patch_naver, unpatch_naver, mock_post as naver_mock_post
from tests.mocks.mock_crawler import patch_crawler, unpatch_crawler, mock_get as crawler_mock_get

class TestPipelineFramework(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.outputs_dir = os.path.join(self.base_dir, "outputs")
        
        # Clean up any existing logs to ensure fresh test runs verify logging behavior
        for agent_name in ["trend_analyst", "copywriter", "fact_checker", "publisher"]:
            log_file_path = os.path.join(self.outputs_dir, f"{agent_name}.log")
            if os.path.exists(log_file_path):
                try:
                    os.remove(log_file_path)
                except OSError:
                    pass
        
        # Patch Gemini, Naver API, and crawler
        patch_gemini()
        patch_naver()
        patch_crawler()
        
        # Intercept HTTP requests
        self._original_get = requests.get
        self._original_post = requests.post
        
        def local_get(url, *args, **kwargs):
            return crawler_mock_get(url, *args, **kwargs)
            
        def local_post(url, *args, **kwargs):
            return naver_mock_post(url, *args, **kwargs)
            
        requests.get = local_get
        requests.post = local_post

    def tearDown(self):
        unpatch_naver()
        unpatch_crawler()
        requests.get = self._original_get
        requests.post = self._original_post
        
    def test_successful_pipeline_run(self):
        # Initialize pipeline and agents
        pipeline = Pipeline()
        trend_analyst = TrendAnalystAgent()
        copywriter = CopywriterAgent()
        fact_checker = FactCheckerAgent()
        publisher = PublisherAgent()
        
        # Register in sequence
        pipeline.register(trend_analyst)
        pipeline.register(copywriter)
        pipeline.register(fact_checker)
        pipeline.register(publisher)
        
        # Run pipeline
        initial_context = create_default_context()
        initial_context["keyword"] = "AI in Healthcare 2026"
        initial_context["category"] = "Health/Tech"
        initial_context["source"] = "Daum Trends & PDF Agenda"
        initial_context["agenda_brief"] = "Analysis of AI applications in diagnostic imaging and patient care in 2026."
        
        final_context = pipeline.run(initial_context)
        
        # Assertions on final context
        self.assertEqual(final_context["keyword"], "AI in Healthcare 2026")
        self.assertEqual(final_context["category"], "Health/Tech")
        self.assertEqual(final_context["source"], "Daum Trends & PDF Agenda")
        self.assertIn("diagnostic imaging", final_context["agenda_brief"])
        self.assertIn("Latest Updates on AI in Healthcare 2026", final_context["draft_html"])
        self.assertIn("소정의 원고료", final_context["draft_html"])
        self.assertTrue(final_context["verification_report"]["is_passed"])
        self.assertIn(final_context["published_post_id"], ["naver_post_999", "local_fallback_post_56789"])
        self.assertIn(final_context["published_url"], [
            "https://blog.naver.com/post/naver_post_999",
            "https://blog.naver.com/mock_user/local_fallback_post_56789"
        ])
        
        # Verify log files are generated and contain JSON structures
        for agent_name in ["trend_analyst", "copywriter", "fact_checker", "publisher"]:
            log_file_path = os.path.join(self.outputs_dir, f"{agent_name}.log")
            self.assertTrue(os.path.exists(log_file_path), f"Log file for {agent_name} should exist at {log_file_path}")
            
            # Read and verify the JSON format of log lines
            with open(log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.assertTrue(len(lines) > 0, f"Log file for {agent_name} is empty")
                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        log_entry = json.loads(line_str)
                        self.assertIn("timestamp", log_entry)
                        self.assertIn("agent", log_entry)
                        self.assertIn("level", log_entry)
                        self.assertIn("message", log_entry)
                        self.assertIn("traceback", log_entry)
                    except json.JSONDecodeError:
                        self.fail(f"Log line in {agent_name}.log is not valid JSON: {line_str}")
            
    def test_pipeline_validation_fails_initially(self):
        pipeline = Pipeline()
        pipeline.register(TrendAnalystAgent())
        
        # Pass completely invalid context (missing keys)
        invalid_context = {"wrong_key": "value"}
        with self.assertRaises(ValueError) as context:
            pipeline.run(invalid_context)
        self.assertIn("Schema validation error", str(context.exception))
        
    def test_publisher_fails_when_fact_checker_fails(self):
        pipeline = Pipeline()
        pipeline.register(TrendAnalystAgent())
        pipeline.register(CopywriterAgent())
        
        # Custom mock fact checker that fails
        class FailingFactChecker(FactCheckerAgent):
            def execute(self, ctx: dict) -> dict:
                ctx["verification_report"] = {
                    "is_passed": False,
                    "issues": ["Inaccurate diagnostic stat in paragraph 2."]
                }
                return ctx
                
        pipeline.register(FailingFactChecker())
        pipeline.register(PublisherAgent())
        
        initial_context = create_default_context()
        with self.assertRaises(ValueError) as context:
            pipeline.run(initial_context)
        self.assertIn("Publisher execution failed: Article has not passed fact-checking verification.", str(context.exception))

    def test_pipeline_run_with_no_arguments(self):
        pipeline = Pipeline()
        final_context = pipeline.run()
        self.assertIsNone(final_context["keyword"])
        self.assertIsNone(final_context["category"])
        self.assertIsNone(final_context["published_url"])

    def test_publisher_handles_paragraphs_with_attributes(self):
        publisher = PublisherAgent()
        context = create_default_context()
        context["draft_html"] = '<p style="font-size: 14px;">This is a styled paragraph.</p>'
        context["verification_report"] = {"is_passed": True, "issues": []}
        
        updated_context = publisher.execute(context)
        self.assertIn('naver-style-', updated_context["draft_html"])
        self.assertIn('This is a styled paragraph.', updated_context["draft_html"])

if __name__ == "__main__":
    unittest.main()
