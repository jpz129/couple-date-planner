from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from couple_date_planner.generate import generate_date_ideas, normalize_fingerprint
from couple_date_planner.models import default_profile


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self._index = 0

    def create(self, **_: Any) -> _FakeResponse:
        content = self._contents[min(self._index, len(self._contents) - 1)]
        self._index += 1
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=content))])


class _FakeChat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _FakeCompletions(contents)


class _FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _FakeChat(contents)


def _client_factory(contents: list[str]):
    def _factory(_: float) -> _FakeClient:
        return _FakeClient(contents)

    return _factory


def test_generation_retries_after_invalid_json() -> None:
    profile = default_profile()
    profile.free_text["about_us"] = "We like cozy and playful date ideas."
    settings = profile.generator_settings

    invalid = "not-json"
    valid = """
    {"ideas":[{"title":"Late Night Mini Golf","description":"Play glow mini-golf then dessert walk.",
    "why_it_fits":"Balances playful energy with easy conversation.",
    "estimated_cost":"$20-$35","prep_notes":"Reserve slots in advance","duration":"2 hours","category":"playful"}]}
    """
    outcome = generate_date_ideas(
        profile,
        settings,
        client_factory=_client_factory([invalid, valid]),
    )
    assert outcome.error_message is None
    assert len(outcome.ideas) == 1
    assert outcome.ideas[0].title == "Late Night Mini Golf"


def test_generation_filters_recent_fingerprints() -> None:
    profile = default_profile()
    profile.free_text["about_us"] = "We enjoy low-cost romantic ideas."
    profile.recent_ideas_fingerprint = [normalize_fingerprint("Rooftop Sunset Picnic")]
    settings = profile.generator_settings
    settings.idea_count = 2

    payload = """
    {"ideas":[
      {"title":"Rooftop Sunset Picnic","description":"Pack snacks and watch sunset.",
      "why_it_fits":"Romantic and simple.","estimated_cost":"$10","prep_notes":"Bring blanket","duration":"90 mins","category":"romance"},
      {"title":"Library Date Challenge","description":"Pick mystery books for each other and discuss over tea.",
      "why_it_fits":"Sweet and budget-friendly.","estimated_cost":"Free-$8","prep_notes":"Pick a nearby cafe","duration":"2 hours","category":"cozy"}
    ]}
    """

    outcome = generate_date_ideas(
        profile,
        settings,
        client_factory=_client_factory([payload]),
    )
    assert outcome.error_message is None
    assert len(outcome.ideas) == 1
    assert outcome.ideas[0].title == "Library Date Challenge"
