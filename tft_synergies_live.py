#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request

BASE = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1"
SETS_URL = f"{BASE}/tftsets.json"
CHAMPS_URL = f"{BASE}/tftchampions.json"
CHAMPS_TEAMPLANNER_URL = f"{BASE}/tftchampions-teamplanner.json"
TRAITS_URL = f"{BASE}/tfttraits.json"
CACHE_DIR = Path('.tft_synergy_cache')
CACHE_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 25
RETRIES = 3

# Heuristics for filtering playable units from CommunityDragon.
BANNED_NAME_PATTERNS = [
    r"^TFT\d+_PVE_",
    r"^TFTTutorial",
    r"TrainingDummy",
    r"TargetDummy",
    r"GangplankBarrel",
    r"Tibbers",
    r"MechPilot",
    r"Turret",
    r"Tentacle",
    r"Portal",
    r"Minion",
    r"Nexus",
    r"DragonEgg",
    r"Summon",
    r"Monster",
    r"Treasure",
    r"Krug",
    r"Raptor",
    r"Wolf",
    r"Herald",
    r"Scuttle",
]

ALLOWED_SPECIAL_NAMES = {
    # Keep a small allowlist for special but legitimate boardable/unlockable units.
    "Baron Nashor",
}

TANK_KEYWORDS = {
    "bastion", "bruiser", "warden", "juggernaut", "guardian", "sentinel",
    "behemoth", "vanguard", "protector", "knight", "defender"
}
DAMAGE_KEYWORDS = {
    "sorcerer", "sniper", "invoker", "challenger", "assassin", "marksman",
    "gunslinger", "slayer", "duelist", "reaper", "carry", "arcanist",
    "trickshot", "artillerist", "multistriker", "blaster"
}


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def normalize_text(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def titleish(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def fetch_json(url: str, refresh: bool) -> object:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"{digest}.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding='utf-8'))
    last_err = None
    for i in range(RETRIES):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode('utf-8')
            cache_path.write_text(body, encoding='utf-8')
            return json.loads(body)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as err:
            last_err = err
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


@dataclass
class TraitDef:
    id: str
    name: str
    breakpoints: List[int]


@dataclass
class Champion:
    id: str
    api_name: str
    name: str
    cost: int
    raw_cost: int
    traits: List[str]
    role: str


@dataclass
class SearchConfig:
    level: int
    include_units: List[str] = field(default_factory=list)
    exclude_costs: List[int] = field(default_factory=list)
    max_unused_traits: int = 99
    trait_plus1: Optional[str] = None
    sort_by: str = "score"
    limit: int = 20
    beam_width: int = 500
    min_tanks: int = 2
    min_damage: int = 2
    max_role_diff: float = 2.0
    role_balance_weight: float = 8.0
    json_output: bool = False
    dump_meta: bool = False
    dump_champions: bool = False
    dump_traits: bool = False


@dataclass
class State:
    units: Tuple[Champion, ...]
    next_idx: int
    trait_counts: Dict[str, int]
    total_cost: int
    tank_count: int
    damage_count: int
    flex_count: int
    score_estimate: float


def pick_current_set(sets_payload: object) -> Tuple[str, str, str]:
    current: Optional[dict] = None
    candidates: List[dict] = []

    if isinstance(sets_payload, list):
        candidates = [item for item in sets_payload if isinstance(item, dict)]
    elif isinstance(sets_payload, dict):
        candidates = [sets_payload]
        mode_data = sets_payload.get('LCTFTModeData')
        if isinstance(mode_data, dict):
            default_set = mode_data.get('mDefaultSet')
            if isinstance(default_set, dict):
                current = default_set
            active_sets = mode_data.get('mActiveSets')
            if isinstance(active_sets, list):
                candidates.extend(item for item in active_sets if isinstance(item, dict))
    else:
        raise RuntimeError("Unexpected tftsets.json format")

    if not current:
        for item in candidates:
            default_set = item.get('mDefaultSet')
            if isinstance(default_set, dict) and default_set.get('SetName'):
                current = default_set
                break
            if item.get('mDefaultSet') and item.get('SetName'):
                current = item
                break
    if not current:
        for item in candidates:
            if item.get('SetName'):
                current = item
                break
    if not current:
        raise RuntimeError("Could not determine current TFT set from tftsets.json")

    set_name = current.get('SetName') or current.get('mDefaultSet')
    set_display = current.get('SetDisplayName') or set_name
    m = re.search(r'(\d+)', str(set_name))
    set_num = m.group(1) if m else ''
    return str(set_name), str(set_display), set_num


def load_traits(refresh: bool, set_num: str) -> Dict[str, TraitDef]:
    payload = fetch_json(TRAITS_URL, refresh)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected tfttraits.json format")
    out: Dict[str, TraitDef] = {}
    set_name = f"TFTSet{set_num}" if set_num else None
    prefix = f"TFT{set_num}_" if set_num else None
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_set = item.get('set') or item.get('SetName')
        if set_name and item_set and str(item_set) != set_name:
            continue
        api_name = str(item.get('apiName') or item.get('mName') or item.get('trait_id') or '')
        display_name = titleish(str(item.get('name') or item.get('displayName') or item.get('display_name') or ''))
        if not display_name:
            continue
        if prefix and api_name and not api_name.startswith(prefix):
            # keep generic traits if they happen to be missing prefix.
            pass
        effects = item.get('effects') or item.get('conditionalTraitSets') or item.get('conditional_trait_sets') or []
        bps = []
        if isinstance(effects, list):
            for eff in effects:
                if isinstance(eff, dict):
                    mn = eff.get('minUnits')
                    if mn is None:
                        mn = eff.get('min_units')
                    if isinstance(mn, int) and mn > 0:
                        bps.append(mn)
        bps = sorted(set(bps))
        if not bps:
            continue
        out[display_name] = TraitDef(id=normalize_text(display_name), name=display_name, breakpoints=bps)
    if not out:
        raise RuntimeError("No traits parsed from CommunityDragon")
    return out


def normalize_search_cost(cost: int) -> int:
    return min(max(int(cost), 0), 5) if cost > 0 else 0


def is_playable_champion(item: dict, set_num: str) -> bool:
    record = item.get('character_record') if isinstance(item.get('character_record'), dict) else item
    api_name = str(record.get('apiName') or record.get('mCharacterName') or record.get('character_id') or item.get('name') or '')
    name = titleish(str(record.get('name') or record.get('displayName') or record.get('display_name') or item.get('name') or ''))
    if not name:
        return False
    if name in ALLOWED_SPECIAL_NAMES:
        return True
    prefix = f"TFT{set_num}_"
    if set_num and api_name and not api_name.startswith(prefix):
        return False
    if record.get('rarity') is None and record.get('cost') is None and record.get('tier') is None:
        return False
    for pat in BANNED_NAME_PATTERNS:
        if re.search(pat, api_name, re.I) or re.search(pat, name, re.I):
            return False
    lname = normalize_text(name)
    if any(tok in lname for tok in ["dummy", "summon", "barrel", "portal", "monster", "minion"]):
        return False
    traits = record.get('traits') or []
    if not isinstance(traits, list) or not traits:
        return False
    return True


def infer_role(traits: List[str]) -> str:
    tset = {normalize_text(t) for t in traits}
    tank = any(any(k in t for k in TANK_KEYWORDS) for t in tset)
    dmg = any(any(k in t for k in DAMAGE_KEYWORDS) for t in tset)
    if tank and dmg:
        return 'flex'
    if tank:
        return 'tank'
    if dmg:
        return 'damage'
    # fallback: utility / weird units treated as flex
    return 'flex'


def load_champions(refresh: bool, set_num: str, traits: Dict[str, TraitDef]) -> List[Champion]:
    payload = fetch_json(CHAMPS_TEAMPLANNER_URL, refresh)
    if isinstance(payload, dict):
        set_key = f"TFTSet{set_num}" if set_num else ""
        if set_key and isinstance(payload.get(set_key), list):
            payload = payload[set_key]
        else:
            # fallback to the first list payload if the set key isn't present.
            list_values = [v for v in payload.values() if isinstance(v, list)]
            payload = list_values[0] if list_values else []
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected tftchampions-teamplanner.json format")
    out: List[Champion] = []
    seen_names = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        if not is_playable_champion(item, set_num):
            continue
        record = item.get('character_record') if isinstance(item.get('character_record'), dict) else item
        name = titleish(str(record.get('name') or record.get('displayName') or record.get('display_name') or item.get('name') or ''))
        raw_cost = record.get('cost')
        if not isinstance(raw_cost, int):
            raw_cost = record.get('tier')
        if not isinstance(raw_cost, int):
            rarity = record.get('rarity')
            raw_cost = rarity + 1 if isinstance(rarity, int) and 0 <= rarity <= 5 else None
        if not isinstance(raw_cost, int) or raw_cost <= 0:
            continue
        raw_traits = record.get('traits') or []
        display_traits = []
        for tr in raw_traits:
            if isinstance(tr, dict):
                tr_name = titleish(str(tr.get('name') or tr.get('displayName') or tr.get('display_name') or ''))
            else:
                tr_name = titleish(str(tr))
            if tr_name in traits:
                display_traits.append(tr_name)
        display_traits = sorted(set(display_traits))
        if not display_traits:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        api_name = str(record.get('apiName') or record.get('mCharacterName') or record.get('character_id') or item.get('name') or '')
        role = infer_role(display_traits)
        out.append(Champion(
            id=normalize_text(name),
            api_name=api_name,
            name=name,
            cost=normalize_search_cost(raw_cost),
            raw_cost=raw_cost,
            traits=display_traits,
            role=role,
        ))
    # pragmatic validation: Set 16 is very large, but exact count can fluctuate if CDragon schema shifts.
    if len(out) < 50:
        raise RuntimeError(
            f"Parsed only {len(out)} playable champions for TFTSet{set_num} from CommunityDragon. "
            "The JSON schema likely changed; inspect --dump-meta / --dump-champions."
        )
    return sorted(out, key=lambda c: (c.cost, c.name))


def evaluate_traits(trait_counts: Dict[str, int], trait_defs: Dict[str, TraitDef], trait_plus1: Optional[str]) -> Tuple[List[str], List[str], List[str], int, int, float]:
    active = []
    near = []
    unused = []
    unused_count = 0
    leftover_units = 0
    score = 0.0

    counts = dict(trait_counts)
    if trait_plus1:
        counts[trait_plus1] = counts.get(trait_plus1, 0) + 1

    for tr_name, cnt in sorted(counts.items()):
        tdef = trait_defs.get(tr_name)
        if not tdef or cnt <= 0:
            continue
        best_bp = 0
        next_bp = None
        for bp in tdef.breakpoints:
            if cnt >= bp:
                best_bp = bp
            elif next_bp is None:
                next_bp = bp
        if best_bp > 0:
            active.append(f"{tr_name} {cnt}/{best_bp}")
            score += best_bp * 8.0
            leftover_units += max(0, cnt - best_bp)
        else:
            unused.append(f"{tr_name}({cnt})")
            unused_count += 1
            score -= 9.0
        if next_bp is not None and next_bp - cnt == 1:
            near.append(f"{tr_name} {cnt}→{next_bp}")
            score += 4.0
    score -= leftover_units * 1.5
    return active, near, unused, unused_count, leftover_units, score


def effective_role_counts(state: State) -> Tuple[float, float, float]:
    eff_tank = state.tank_count + 0.5 * state.flex_count
    eff_damage = state.damage_count + 0.5 * state.flex_count
    diff = abs(eff_tank - eff_damage)
    return eff_tank, eff_damage, diff


def estimate_state_score(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    _, _, _, unused_count, _, trait_score = evaluate_traits(state.trait_counts, trait_defs, cfg.trait_plus1)
    eff_tank, eff_damage, diff = effective_role_counts(state)
    score = trait_score
    score -= state.total_cost * 0.45
    score -= diff * cfg.role_balance_weight
    # light encouragement for minimum role coverage as search develops
    score -= max(0.0, cfg.min_tanks - eff_tank) * 3.5
    score -= max(0.0, cfg.min_damage - eff_damage) * 3.5
    if unused_count > cfg.max_unused_traits:
        score -= 20 * (unused_count - cfg.max_unused_traits)
    return score


def state_sort_key(result: dict, sort_by: str):
    if sort_by == 'cost':
        return (result['total_cost'], -result['score'], result['champion_names'])
    return (-result['score'], result['total_cost'], result['champion_names'])


def final_valid(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> bool:
    _, _, _, unused_count, _, _ = evaluate_traits(state.trait_counts, trait_defs, cfg.trait_plus1)
    if unused_count > cfg.max_unused_traits:
        return False
    eff_tank, eff_damage, diff = effective_role_counts(state)
    if eff_tank < cfg.min_tanks:
        return False
    if eff_damage < cfg.min_damage:
        return False
    if diff > cfg.max_role_diff:
        return False
    return True


def build_result(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> dict:
    active, near, unused, unused_count, leftover_units, trait_score = evaluate_traits(state.trait_counts, trait_defs, cfg.trait_plus1)
    eff_tank, eff_damage, diff = effective_role_counts(state)
    score = trait_score - state.total_cost * 0.45 - diff * cfg.role_balance_weight
    return {
        'score': round(score, 2),
        'total_cost': state.total_cost,
        'champion_names': [u.name for u in state.units],
        'units': [dataclasses.asdict(u) for u in state.units],
        'roles': {
            'tank': state.tank_count,
            'damage': state.damage_count,
            'flex': state.flex_count,
            'effective_tanks': round(eff_tank, 1),
            'effective_damage': round(eff_damage, 1),
            'diff': round(diff, 1),
        },
        'active_traits': active,
        'near_traits': near,
        'unused_traits': unused,
        'unused_trait_count': unused_count,
        'leftover_units': leftover_units,
    }


def search(champions: List[Champion], trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> List[dict]:
    champ_by_name = {normalize_text(c.name): c for c in champions}
    include_units = []
    used_ids = set()
    for raw in cfg.include_units:
        key = normalize_text(raw)
        if key not in champ_by_name:
            raise RuntimeError(f"Unknown unit: {raw}")
        c = champ_by_name[key]
        if c.cost in cfg.exclude_costs:
            raise RuntimeError(f"Included unit {c.name} is excluded by cost filter")
        if c.id not in used_ids:
            include_units.append(c)
            used_ids.add(c.id)
    if len(include_units) > cfg.level:
        raise RuntimeError("More included units than level")

    # Only search over optional units; included units are fixed in every state.
    pool = [c for c in champions if c.cost not in cfg.exclude_costs and c.id not in used_ids]
    # sort by cheap + more traits first to help beam search
    pool = sorted(pool, key=lambda c: (c.cost, -len(c.traits), c.name))

    init_trait_counts: Dict[str, int] = {}
    tank = damage = flex = total_cost = 0
    for c in include_units:
        total_cost += c.cost
        for tr in c.traits:
            init_trait_counts[tr] = init_trait_counts.get(tr, 0) + 1
        if c.role == 'tank':
            tank += 1
        elif c.role == 'damage':
            damage += 1
        else:
            flex += 1
    init_state = State(
        units=tuple(include_units),
        next_idx=0,
        trait_counts=init_trait_counts,
        total_cost=total_cost,
        tank_count=tank,
        damage_count=damage,
        flex_count=flex,
        score_estimate=0.0,
    )
    init_state.score_estimate = estimate_state_score(init_state, trait_defs, cfg)

    states = [init_state]
    slots_remaining = cfg.level - len(include_units)
    if slots_remaining < 0:
        return []

    for _ in range(slots_remaining):
        next_states: List[State] = []
        for st in states:
            for idx in range(st.next_idx, len(pool)):
                c = pool[idx]
                tc = dict(st.trait_counts)
                for tr in c.traits:
                    tc[tr] = tc.get(tr, 0) + 1
                tank2 = st.tank_count + (1 if c.role == 'tank' else 0)
                dmg2 = st.damage_count + (1 if c.role == 'damage' else 0)
                flex2 = st.flex_count + (1 if c.role == 'flex' else 0)
                ns = State(
                    units=st.units + (c,),
                    next_idx=idx + 1,
                    trait_counts=tc,
                    total_cost=st.total_cost + c.cost,
                    tank_count=tank2,
                    damage_count=dmg2,
                    flex_count=flex2,
                    score_estimate=0.0,
                )
                ns.score_estimate = estimate_state_score(ns, trait_defs, cfg)
                next_states.append(ns)
        states = sorted(next_states, key=lambda s: (-s.score_estimate, s.total_cost))[:cfg.beam_width]
        if not states:
            break

    results = []
    for st in states:
        if final_valid(st, trait_defs, cfg):
            results.append(build_result(st, trait_defs, cfg))
    results.sort(key=lambda r: state_sort_key(r, cfg.sort_by))
    return results if cfg.limit == 0 else results[: cfg.limit]


def print_text_results(results: List[dict], meta: dict):
    print(f"Set: {meta['set_display_name']} ({meta['set_name']})")
    print(f"Champions: {meta['champion_count']} | Traits: {meta['trait_count']}")
    if not results:
        print("No results matched the constraints.")
        return
    for i, r in enumerate(results, 1):
        print()
        print(f"#{i}  score={r['score']:.2f}  cost={r['total_cost']}")
        print("Units: " + ", ".join(r['champion_names']))
        roles = r['roles']
        print(
            f"Roles: tank={roles['tank']}, damage={roles['damage']}, flex={roles['flex']} | "
            f"effective_tanks={roles['effective_tanks']}, effective_damage={roles['effective_damage']}, diff={roles['diff']}"
        )
        print("Active: " + ("; ".join(r['active_traits']) if r['active_traits'] else "none"))
        print("Near: " + ("; ".join(r['near_traits']) if r['near_traits'] else "none"))
        print("Unused: " + ("; ".join(r['unused_traits']) if r['unused_traits'] else "none"))


def parse_args() -> SearchConfig:
    p = argparse.ArgumentParser(description="Find TFT perfect-synergy comps using CommunityDragon JSON only.")
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--level', type=int, required=True)
    p.add_argument('--include-units', type=str, default='')
    p.add_argument('--exclude-costs', type=str, default='')
    p.add_argument('--max-unused-traits', type=int, default=99)
    p.add_argument('--trait-plus1', type=str, default='')
    p.add_argument('--sort-by', choices=['score', 'cost'], default='score')
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--beam-width', type=int, default=500)
    p.add_argument('--min-tanks', type=float, default=2)
    p.add_argument('--min-damage', type=float, default=2)
    p.add_argument('--max-role-diff', type=float, default=2)
    p.add_argument('--role-balance-weight', type=float, default=8)
    p.add_argument('--json', action='store_true')
    p.add_argument('--dump-meta', action='store_true')
    p.add_argument('--dump-champions', action='store_true')
    p.add_argument('--dump-traits', action='store_true')
    args = p.parse_args()

    include_units = [titleish(x) for x in args.include_units.split(',') if x.strip()]
    exclude_costs = [int(x) for x in args.exclude_costs.split(',') if x.strip()]
    return SearchConfig(
        level=args.level,
        include_units=include_units,
        exclude_costs=exclude_costs,
        max_unused_traits=args.max_unused_traits,
        trait_plus1=titleish(args.trait_plus1) if args.trait_plus1.strip() else None,
        sort_by=args.sort_by,
        limit=args.limit,
        beam_width=args.beam_width,
        min_tanks=args.min_tanks,
        min_damage=args.min_damage,
        max_role_diff=args.max_role_diff,
        role_balance_weight=args.role_balance_weight,
        json_output=args.json,
        dump_meta=args.dump_meta,
        dump_champions=args.dump_champions,
        dump_traits=args.dump_traits,
    ), args.refresh


def main() -> int:
    cfg, refresh = parse_args()
    try:
        set_name, set_display_name, set_num = pick_current_set(fetch_json(SETS_URL, refresh))
        traits = load_traits(refresh, set_num)
        champs = load_champions(refresh, set_num, traits)
        meta = {
            'set_name': set_name,
            'set_display_name': set_display_name,
            'set_number': set_num,
            'champion_count': len(champs),
            'trait_count': len(traits),
            'sources': {
                'sets': SETS_URL,
                'champions': CHAMPS_TEAMPLANNER_URL,
                'traits': TRAITS_URL,
            }
        }
        if cfg.trait_plus1 and cfg.trait_plus1 not in traits:
            raise RuntimeError(f"Unknown trait: {cfg.trait_plus1}")

        if cfg.dump_meta:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
            return 0
        if cfg.dump_traits:
            print(json.dumps([dataclasses.asdict(v) for v in sorted(traits.values(), key=lambda x: x.name)], indent=2, ensure_ascii=False))
            return 0
        if cfg.dump_champions:
            payload = [dataclasses.asdict(c) for c in champs]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        results = search(champs, traits, cfg)
        if cfg.json_output:
            print(json.dumps({'meta': meta, 'results': results}, indent=2, ensure_ascii=False))
        else:
            print_text_results(results, meta)
        return 0
    except Exception as err:
        eprint(f"ERROR: {err}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
