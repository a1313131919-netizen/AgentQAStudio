from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from engine import ApiConfig, TestCase, TestResult, summarize_results


APP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AgentQAStudio"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "history.db"
CONFIG_PATH = APP_DIR / "config.json"
BROWSER_CONFIG_PATH = APP_DIR / "browser_config.json"
CASES_PATH = APP_DIR / "test_cases.json"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                endpoint TEXT,
                total INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                failed INTEGER NOT NULL,
                pass_rate REAL NOT NULL,
                avg_latency_ms REAL NOT NULL,
                p95_latency_ms REAL NOT NULL,
                results_json TEXT NOT NULL
            )
            """
        )


def save_config(config: ApiConfig) -> None:
    data = asdict(config)
    data["bearer_token"] = ""  # Never persist API secrets by default.
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> ApiConfig:
    if not CONFIG_PATH.exists():
        return ApiConfig()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        allowed = {f.name for f in ApiConfig.__dataclass_fields__.values()}
        return ApiConfig(**{k: v for k, v in data.items() if k in allowed})
    except Exception:
        return ApiConfig()


def save_browser_settings(data: dict[str, Any]) -> None:
    BROWSER_CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_browser_settings() -> dict[str, Any]:
    if not BROWSER_CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(BROWSER_CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cases(cases: list[TestCase]) -> None:
    CASES_PATH.write_text(
        json.dumps([asdict(case) for case in cases], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cases() -> list[TestCase]:
    if not CASES_PATH.exists():
        return []
    try:
        rows = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            return []
        allowed = set(TestCase.__dataclass_fields__.keys())
        return [
            TestCase(**{k: v for k, v in row.items() if k in allowed})
            for row in rows
            if isinstance(row, dict)
        ]
    except Exception:
        return []


def save_run(started_at: str, endpoint: str, results: list[TestResult]) -> int:
    summary = summarize_results(results)
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs(
                started_at, endpoint, total, passed, failed, pass_rate,
                avg_latency_ms, p95_latency_ms, results_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                endpoint,
                summary["total"],
                summary["passed"],
                summary["failed"],
                summary["pass_rate"],
                summary["avg_latency_ms"],
                summary["p95_latency_ms"],
                json.dumps([r.to_dict() for r in results], ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, started_at, endpoint, total, passed, failed, pass_rate,
                   avg_latency_ms, p95_latency_ms
            FROM runs ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def load_run(run_id: int) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT results_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return []
        return json.loads(row[0])
