from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from couple_date_planner.models import CoupleProfileV1, default_profile, migrate_profile_data


def default_profile_path() -> Path:
    return Path("data/profile.json")


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_profile(path: Path | None = None) -> CoupleProfileV1:
    profile_path = path or default_profile_path()
    if not profile_path.exists():
        return default_profile()

    raw = profile_path.read_text(encoding="utf-8")
    payload = json.loads(raw) if raw.strip() else {}
    return migrate_profile_data(payload)


def save_profile(profile: CoupleProfileV1, path: Path | None = None) -> CoupleProfileV1:
    profile_path = path or default_profile_path()
    to_save = profile.with_defaults().model_copy(
        update={"updated_at": datetime.now(timezone.utc)}
    )
    atomic_write_json(
        profile_path,
        to_save.model_dump(mode="json", exclude_none=True),
    )
    return to_save
