from __future__ import annotations

import json
from pathlib import Path

from couple_date_planner.models import default_profile
from couple_date_planner.storage import load_profile, save_profile


def test_storage_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "profile.json"
    profile = default_profile()
    profile.free_text["about_us"] = "We love surprise picnics and bookstores."
    saved = save_profile(profile, target)
    loaded = load_profile(target)

    assert loaded.free_text["about_us"] == "We love surprise picnics and bookstores."
    assert loaded.version == saved.version
    assert loaded.updated_at is not None


def test_migration_hook_applies_defaults(tmp_path: Path) -> None:
    target = tmp_path / "profile.json"
    target.write_text(
        json.dumps(
            {
                "version": 0,
                "free_text": {"about_us": "Legacy profile"},
                "include_when_generating": {"about_us": True},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_profile(target)
    assert loaded.version == 1
    assert "their_likes" in loaded.free_text
    assert loaded.never_send.get("about_us") is False


def test_migration_converts_minutes_and_km_to_hours_and_miles(tmp_path: Path) -> None:
    target = tmp_path / "profile.json"
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "free_text": {"about_us": "Test"},
                "generator_settings": {
                    "duration_minutes": 120,
                    "travel_radius_km": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = load_profile(target)
    assert loaded.generator_settings.max_hours == 2
    assert loaded.generator_settings.travel_radius_miles == 6
