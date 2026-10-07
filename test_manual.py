import unittest

from engine import TestCase
from manual_eval import Observation, evaluate_observation


class ManualEvaluationTests(unittest.TestCase):
    def test_manual_pass(self):
        case = TestCase(
            "M1",
            "manual",
            "查詢 A001",
            expected_tool="get_order_status",
            expected_args_json='{"order_id":"A001"}',
            must_contain="配送",
            min_sources=1,
            max_latency_ms=3000,
        )
        obs = Observation(
            answer="A001 目前配送中",
            tool="get_order_status",
            arguments_json='{"order_id":"A001","extra":true}',
            source_count=1,
            latency_ms=1200,
            origin="manual-ui",
        )
        result = evaluate_observation(case, obs)
        self.assertTrue(result.passed, result.failures)

    def test_manual_ignores_http_when_not_observed(self):
        case = TestCase("M2", "manual", "hello", expected_status="200", must_contain="hello")
        obs = Observation(answer="hello", status_code=None)
        result = evaluate_observation(case, obs)
        self.assertTrue(result.passed, result.failures)

    def test_manual_detects_tool_failure(self):
        case = TestCase("M3", "manual", "cancel", expected_tool="cancel_order")
        obs = Observation(answer="ok", tool="get_order_status")
        result = evaluate_observation(case, obs)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_category, "Tool Calling")


if __name__ == "__main__":
    unittest.main()
