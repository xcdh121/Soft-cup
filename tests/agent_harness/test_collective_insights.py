from edu_core.services.collective_insights import CollectiveInsightService


def test_collective_insight_suppresses_small_cohorts() -> None:
    rows = [("kp-1", f"student-{index}", index % 2 == 0) for index in range(9)]

    assert CollectiveInsightService.aggregate_events(rows) == {}


def test_collective_insight_publishes_only_deidentified_aggregate() -> None:
    rows = [("kp-1", f"student-{index}", index < 6) for index in range(10)]

    result = CollectiveInsightService.aggregate_events(rows)

    assert result == {
        "kp-1": {
            "sample_size": 10,
            "attempt_count": 10,
            "correct_rate": 0.6,
            "difficulty_rate": 0.4,
        }
    }
    assert "student" not in str(result)
