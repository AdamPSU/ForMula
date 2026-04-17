"""Declarative quiz loader + answers→HairProfile mapper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai.orchestrator import HairProfile

_QUIZ_PATH = Path(__file__).resolve().parent / "data" / "quiz.json"

QUIZ: dict = json.loads(_QUIZ_PATH.read_text())
QUESTIONS: list[dict] = QUIZ["questions"]
_BY_ID: dict[str, dict] = {q["id"]: q for q in QUESTIONS}


class QuizAnswerError(ValueError):
    """Raised when submitted answers don't satisfy the quiz schema."""


def _is_active(question: dict, answers: dict[str, Any]) -> bool:
    cond = question.get("conditional_on")
    if cond is None:
        return True
    parent = answers.get(cond["question_id"])
    if parent is None:
        return False
    parent_values = parent if isinstance(parent, list) else [parent]
    forbidden = set(cond["value_not_in"])
    return any(v not in forbidden for v in parent_values)


def answers_to_profile(answers: dict[str, Any]) -> HairProfile:
    fields: dict[str, Any] = {"free_text": ""}
    for q in QUESTIONS:
        qid, qtype, field = q["id"], q["type"], q["maps_to"]
        valid_ids = {opt["id"] for opt in q["options"]}

        if not _is_active(q, answers):
            skip = q.get("skip_value")
            if skip is None:
                raise QuizAnswerError(f"{qid}: inactive question has no skip_value")
            fields[field] = skip
            continue

        if qid not in answers:
            raise QuizAnswerError(f"{qid}: missing answer")
        value = answers[qid]

        if qtype == "multi":
            if not isinstance(value, list) or not value:
                raise QuizAnswerError(f"{qid}: expected non-empty list")
            bad = [v for v in value if v not in valid_ids]
            if bad:
                raise QuizAnswerError(f"{qid}: invalid options {bad}")
            max_select = q.get("max_select")
            if max_select and len(value) > max_select:
                raise QuizAnswerError(f"{qid}: pick at most {max_select}")
            fields[field] = value
        else:
            if value not in valid_ids:
                raise QuizAnswerError(f"{qid}: invalid option {value!r}")
            fields[field] = [value] if q.get("wrap_in_list") else value

    return HairProfile(**fields)
