#!/usr/bin/env python3
"""Unit tests for Lantern Atlas Cross-Game LiveOps Engine and LinUCB Bandit."""
import unittest
from studio.liveops.liveops_engine import LiveOpsManager, ContractEvent
from studio.liveops.contextual_bandit import (
    LinUCBBandit,
    COSMETIC_ARMS,
    generate_player_context,
    mat_invert,
    mat_vec_mul,
)
import random


class TestLiveOps(unittest.TestCase):
    def setUp(self):
        self.mgr = LiveOpsManager(":memory:")

    def test_season_initialization(self):
        season = self.mgr.get_current_season()
        self.assertEqual(season["season_id"], "SEASON_NORTHERN_EXPEDITION")
        self.assertEqual(len(season["active_games"]), 4)

    def test_contracts_retrieval(self):
        contracts = self.mgr.get_contracts()
        self.assertGreaterEqual(len(contracts), 3)

    def test_cross_game_progress_and_battlepass_level_up(self):
        player_id = "PLAYER_TEST_42"
        # Progress on Archipelago Tactician contract
        res = self.mgr.record_progress(ContractEvent(
            player_id=player_id,
            game_id="atlas",
            metric="tactical_wins",
            increment=5
        ))
        self.assertIn("Archipelago Tactician", res["completed_contracts"])
        self.assertGreater(res["xp_awarded"], 0)

        # Check battlepass
        bp = self.mgr.get_player_battlepass(player_id)
        self.assertGreaterEqual(bp["total_xp"], 750)
        self.assertEqual(bp["current_tier"], 2)


class TestContextualBandit(unittest.TestCase):
    def test_matrix_inversion(self):
        m = [
            [2.0, 1.0],
            [1.0, 3.0]
        ]
        inv = mat_invert(m)
        # Check that m * inv is approximately identity
        r0 = mat_vec_mul(m, inv[0])
        self.assertAlmostEqual(r0[0], 1.0, places=5)
        self.assertAlmostEqual(r0[1], 0.0, places=5)

    def test_linucb_arm_selection(self):
        bandit = LinUCBBandit(num_arms=len(COSMETIC_ARMS), d=6, alpha=1.0)
        context = [0.5, 0.2, 0.8, 0.4, 0.9, 0.7]
        arm = bandit.select_arm(context)
        self.assertTrue(0 <= arm < len(COSMETIC_ARMS))

    def test_linucb_learning_update(self):
        bandit = LinUCBBandit(num_arms=4, d=2, alpha=0.5)
        context = [1.0, 0.0]
        # Arm 1 gives reward 1.0, Arm 0 gives 0.0
        for _ in range(10):
            bandit.update(1, context, 1.0)
            bandit.update(0, context, 0.0)

        # Selecting on context should now favor arm 1
        arm = bandit.select_arm(context)
        self.assertEqual(arm, 1)


if __name__ == "__main__":
    unittest.main()
