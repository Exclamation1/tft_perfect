from __future__ import annotations

import dataclasses
import copy
import re
import time
from typing import Dict, List

from tft_synergies_live import SearchConfig, load_runtime_bundle, normalize_cost_range, run_search_with_config, titleish

from .assets import trait_icon_public_url, unit_avatar_public_url
from .cache import cached_call
from .schemas import SearchRequest

META_CACHE_TTL_SECONDS = 24 * 60 * 60
SEARCH_CACHE_TTL_SECONDS = 60 * 60
WARMUP_SEARCH_REQUESTS = (
    {
        "set_number": "17",
        "level": 8,
        "limit": 12,
        "max_unused_traits": 3,
        "sort_by": "score",
        "mecha_transform_min": 0,
        "mecha_transform_max": 0,
        "cost_1_min": 0,
        "cost_1_max": 2,
        "cost_2_min": 0,
        "cost_2_max": 2,
        "cost_4_min": 2,
        "cost_4_max": 8,
    },
    {"set_number": "17", "level": 8, "limit": 100},
    {"set_number": "17", "level": 7, "limit": 100},
    {"set_number": "17", "level": 9, "limit": 100},
    {"set_number": "17", "level": 8, "limit": 100, "max_unused_traits": 0},
    {"set_number": "17", "level": 8, "limit": 100, "max_unused_traits": 1},
    {"set_number": "17", "level": 8, "limit": 100, "exclude_costs": [5]},
    {"set_number": "17", "level": 8, "limit": 100, "exclude_costs": [4, 5]},
    {"set_number": "17", "level": 8, "carry": "Kai'Sa", "limit": 100},
    {"set_number": "17", "level": 8, "carry": "Kai'Sa", "limit": 100, "exclude_costs": [5]},
    {"set_number": "17", "level": 8, "carry": "Miss Fortune [Channeler]", "limit": 100},
    {"set_number": "17", "level": 8, "carry": "Miss Fortune [Channeler]", "limit": 100, "exclude_costs": [5]},
)


def choose_beam_width(
    *,
    level: int,
    carry: str | None,
    limit: int,
    include_units: List[str],
    exclude_units: List[str],
    exclude_costs: List[int],
) -> int:
    if carry:
        if limit <= 10:
            beam_width = 650
        elif limit <= 50:
            beam_width = 850
        elif limit <= 100:
            beam_width = 1000
        elif limit <= 250:
            beam_width = 1200
        else:
            beam_width = 1400
        if limit >= 500:
            beam_width += 150
        if limit >= 1000:
            beam_width += 150
        beam_width -= 40 * len(include_units)
        beam_width -= 20 * len(exclude_units)
        beam_width -= 30 * len(exclude_costs)
        return max(600, min(1700, beam_width))

    if limit <= 10:
        beam_width = 850
    elif limit <= 50:
        beam_width = 1050
    elif limit <= 100:
        beam_width = 1300
    elif limit <= 250:
        beam_width = 1500
    else:
        beam_width = 1700
    if level >= 8:
        beam_width += 150
    if level >= 9:
        beam_width += 250
    if limit >= 500:
        beam_width += 200
    if limit >= 1000:
        beam_width += 200
    beam_width -= 80 * len(include_units)
    beam_width -= 40 * len(exclude_units)
    beam_width -= 60 * len(exclude_costs)
    return max(800, min(2600, beam_width))


def _request_to_config(req: SearchRequest) -> SearchConfig:
    raw_cost_ranges = {
        1: (req.cost_1_min, req.cost_1_max, req.cost_1_count),
        2: (req.cost_2_min, req.cost_2_max, req.cost_2_count),
        3: (req.cost_3_min, req.cost_3_max, req.cost_3_count),
        4: (req.cost_4_min, req.cost_4_max, req.cost_4_count),
        5: (req.cost_5_min, req.cost_5_max, req.cost_5_count),
    }
    cost_unit_ranges = {}
    for cost, (min_count, max_count, exact_count) in raw_cost_ranges.items():
        if exact_count is not None:
            min_count = max_count = exact_count
        lo, hi = normalize_cost_range(min_count, max_count, req.level)
        if lo is not None or hi is not None:
            cost_unit_ranges[cost] = (lo, hi)
    mecha_transform_range = normalize_cost_range(req.mecha_transform_min, req.mecha_transform_max, 3)
    include_units = [titleish(x) for x in req.include_units if str(x).strip()]
    exclude_units = [titleish(x) for x in req.exclude_units if str(x).strip()]
    required_trait_breakpoints = {
        titleish(item.name): int(item.breakpoint)
        for item in req.trait_filters
        if str(item.name).strip()
    }
    beam_width = choose_beam_width(
        level=req.level,
        carry=req.carry,
        limit=req.limit,
        include_units=include_units,
        exclude_units=exclude_units,
        exclude_costs=req.exclude_costs,
    )
    return SearchConfig(
        level=req.level,
        set_number=req.set_number.strip(),
        include_units=include_units,
        exclude_units=exclude_units,
        exclude_costs=req.exclude_costs,
        cost_unit_ranges=cost_unit_ranges,
        mecha_transform_range=mecha_transform_range,
        enable_anima_trait=req.enable_anima_trait,
        required_trait_breakpoints=required_trait_breakpoints,
        max_unused_traits=req.max_unused_traits,
        trait_plus1=titleish(req.trait_plus1) if req.trait_plus1 else None,
        sort_by=req.sort_by,
        limit=req.limit,
        beam_width=beam_width,
        min_tanks=req.min_tanks,
        min_damage=req.min_damage,
        max_role_diff=req.max_role_diff,
        role_balance_weight=req.role_balance_weight,
        carry=titleish(req.carry) if req.carry else None,
    )


def get_meta(set_number: str = "17", refresh: bool = False) -> Dict:
    return cached_call(
        namespace="meta",
        payload={"set_number": set_number.strip()},
        ttl_seconds=META_CACHE_TTL_SECONDS,
        bypass=refresh,
        producer=lambda: _get_meta_uncached(set_number=set_number, refresh=refresh),
    )


def _get_meta_uncached(set_number: str = "17", refresh: bool = False) -> Dict:
    cfg = SearchConfig(level=8, set_number=set_number)
    meta, _, _ = load_runtime_bundle(cfg, refresh=refresh)
    return meta


def get_units(set_number: str = "17", refresh: bool = False) -> Dict:
    return cached_call(
        namespace="units",
        payload={"set_number": set_number.strip()},
        ttl_seconds=META_CACHE_TTL_SECONDS,
        bypass=refresh,
        producer=lambda: _get_units_uncached(set_number=set_number, refresh=refresh),
    )


def _get_units_uncached(set_number: str = "17", refresh: bool = False) -> Dict:
    cfg = SearchConfig(level=8, set_number=set_number)
    meta, _, champs = load_runtime_bundle(cfg, refresh=refresh)
    units = []
    for c in champs:
        payload = dataclasses.asdict(c)
        payload["avatar_local_url"] = unit_avatar_public_url(c.api_name) if set_number == "17" else None
        payload["avatar_remote_url"] = getattr(c, "avatar_url", None)
        units.append(payload)
    return {
        "meta": meta,
        "units": units,
    }


def get_traits(set_number: str = "17", refresh: bool = False) -> Dict:
    return cached_call(
        namespace="traits",
        payload={"set_number": set_number.strip()},
        ttl_seconds=META_CACHE_TTL_SECONDS,
        bypass=refresh,
        producer=lambda: _get_traits_uncached(set_number=set_number, refresh=refresh),
    )


def _get_traits_uncached(set_number: str = "17", refresh: bool = False) -> Dict:
    cfg = SearchConfig(level=8, set_number=set_number)
    meta, traits, _ = load_runtime_bundle(cfg, refresh=refresh)
    trait_items = [dataclasses.asdict(v) for v in sorted(traits.values(), key=lambda x: x.name)]
    if set_number == "17":
        from tft_synergies_live import load_set17_snapshot

        snapshot = load_set17_snapshot(refresh)
        trait_index = {item["name"]: item for item in snapshot.get("traits", []) if isinstance(item, dict)}
        for item in trait_items:
            snap = trait_index.get(item["name"])
            if not snap:
                continue
            icon_slug = snap.get("icon_slug")
            item["icon_slug"] = icon_slug
            item["icon_remote_url"] = snap.get("icon_url")
            item["icon_local_url"] = trait_icon_public_url(icon_slug) if icon_slug else None
            item["description"] = snap.get("description", "")
            item["variants"] = snap.get("variants", [])
    return {
        "meta": meta,
        "traits": trait_items,
    }


def get_bootstrap(set_number: str = "17", refresh: bool = False) -> Dict:
    units_payload = get_units(set_number=set_number, refresh=refresh)
    traits_payload = get_traits(set_number=set_number, refresh=refresh)
    return {
        "meta": units_payload["meta"],
        "units": units_payload["units"],
        "traits": traits_payload["traits"],
    }


def search(req: SearchRequest) -> Dict:
    cfg = _request_to_config(req)
    return cached_call(
        namespace="search",
        payload=_search_cache_payload(cfg),
        ttl_seconds=SEARCH_CACHE_TTL_SECONDS,
        bypass=req.refresh,
        producer=lambda: _search_uncached(cfg, refresh=req.refresh),
    )


def _search_uncached(cfg: SearchConfig, refresh: bool = False) -> Dict:
    started_at = time.perf_counter()
    bundle = run_search_with_config(cfg, refresh=refresh)
    enrich_started_at = time.perf_counter()
    results = copy.deepcopy(bundle["results"])
    trait_index = {}
    if cfg.set_number == "17":
        from tft_synergies_live import load_set17_snapshot

        snapshot = load_set17_snapshot(refresh)
        trait_index = {item["name"]: item for item in snapshot.get("traits", []) if isinstance(item, dict)}
    for result in results:
        for unit in result["units"]:
            api_name = str(unit.get("api_name") or "")
            unit["avatar_local_url"] = unit_avatar_public_url(api_name) if cfg.set_number == "17" else None
            unit["avatar_remote_url"] = unit.get("avatar_url")
        result["display_traits"] = []
        for trait_text in result.get("active_traits", []):
            match = re.match(r"^(.*)\s+\d+/\d+$", trait_text)
            trait_name = match.group(1) if match else trait_text
            snap = trait_index.get(trait_name, {})
            icon_slug = snap.get("icon_slug")
            result["display_traits"].append({
                "label": trait_text,
                "name": trait_name,
                "icon_slug": icon_slug,
                "icon_local_url": trait_icon_public_url(icon_slug) if icon_slug else None,
                "icon_remote_url": snap.get("icon_url"),
            })
    timings = dict(bundle["meta"].get("timings", {}))
    timings["result_enrichment_ms"] = round((time.perf_counter() - enrich_started_at) * 1000.0, 2)
    timings["search_response_total_ms"] = round((time.perf_counter() - started_at) * 1000.0, 2)
    bundle["meta"]["timings"] = timings
    return {
        "meta": bundle["meta"],
        "results": results,
    }


def _search_cache_payload(cfg: SearchConfig) -> Dict:
    payload = dataclasses.asdict(cfg)
    payload["include_units"] = sorted(payload.get("include_units", []))
    payload["exclude_units"] = sorted(payload.get("exclude_units", []))
    payload["exclude_costs"] = sorted(payload.get("exclude_costs", []))
    payload["cost_unit_ranges"] = {
        str(k): list(v) for k, v in sorted(payload.get("cost_unit_ranges", {}).items(), key=lambda item: item[0])
    }
    payload["mecha_transform_range"] = list(payload.get("mecha_transform_range", (None, None)))
    payload["required_trait_breakpoints"] = {
        k: payload["required_trait_breakpoints"][k]
        for k in sorted(payload.get("required_trait_breakpoints", {}).keys())
    }
    return payload


def normalize_external_set_number(raw_set: str) -> str:
    raw_set = str(raw_set).strip()
    if raw_set.endswith("0") and raw_set[:-1].isdigit():
        shortened = raw_set[:-1]
        if shortened:
            return shortened
    return raw_set


def search_compact(
    set_number: str,
    max_unused_traits: int,
    level: int,
    mode: str = "base",
    limit: int = 100,
    refresh: bool = False,
) -> List[List[str]]:
    normalized_set = normalize_external_set_number(set_number)
    exclude_costs: List[int] = []
    sort_by = "cost"
    mode_key = mode.strip().lower()
    if mode_key in {"x4", "exclude4"}:
        exclude_costs = [4]
    elif mode_key in {"x5", "exclude5"}:
        exclude_costs = [5]
    elif mode_key in {"x45", "exclude45"}:
        exclude_costs = [4, 5]
    elif mode_key in {"score"}:
        sort_by = "score"

    cfg = SearchConfig(
        level=level,
        set_number=normalized_set,
        exclude_costs=exclude_costs,
        max_unused_traits=max_unused_traits,
        sort_by=sort_by,
        limit=limit,
        beam_width=choose_beam_width(
            level=level,
            carry=None,
            limit=limit,
            include_units=[],
            exclude_units=[],
            exclude_costs=exclude_costs,
        ),
    )
    return cached_call(
        namespace="search_compact",
        payload={
            "cfg": _search_cache_payload(cfg),
            "mode": mode_key,
        },
        ttl_seconds=SEARCH_CACHE_TTL_SECONDS,
        bypass=refresh,
        producer=lambda: _search_compact_uncached(cfg, refresh=refresh),
    )


def _search_compact_uncached(cfg: SearchConfig, refresh: bool = False) -> List[List[str]]:
    bundle = run_search_with_config(cfg, refresh=refresh)
    compact_results: List[List[str]] = []
    for result in bundle["results"]:
        compact_results.append([str(unit["api_name"]) for unit in result["units"]])
    return compact_results


def warm_up_cache() -> Dict:
    warmed = {
        "meta": False,
        "units": False,
        "traits": False,
        "searches": [],
        "errors": [],
    }

    try:
        get_meta(set_number="17", refresh=False)
        warmed["meta"] = True
    except Exception as err:
        warmed["errors"].append(f"meta: {err}")

    try:
        get_units(set_number="17", refresh=False)
        warmed["units"] = True
    except Exception as err:
        warmed["errors"].append(f"units: {err}")

    try:
        get_traits(set_number="17", refresh=False)
        warmed["traits"] = True
    except Exception as err:
        warmed["errors"].append(f"traits: {err}")

    for payload in WARMUP_SEARCH_REQUESTS:
        try:
            result = search(SearchRequest(**payload))
            warmed["searches"].append({
                "payload": payload,
                "result_count": len(result.get("results", [])),
            })
        except Exception as err:
            warmed["errors"].append(f"search {payload}: {err}")

    return warmed
