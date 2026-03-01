from math_logic_agent.config import HARDCODED_BRIDGE_API_KEY, Settings


def test_bridge_key_defaults_to_hardcoded_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_API_KEY", raising=False)
    s = Settings.from_env()
    assert s.bridge_api_key == HARDCODED_BRIDGE_API_KEY


def test_bridge_key_defaults_to_hardcoded_for_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_API_KEY", "your_bridge_api_key_here")
    s = Settings.from_env()
    assert s.bridge_api_key == HARDCODED_BRIDGE_API_KEY


def test_bridge_key_honors_non_placeholder_env(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_API_KEY", "my-real-key")
    s = Settings.from_env()
    assert s.bridge_api_key == "my-real-key"
