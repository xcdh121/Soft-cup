from .evaluator import load_golden_cases, release_gate


def test_golden_set_contains_all_120_cases():
    cases = load_golden_cases()
    assert len(cases) == 120
    assert len({case["case_id"] for case in cases}) == 120


def test_release_gate_blocks_quality_or_cost_regression():
    report = release_gate(
        {
            "route_accuracy": 0.94,
            "schema_validity": 1.0,
            "success_rate": 1.0,
            "unsupported_strong_claim_rate": 0.01,
            "cost_regression": 0.02,
        }
    )
    assert not report["passed"]
    assert report["checks"]["route_accuracy"] is False
