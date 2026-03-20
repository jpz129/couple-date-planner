from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable

from openai import APIError, APITimeoutError, OpenAI

from couple_date_planner.models import CoupleProfileV1, DateIdea, DateIdeaBatch, GeneratorSettings

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_CONTEXT_CHARS = 4000


@dataclass
class GenerationOutcome:
    ideas: list[DateIdea]
    error_message: str | None = None


def normalize_fingerprint(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base[:80]


def select_diverse_ideas(ideas: list[DateIdea], count: int) -> list[DateIdea]:
    selected: list[DateIdea] = []
    seen_categories: set[str] = set()

    for idea in ideas:
        category_key = idea.category.lower().strip()
        if category_key in seen_categories:
            continue
        selected.append(idea)
        seen_categories.add(category_key)
        if len(selected) >= count:
            return selected

    for idea in ideas:
        if len(selected) >= count:
            break
        if idea in selected:
            continue
        selected.append(idea)
    return selected


def create_openai_client(timeout_seconds: float) -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=timeout_seconds,
    )


def build_messages(profile: CoupleProfileV1, settings: GeneratorSettings) -> list[dict[str, Any]]:
    context = profile.context_for_generation(MAX_CONTEXT_CHARS)
    recent = profile.recent_ideas_fingerprint[-20:]
    prompt_payload = {
        "profile_context": context,
        "preferences": settings.model_dump(),
        "avoid_fingerprints": recent,
        "style_guide": {
            "core_approach": (
                "Come up with non-cheesy, engaging dates: emphasize shared activities, "
                "low-stakes creativity, and interactive experiences—not passive, "
                "traditional dinner-only nights. Strong patterns: light competition, "
                "exploring new places, or learning something new together (e.g. thrift "
                "shopping, niche museum visits, or a short class)."
            ),
            "active_and_competitive_examples": [
                "Arcade or barcade: old-school games or pinball against each other.",
                "Bowling or mini-golf: active, conversational classics.",
                "Karaoke-off: pick songs for each other to sing.",
                "Trivia night: join a team at a local pub.",
                "Active adventures: hike, rent a rowboat, or hit a driving range.",
            ],
            "creative_and_exploratory_examples": [
                "Thrift store challenge: outfits for each other under a budget, wear them out.",
                "Themed picnic: scenic spot with chosen cheeses, chocolates, or snacks.",
                "DIY mystery night: scavenger hunt around town ending at dinner.",
                "Farmer's market hop: sample, pick ingredients, cook together.",
                "Test drives: fun, low-pressure dealership visits for dream cars (where appropriate).",
            ],
            "unique_and_cozy_examples": [
                "Live local music: small venue or dive bar, not a huge arena show.",
                "Class together: pottery, cooking, or dance—learn side by side.",
                "Board or card games: coffee shop or park with something competitive.",
                "Bookstore date: pick books for each other that reflect childhood or passions.",
            ],
            "non_cheesy_tips": [
                "Avoid over-planning: leave room for spontaneity instead of a rigid itinerary.",
                "Favor interaction: choose talk-and-laugh activities over long silent stretches (e.g. defaulting to a movie as the whole date).",
                "Keep it casual: low-pressure mini-dates (coffee + walk, market stroll) can beat high-stakes formal plans.",
            ],
            "safety_and_verification": (
                "Ideas must be safe, legal, and respectful of the couple's preferences. "
                "Do not invent real venue names or schedules; keep prep_notes practical. "
                "Reminder for the user in prep_notes when useful: double-check hours, "
                "bookings, and costs—suggestions may need verification."
            ),
        },
        "instructions": {
            "tone": "warm, playful, genuine—never corny or generic-romantic cliché",
            "budget_bias": "favor free and low-cost ideas unless user asks for more",
            "safety": "avoid unsafe, illegal, or manipulative suggestions",
            "novelty": "propose fresh ideas; diversify across active, creative, and cozy themes when possible",
            "time_budget": (
                "preferences.max_hours is a soft ceiling (hours), not a rigid duration. "
                "Prefer ideas that can reasonably complete within that window if the couple wants a "
                "full outing; shorter mini-dates and flexible flows are welcome. Do not assume they "
                "must use the entire time."
            ),
            "travel_budget": (
                "preferences.travel_radius_miles is an approximate distance budget in miles from their "
                "starting area; suggest activities that fit that reach unless the profile suggests otherwise."
            ),
            "avoid_defaults": (
                "Do not center ideas on a passive dinner-and-sit-still evening or movie-only "
                "as the main date; if food appears, pair it with an interactive or exploratory hook."
            ),
            "category_field": (
                "Use concise category labels such as active_competitive, creative_exploratory, "
                "unique_cozy, or similar—match the idea's primary vibe."
            ),
        },
        "output_schema": {
            "ideas": [
                {
                    "title": "string",
                    "description": "string",
                    "why_it_fits": "string",
                    "estimated_cost": "string",
                    "prep_notes": "string",
                    "duration": "string",
                    "category": "string",
                }
            ]
        },
    }

    return [
        {
            "role": "system",
            "content": (
                "You generate thoughtful, non-cheesy date ideas for a couple—interactive, "
                "low-stakes creative, and activity-forward (see the user's style_guide and "
                "profile). Return strict JSON only: a single JSON object matching the schema "
                "in the user message. No markdown fences, no commentary outside JSON."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt_payload),
        },
    ]


def extract_json_content(response: Any) -> str:
    choices = getattr(response, "choices", [])
    if not choices:
        raise ValueError("Model returned no choices.")
    message = choices[0].message
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Model returned empty content.")
    return content


def parse_ideas(content: str) -> DateIdeaBatch:
    payload = json.loads(content)
    return DateIdeaBatch.model_validate(payload)


def generate_date_ideas(
    profile: CoupleProfileV1,
    settings: GeneratorSettings,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client_factory: Callable[[float], Any] = create_openai_client,
) -> GenerationOutcome:
    context = profile.context_for_generation(MAX_CONTEXT_CHARS)
    if not context:
        return GenerationOutcome(
            ideas=[],
            error_message=(
                "No profile text is eligible for generation. Add text and ensure at least "
                "one section is included and not marked never-send."
            ),
        )

    model = settings.model_override.strip() or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    messages = build_messages(profile, settings)
    parse_error: str | None = None
    client = client_factory(timeout_seconds)

    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.9,
            )
            parsed = parse_ideas(extract_json_content(response))

            blocked = set(profile.recent_ideas_fingerprint[-30:])
            filtered = [
                idea
                for idea in parsed.ideas
                if normalize_fingerprint(idea.title) not in blocked
            ]
            diverse = select_diverse_ideas(filtered or parsed.ideas, settings.idea_count)
            return GenerationOutcome(ideas=diverse[: settings.idea_count], error_message=None)
        except APITimeoutError:
            return GenerationOutcome(
                ideas=[],
                error_message=(
                    "The model request timed out. Try again, reduce idea count, "
                    "or shorten profile text."
                ),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            parse_error = str(exc)
            continue
        except APIError as exc:
            return GenerationOutcome(
                ideas=[],
                error_message=f"The model request failed: {exc}",
            )

    return GenerationOutcome(
        ideas=[],
        error_message=(
            "The model returned invalid JSON twice. Please retry. "
            f"Last parsing issue: {parse_error}"
        ),
    )
