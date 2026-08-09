"""Pure, deterministic expert-parameter Bayesian Knowledge Tracing helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import exp


DEFAULT_DIFFICULTY_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "easy": {"slip": 0.08, "guess": 0.25, "weight": 0.70},
    "medium": {"slip": 0.10, "guess": 0.20, "weight": 1.00},
    "hard": {"slip": 0.15, "guess": 0.10, "weight": 1.00},
}

DEFAULT_ANSWER_MODE_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "flashcard": {"slip": 0.15, "guess": 0.05, "weight": 0.60},
    "subjective": {"slip": 0.15, "guess": 0.02, "weight": 0.80},
    "programming": {"slip": 0.10, "guess": 0.01, "weight": 1.00},
    "manual": {"slip": 0.15, "guess": 0.02, "weight": 0.80},
}


def clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class BKTParameters:
    initial_mastery: float = 0.20
    learn_probability: float = 0.12
    slip_probability: float = 0.10
    guess_probability: float = 0.20
    forget_probability_daily: float = 0.005
    event_weight: float = 1.0

    def normalized(self) -> "BKTParameters":
        return BKTParameters(
            initial_mastery=clamp_probability(self.initial_mastery),
            learn_probability=clamp_probability(self.learn_probability),
            slip_probability=clamp_probability(self.slip_probability),
            guess_probability=clamp_probability(self.guess_probability),
            forget_probability_daily=clamp_probability(
                self.forget_probability_daily
            ),
            event_weight=clamp_probability(self.event_weight),
        )


@dataclass(frozen=True)
class BKTResult:
    prior_mastery: float
    prior_after_forgetting: float
    posterior_if_correct: float
    posterior_if_wrong: float
    posterior_after_observation: float
    posterior_after_learning: float
    mastery_probability: float
    p_correct_before: float
    p_correct_next: float
    observed_score: float
    event_weight: float
    effective_parameters: dict[str, float]
    reason_codes: list[str]


def apply_adjustments(
    parameters: BKTParameters,
    *,
    difficulty: str | None,
    answer_mode: str,
    difficulty_adjustments: dict | None = None,
    answer_mode_adjustments: dict | None = None,
    explicit_weight: float | None = None,
    is_verification: bool = False,
) -> BKTParameters:
    """Resolve transparent difficulty/mode overrides into effective parameters."""

    difficulty_rules = {
        **DEFAULT_DIFFICULTY_ADJUSTMENTS,
        **(difficulty_adjustments or {}),
    }
    mode_rules = {
        **DEFAULT_ANSWER_MODE_ADJUSTMENTS,
        **(answer_mode_adjustments or {}),
    }
    resolved = parameters
    for rule in (
        difficulty_rules.get((difficulty or "").lower(), {}),
        mode_rules.get(answer_mode.lower(), {}),
    ):
        if not rule:
            continue
        resolved = replace(
            resolved,
            slip_probability=float(rule.get("slip", resolved.slip_probability)),
            guess_probability=float(rule.get("guess", resolved.guess_probability)),
            event_weight=float(rule.get("weight", resolved.event_weight)),
        )
    if explicit_weight is not None:
        resolved = replace(resolved, event_weight=explicit_weight)
    if is_verification:
        resolved = replace(resolved, learn_probability=0.0)
    return resolved.normalized()


def _observation_posteriors(
    prior: float, parameters: BKTParameters
) -> tuple[float, float, float]:
    slip = parameters.slip_probability
    guess = parameters.guess_probability
    p_correct = prior * (1 - slip) + (1 - prior) * guess
    p_wrong = prior * slip + (1 - prior) * (1 - guess)
    correct = prior if p_correct == 0 else prior * (1 - slip) / p_correct
    wrong = prior if p_wrong == 0 else prior * slip / p_wrong
    return clamp_probability(correct), clamp_probability(wrong), clamp_probability(
        p_correct
    )


def update_bkt(
    *,
    prior_mastery: float,
    observed_score: float,
    parameters: BKTParameters,
    occurred_at: datetime,
    last_occurred_at: datetime | None,
) -> BKTResult:
    """Apply forgetting, observation, learning transition and evidence weighting."""

    params = parameters.normalized()
    prior = clamp_probability(prior_mastery)
    elapsed_days = 0.0
    if last_occurred_at is not None:
        # SQLite drops timezone metadata even for timezone-aware columns.
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        if last_occurred_at.tzinfo is None:
            last_occurred_at = last_occurred_at.replace(tzinfo=timezone.utc)
        elapsed_days = max(
            0.0, (occurred_at - last_occurred_at).total_seconds() / 86400.0
        )
    forget_delta = 1 - (1 - params.forget_probability_daily) ** elapsed_days
    forgotten_prior = params.initial_mastery + (
        prior - params.initial_mastery
    ) * (1 - forget_delta)
    forgotten_prior = clamp_probability(forgotten_prior)

    correct, wrong, p_correct_before = _observation_posteriors(
        forgotten_prior, params
    )
    score = clamp_probability(observed_score)
    observed = wrong + score * (correct - wrong)
    learned = observed + (1 - observed) * params.learn_probability
    weighted = forgotten_prior + params.event_weight * (
        learned - forgotten_prior
    )
    weighted = clamp_probability(weighted)
    p_correct_next = weighted * (1 - params.slip_probability) + (
        1 - weighted
    ) * params.guess_probability

    reasons = ["time_forgetting_applied"] if elapsed_days > 0 else []
    if score >= 0.999:
        reasons.extend(["correct_answer", "observation_increased_mastery"])
    elif score <= 0.001:
        reasons.extend(["incorrect_answer", "observation_reduced_mastery"])
    else:
        reasons.extend(["partial_score", "weighted_observation"])
    if params.learn_probability > 0:
        reasons.append("learning_transition_applied")
    else:
        reasons.append("verification_without_learning_transition")
    if params.event_weight < 1:
        reasons.append("event_weight_applied")

    return BKTResult(
        prior_mastery=prior,
        prior_after_forgetting=forgotten_prior,
        posterior_if_correct=correct,
        posterior_if_wrong=wrong,
        posterior_after_observation=clamp_probability(observed),
        posterior_after_learning=clamp_probability(learned),
        mastery_probability=weighted,
        p_correct_before=p_correct_before,
        p_correct_next=clamp_probability(p_correct_next),
        observed_score=score,
        event_weight=params.event_weight,
        effective_parameters=asdict(params),
        reason_codes=reasons,
    )


def evidence_confidence(
    effective_event_count: float, average_mapping_confidence: float
) -> float:
    evidence_factor = 1 - exp(-max(0.0, effective_event_count) / 5.0)
    return clamp_probability(average_mapping_confidence * evidence_factor)


def classify_status(
    mastery_probability: float,
    confidence: float,
    *,
    event_count: float,
    days_since_verification: float | None,
) -> tuple[str, list[str]]:
    if event_count <= 0:
        return "not_started", ["no_learning_event"]
    if confidence < 0.40:
        return "insufficient_evidence", ["low_evidence_confidence"]
    if days_since_verification is not None and days_since_verification >= 30:
        return "at_risk", ["verification_stale"]
    if mastery_probability < 0.60:
        return "weak", ["below_weak_threshold"]
    if mastery_probability < 0.80:
        return "developing", ["below_mastery_threshold"]
    if confidence < 0.60:
        return "insufficient_evidence", ["mastery_high_but_evidence_insufficient"]
    return "mastered", ["mastery_and_evidence_sufficient"]


def classify_trend(probabilities: list[float]) -> str:
    if len(probabilities) < 2:
        return "insufficient_evidence"
    delta = probabilities[-1] - probabilities[0]
    if delta >= 0.05:
        return "up"
    if delta <= -0.05:
        return "down"
    return "stable"


def legacy_ewma(previous: float, score: float) -> float:
    return clamp_probability(previous * 0.7 + clamp_probability(score) * 0.3)


def payload_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
