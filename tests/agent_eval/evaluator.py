"""Deterministic golden-set expansion and release gate calculations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


FIXTURE_DIR = Path(__file__).with_name("fixtures")


def load_golden_cases() -> list[dict]:
    manifest = json.loads((FIXTURE_DIR / "golden_manifest.json").read_text(encoding="utf-8"))
    cases = []
    for category in manifest["categories"]:
        for index in range(1, int(category["count"]) + 1):
            cases.append(
                {
                    **category,
                    "case_id": f"{category['name']}-{index:03d}",
                }
            )
    return cases


@dataclass(frozen=True)
class ReleaseThresholds:
    route_accuracy: float = 0.95
    schema_validity: float = 0.99
    success_rate: float = 0.995
    unsupported_strong_claim_rate: float = 0.03
    max_cost_regression: float = 0.15


def release_gate(metrics: dict[str, float], thresholds: ReleaseThresholds | None = None) -> dict:
    limits = thresholds or ReleaseThresholds()
    checks = {
        "route_accuracy": metrics.get("route_accuracy", 0) >= limits.route_accuracy,
        "schema_validity": metrics.get("schema_validity", 0) >= limits.schema_validity,
        "success_rate": metrics.get("success_rate", 0) >= limits.success_rate,
        "unsupported_strong_claim_rate": metrics.get("unsupported_strong_claim_rate", 1)
        <= limits.unsupported_strong_claim_rate,
        "cost_regression": metrics.get("cost_regression", 1) <= limits.max_cost_regression,
    }
    return {"passed": all(checks.values()), "checks": checks}
