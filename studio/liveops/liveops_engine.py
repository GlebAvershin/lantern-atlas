#!/usr/bin/env python3
"""Lantern Atlas & Cross-Game LiveOps Engine (Battle Pass & Multi-Game Manager).

Provides a centralized backend managing seasons, cross-game contracts,
Battle Pass tiers, and shared meta-achievements across all 4 games:
- Lantern Atlas
- Soccerpoly
- Mosaic Pier
- Blackout Freight
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

# SQLite Schema
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS seasons (
    season_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    duration_days INTEGER NOT NULL,
    active_games TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_games TEXT NOT NULL,
    goal_metric TEXT NOT NULL,
    target_value INTEGER NOT NULL,
    xp_reward INTEGER NOT NULL,
    token_reward INTEGER NOT NULL,
    FOREIGN KEY(season_id) REFERENCES seasons(season_id)
);

CREATE TABLE IF NOT EXISTS player_battlepass (
    player_id TEXT NOT NULL,
    season_id TEXT NOT NULL,
    total_xp INTEGER NOT NULL DEFAULT 0,
    current_tier INTEGER NOT NULL DEFAULT 1,
    unlocked_rewards TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY(player_id, season_id)
);

CREATE TABLE IF NOT EXISTS contract_progress (
    player_id TEXT NOT NULL,
    contract_id TEXT NOT NULL,
    current_value INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(player_id, contract_id)
);
"""


@dataclass
class ContractEvent:
    player_id: str
    game_id: str
    metric: str
    increment: int = 1


class LiveOpsManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)
            # Seed default active cross-game season
            self.conn.execute("""
                INSERT OR IGNORE INTO seasons (season_id, title, duration_days, active_games, status)
                VALUES (
                    'SEASON_NORTHERN_EXPEDITION',
                    'Northern Expedition · Cross-Game Frontier',
                    45,
                    '["atlas", "soccer", "mosaic", "freight"]',
                    'ACTIVE'
                )
            """)
            # Seed cross-game contracts
            contracts = [
                (
                    "CONTRACT_01",
                    "SEASON_NORTHERN_EXPEDITION",
                    "Archipelago Tactician",
                    "Solve 3 charts in Lantern Atlas and win 2 auctions in Soccerpoly",
                    '["atlas", "soccer"]',
                    "tactical_wins",
                    5,
                    750,
                    150
                ),
                (
                    "CONTRACT_02",
                    "SEASON_NORTHERN_EXPEDITION",
                    "Shadow & Glass",
                    "Extract 3 batteries in Blackout Freight and clear 4 boards in Mosaic Pier",
                    '["freight", "mosaic"]',
                    "stealth_puzzles",
                    7,
                    900,
                    200
                ),
                (
                    "CONTRACT_03",
                    "SEASON_NORTHERN_EXPEDITION",
                    "Grand Quad Master",
                    "Participate in matches across all 4 titles during active season",
                    '["atlas", "soccer", "mosaic", "freight"]',
                    "quad_matches",
                    4,
                    1500,
                    400
                )
            ]
            for c in contracts:
                self.conn.execute("""
                    INSERT OR IGNORE INTO contracts (
                        contract_id, season_id, title, description, target_games,
                        goal_metric, target_value, xp_reward, token_reward
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, c)

    def get_current_season(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM seasons WHERE status = 'ACTIVE' LIMIT 1")
        row = cur.fetchone()
        if not row:
            return {}
        return {
            "season_id": row["season_id"],
            "title": row["title"],
            "duration_days": row["duration_days"],
            "active_games": json.loads(row["active_games"]),
            "status": row["status"]
        }

    def get_contracts(self, season_id: str = "SEASON_NORTHERN_EXPEDITION") -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM contracts WHERE season_id = ?", (season_id,))
        rows = cur.fetchall()
        return [
            {
                "contract_id": r["contract_id"],
                "season_id": r["season_id"],
                "title": r["title"],
                "description": r["description"],
                "target_games": json.loads(r["target_games"]),
                "goal_metric": r["goal_metric"],
                "target_value": r["target_value"],
                "xp_reward": r["xp_reward"],
                "token_reward": r["token_reward"],
            }
            for r in rows
        ]

    def record_progress(self, event: ContractEvent) -> Dict[str, Any]:
        """Record game action and update cross-game battlepass XP."""
        season = self.get_current_season()
        season_id = season.get("season_id", "SEASON_NORTHERN_EXPEDITION")
        contracts = self.get_contracts(season_id)

        xp_awarded = 0
        tokens_awarded = 0
        completed_contracts = []

        cur = self.conn.cursor()
        with self.conn:
            for c in contracts:
                if event.game_id in c["target_games"] and c["goal_metric"] == event.metric:
                    c_id = c["contract_id"]
                    cur.execute(
                        "SELECT current_value, completed FROM contract_progress WHERE player_id = ? AND contract_id = ?",
                        (event.player_id, c_id)
                    )
                    row = cur.fetchone()
                    current_val = row["current_value"] if row else 0
                    is_done = bool(row["completed"]) if row else False

                    if not is_done:
                        new_val = current_val + event.increment
                        completed = 1 if new_val >= c["target_value"] else 0
                        cur.execute("""
                            INSERT INTO contract_progress (player_id, contract_id, current_value, completed)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(player_id, contract_id) DO UPDATE SET
                                current_value = excluded.current_value,
                                completed = excluded.completed
                        """, (event.player_id, c_id, new_val, completed))

                        if completed:
                            xp_awarded += c["xp_reward"]
                            tokens_awarded += c["token_reward"]
                            completed_contracts.append(c["title"])

            # Update Battle Pass
            cur.execute(
                "SELECT total_xp, current_tier, unlocked_rewards FROM player_battlepass WHERE player_id = ? AND season_id = ?",
                (event.player_id, season_id)
            )
            bp_row = cur.fetchone()
            total_xp = (bp_row["total_xp"] if bp_row else 0) + xp_awarded
            # 500 XP per tier, max 30
            new_tier = min(30, max(1, (total_xp // 500) + 1))
            rewards = json.loads(bp_row["unlocked_rewards"]) if bp_row else []

            if xp_awarded > 0:
                rewards.append(f"TIER_{new_tier}_REWARD")

            cur.execute("""
                INSERT INTO player_battlepass (player_id, season_id, total_xp, current_tier, unlocked_rewards)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(player_id, season_id) DO UPDATE SET
                    total_xp = excluded.total_xp,
                    current_tier = excluded.current_tier,
                    unlocked_rewards = excluded.unlocked_rewards
            """, (event.player_id, season_id, total_xp, new_tier, json.dumps(rewards)))

        return {
            "player_id": event.player_id,
            "xp_awarded": xp_awarded,
            "tokens_awarded": tokens_awarded,
            "completed_contracts": completed_contracts,
            "current_battlepass_tier": new_tier,
            "total_xp": total_xp
        }

    def get_player_battlepass(self, player_id: str, season_id: str = "SEASON_NORTHERN_EXPEDITION") -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT total_xp, current_tier, unlocked_rewards FROM player_battlepass WHERE player_id = ? AND season_id = ?",
            (player_id, season_id)
        )
        row = cur.fetchone()
        if not row:
            return {
                "player_id": player_id,
                "season_id": season_id,
                "total_xp": 0,
                "current_tier": 1,
                "tier_progress_pct": 0.0,
                "unlocked_rewards": []
            }
        total_xp = row["total_xp"]
        tier = row["current_tier"]
        tier_xp = total_xp % 500
        return {
            "player_id": player_id,
            "season_id": season_id,
            "total_xp": total_xp,
            "current_tier": tier,
            "tier_progress_pct": round((tier_xp / 500.0) * 100, 1),
            "unlocked_rewards": json.loads(row["unlocked_rewards"])
        }
