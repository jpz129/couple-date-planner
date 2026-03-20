from __future__ import annotations

import streamlit as st

from couple_date_planner.generate import generate_date_ideas, normalize_fingerprint
from couple_date_planner.models import (
    CoupleProfileV1,
    CostBand,
    DEFAULT_TEXT_SECTIONS,
    DrinkingPreference,
    EnvironmentPreference,
)
from couple_date_planner.storage import load_profile, save_profile

SECTION_LABELS = {
    "about_us": "About us",
    "their_likes": "Their likes and joys",
    "constraints": "Boundaries and constraints",
    "inside_jokes": "Inside jokes and sentimental details",
    "special_notes": "Special notes (dates, traditions, memories)",
}


def _ensure_state() -> None:
    if "profile" not in st.session_state:
        st.session_state.profile = load_profile()
    if "last_ideas" not in st.session_state:
        st.session_state.last_ideas = []
    if "error_message" not in st.session_state:
        st.session_state.error_message = None


def _text_sections_ui(profile: CoupleProfileV1) -> CoupleProfileV1:
    st.subheader("Couple context")
    st.caption("Only sections marked Include and not Never send will be shared with the model.")
    for section in DEFAULT_TEXT_SECTIONS:
        label = SECTION_LABELS.get(section, section)
        profile.free_text[section] = st.text_area(
            label,
            value=profile.free_text.get(section, ""),
            key=f"text_{section}",
            height=120,
        )
        include_col, never_col = st.columns(2)
        with include_col:
            profile.include_when_generating[section] = st.checkbox(
                "Include when generating",
                value=profile.include_when_generating.get(section, True),
                key=f"include_{section}",
            )
        with never_col:
            profile.never_send[section] = st.checkbox(
                "Never send to model",
                value=profile.never_send.get(section, False),
                key=f"never_{section}",
                help="Privacy override that always excludes this section from model input.",
            )
    return profile


def _settings_ui(profile: CoupleProfileV1) -> CoupleProfileV1:
    settings = profile.generator_settings

    with st.sidebar:
        st.subheader("Generation settings")
        settings.idea_count = st.number_input(
            "Number of ideas",
            min_value=1,
            max_value=8,
            value=settings.idea_count,
            step=1,
        )
        settings.model_override = st.text_input(
            "Model override (optional)",
            value=settings.model_override,
            placeholder="e.g. gpt-4o-mini",
        )
        st.caption("Cost guardrail: keep idea count low and avoid long profile text when testing.")

    col1, col2 = st.columns(2)
    with col1:
        settings.cost_band = CostBand(
            st.selectbox(
                "Cost",
                options=[band.value for band in CostBand],
                index=[band.value for band in CostBand].index(settings.cost_band.value),
            )
        )
        settings.drinking = DrinkingPreference(
            st.selectbox(
                "Drinking preference",
                options=[pref.value for pref in DrinkingPreference],
                index=[pref.value for pref in DrinkingPreference].index(settings.drinking.value),
            )
        )
        settings.environment = EnvironmentPreference(
            st.selectbox(
                "Environment",
                options=[env.value for env in EnvironmentPreference],
                index=[env.value for env in EnvironmentPreference].index(
                    settings.environment.value
                ),
            )
        )
    with col2:
        settings.comfort_zone = st.slider(
            "Comfort-zone stretch",
            min_value=0,
            max_value=100,
            value=settings.comfort_zone,
            help="0 means super familiar, 100 means adventurous.",
        )
        settings.max_hours = st.slider(
            "Available time (up to, hours)",
            min_value=1,
            max_value=24,
            value=settings.max_hours,
            step=1,
            help=(
                "Soft upper limit: ideas should usually fit within about this much window, "
                "but shorter outings are fine. 24 = up to a full day."
            ),
        )
        settings.travel_radius_miles = st.slider(
            "Travel radius (miles)",
            min_value=0,
            max_value=100,
            value=settings.travel_radius_miles,
            help="Rough max distance you're willing to go for the date.",
        )
    return profile


def _render_ideas() -> None:
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
    if not st.session_state.last_ideas:
        st.info("No ideas yet. Generate ideas to see suggestions.")
        return

    for idea in st.session_state.last_ideas:
        with st.container(border=True):
            st.markdown(f"### {idea.title}")
            st.write(idea.description)
            st.write(f"**Why it fits:** {idea.why_it_fits}")
            meta_col1, meta_col2, meta_col3 = st.columns(3)
            meta_col1.metric("Estimated cost", idea.estimated_cost)
            meta_col2.metric("Duration", idea.duration)
            meta_col3.metric("Category", idea.category)
            st.caption(f"Prep notes: {idea.prep_notes}")


def _update_recent_fingerprints(profile: CoupleProfileV1) -> None:
    current = profile.recent_ideas_fingerprint
    additions = [normalize_fingerprint(idea.title) for idea in st.session_state.last_ideas]
    merged = [item for item in current + additions if item]
    profile.recent_ideas_fingerprint = merged[-40:]


def main() -> None:
    st.set_page_config(page_title="Couple Date Planner", page_icon=":heart:", layout="wide")
    st.title("Couple Date Planner")
    st.caption("Create thoughtful date ideas with your own context and boundaries.")

    _ensure_state()
    profile: CoupleProfileV1 = st.session_state.profile
    tab_profile, tab_ideas = st.tabs(["Profile", "Date ideas"])

    with tab_profile:
        profile = _text_sections_ui(profile)
        if st.button("Save profile", type="primary"):
            st.session_state.profile = save_profile(profile)
            st.success("Profile saved.")

    with tab_ideas:
        profile = _settings_ui(profile)
        if st.button("Generate ideas", type="primary"):
            with st.spinner("Generating date ideas..."):
                outcome = generate_date_ideas(profile, profile.generator_settings)
            if outcome.error_message:
                st.session_state.error_message = outcome.error_message
            else:
                st.session_state.error_message = None
                st.session_state.last_ideas = outcome.ideas
                _update_recent_fingerprints(profile)
                st.session_state.profile = save_profile(profile)
        _render_ideas()

    st.session_state.profile = profile


if __name__ == "__main__":
    main()
