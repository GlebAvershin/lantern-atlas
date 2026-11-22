#!/usr/bin/env python3
"""Cross-Game Contextual Multi-Armed Bandit (LinUCB) for Dynamic In-Game Shop.

Personalizes non-predatory cosmetic offerings (skins, lenses, patterns, decals)
across all 4 titles (Lantern Atlas, Soccerpoly, Mosaic Pier, Blackout Freight)
without paywalls or aggressive monetization.
Implemented using pure Python linear algebra for 100% dependency-free execution.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import time
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]

# 8 Cosmetic Arms spanning the 4 games
COSMETIC_ARMS = [
    {"arm_id": "atlas_aurora_lens", "game": "atlas", "category": "Lens", "style": "Luminescent", "price_tokens": 150},
    {"arm_id": "atlas_brass_frame", "game": "atlas", "category": "Frame", "style": "Steampunk", "price_tokens": 200},
    {"arm_id": "soccer_golden_ball", "game": "soccer", "category": "Ball", "style": "Prestige", "price_tokens": 300},
    {"arm_id": "soccer_retro_kit", "game": "soccer", "category": "Kit", "style": "Classic", "price_tokens": 250},
    {"arm_id": "mosaic_azure_glaze", "game": "mosaic", "category": "Tile", "style": "Artistic", "price_tokens": 120},
    {"arm_id": "mosaic_pearl_pier", "game": "mosaic", "category": "Theme", "style": "Luminescent", "price_tokens": 180},
    {"arm_id": "freight_carbon_drone", "game": "freight", "category": "Chassis", "style": "Tactical", "price_tokens": 350},
    {"arm_id": "freight_amber_visor", "game": "freight", "category": "Optics", "style": "Tactical", "price_tokens": 180},
]


# Pure-Python matrix routines for d x d matrices
def mat_identity(d: int) -> List[List[float]]:
    return [[1.0 if i == j else 0.0 for j in range(d)] for i in range(d)]


def mat_zeros(d: int) -> List[List[float]]:
    return [[0.0 for _ in range(d)] for _ in range(d)]


def mat_vec_mul(mat: List[List[float]], vec: List[float]) -> List[float]:
    return [sum(row[j] * vec[j] for j in range(len(vec))) for row in mat]


def dot_product(v1: List[float], v2: List[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


def outer_product(v: List[float]) -> List[List[float]]:
    d = len(v)
    return [[v[i] * v[j] for j in range(d)] for i in range(d)]


def mat_add(m1: List[List[float]], m2: List[List[float]]) -> List[List[float]]:
    d = len(m1)
    return [[m1[i][j] + m2[i][j] for j in range(d)] for i in range(d)]


def mat_invert(m: List[List[float]]) -> List[List[float]]:
    """Invert d x d matrix using Gauss-Jordan elimination."""
    n = len(m)
    # Augment with identity
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]

    for col in range(n):
        # Pivot selection
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            aug[pivot_row][col] = 1e-6  # Regularization
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]

        pivot = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= pivot

        for r in range(n):
            if r != col:
                factor = aug[r][col]
                for j in range(2 * n):
                    aug[r][j] -= factor * aug[col][j]

    return [row[n:] for row in aug]


class LinUCBBandit:
    """Disjoint Linear Upper Confidence Bound (LinUCB) contextual bandit."""

    def __init__(self, num_arms: int, d: int = 6, alpha: float = 0.8):
        self.num_arms = num_arms
        self.d = d
        self.alpha = alpha
        # A_a: d x d identity matrix for each arm
        self.A = [mat_identity(d) for _ in range(num_arms)]
        # b_a: d-dimensional response vector
        self.b = [[0.0] * d for _ in range(num_arms)]

    def select_arm(self, x: List[float]) -> int:
        best_arm = 0
        best_p = -float("inf")

        for a in range(self.num_arms):
            A_inv = mat_invert(self.A[a])
            theta = mat_vec_mul(A_inv, self.b[a])
            expected_payoff = dot_product(theta, x)
            # quadratic form: x^T A_inv x
            A_inv_x = mat_vec_mul(A_inv, x)
            variance = max(0.0, dot_product(x, A_inv_x))
            uncertainty = self.alpha * math.sqrt(variance)
            p = expected_payoff + uncertainty

            if p > best_p:
                best_p = p
                best_arm = a

        return best_arm

    def update(self, arm: int, x: List[float], reward: float):
        outer = outer_product(x)
        self.A[arm] = mat_add(self.A[arm], outer)
        for i in range(self.d):
            self.b[arm][i] += reward * x[i]


def generate_player_context(rng: random.Random) -> Tuple[List[float], Dict[str, Any]]:
    """Generates player context vector x in R^6.

    Features:
    0: Playstyle velocity (0: methodical / stealth, 1: fast-paced arcade)
    1: Battle pass tier normalized [0, 1]
    2: Session frequency index [0, 1]
    3: Soft currency balance bracket [0, 1]
    4: Game affinity index (0: puzzle/board, 1: action/tactics)
    5: Aesthetic preference (0: minimalist, 1: flamboyant/prestige)
    """
    velocity = rng.uniform(0.1, 0.9)
    bp_tier = rng.uniform(0.0, 1.0)
    session_freq = rng.uniform(0.2, 1.0)
    currency = rng.uniform(0.1, 1.0)
    game_affinity = rng.uniform(0.0, 1.0)
    aesthetic = rng.uniform(0.1, 0.9)

    vec = [velocity, bp_tier, session_freq, currency, game_affinity, aesthetic]
    profile = {
        "is_action_oriented": game_affinity > 0.5,
        "is_tactical": velocity < 0.4 and game_affinity > 0.5,
        "prefers_prestige": aesthetic > 0.6,
        "prefers_puzzle": game_affinity <= 0.5,
    }
    return vec, profile


def simulate_user_response(
    arm: Dict[str, Any],
    profile: Dict[str, Any],
    rng: random.Random,
) -> float:
    """True user response probability modeling based on aesthetic and gameplay alignment."""
    prob = 0.15  # Base organic engagement

    # Alignment boosts
    if arm["game"] == "freight" and profile["is_tactical"]:
        prob += 0.45
    elif arm["game"] == "soccer" and profile["is_action_oriented"]:
        prob += 0.40
    elif arm["game"] in ("atlas", "mosaic") and profile["prefers_puzzle"]:
        prob += 0.42

    if arm["style"] == "Prestige" and profile["prefers_prestige"]:
        prob += 0.30
    if arm["style"] == "Tactical" and profile["is_tactical"]:
        prob += 0.35

    prob = min(0.92, max(0.05, prob))
    return 1.0 if rng.random() < prob else 0.0


def run_bandit_simulation(impressions: int = 20000) -> Dict[str, Any]:
    rng = random.Random(42)
    num_arms = len(COSMETIC_ARMS)
    bandit = LinUCBBandit(num_arms=num_arms, d=6, alpha=0.8)

    # Baselines
    random_rewards = []
    top_chart_rewards = []
    bandit_rewards = []

    t0 = time.perf_counter()

    for t in range(impressions):
        vec, profile = generate_player_context(rng)

        # 1. Random Policy
        arm_rand = rng.randint(0, num_arms - 1)
        r_rand = simulate_user_response(COSMETIC_ARMS[arm_rand], profile, rng)
        random_rewards.append(r_rand)

        # 2. Static Top-Charts Policy
        arm_top = 2 if t % 2 == 0 else 6
        r_top = simulate_user_response(COSMETIC_ARMS[arm_top], profile, rng)
        top_chart_rewards.append(r_top)

        # 3. Contextual LinUCB Bandit Policy
        arm_bandit = bandit.select_arm(vec)
        r_bandit = simulate_user_response(COSMETIC_ARMS[arm_bandit], profile, rng)
        bandit.update(arm_bandit, vec, r_bandit)
        bandit_rewards.append(r_bandit)

    elapsed_s = time.perf_counter() - t0

    mean_rand_ctr = sum(random_rewards) / len(random_rewards)
    mean_top_ctr = sum(top_chart_rewards) / len(top_chart_rewards)
    mean_bandit_ctr = sum(bandit_rewards) / len(bandit_rewards)

    # Arm popularity breakdown in bandit
    arm_picks = {COSMETIC_ARMS[i]["arm_id"]: 0 for i in range(num_arms)}
    for _ in range(2000):
        vec, _ = generate_player_context(rng)
        picked = bandit.select_arm(vec)
        arm_picks[COSMETIC_ARMS[picked]["arm_id"]] += 1

    return {
        "study_title": "Cross-Game Contextual Bandit (LinUCB) Dynamic Cosmetic Personalization",
        "total_simulated_impressions": impressions,
        "execution_time_seconds": round(elapsed_s, 3),
        "performance_comparison": {
            "random_recommendations_ctr_pct": round(mean_rand_ctr * 100, 2),
            "static_top_charts_ctr_pct": round(mean_top_ctr * 100, 2),
            "linucb_contextual_bandit_ctr_pct": round(mean_bandit_ctr * 100, 2),
            "relative_uplift_over_static_pct": round(((mean_bandit_ctr - mean_top_ctr) / mean_top_ctr) * 100, 2),
            "relative_uplift_over_random_pct": round(((mean_bandit_ctr - mean_rand_ctr) / mean_rand_ctr) * 100, 2),
        },
        "arm_distribution_sample": arm_picks,
        "ethical_monetization_principles": [
            "Zero paywalls or lootboxes: 100% of personalized items are claimable through earned Battle Pass tokens.",
            "LinUCB aligns item recommendations with player artistic taste rather than pressure tactics or FOMO timers.",
            "Dynamic catalog rotation ensures players discover cosmetic assets across all 4 titles organically."
        ]
    }


def main():
    report = run_bandit_simulation(20000)
    out_dir = ROOT / "docs/evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "contextual-bandit-study.json"
    out_file.write_text(json.dumps(report, indent=2))
    print(f"Generated {out_file} with {report['performance_comparison']['linucb_contextual_bandit_ctr_pct']}% CTR.")


if __name__ == "__main__":
    main()
