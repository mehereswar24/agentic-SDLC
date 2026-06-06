from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import PRD, Critique
from tests.fixtures import make_critique, make_prd


def test_prd_fixture_is_valid() -> None:
    prd = make_prd()
    assert prd.title == "Habit Tracker"
    assert len(prd.user_stories) >= 1
    # Round-trip JSON to ensure the schema serialises cleanly.
    revived = PRD.model_validate_json(prd.model_dump_json())
    assert revived == prd


def test_prd_rejects_wrong_types() -> None:
    payload = make_prd().model_dump(mode="python")
    payload["user_stories"] = "not a list"
    with pytest.raises(ValidationError):
        PRD.model_validate(payload)


def test_prd_rejects_missing_required_field() -> None:
    payload = make_prd().model_dump(mode="python")
    del payload["title"]
    with pytest.raises(ValidationError):
        PRD.model_validate(payload)


def test_prd_silently_ignores_extra_fields() -> None:
    # We removed extra="forbid" because Gemini's structured-output API rejects
    # `additionalProperties` in the schema. Pydantic now ignores unknown keys;
    # required-field + type validation still applies.
    payload = make_prd().model_dump(mode="python")
    payload["secret_field"] = "nope"
    prd = PRD.model_validate(payload)
    assert not hasattr(prd, "secret_field")


def test_prd_accepts_empty_optional_lists() -> None:
    # Size bounds were dropped from the schema because Gemini 2.5 rejects
    # schemas with too many state constraints. Empty lists are now valid;
    # content quality is enforced via prompting + post-validation in the agent.
    payload = make_prd().model_dump(mode="python")
    payload["constraints"] = []
    payload["risks"] = []
    payload["open_questions"] = []
    prd = PRD.model_validate(payload)
    assert prd.constraints == []
    assert prd.risks == []


def test_critique_fixture_is_valid() -> None:
    c = make_critique()
    assert isinstance(c.score, int)
    assert c.should_revise is True


def test_critique_rejects_wrong_score_type() -> None:
    with pytest.raises(ValidationError):
        Critique(score="not a number", summary="x", should_revise=False)  # type: ignore[arg-type]
