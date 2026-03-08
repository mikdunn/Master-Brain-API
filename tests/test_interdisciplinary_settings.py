from math_logic_agent.config import Settings


def test_interdisciplinary_env_knobs_are_parsed(monkeypatch) -> None:
    monkeypatch.setenv("INTERDISCIPLINARY_MIN_PER_BRAIN", "2")
    monkeypatch.setenv("INTERDISCIPLINARY_SEED_SCORE_RATIO", "0.85")

    s = Settings.from_env()
    assert s.interdisciplinary_min_per_brain == 2
    assert abs(s.interdisciplinary_seed_score_ratio - 0.85) < 1e-9


def test_interdisciplinary_env_knobs_are_clamped(monkeypatch) -> None:
    monkeypatch.setenv("INTERDISCIPLINARY_MIN_PER_BRAIN", "0")
    monkeypatch.setenv("INTERDISCIPLINARY_SEED_SCORE_RATIO", "1.8")

    s = Settings.from_env()
    assert s.interdisciplinary_min_per_brain == 1
    assert s.interdisciplinary_seed_score_ratio == 1.0
