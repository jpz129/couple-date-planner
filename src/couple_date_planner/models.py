from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

PROFILE_VERSION = 1
DEFAULT_TEXT_SECTIONS = (
    "about_us",
    "their_likes",
    "constraints",
    "inside_jokes",
    "special_notes",
)


class CostBand(str, Enum):
    free = "free"
    low = "low"
    medium = "medium"
    high = "high"
    any = "any"


class DrinkingPreference(str, Enum):
    no = "no"
    either = "either"
    yes = "yes"


class EnvironmentPreference(str, Enum):
    indoor = "indoor"
    outdoor = "outdoor"
    either = "either"


class GeneratorSettings(BaseModel):
    cost_band: CostBand = CostBand.any
    comfort_zone: int = Field(default=35, ge=0, le=100)
    drinking: DrinkingPreference = DrinkingPreference.either
    environment: EnvironmentPreference = EnvironmentPreference.either
    duration_minutes: int = Field(default=120, ge=30, le=720)
    travel_radius_km: int = Field(default=10, ge=0, le=100)
    idea_count: int = Field(default=5, ge=1, le=8)
    model_override: str = ""


class DateIdea(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=20, max_length=500)
    why_it_fits: str = Field(min_length=20, max_length=400)
    estimated_cost: str = Field(min_length=2, max_length=80)
    prep_notes: str = Field(min_length=2, max_length=400)
    duration: str = Field(min_length=2, max_length=60)
    category: str = Field(min_length=2, max_length=40)


class DateIdeaBatch(BaseModel):
    ideas: list[DateIdea]


class CoupleProfileV1(BaseModel):
    version: int = PROFILE_VERSION
    free_text: dict[str, str] = Field(default_factory=dict)
    include_when_generating: dict[str, bool] = Field(default_factory=dict)
    never_send: dict[str, bool] = Field(default_factory=dict)
    generator_settings: GeneratorSettings = Field(default_factory=GeneratorSettings)
    recent_ideas_fingerprint: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None

    @field_validator("free_text")
    @classmethod
    def normalize_free_text(cls, value: dict[str, str]) -> dict[str, str]:
        return {k: str(v) for k, v in value.items()}

    def with_defaults(self) -> "CoupleProfileV1":
        profile = self.model_copy(deep=True)
        for section in DEFAULT_TEXT_SECTIONS:
            profile.free_text.setdefault(section, "")
            profile.include_when_generating.setdefault(section, True)
            profile.never_send.setdefault(section, False)
        return profile

    def context_for_generation(self, max_chars: int) -> dict[str, str]:
        selected: dict[str, str] = {}
        remaining = max_chars
        for key, text in self.free_text.items():
            if self.never_send.get(key, False):
                continue
            if not self.include_when_generating.get(key, False):
                continue
            cleaned = text.strip()
            if not cleaned:
                continue
            if remaining <= 0:
                break
            clipped = cleaned[:remaining]
            selected[key] = clipped
            remaining -= len(clipped)
        return selected


def default_profile() -> CoupleProfileV1:
    profile = CoupleProfileV1(updated_at=datetime.now(timezone.utc))
    return profile.with_defaults()


def migrate_profile_data(payload: dict[str, Any]) -> CoupleProfileV1:
    if not payload:
        return default_profile()

    version = payload.get("version", 1)
    if version != PROFILE_VERSION:
        payload["version"] = PROFILE_VERSION

    profile = CoupleProfileV1.model_validate(payload)
    return profile.with_defaults()
