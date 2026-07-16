from __future__ import annotations

from pathlib import Path
from typing import Optional

from tft_synergies_live import (
    SET17_TRAIT_ASSETS_DIR,
    SET17_UNIT_ASSETS_DIR,
    set17_trait_icon_local_filename,
    set17_unit_avatar_local_filename,
)


def unit_avatar_local_path(api_name: str) -> Path:
    return SET17_UNIT_ASSETS_DIR / set17_unit_avatar_local_filename(api_name)


def unit_avatar_public_url(api_name: str) -> Optional[str]:
    path = unit_avatar_local_path(api_name)
    if path.exists():
        return f"/assets/set17/units/{path.name}"
    return None


def trait_icon_local_path(icon_slug: str) -> Path:
    return SET17_TRAIT_ASSETS_DIR / set17_trait_icon_local_filename(icon_slug)


def trait_icon_public_url(icon_slug: str) -> Optional[str]:
    path = trait_icon_local_path(icon_slug)
    if path.exists():
        return f"/assets/set17/traits/{path.name}"
    return None
