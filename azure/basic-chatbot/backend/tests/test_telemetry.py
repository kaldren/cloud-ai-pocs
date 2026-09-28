import pytest

import app.telemetry
from app.config import Settings
from app.telemetry import configure_telemetry


class NoCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> None:
        raise AssertionError("telemetry should not ask for a token when disabled")


def test_is_off_without_a_connection_string(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")

    assert configure_telemetry(settings, NoCredential()) is False  # pyright: ignore[reportArgumentType]
    assert "tracing is off" in caplog.text


def test_agent_name_must_be_a_valid_foundry_name(
    env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FOUNDRY_AGENT_NAME", "basic chatbot")

    with pytest.raises(ValueError, match="foundry_agent_name"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_keeps_whole_traces_and_skips_duplicate_http_spans(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_use_microsoft_opentelemetry(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(
        app.telemetry, "use_microsoft_opentelemetry", fake_use_microsoft_opentelemetry
    )
    settings.applicationinsights_connection_string = (
        "InstrumentationKey=00000000-0000-0000-0000-000000000000"  # betterleaks:allow
    )

    assert configure_telemetry(settings, NoCredential()) is True  # pyright: ignore[reportArgumentType]
    # The default rate-limited sampler drops parts of a chat turn.
    assert captured["sampling_ratio"] == 1.0
    # The OpenAI SDK sends through httpx2; its spans would duplicate the OpenAI spans.
    options = captured["instrumentation_options"]
    assert isinstance(options, dict)
    for name in ("httpx", "httpx2", "fastapi"):
        assert options[name] == {"enabled": False}
