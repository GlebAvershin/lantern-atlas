#!/usr/bin/env python3
import unittest
from unittest.mock import patch
import live_platform_gateway

class TestLivePlatformGateway(unittest.TestCase):
    def setUp(self):
        self.gw = live_platform_gateway.LivePlatformGateway()

    def test_cache_deduplication(self):
        with patch.object(self.gw, "_query_databricks_serving", return_value={"text": "OK", "usage": {"total_tokens": 50}}):
            r1 = self.gw.generate("Test prompt")
            self.assertEqual(r1["source"], "inference")
            self.assertEqual(r1["tokens_billed"], 50)

            r2 = self.gw.generate("Test prompt")
            self.assertEqual(r2["source"], "cache")
            self.assertEqual(r2["tokens_billed"], 0)
            self.assertEqual(r2["tokens_saved"], 50)

    def test_circuit_breaker_tripping(self):
        with patch.object(self.gw, "_query_databricks_serving", side_effect=RuntimeError("Endpoint 503")):
            for _ in range(3):
                res = self.gw.generate("Failing query", cache_result=False)
                self.assertIn("fallback", res["source"])

            self.assertEqual(self.gw.circuit_breaker.state, "OPEN")
            
            # Next request should be directly rejected by circuit breaker without calling Databricks
            res_open = self.gw.generate("Failing query 4", cache_result=False)
            self.assertEqual(res_open["model"], "circuit_open_fallback")

    def test_metrics_calculation(self):
        with patch.object(self.gw, "_query_databricks_serving", return_value={"text": "Result", "usage": {"total_tokens": 100}}):
            self.gw.generate("Q1")
            self.gw.generate("Q1")
            metrics = self.gw.get_metrics()
            self.assertEqual(metrics["requests_total"], 2)
            self.assertEqual(metrics["cache_hits"], 1)
            self.assertEqual(metrics["tokens_billed"], 100)
            self.assertEqual(metrics["tokens_saved"], 100)

if __name__ == "__main__":
    unittest.main()
