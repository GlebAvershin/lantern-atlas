#!/usr/bin/env python3
"""Unit tests for Lantern Atlas Adaptive Cascade Router."""
import unittest
from pathlib import Path
from cascade_router import CascadeRouter, CATALOG

ROOT = Path(__file__).resolve().parents[2]


class TestCascadeRouter(unittest.TestCase):
    def setUp(self):
        self.router = CascadeRouter(oracle_path=ROOT / "studio/oracle")

    def test_complexity_classification(self):
        self.assertEqual(self.router.classify_complexity(scramble_par=1, active_lights=1), "fast")
        self.assertEqual(self.router.classify_complexity(scramble_par=3, active_lights=5), "fast")
        self.assertEqual(self.router.classify_complexity(scramble_par=4, active_lights=6), "deep")
        self.assertEqual(self.router.classify_complexity(scramble_par=6, active_lights=9), "deep")

    def test_model_selection(self):
        primary_fast, fallback_fast = self.router.select_model("fast")
        self.assertEqual(CATALOG[primary_fast].tier, "fast")
        
        primary_deep, fallback_deep = self.router.select_model("deep")
        self.assertEqual(CATALOG[primary_deep].tier, "deep")

    def test_provider_affinity(self):
        primary_google, _ = self.router.select_model("deep", preferred_provider="google")
        self.assertEqual(CATALOG[primary_google].provider, "google")

        primary_codex, _ = self.router.select_model("deep", preferred_provider="codex")
        self.assertEqual(CATALOG[primary_codex].provider, "codex")

    def test_route_chart_execution(self):
        decision = self.router.route_chart("chart_01_harbour", scramble_par=1, active_lights=1)
        self.assertEqual(decision.selected_tier, "fast")
        self.assertTrue(decision.verified_by_oracle)
        self.assertGreater(decision.estimated_latency_ms, 0)
        self.assertGreater(decision.estimated_cost_usd, 0)

    def test_benchmark_generation(self):
        report = self.router.generate_benchmark_report()
        self.assertEqual(report["charts_tested"], 8)
        self.assertGreater(report["finops_savings_percentage"], 50.0)
        self.assertGreater(report["latency_reduction_percentage"], 30.0)
        self.assertEqual(report["oracle_verification_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
