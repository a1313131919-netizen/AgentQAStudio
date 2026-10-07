from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from engine import TestCase, TestResult, categorize_failures, json_subset


@dataclass
class Observation:
    answer: str = ""
    tool: str = ""
    arguments_json: str = ""
    source_count: int = 0
    latency_ms: float = 0.0
    status_code: int | None = None
    raw_text: str = ""
    raw_json: Any = None
    origin: str = "manual"


def evaluate_observation(case: TestCase, obs: Observation) -> TestResult:
    failures: list[str] = []

    if case.expected_status.strip() and obs.status_code is not None:
        expected_statuses: set[int] = set()
        for token in case.expected_status.replace("/", ",").replace(" ", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                expected_statuses.add(int(token))
            except ValueError:
                failures.append(f"Invalid expected status: {token}")
                break
        if expected_statuses and obs.status_code not in expected_statuses:
            failures.append(f"Status expected {sorted(expected_statuses)}, actual {obs.status_code}")

    if case.expected_tool.strip() and obs.tool.strip() != case.expected_tool.strip():
        failures.append(f"Tool expected '{case.expected_tool.strip()}', actual '{obs.tool.strip()}'")

    if case.expected_args_json.strip():
        try:
            expected_args = json.loads(case.expected_args_json)
        except json.JSONDecodeError as exc:
            failures.append(f"Expected arguments JSON invalid: {exc}")
        else:
            try:
                actual_args = json.loads(obs.arguments_json) if obs.arguments_json.strip() else None
            except json.JSONDecodeError as exc:
                failures.append(f"Actual arguments JSON invalid: {exc}")
            else:
                if not json_subset(expected_args, actual_args):
                    failures.append(
                        "Arguments mismatch: expected subset "
                        + json.dumps(expected_args, ensure_ascii=False)
                        + ", actual "
                        + json.dumps(actual_args, ensure_ascii=False)
                    )

    answer = obs.answer or obs.raw_text
    if case.must_contain.strip():
        required = [x.strip() for x in case.must_contain.split("|") if x.strip()]
        missing = [x for x in required if x.lower() not in answer.lower()]
        if missing:
            failures.append("Answer missing: " + ", ".join(missing))

    if case.must_not_contain.strip():
        forbidden = [x.strip() for x in case.must_not_contain.split("|") if x.strip()]
        found = [x for x in forbidden if x.lower() in answer.lower()]
        if found:
            failures.append("Answer contains forbidden: " + ", ".join(found))

    if case.min_sources > 0 and obs.source_count < case.min_sources:
        failures.append(f"Sources expected >= {case.min_sources}, actual {obs.source_count}")

    if case.max_latency_ms > 0 and obs.latency_ms > 0 and obs.latency_ms > case.max_latency_ms:
        failures.append(
            f"Latency expected <= {case.max_latency_ms} ms, actual {obs.latency_ms:.0f} ms"
        )

    response_json = obs.raw_json
    if response_json is None and obs.arguments_json.strip():
        try:
            response_json = {"arguments": json.loads(obs.arguments_json)}
        except json.JSONDecodeError:
            response_json = None

    return TestResult(
        case_id=case.case_id,
        name=case.name,
        category=case.category,
        input_text=case.input_text,
        passed=not failures,
        status_code=obs.status_code,
        latency_ms=obs.latency_ms,
        expected_tool=case.expected_tool,
        actual_tool=obs.tool,
        answer=answer,
        source_count=obs.source_count,
        failures=failures,
        error_category=categorize_failures(failures),
        response_text=obs.raw_text or answer,
        response_json=response_json,
        request_body=case.input_text,
        request_url=obs.origin,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
