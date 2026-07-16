#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tft_synergies_live import (
    HEADERS,
    SET17_SNAPSHOT_PATH,
    SET17_TRAIT_ASSETS_DIR,
    SET17_UNIT_ASSETS_DIR,
    load_set17_snapshot,
    set17_trait_icon_local_filename,
    set17_unit_avatar_local_filename,
)


def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        body = resp.read()
    dest.write_bytes(body)
    return True


def main() -> int:
    snapshot = load_set17_snapshot(False)
    unit_downloads = 0
    trait_downloads = 0
    failures = []

    for unit in snapshot.get("units", []):
        if not isinstance(unit, dict):
            continue
        url = str(unit.get("avatar_url") or "")
        api_name = str(unit.get("api_name") or "")
        if not url or not api_name:
            continue
        dest = SET17_UNIT_ASSETS_DIR / set17_unit_avatar_local_filename(api_name)
        try:
            if download(url, dest):
                unit_downloads += 1
        except Exception as err:
            failures.append({"type": "unit", "name": api_name, "url": url, "error": str(err)})

    for trait in snapshot.get("traits", []):
        if not isinstance(trait, dict):
            continue
        url = str(trait.get("icon_url") or "")
        icon_slug = str(trait.get("icon_slug") or "")
        if not url or not icon_slug:
            continue
        dest = SET17_TRAIT_ASSETS_DIR / set17_trait_icon_local_filename(icon_slug)
        try:
            if download(url, dest):
                trait_downloads += 1
        except Exception as err:
            failures.append({"type": "trait", "name": icon_slug, "url": url, "error": str(err)})

    print(json.dumps({
        "snapshot": str(SET17_SNAPSHOT_PATH),
        "unit_downloads": unit_downloads,
        "trait_downloads": trait_downloads,
        "unit_asset_dir": str(SET17_UNIT_ASSETS_DIR),
        "trait_asset_dir": str(SET17_TRAIT_ASSETS_DIR),
        "failures": failures,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
