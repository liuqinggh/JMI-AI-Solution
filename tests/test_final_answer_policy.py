from __future__ import annotations

import pytest

from src.agent.executor import assemble_final_answer


@pytest.mark.parametrize(
    ("policy", "turns", "fallback", "expected"),
    [
        ("full", ["a", "b"], None, "a\nb"),
        ("last_assistant_turn", ["a", "b"], None, "b"),
        ("full", [], None, "任务已执行完成"),
        ("full", [], " only fallback ", "only fallback"),
        ("last_assistant_turn", [], "x", "x"),
        ("last_assistant_turn", ["solo"], None, "solo"),
    ],
)
def test_assemble_final_answer(
    policy: str,
    turns: list[str],
    fallback: str | None,
    expected: str,
) -> None:
    assert (
        assemble_final_answer(
            assistant_turn_texts=turns,
            result_fallback=fallback,
            policy=policy,
        )
        == expected
    )


def test_assemble_final_answer_empty_fallback() -> None:
    assert (
        assemble_final_answer(
            assistant_turn_texts=[],
            result_fallback="",
            policy="full",
        )
        == "任务已执行完成"
    )
