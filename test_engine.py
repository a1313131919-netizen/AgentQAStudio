import json
import tempfile
import unittest
from pathlib import Path

from engine import ApiConfig, TestCase, evaluate_case, generate_edge_cases, summarize_results
from reports import export_csv, export_html, export_json


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.config = ApiConfig(
            url="mock://agent",
            method="POST",
            headers_json='{"Content-Type":"application/json"}',
            body_template='{"message":"{{input}}"}',
            answer_path="answer",
            tool_path="tool",
            arguments_path="arguments",
            sources_path="sources",
        )

    def test_tool_call_query(self):
        case = TestCase(
            "T1",
            "query",
            "幫我查訂單 A001",
            expected_status="200",
            expected_tool="get_order_status",
            expected_args_json='{"order_id":"A001"}',
            must_contain="配送",
            min_sources=1,
            max_latency_ms=1500,
        )
        result = evaluate_case(self.config, case)
        self.assertTrue(result.passed, result.failures)
        self.assertEqual(result.actual_tool, "get_order_status")
        self.assertEqual(result.source_count, 1)

    def test_tool_call_cancel(self):
        case = TestCase(
            "T2",
            "cancel",
            "請取消訂單 A002",
            expected_tool="cancel_order",
            expected_args_json='{"order_id":"A002"}',
            must_contain="取消",
        )
        result = evaluate_case(self.config, case)
        self.assertTrue(result.passed, result.failures)

    def test_failure_is_categorized(self):
        case = TestCase("T3", "wrong expectation", "幫我查訂單 A001", expected_tool="cancel_order")
        result = evaluate_case(self.config, case)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_category, "Tool Calling")

    def test_edge_case_generator(self):
        cases = generate_edge_cases(TestCase("B", "base", "hello"))
        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue(any(c.input_text == "" for c in cases))

    def test_summary_and_reports(self):
        ok = evaluate_case(self.config, TestCase("T4", "ok", "幫我查訂單 A001", expected_tool="get_order_status"))
        bad = evaluate_case(self.config, TestCase("T5", "bad", "幫我查訂單 A001", expected_tool="cancel_order"))
        summary = summarize_results([ok, bad])
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertAlmostEqual(summary["pass_rate"], 50.0)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = str(Path(tmp) / "report.csv")
            html_path = str(Path(tmp) / "report.html")
            json_path = str(Path(tmp) / "report.json")
            export_csv(csv_path, [ok, bad])
            export_html(html_path, [ok, bad])
            export_json(json_path, [ok, bad])
            self.assertTrue(Path(csv_path).exists())
            self.assertIn("Pass Rate", Path(html_path).read_text(encoding="utf-8"))
            payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
