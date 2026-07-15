"""Utilities for resolving study content to a course knowledge point."""

import re

from edu_db.models import KnowledgePoint


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii() and term.replace(" ", "").isalnum():
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
    return term in text


def _add_term(terms: dict[str, int], value: str, weight: int) -> None:
    normalized = _normalize(value)
    if normalized:
        terms[normalized] = max(weight, terms.get(normalized, 0))


def _weighted_terms(point: KnowledgePoint) -> dict[str, int]:
    """Build useful aliases without requiring generated text to repeat a full title."""
    terms: dict[str, int] = {}
    _add_term(terms, point.name, 1000)
    for tag in point.tags or []:
        normalized_tag = str(tag).replace("-", " ")
        _add_term(terms, normalized_tag, 900)
        _add_term(terms, str(tag), 900)

    name = _normalize(point.name)
    parts = [part.strip() for part in re.split(r"\s*(?:与|和|及|、)\s*", name)]
    if len(parts) > 1:
        for part in parts:
            _add_term(terms, part, 600)

        # “时间与空间复杂度” should recognize both “时间复杂度” and
        # “空间复杂度”, while treating the bare word “复杂度” as less specific.
        shared_suffixes = ("复杂度", "排序", "查找", "遍历", "匹配")
        for suffix in shared_suffixes:
            if parts[-1].endswith(suffix):
                _add_term(terms, suffix, 250)
                for part in parts[:-1]:
                    if not part.endswith(suffix):
                        _add_term(terms, f"{part}{suffix}", 700)

    for generic_suffix in ("基础", "设计", "问题"):
        if name.endswith(generic_suffix):
            _add_term(terms, name[: -len(generic_suffix)], 700)

    # Titles such as “图的概念与存储” need to recognize the subject “图”.
    for part in parts:
        if "的概念" in part:
            _add_term(terms, part.split("的概念", 1)[0], 750)
    return terms


def match_knowledge_point_id(
    points: list[KnowledgePoint],
    texts: list[str | None] | None,
    *,
    allow_contains: bool = True,
) -> str | None:
    """Match one best knowledge point from already-loaded course points."""
    normalized_texts = [_normalize(text) for text in (texts or []) if text]
    if not normalized_texts:
        return None

    scores: dict[str, int] = {}
    for point in points:
        terms = _weighted_terms(point)
        exact_weight = max(
            (
                weight
                for text in normalized_texts
                for term, weight in terms.items()
                if text == term
            ),
            default=0,
        )
        if exact_weight:
            scores[point.id] = 10_000 + exact_weight
            continue
        if not allow_contains:
            continue

        matched = sorted(
            {
                (weight, len(term))
                for text in normalized_texts
                for term, weight in terms.items()
                if _contains_term(text, term)
            },
            reverse=True,
        )
        if matched:
            best_weight, best_length = matched[0]
            # Multiple distinct clues slightly strengthen the result without
            # allowing generic repeated words to dominate a specific subject.
            scores[point.id] = best_weight + best_length + min(50, len(matched) * 5)

    if not scores:
        return None
    best_score = max(scores.values())
    best_matches = [
        point_id for point_id, score in scores.items() if score == best_score
    ]
    return best_matches[0] if len(best_matches) == 1 else None


def resolve_knowledge_point_id(
    db,
    course_id: str | None,
    *,
    explicit_id: str | None = None,
    texts: list[str | None] | None = None,
    allow_contains: bool = True,
) -> str | None:
    """Resolve one unambiguous knowledge point from an ID or related text."""
    if explicit_id:
        point = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.id == explicit_id,
                KnowledgePoint.course_id == course_id,
            )
            .first()
        )
        if not point:
            raise ValueError(
                f"Knowledge point {explicit_id} is not in the project course"
            )
        return point.id

    if not course_id:
        return None
    points = (
        db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    )
    return match_knowledge_point_id(points, texts, allow_contains=allow_contains)
