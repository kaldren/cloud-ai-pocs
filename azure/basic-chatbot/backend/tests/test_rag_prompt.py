import pytest

from app.chat import ChatRequest
from app.rag.prompt import (
    NO_SOURCES,
    SYSTEM_PROMPT,
    build_messages,
    cited_numbers,
    sources_footer,
)
from app.rag.retrieve import RetrievedChunk

SOURCES = [
    RetrievedChunk("hb-0003", "Handbook", "handbook.md", 3, "Recharge Week is 24-28 August.\n"),
    RetrievedChunk("pol-0000", "Travel Policy", "travel.md", 0, "Hotel cap: 250 GBP."),
]


def test_system_prompt_requires_grounding_citations_and_admitting_ignorance() -> None:
    assert "only from the sources" in SYSTEM_PROMPT
    assert "[1]" in SYSTEM_PROMPT
    assert "don't know" in SYSTEM_PROMPT


def test_build_messages_injects_numbered_sources() -> None:
    request = ChatRequest.model_validate({"messages": [{"role": "user", "content": "When?"}]})

    messages = build_messages(request, SOURCES)

    assert messages[1:] == [{"role": "user", "content": "When?"}]
    system = messages[0]
    assert system["role"] == "system"
    content = system["content"]
    assert isinstance(content, str)
    assert content.startswith(SYSTEM_PROMPT)
    assert (
        "<sources>\n[1] Handbook (handbook.md)\nRecharge Week is 24-28 August.\n\n"
        "[2] Travel Policy (travel.md)\nHotel cap: 250 GBP.\n</sources>"
    ) in content


def test_build_messages_without_sources_says_so() -> None:
    request = ChatRequest.model_validate({"messages": [{"role": "user", "content": "Tokyo?"}]})

    content = build_messages(request, [])[0].get("content")

    assert isinstance(content, str)
    assert f"<sources>\n{NO_SOURCES}\n</sources>" in content


def test_build_messages_strips_earlier_footers_from_history() -> None:
    history = [
        {"role": "user", "content": "When?"},
        {
            "role": "assistant",
            "content": "24-28 August [1].\n\nSources:\n[1] Handbook (handbook.md)",
        },
        {"role": "user", "content": "Thanks"},
    ]

    messages = build_messages(ChatRequest.model_validate({"messages": history}), SOURCES)

    assert messages[2] == {"role": "assistant", "content": "24-28 August [1]."}


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        pytest.param("A [2] and B [1][2].", [2, 1], id="first-cited-order"),
        pytest.param("I don't know.", [], id="none"),
        pytest.param("See [3] and [0].", [], id="out-of-range"),
    ],
)
def test_cited_numbers(reply: str, expected: list[int]) -> None:
    assert cited_numbers(reply, source_count=2) == expected


def test_footer_lists_only_cited_sources() -> None:
    assert sources_footer("Hotel cap is 250 GBP [2].", SOURCES) == (
        "\n\nSources:\n[2] Travel Policy (travel.md)"
    )


def test_no_footer_without_citations() -> None:
    assert sources_footer("I don't know based on the available documents.", SOURCES) == ""
