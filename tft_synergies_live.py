#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import html as html_lib
import hashlib
import json
import itertools
import math
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request

BASE = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1"
SETS_URL = f"{BASE}/tftsets.json"
CHAMPS_URL = f"{BASE}/tftchampions.json"
CHAMPS_TEAMPLANNER_URL = f"{BASE}/tftchampions-teamplanner.json"
TRAITS_URL = f"{BASE}/tfttraits.json"
TACTICS_TOOLS_UNITS_URL = "https://tactics.tools/info/units"
TACTICS_TOOLS_SET_UPDATE_URL = "https://tactics.tools/info/set-update"
CACHE_DIR = Path('.tft_synergy_cache')
CACHE_DIR.mkdir(exist_ok=True)
DATA_DIR = Path('data')
SET17_SNAPSHOT_PATH = DATA_DIR / 'tft_set17_snapshot.json'
ASSETS_DIR = Path('assets')
SET17_UNIT_ASSETS_DIR = ASSETS_DIR / 'set17' / 'units'
SET17_TRAIT_ASSETS_DIR = ASSETS_DIR / 'set17' / 'traits'

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

TANK_KEYWORDS = {
    "bastion", "bruiser", "warden", "juggernaut", "guardian", "sentinel",
    "behemoth", "vanguard", "protector", "knight", "defender"
}
DAMAGE_KEYWORDS = {
    "sorcerer", "sniper", "invoker", "challenger", "assassin", "marksman",
    "gunslinger", "slayer", "duelist", "reaper", "carry", "arcanist",
    "trickshot", "artillerist", "multistriker", "blaster"
}

@dataclass(frozen=True)
class SetRuleConfig:
    allowed_special_names: Set[str] = field(default_factory=set)
    opt_in_only_names: Set[str] = field(default_factory=set)
    team_buff_traits: Set[str] = field(default_factory=set)
    always_work_team_buff_traits: Set[str] = field(default_factory=set)
    frontline_team_buff_traits: Set[str] = field(default_factory=set)
    carry_ap_hybrid_team_buff_traits: Set[str] = field(default_factory=set)
    carry_caster_team_buff_traits: Set[str] = field(default_factory=set)
    carry_attack_speed_team_buff_traits: Set[str] = field(default_factory=set)
    special_champion_synergies: Dict[str, Set[str]] = field(default_factory=dict)
    special_champion_min_level: Dict[str, int] = field(default_factory=dict)


SET_RULES: Dict[str, SetRuleConfig] = {
    "16": SetRuleConfig(
        allowed_special_names={"Baron Nashor"},
        team_buff_traits={
            "Arcanist", "Bruiser", "Defender", "Invoker", "Quickstriker",
            "Demacia", "Dragonborn", "Freljord", "Harvester", "Ionia",
            "Noxus", "Shurima", "Soulbound", "Void", "Yordle", "Zaun",
            "Riftscourge", "Piltover",
        },
        always_work_team_buff_traits={"Soulbound", "Harvester", "Piltover", "Freljord"},
        frontline_team_buff_traits={"Dragonborn", "Bruiser", "Defender"},
        carry_ap_hybrid_team_buff_traits={"Arcanist"},
        carry_caster_team_buff_traits={"Invoker"},
        carry_attack_speed_team_buff_traits={"Quickstriker"},
        special_champion_synergies={
            "Zaahen": {"Ionia", "Demacia"},
            "Aurelion Sol": {"Targon", "Arcanist"},
            "Baron Nashor": {"Void"},
        },
        special_champion_min_level={"Baron Nashor": 10},
    ),
    "17": SetRuleConfig(
        allowed_special_names=set(),
        opt_in_only_names={"Zed", "Rhaast"},
        team_buff_traits={
            "N.O.V.A.", "Bulwark", "Dark Lady", "Redeemer", "Stargazer",
            "Timebreaker", "Bastion", "Brawler", "Challenger",
            "Channeler", "Marauder", "Voyager", "Eradicator", "Commander", "Psionic", "Dark Star",
        },
        always_work_team_buff_traits={"Dark Lady", "Redeemer", "Timebreaker", "Bulwark", "Voyager", "Stargazer", "Marauder", "Eradicator", "Commander", "Psionic", "Dark Star"},
        frontline_team_buff_traits={"Bastion", "Brawler"},
        carry_ap_hybrid_team_buff_traits=set(),
        carry_caster_team_buff_traits={"Channeler"},
        carry_attack_speed_team_buff_traits={"Challenger"},
        special_champion_synergies={},
        special_champion_min_level={},
    ),
}

CARRY_TRAIT_BONUS = 5.0
TEAM_BUFF_BONUS = 4.0
CARRY_TEAM_BUFF_STACK_BONUS = 5.0
IRRELEVANT_TRAIT_PENALTY = 2.0
CARRY_INACTIVE_TRAIT_PENALTY = 2.5
SPECIAL_NO_SYNERGY_PENALTY = 25.0
TEAM_BUFF_MISMATCH_PENALTY = 1.0
FRONTLINE_SHORTFALL_PENALTY = 9.0
BACKLINE_SHORTFALL_PENALTY = 7.0
STRUCTURE_STABILITY_BONUS = 3.0
OFF_PROFILE_MAGIC_DAMAGE_BASE_PENALTY = 2.0
OFF_PROFILE_MAGIC_DAMAGE_COST_WEIGHT = 1.5
SUPPORTIVE_OFF_PROFILE_DISCOUNT = 0.65
ACTIVE_TRAIT_OVERFLOW_PENALTY = 3.0
NOVA_UNIT_USEFUL_BONUS = 1.6
NOVA_UNIT_USELESS_MULTIPLIER = 1.0 / 3.0
NOVA_ALWAYS_GOOD_UNITS = {"Aatrox", "Kindred"}
NOVA_ATTACK_SPEED_UNITS = {"Caitlyn"}
NOVA_CASTER_UNITS = {"Akali"}
NOVA_FRONTLINE_UNITS = {"Maokai"}
NOVA_EMBLEM_NAME = "N.O.V.A. Emblem"
MECHA_TRAIT_NAME = "Mecha"
RHAAST_REDEEMER_BASE_TRAIT_TARGET = 8.0
RHAAST_REDEEMER_MARKSMAN_SPECIALIST_FACTOR = 1.093
RHAAST_REDEEMER_FIGHTER_FACTOR = 3.186
SINGLE_TRAIT_OWNER_BY_TRAIT = {
    "Dark Lady": {"Morgana"},
    "Factory New": {"Graves"},
    "Doomer": {"Vex"},
}
SINGLE_TRAIT_FACTOR_BY_TRAIT = {
    # Morgana already routes through the "always good team-buff" branch,
    # so only give it a light uplift for being a 1-trait champion.
    "Dark Lady": 1.5,
    # Graves only brings Factory New, so rate it materially above a normal trait.
    "Factory New": 2.0,
    "Doomer": 2.0,
}
TRAIT_BONUS_FACTOR_BY_TRAIT = {
    "Eradicator": 1.5,
    "Commander": 1.5,
}


TRAIT_BREAKPOINT_SCORE_MULTIPLIERS = {
    ("Arbiter", 3): 1.2,
    ("Primordian", 3): 1.2,
    ("Timebreaker", 4): 1.2,
    ("Fateweaver", 4): 1.2,
}

MISS_FORTUNE_BASE_NAME = "Miss Fortune"
MISS_FORTUNE_DEFAULT_MODE = "Channeler"
MISS_FORTUNE_MODES = {
    "Channeler": "Channeler",
    "Challenger": "Challenger",
    "Replicator": "Replicator",
}


def miss_fortune_variant_name(mode: str) -> str:
    return f"{MISS_FORTUNE_BASE_NAME} [{mode}]"


def is_miss_fortune_name(name: str) -> bool:
    return normalize_text(name).startswith(normalize_text(MISS_FORTUNE_BASE_NAME))


def resolve_special_unit_name(raw_name: Optional[str], champions: List["Champion"]) -> Optional[str]:
    if not raw_name:
        return raw_name
    key = normalize_text(raw_name)
    if any(c.id == key for c in champions):
        return raw_name
    if key == normalize_text(MISS_FORTUNE_BASE_NAME):
        preferred_name = miss_fortune_variant_name(MISS_FORTUNE_DEFAULT_MODE)
        if any(c.name == preferred_name for c in champions):
            return preferred_name
    return raw_name


def expand_special_variants(champions: List["Champion"], set_num: str) -> List["Champion"]:
    if set_num != "17":
        return champions
    out: List[Champion] = []
    for champion in champions:
        if champion.base_name == MISS_FORTUNE_BASE_NAME or champion.name == MISS_FORTUNE_BASE_NAME:
            for mode, trait_name in MISS_FORTUNE_MODES.items():
                variant_name = miss_fortune_variant_name(mode)
                variant_traits = sorted(set([tr for tr in champion.traits if tr != trait_name] + [trait_name]))
                out.append(Champion(
                    id=normalize_text(variant_name),
                    api_name=champion.api_name,
                    name=variant_name,
                    display_name=champion.display_name,
                    cost=champion.cost,
                    raw_cost=champion.raw_cost,
                    traits=variant_traits,
                    role=champion.role,
                    unit_archetype=champion.unit_archetype,
                    damage_profile=champion.damage_profile,
                    attack_range=champion.attack_range,
                    avatar_url=champion.avatar_url,
                    base_name=MISS_FORTUNE_BASE_NAME,
                    special_mode=mode,
                ))
            continue
        out.append(champion)
    return sorted(out, key=lambda c: (c.cost, c.display_name, c.name))


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


def set17_unit_avatar_remote_url(api_name: str) -> str:
    slug = api_name.lower()
    return f"https://ap.tft.tools/img/new17/face/{slug}.jpg?w=116"


def set17_trait_icon_local_filename(icon_slug: str) -> str:
    return f"{icon_slug}.svg"


def set17_unit_avatar_local_filename(api_name: str) -> str:
    return f"{api_name}.jpg"


def fetch_json(url: str, refresh: bool) -> object:
    body = fetch_text(url, refresh, suffix='.json')
    return json.loads(body)


def fetch_text(url: str, refresh: bool, suffix: str = '.txt') -> str:
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"{digest}{suffix}"
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding='utf-8')
    last_err = None
    for i in range(RETRIES):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode('utf-8')
            cache_path.write_text(body, encoding='utf-8')
            return body
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
    display_name: str
    cost: int
    raw_cost: int
    traits: List[str]
    role: str
    unit_archetype: Optional[str] = None
    damage_profile: Optional[str] = None
    attack_range: Optional[int] = None
    avatar_url: Optional[str] = None
    base_name: Optional[str] = None
    special_mode: Optional[str] = None


@dataclass(frozen=True)
class UnitProfile:
    name: str
    api_name: str
    cost: Optional[int]
    archetype: str
    damage_profile: Optional[str]
    attack_range: Optional[int]
    traits: Tuple[str, ...] = ()
    avatar_url: Optional[str] = None


@dataclass
class SearchConfig:
    level: int
    set_number: str = ""
    include_units: List[str] = field(default_factory=list)
    exclude_units: List[str] = field(default_factory=list)
    exclude_costs: List[int] = field(default_factory=list)
    cost_unit_ranges: Dict[int, Tuple[Optional[int], Optional[int]]] = field(default_factory=dict)
    mecha_transform_range: Tuple[Optional[int], Optional[int]] = (None, None)
    required_trait_breakpoints: Dict[str, int] = field(default_factory=dict)
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
    carry: Optional[str] = None
    carry_traits: List[str] = field(default_factory=list)
    carry_cost: Optional[int] = None
    carry_damage_profile: Optional[str] = None
    carry_archetype: Optional[str] = None
    enable_anima_trait: bool = False
    min_active_carry_traits: int = 0
    required_four_cost_tank_names: List[str] = field(default_factory=list)
    required_tank_cost: Optional[int] = None
    required_tank_names: List[str] = field(default_factory=list)
    debug_timings: Dict[str, float] = field(default_factory=dict)
    debug_cumulative_timings: Dict[str, float] = field(default_factory=dict)
    cached_carry_subtypes: Optional[Tuple[str, ...]] = None
    cached_carry_trait_names: Optional[Tuple[str, ...]] = None
    state_mecha_metrics_cache: Dict[Tuple[str, ...], Tuple[int, int, int, int]] = field(default_factory=dict)
    state_effective_trait_counts_cache: Dict[Tuple[str, ...], Dict[str, int]] = field(default_factory=dict)
    state_trait_evaluation_cache: Dict[Tuple[str, ...], Tuple[List[str], List[str], List[str], int, int, float]] = field(default_factory=dict)
    state_frontline_backline_cache: Dict[Tuple[str, ...], Tuple[float, float]] = field(default_factory=dict)
    state_role_metrics_cache: Dict[Tuple[str, ...], Tuple[float, float, float, int, int]] = field(default_factory=dict)
    state_archetype_subtypes_cache: Dict[Tuple[str, ...], Set[str]] = field(default_factory=dict)
    state_main_tank_cache: Dict[Tuple[str, ...], Tuple[Optional["Champion"], float]] = field(default_factory=dict)
    state_active_carry_trait_count_cache: Dict[Tuple[str, ...], int] = field(default_factory=dict)


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
    cache_key: Optional[Tuple[str, ...]] = None


def state_cache_key(state: State) -> Tuple[str, ...]:
    if state.cache_key is None:
        state.cache_key = tuple(unit.id for unit in state.units)
    return state.cache_key


def state_cost_counts(state: State) -> Dict[int, int]:
    counts = {i: 0 for i in range(1, 6)}
    for unit in state.units:
        if unit.cost in counts:
            counts[unit.cost] += 1
    return counts


def accumulate_debug_timing(cfg: SearchConfig, key: str, elapsed_ms: float) -> None:
    cfg.debug_cumulative_timings[key] = round(cfg.debug_cumulative_timings.get(key, 0.0) + elapsed_ms, 2)


def normalize_cost_range(min_count: Optional[int], max_count: Optional[int], level: int) -> Tuple[Optional[int], Optional[int]]:
    lo = min_count if min_count is not None and min_count > 0 else None
    hi = max_count if max_count is not None and max_count < level else None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return lo, hi


def get_set_rules(set_number: str) -> SetRuleConfig:
    return SET_RULES.get(set_number, SetRuleConfig())


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
    if set_num == "17":
        snapshot = load_set17_snapshot(refresh)
        trait_unit_counts = {
            titleish(str(item.get('name') or '')): len(item.get('units', []))
            for item in snapshot.get('traits', [])
            if isinstance(item, dict)
        }
        out: Dict[str, TraitDef] = {}
        for item in snapshot.get('traits', []):
            if not isinstance(item, dict):
                continue
            display_name = titleish(str(item.get('name') or ''))
            breakpoints = sorted(set(int(x) for x in item.get('breakpoints', []) if isinstance(x, int) and x > 0))
            max_reachable = trait_unit_counts.get(display_name, 0) + 1
            if display_name == MECHA_TRAIT_NAME:
                max_reachable = max(max_reachable, trait_unit_counts.get(display_name, 0) * 2)
            if max_reachable > 0:
                breakpoints = [bp for bp in breakpoints if bp <= max_reachable]
            if not display_name or not breakpoints:
                continue
            out[display_name] = TraitDef(id=normalize_text(display_name), name=display_name, breakpoints=breakpoints)
        if not out:
            raise RuntimeError("No traits parsed from local Set 17 snapshot")
        return out

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
    set_rules = get_set_rules(set_num)
    if not name:
        return False
    if name in set_rules.allowed_special_names:
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


def damage_profile_from_archetype(archetype: str) -> Optional[str]:
    family = archetype.split(' ', 1)[0].lower()
    return family if family in {'attack', 'magic', 'hybrid'} else None


def role_from_unit_archetype(archetype: str) -> Optional[str]:
    """
    Map tactics.tools combat archetypes onto our search roles.
    """
    parts = archetype.split(' ', 1)
    subtype = parts[1].lower() if len(parts) == 2 else ''
    if subtype in {'caster', 'marksman', 'assassin', 'specialist'}:
        return 'damage'
    if subtype == 'tank':
        return 'tank'
    if subtype == 'fighter':
        return 'flex'
    return None


def archetype_subtype(archetype: Optional[str]) -> Optional[str]:
    if not archetype:
        return None
    parts = archetype.split(' ', 1)
    return parts[1].lower() if len(parts) == 2 else None


def effective_carry_subtypes(cfg: SearchConfig) -> Set[str]:
    if cfg.cached_carry_subtypes is not None:
        return set(cfg.cached_carry_subtypes)
    out: Set[str] = set()
    subtype = archetype_subtype(cfg.carry_archetype)
    if subtype:
        out.add(subtype)
    if is_miss_fortune_name(cfg.carry or ""):
        out.update({"marksman", "caster"})
    cfg.cached_carry_subtypes = tuple(sorted(out))
    return set(cfg.cached_carry_subtypes)


def carry_is_melee(cfg: SearchConfig) -> bool:
    return bool(effective_carry_subtypes(cfg) & {"assassin", "fighter", "tank"})


def effective_carry_trait_names(cfg: SearchConfig) -> List[str]:
    if cfg.cached_carry_trait_names is not None:
        return list(cfg.cached_carry_trait_names)
    traits = [tr for tr in cfg.carry_traits]
    if not cfg.enable_anima_trait:
        traits = [tr for tr in traits if tr != "Anima"]
    cfg.cached_carry_trait_names = tuple(traits)
    return list(cfg.cached_carry_trait_names)


def level_threshold(level: int, thresholds: Dict[int, float]) -> float:
    eligible = [lv for lv in thresholds if lv <= level]
    if eligible:
        return thresholds[max(eligible)]
    return thresholds[min(thresholds)]


def trait_breakpoint_score(tdef: "TraitDef", bp: int) -> float:
    """
    Score a breakpoint by its rank within the trait, not by the raw unit count.
    This keeps first breakpoints comparable across traits like 2/2 vs 3/3.
    """
    if bp <= 0:
        return 0.0
    try:
        rank = tdef.breakpoints.index(bp) + 1
    except ValueError:
        return 0.0
    if is_unique_trait(tdef):
        return 5.0
    base_score = rank * rank + 4.0 * rank + 7.0
    return base_score * TRAIT_BREAKPOINT_SCORE_MULTIPLIERS.get((tdef.name, bp), 1.0)


def unit_frontline_backline_value(unit: Champion) -> Tuple[float, float]:
    subtype = archetype_subtype(unit.unit_archetype)
    if subtype == 'tank':
        return 1.0, 0.0
    if subtype in {'assassin', 'fighter'}:
        return 0.5, 0.5
    if subtype in {'marksman', 'caster', 'specialist'}:
        return 0.0, 1.0
    return 0.5, 0.0


def frontline_backline_scores(state: State, cfg: Optional[SearchConfig] = None) -> Tuple[float, float]:
    if cfg is not None:
        key = state_cache_key(state)
        cached = cfg.state_frontline_backline_cache.get(key)
        if cached is not None:
            return cached
    frontline = 0.0
    backline = 0.0
    for unit in state.units:
        front, back = unit_frontline_backline_value(unit)
        frontline += front
        backline += back
    if cfg is not None:
        cfg.state_frontline_backline_cache[key] = (frontline, backline)
    return frontline, backline


def frontline_target(level: int) -> float:
    return level_threshold(level, {
        6: 2.5,
        7: 3.0,
        8: 3.5,
        9: 4.0,
        10: 4.5,
    })


def backline_target(level: int) -> float:
    return level_threshold(level, {
        6: 0.0,
        7: 0.0,
        8: 1.0,
        9: 2.0,
        10: 3.0,
    })


def frontline_team_buff_target(level: int) -> float:
    return level_threshold(level, {
        6: 3.5,
        7: 4.0,
        8: 4.5,
        9: 5.0,
        10: 5.5,
    })


def state_archetype_subtypes(state: State, cfg: Optional[SearchConfig] = None) -> Set[str]:
    if cfg is not None:
        key = state_cache_key(state)
        cached = cfg.state_archetype_subtypes_cache.get(key)
        if cached is not None:
            return set(cached)
    out: Set[str] = set()
    for unit in state.units:
        subtype = archetype_subtype(unit.unit_archetype)
        if subtype:
            out.add(subtype)
    if cfg is not None:
        cfg.state_archetype_subtypes_cache[key] = set(out)
    return out


def nova_buff_multiplier(source_name: str, state: State, cfg: SearchConfig) -> float:
    frontline_score, _ = frontline_backline_scores(state, cfg)
    carry_subtypes = effective_carry_subtypes(cfg)
    present_subtypes = state_archetype_subtypes(state, cfg)

    def has_any_target(targets: Set[str]) -> bool:
        return bool(carry_subtypes & targets) or bool(present_subtypes & targets)

    if source_name in NOVA_ALWAYS_GOOD_UNITS:
        return 1.0
    if source_name in NOVA_ATTACK_SPEED_UNITS:
        return 1.0 if has_any_target({"marksman", "assassin", "fighter", "specialist"}) else NOVA_UNIT_USELESS_MULTIPLIER
    if source_name in NOVA_CASTER_UNITS:
        return 1.0 if has_any_target({"caster", "hybrid fighter"}) else NOVA_UNIT_USELESS_MULTIPLIER
    if source_name in NOVA_FRONTLINE_UNITS:
        return 1.0 if frontline_score >= frontline_target(cfg.level) else NOVA_UNIT_USELESS_MULTIPLIER
    if source_name == NOVA_EMBLEM_NAME:
        return 1.0
    return NOVA_UNIT_USELESS_MULTIPLIER


def nova_team_buff_bonus(state: State, cfg: SearchConfig) -> float:
    bonus = 0.0
    seen_sources: Set[str] = set()
    for unit in state.units:
        if "N.O.V.A." not in unit.traits or unit.name in seen_sources:
            continue
        seen_sources.add(unit.name)
        bonus += NOVA_UNIT_USEFUL_BONUS * nova_buff_multiplier(unit.name, state, cfg)

    if cfg.trait_plus1 == "N.O.V.A.":
        bonus += NOVA_UNIT_USEFUL_BONUS * nova_buff_multiplier(NOVA_EMBLEM_NAME, state, cfg)

    return bonus


def active_non_unique_trait_count(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> int:
    counts = effective_trait_counts_from_state(state, cfg)
    active_count = 0
    for tr_name, cnt in counts.items():
        tdef = trait_defs.get(tr_name)
        if not tdef:
            continue
        if tr_name == "Redeemer":
            continue
        if len(tdef.breakpoints) == 1 and tdef.breakpoints[0] == 1:
            continue
        if _trait_is_active(cnt, tdef):
            active_count += 1
    return active_count


def redeemer_team_buff_bonus(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    frontline_score, _ = frontline_backline_scores(state, cfg)
    present_subtypes = state_archetype_subtypes(state, cfg)
    z = active_non_unique_trait_count(state, trait_defs, cfg)
    if z <= 0:
        return 0.0

    scale = z / RHAAST_REDEEMER_BASE_TRAIT_TARGET
    weight = 0.0
    if present_subtypes & {"marksman", "specialist"}:
        weight = max(weight, RHAAST_REDEEMER_MARKSMAN_SPECIALIST_FACTOR * scale)
    if present_subtypes & {"assassin", "fighter"}:
        weight = max(weight, RHAAST_REDEEMER_FIGHTER_FACTOR * scale)
    if frontline_score >= frontline_team_buff_target(cfg.level):
        weight = max(weight, RHAAST_REDEEMER_MARKSMAN_SPECIALIST_FACTOR * scale)

    if weight <= 0:
        return TEAM_BUFF_BONUS
    return TEAM_BUFF_BONUS * (1.0 + weight)


def single_trait_special_multiplier(state: State, trait_name: str) -> Optional[float]:
    owners = SINGLE_TRAIT_OWNER_BY_TRAIT.get(trait_name)
    factor = SINGLE_TRAIT_FACTOR_BY_TRAIT.get(trait_name)
    if not owners or factor is None:
        return None
    if any(unit.name in owners and len(unit.traits) == 1 for unit in state.units):
        return factor
    return None


def trait_bonus_multiplier(state: State, trait_name: str) -> Optional[float]:
    single_trait_factor = single_trait_special_multiplier(state, trait_name)
    if single_trait_factor is not None:
        return single_trait_factor
    return TRAIT_BONUS_FACTOR_BY_TRAIT.get(trait_name)


def parse_set17_units_from_update_html(html: str) -> Dict[str, UnitProfile]:
    unit_pattern = re.compile(
        r'>([^<>]+?)<div class="flex items-end text-\[16px\]">([1-5])<img.*?'
        r'<img class="mt-\[-3px\] z-\[-1\] aspect-\[9/4\] object-cover [^"]+" alt="([^"]+)" '
        r'src="https://ap\.tft\.tools/img/new17/face_full_ultrawide/(TFT17_[A-Za-z0-9]+)\.jpg\?w=290" width="290"/>'
        r'<div class="absolute text-lg leading-snug bottom-\[6px\] left-\[6px\]">(.*?)'
        r'<div class="flex items-center gap-\[2px\]"><div class="flex-shrink-0"><img title="Range" alt="Range".*?</div>'
        r'<div class="pl-1 font-montserrat text-lg font-medium text-white1 break-all">(\d+)</div>',
        re.S,
    )
    trait_pattern = re.compile(r'<div class="pl-1 css-1fxzlo3">([^<]+)</div>')
    archetype_pattern = re.compile(
        r'<div class="bg-bg2 rounded-lg px-2 py-1 font-montserrat font-medium self-start">'
        r'((?:Attack|Magic|Hybrid)\s+(?:Tank|Fighter|Assassin|Marksman|Caster|Specialist))</div>'
    )
    out: Dict[str, UnitProfile] = {}
    for raw_display_name, raw_cost, raw_alt_name, api_name, chunk, raw_range in unit_pattern.findall(html):
        raw_name = raw_alt_name or raw_display_name
        name = titleish(html_lib.unescape(raw_name))
        archetype_match = archetype_pattern.search(chunk)
        if not archetype_match:
            continue
        archetype = titleish(html_lib.unescape(archetype_match.group(1)))
        traits = tuple(
            titleish(html_lib.unescape(tr.strip()))
            for tr in trait_pattern.findall(chunk)
            if tr.strip()
        )
        try:
            attack_range = int(raw_range)
        except ValueError:
            attack_range = None
        out[normalize_text(name)] = UnitProfile(
            name=name,
            api_name=api_name,
            cost=int(raw_cost),
            archetype=archetype,
            damage_profile=damage_profile_from_archetype(archetype),
            attack_range=attack_range,
            traits=traits,
            avatar_url=set17_unit_avatar_remote_url(api_name),
        )
    return out


def parse_set17_traits_from_update_html(html: str) -> List[dict]:
    card_pattern = re.compile(
        r'<a class="no-webkit-preview" href="/info/set-170/traits/[^"]+"><div class="flex items-center gap-\[3px\]">'
        r'<img alt="([^"]+) 0" class="aspect-square  w-\[24px\]" src="([^"]+)" opacity="0\.87"/>'
        r'<h3 class="inline-block text-xl font-montserrat font-medium">([^<]+)</h3></div></a>'
        r'<div class="py-3 text-sm leading-tight"><div class="leading-tight ">(.*?)</div></div>'
        r'<div class="flex pt-2 gap-\[10px\] flex-wrap">(.*?)</div></div>',
        re.S,
    )
    grouped: Dict[str, dict] = {}
    for _, icon_url, raw_name, desc_chunk, units_chunk in card_pattern.findall(html):
        name = titleish(html_lib.unescape(raw_name).strip())
        desc = html_lib.unescape(
            re.sub(r'<img[^>]+alt="([^"]+)"[^>]*>', r' [\1] ', desc_chunk)
        )
        desc = re.sub(r'<div class="h-\[[^\]]+\]"></div>', '\n', desc)
        desc = re.sub(r'<[^>]+>', '', desc)
        desc = ' '.join(desc.split())
        breakpoints = sorted(set(int(x) for x in re.findall(r'\((\d+)\)', desc)))
        units = [
            titleish(html_lib.unescape(raw_unit).strip())
            for raw_unit in re.findall(r'alt="([^"]+)" src=', units_chunk)
        ]
        entry = grouped.setdefault(name, {
            'name': name,
            'breakpoints': set(),
            'units': set(),
            'descriptions': [],
            'variants': [],
            'icon_url': icon_url,
        })
        entry['breakpoints'].update(breakpoints)
        entry['units'].update(units)
        if desc and desc not in entry['descriptions']:
            entry['descriptions'].append(desc)
        entry['variants'].append({
            'breakpoints': breakpoints,
            'description': desc,
        })

    out: List[dict] = []
    for name, entry in sorted(grouped.items()):
        breakpoints = sorted(entry['breakpoints'])
        if not breakpoints and len(entry['units']) == 1:
            breakpoints = [1]
        out.append({
            'name': name,
            'breakpoints': breakpoints,
            'units': sorted(entry['units']),
            'description': entry['descriptions'][0] if entry['descriptions'] else '',
            'variants': entry['variants'],
            'icon_url': entry['icon_url'],
            'icon_slug': re.search(r'new17_tft17_([a-z0-9]+)_w\.svg', entry['icon_url']).group(1) if re.search(r'new17_tft17_([a-z0-9]+)_w\.svg', entry['icon_url']) else normalize_text(name),
        })
    return out


def build_set17_snapshot(refresh: bool) -> dict:
    html = fetch_text(TACTICS_TOOLS_SET_UPDATE_URL, refresh, suffix='.html')
    unit_profiles = parse_set17_units_from_update_html(html)
    traits = parse_set17_traits_from_update_html(html)
    units = []
    for key, profile in sorted(unit_profiles.items()):
        units.append({
            'id': key,
            'name': profile.name,
            'api_name': profile.api_name,
            'cost': profile.cost,
            'traits': list(profile.traits),
            'archetype': profile.archetype,
            'damage_profile': profile.damage_profile,
            'attack_range': profile.attack_range,
            'avatar_url': profile.avatar_url,
        })
    return {
        'set_number': '17',
        'source': TACTICS_TOOLS_SET_UPDATE_URL,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'traits': traits,
        'units': units,
    }


def load_set17_snapshot(refresh: bool) -> dict:
    if SET17_SNAPSHOT_PATH.exists() and not refresh:
        return json.loads(SET17_SNAPSHOT_PATH.read_text(encoding='utf-8'))
    snapshot = build_set17_snapshot(refresh)
    DATA_DIR.mkdir(exist_ok=True)
    SET17_SNAPSHOT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    return snapshot


def load_unit_profiles(refresh: bool, set_num: str) -> Dict[str, UnitProfile]:
    """
    Load unit combat metadata from tactics.tools.
    For Set 17, parse the set-update page directly so we can keep working
    even before CommunityDragon/latest rotates over to the new set.
    """
    out: Dict[str, UnitProfile] = {}
    if set_num == "17":
        snapshot = load_set17_snapshot(refresh)
        for item in snapshot.get('units', []):
            if not isinstance(item, dict):
                continue
            name = titleish(str(item.get('name') or ''))
            if not name:
                continue
            archetype = titleish(str(item.get('archetype') or ''))
            out[normalize_text(name)] = UnitProfile(
                name=name,
                api_name=str(item.get('api_name') or name),
                cost=item.get('cost') if isinstance(item.get('cost'), int) else None,
                archetype=archetype,
                damage_profile=str(item.get('damage_profile')) if item.get('damage_profile') else damage_profile_from_archetype(archetype),
                attack_range=item.get('attack_range') if isinstance(item.get('attack_range'), int) else None,
                traits=tuple(titleish(str(tr)) for tr in item.get('traits', []) if str(tr).strip()),
                avatar_url=str(item.get('avatar_url')) if item.get('avatar_url') else None,
            )
        return out

    html = fetch_text(TACTICS_TOOLS_UNITS_URL, refresh)
    pattern = re.compile(
        r'href="/info/units/[^"]+".*?font-montserrat font-semibold[^>]*>([^<]+)<div.*?'
        r'self-start">([^<]+)</div>',
        re.S,
    )
    for raw_name, archetype in pattern.findall(html):
        name = titleish(html_lib.unescape(raw_name))
        archetype = titleish(html_lib.unescape(archetype))
        out[normalize_text(name)] = UnitProfile(
            name=name,
            api_name=name,
            cost=None,
            archetype=archetype,
            damage_profile=damage_profile_from_archetype(archetype),
            attack_range=None,
            traits=(),
            avatar_url=None,
        )
    return out


def trait_profile_key(champion: Champion) -> Tuple[str, ...]:
    return tuple(sorted(champion.traits))


def prefer_expensive_equivalents(champions: List[Champion], locked_ids: set[str]) -> List[Champion]:
    """
    Keep only the most expensive optional champion per identical trait profile.
    Included/locked units are never removed.
    """
    by_profile: Dict[Tuple[str, ...], List[Champion]] = {}
    for c in champions:
        by_profile.setdefault(trait_profile_key(c), []).append(c)

    kept: List[Champion] = []
    for group in by_profile.values():
        locked = [c for c in group if c.id in locked_ids]
        unlocked = [c for c in group if c.id not in locked_ids]
        kept.extend(locked)
        if not unlocked:
            continue
        max_cost = max(c.cost for c in unlocked)
        best = [c for c in unlocked if c.cost == max_cost]
        kept.extend(best)

    # deterministic order for stable search traversal.
    return sorted(kept, key=lambda c: (c.cost, -len(c.traits), c.name))


def is_level_allowed(champion_name: str, level: int) -> bool:
    min_level = None
    for rules in SET_RULES.values():
        if champion_name in rules.special_champion_min_level:
            min_level = rules.special_champion_min_level[champion_name]
            break
    return min_level is None or level >= min_level


def load_champions(refresh: bool, set_num: str, traits: Dict[str, TraitDef], unit_profiles: Dict[str, UnitProfile]) -> List[Champion]:
    if set_num == "17":
        snapshot = load_set17_snapshot(refresh)
        out: List[Champion] = []
        for item in snapshot.get('units', []):
            if not isinstance(item, dict):
                continue
            name = titleish(str(item.get('name') or ''))
            raw_cost = item.get('cost')
            if not name or not isinstance(raw_cost, int) or raw_cost <= 0:
                continue
            display_traits = sorted({
                titleish(str(tr))
                for tr in item.get('traits', [])
                if titleish(str(tr)) in traits
            })
            if not display_traits:
                continue
            profile = unit_profiles.get(normalize_text(name))
            archetype = profile.archetype if profile else titleish(str(item.get('archetype') or ''))
            role = role_from_unit_archetype(archetype) if archetype else None
            if role is None:
                role = infer_role(display_traits)
            damage_profile = profile.damage_profile if profile else damage_profile_from_archetype(archetype) if archetype else None
            attack_range = profile.attack_range if profile else item.get('attack_range') if isinstance(item.get('attack_range'), int) else None
            out.append(Champion(
                id=normalize_text(name),
                api_name=str(item.get('api_name') or name),
                name=name,
                display_name=name,
                cost=normalize_search_cost(raw_cost),
                raw_cost=raw_cost,
                traits=display_traits,
                role=role,
                unit_archetype=archetype,
                damage_profile=damage_profile,
                attack_range=attack_range,
                avatar_url=profile.avatar_url if profile else str(item.get('avatar_url') or ''),
                base_name=name,
            ))
        if len(out) < 50:
            raise RuntimeError(f"Parsed only {len(out)} Set 17 champions from local snapshot")
        return expand_special_variants(sorted(out, key=lambda c: (c.cost, c.name)), set_num)

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
        profile = unit_profiles.get(normalize_text(name))
        archetype = profile.archetype if profile else None
        role = role_from_unit_archetype(archetype) if archetype else None
        if role is None:
            role = infer_role(display_traits)
        out.append(Champion(
            id=normalize_text(name),
            api_name=api_name or (profile.api_name if profile else name),
            name=name,
            display_name=name,
            cost=normalize_search_cost(raw_cost),
            raw_cost=raw_cost,
            traits=display_traits,
            role=role,
            unit_archetype=archetype,
            damage_profile=profile.damage_profile if profile else None,
            attack_range=profile.attack_range if profile else None,
            avatar_url=profile.avatar_url if profile else None,
            base_name=name,
        ))
    # pragmatic validation: Set 16 is very large, but exact count can fluctuate if CDragon schema shifts.
    if len(out) < 50:
        raise RuntimeError(
            f"Parsed only {len(out)} playable champions for TFTSet{set_num} from CommunityDragon. "
            "The JSON schema likely changed; inspect --dump-meta / --dump-champions."
        )
    return expand_special_variants(sorted(out, key=lambda c: (c.cost, c.name)), set_num)


NEAR_BREAKPOINT_BONUS = 4.0


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
            score += trait_breakpoint_score(tdef, best_bp)
            leftover_units += max(0, cnt - best_bp)
        else:
            unused.append(f"{tr_name}({cnt})")
            unused_count += 1
            score += 0.0
        # Only reward "near" traits when the first breakpoint is still inactive.
        if best_bp == 0 and next_bp is not None and next_bp - cnt == 1:
            near.append(f"{tr_name} {cnt}->{next_bp}")
            score += NEAR_BREAKPOINT_BONUS
    score -= leftover_units * 1.5
    return active, near, unused, unused_count, leftover_units, score


def evaluate_state_traits(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> Tuple[List[str], List[str], List[str], int, int, float]:
    key = state_cache_key(state)
    cached = cfg.state_trait_evaluation_cache.get(key)
    if cached is not None:
        return cached
    evaluated = evaluate_traits(effective_trait_counts_from_state(state, cfg), trait_defs, cfg.trait_plus1)
    cfg.state_trait_evaluation_cache[key] = evaluated
    return evaluated


def effective_role_counts(state: State, cfg: Optional[SearchConfig] = None) -> Tuple[float, float, float]:
    if cfg is not None:
        key = state_cache_key(state)
        cached = cfg.state_role_metrics_cache.get(key)
        if cached is not None:
            return cached[:3]
    eff_tank = state.tank_count + 0.5 * state.flex_count
    eff_damage = state.damage_count + 0.5 * state.flex_count
    diff = abs(eff_tank - eff_damage)
    if cfg is not None:
        cfg.state_role_metrics_cache[key] = (eff_tank, eff_damage, diff, abs(state.tank_count - state.damage_count), max(0, state.damage_count - state.tank_count - 1))
    return eff_tank, eff_damage, diff


def raw_role_diff(state: State, cfg: Optional[SearchConfig] = None) -> int:
    if cfg is not None:
        key = state_cache_key(state)
        cached = cfg.state_role_metrics_cache.get(key)
        if cached is not None:
            return cached[3]
    return abs(state.tank_count - state.damage_count)


def frontline_shortfall(state: State, cfg: Optional[SearchConfig] = None) -> int:
    """
    Only penalize boards that are meaningfully too light on frontline.
    Extra frontline is acceptable. A one-unit damage lead is fine; start penalizing
    once damage exceeds tanks by 2 or more.
    """
    if cfg is not None:
        key = state_cache_key(state)
        cached = cfg.state_role_metrics_cache.get(key)
        if cached is not None:
            return cached[4]
    return max(0, state.damage_count - state.tank_count - 1)


def _trait_is_active(cnt: int, tdef: TraitDef) -> bool:
    return tdef.breakpoints and cnt >= tdef.breakpoints[0]


def active_breakpoint(cnt: int, tdef: TraitDef) -> int:
    best = 0
    for bp in tdef.breakpoints:
        if cnt >= bp:
            best = bp
    return best


def is_unique_trait(tdef: TraitDef) -> bool:
    return len(tdef.breakpoints) == 1 and tdef.breakpoints[0] == 1


def mecha_state_metrics(state: State, cfg: SearchConfig) -> Tuple[int, int, int, int]:
    """
    Mecha units can transform, taking one extra team slot and counting twice for Mecha.
    At effective Mecha 6, the board gains +1 max team size.
    """
    key = state_cache_key(state)
    cached = cfg.state_mecha_metrics_cache.get(key)
    if cached is not None:
        return cached

    raw_mecha = state.trait_counts.get(MECHA_TRAIT_NAME, 0)
    plus_one = 1 if cfg.trait_plus1 == MECHA_TRAIT_NAME else 0
    unit_count = len(state.units)
    min_allowed, max_allowed = cfg.mecha_transform_range
    lo = max(0, min_allowed or 0)
    hi = raw_mecha if max_allowed is None else min(raw_mecha, max_allowed)

    transformed = 0
    effective_mecha = raw_mecha + plus_one
    capacity = cfg.level + (1 if effective_mecha >= 6 else 0)
    best_found = False
    for candidate in range(hi, -1, -1):
        candidate_effective = raw_mecha + candidate + plus_one
        candidate_capacity = cfg.level + (1 if candidate_effective >= 6 else 0)
        candidate_occupied = unit_count + candidate
        if candidate_occupied > candidate_capacity:
            continue
        transformed = candidate
        effective_mecha = candidate_effective
        capacity = candidate_capacity
        best_found = True
        if candidate >= lo:
            break

    occupied_slots = unit_count + transformed
    metrics = (capacity, transformed, occupied_slots, effective_mecha)
    cfg.state_mecha_metrics_cache[key] = metrics
    return metrics


def mecha_transform_range_satisfied(state: State, cfg: SearchConfig) -> bool:
    min_allowed, max_allowed = cfg.mecha_transform_range
    _, transformed, _, _ = mecha_state_metrics(state, cfg)
    if min_allowed is not None and transformed < min_allowed:
        return False
    if max_allowed is not None and transformed > max_allowed:
        return False
    return True


def state_team_capacity(state: State, cfg: SearchConfig) -> int:
    capacity, _, _, _ = mecha_state_metrics(state, cfg)
    return capacity


def state_occupied_slots(state: State, cfg: SearchConfig) -> int:
    _, _, occupied_slots, _ = mecha_state_metrics(state, cfg)
    return occupied_slots


def state_remaining_slots(state: State, cfg: SearchConfig) -> int:
    capacity, _, occupied_slots, _ = mecha_state_metrics(state, cfg)
    return max(0, capacity - occupied_slots)


def effective_trait_counts_from_state(state: State, cfg: SearchConfig) -> Dict[str, int]:
    key = state_cache_key(state)
    cached = cfg.state_effective_trait_counts_cache.get(key)
    if cached is not None:
        return cached
    counts = dict(state.trait_counts)
    if MECHA_TRAIT_NAME in counts:
        _, _, _, effective_mecha = mecha_state_metrics(state, cfg)
        counts[MECHA_TRAIT_NAME] = effective_mecha
    cfg.state_effective_trait_counts_cache[key] = counts
    return counts


def effective_trait_count(state: State, trait_name: str, cfg: SearchConfig) -> int:
    counts = effective_trait_counts_from_state(state, cfg)
    return counts.get(trait_name, 0) + (1 if cfg.trait_plus1 == trait_name else 0)


def required_trait_shortfall(state: State, trait_name: str, required_bp: int, cfg: SearchConfig) -> int:
    return max(0, required_bp - effective_trait_count(state, trait_name, cfg))


def required_trait_breakpoints_met(state: State, cfg: SearchConfig) -> bool:
    for trait_name, required_bp in cfg.required_trait_breakpoints.items():
        if effective_trait_count(state, trait_name, cfg) < required_bp:
            return False
    return True


def active_carry_trait_count(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> int:
    key = state_cache_key(state)
    cached = cfg.state_active_carry_trait_count_cache.get(key)
    if cached is not None:
        return cached
    count = 0
    effective_counts = effective_trait_counts_from_state(state, cfg)
    for trait_name in effective_carry_trait_names(cfg):
        tdef = trait_defs.get(trait_name)
        if not tdef:
            continue
        if _trait_is_active(effective_counts.get(trait_name, 0), tdef):
            count += 1
    cfg.state_active_carry_trait_count_cache[key] = count
    return count


def has_required_cost_tank(state: State, cfg: SearchConfig) -> bool:
    if cfg.carry_cost is None:
        return True
    required = set(cfg.required_tank_names or cfg.required_four_cost_tank_names)
    if not required:
        return True
    return any(unit.name in required for unit in state.units)


def _compute_main_tank_data(
    state: State,
    trait_defs: Dict[str, TraitDef],
    cfg: SearchConfig,
) -> Tuple[Optional[Champion], float]:
    effective_counts = effective_trait_counts_from_state(state, cfg)

    def unit_trait_value(unit: Champion) -> float:
        total = 0.0
        for trait_name in unit.traits:
            tdef = trait_defs.get(trait_name)
            if not tdef:
                continue
            cnt = effective_counts.get(trait_name, 0)
            bp = active_breakpoint(cnt, tdef)
            if bp > 0:
                total += trait_breakpoint_score(tdef, bp)
        return total

    target_names = set(cfg.required_tank_names or cfg.required_four_cost_tank_names)
    candidates = [unit for unit in state.units if unit.role == 'tank' and (not target_names or unit.name in target_names)]
    if not candidates:
        candidates = [unit for unit in state.units if unit.role == 'tank']
    if not candidates:
        return None, 0.0

    best = max(
        candidates,
        key=lambda unit: (
            unit_trait_value(unit),
            unit.raw_cost,
            len(unit.traits),
            unit.name,
        ),
    )
    return best, unit_trait_value(best)


def main_tank_trait_value(unit: Champion, state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    key = state_cache_key(state)
    cached = cfg.state_main_tank_cache.get(key)
    if cached is None:
        cached = _compute_main_tank_data(state, trait_defs, cfg)
        cfg.state_main_tank_cache[key] = cached
    main_tank, trait_value = cached
    if main_tank and main_tank.id == unit.id:
        return trait_value
    total = 0.0
    for trait_name in unit.traits:
        tdef = trait_defs.get(trait_name)
        if not tdef:
            continue
        cnt = effective_trait_count(state, trait_name, cfg)
        bp = active_breakpoint(cnt, tdef)
        if bp > 0:
            total += trait_breakpoint_score(tdef, bp)
    return total


def determine_main_tank(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> Optional[Champion]:
    key = state_cache_key(state)
    cached = cfg.state_main_tank_cache.get(key)
    if cached is None:
        cached = _compute_main_tank_data(state, trait_defs, cfg)
        cfg.state_main_tank_cache[key] = cached
    return cached[0]


def trait_relevant_to_main_tank(trait_name: str, main_tank: Optional[Champion], set_rules: SetRuleConfig) -> bool:
    if main_tank is None:
        return False
    if trait_name in main_tank.traits:
        return True
    if trait_name in set_rules.frontline_team_buff_traits:
        return True
    return False


def carry_and_special_bonus(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    """Score bonus/penalty for carry synergy and special champion restrictions."""
    bonus = 0.0
    frontline_score, _ = frontline_backline_scores(state, cfg)
    carry_subtypes = effective_carry_subtypes(cfg)
    set_rules = get_set_rules(cfg.set_number)
    carry_set = set(effective_carry_trait_names(cfg))
    main_tank = determine_main_tank(state, trait_defs, cfg)

    nova_count = state.trait_counts.get("N.O.V.A.", 0) + (1 if cfg.trait_plus1 == "N.O.V.A." else 0)
    nova_def = trait_defs.get("N.O.V.A.")
    nova_bp = active_breakpoint(nova_count, nova_def) if nova_def else 0
    # N.O.V.A. buffs only matter once the trait is actually active at its real set breakpoints.
    if nova_bp in {2, 5}:
        bonus += nova_team_buff_bonus(state, cfg)
        if "N.O.V.A." in carry_set:
            bonus += CARRY_TRAIT_BONUS

    redeemer_count = effective_trait_count(state, "Redeemer", cfg)
    redeemer_def = trait_defs.get("Redeemer")
    if redeemer_def and _trait_is_active(redeemer_count, redeemer_def):
        bonus += redeemer_team_buff_bonus(state, trait_defs, cfg)
        if "Redeemer" in carry_set:
            bonus += CARRY_TRAIT_BONUS

    # --- Carry scoring ---
    if cfg.carry_traits:
        for tr_name, cnt in state.trait_counts.items():
            tdef = trait_defs.get(tr_name)
            if not tdef or cnt <= 0:
                continue
            if not _trait_is_active(cnt, tdef):
                continue
            if tr_name in {"N.O.V.A.", "Redeemer"}:
                continue
            trait_factor = trait_bonus_multiplier(state, tr_name)
            is_carry = tr_name in carry_set
            is_buff = tr_name in set_rules.team_buff_traits
            if is_carry and is_buff:
                # Keep both meanings: it is still a carry trait and still a teamwide buff,
                # but do not stack an extra overlap bonus on top.
                trait_bonus = CARRY_TRAIT_BONUS + TEAM_BUFF_BONUS
                if trait_factor is not None:
                    trait_bonus *= trait_factor
                bonus += trait_bonus
            elif is_carry:
                trait_bonus = CARRY_TRAIT_BONUS
                if trait_factor is not None:
                    trait_bonus *= trait_factor
                bonus += trait_bonus
            elif tr_name == "Shepherd":
                if cfg.carry_damage_profile in {'magic', 'hybrid'}:
                    bonus += CARRY_TRAIT_BONUS
                else:
                    bonus += 0.0
            elif tr_name == "Marauder":
                if carry_is_melee(cfg):
                    trait_bonus = TEAM_BUFF_BONUS + 1.5
                    if trait_factor is not None:
                        trait_bonus *= trait_factor
                    bonus += trait_bonus
                else:
                    bonus += 0.0
            elif tr_name in set_rules.always_work_team_buff_traits:
                trait_bonus = TEAM_BUFF_BONUS + 1.5
                if trait_factor is not None:
                    trait_bonus *= trait_factor
                bonus += trait_bonus
            elif tr_name in set_rules.frontline_team_buff_traits:
                if frontline_score >= frontline_team_buff_target(cfg.level):
                    trait_bonus = TEAM_BUFF_BONUS + 2.0
                    if trait_factor is not None:
                        trait_bonus *= trait_factor
                    bonus += trait_bonus
                else:
                    bonus += 0.0
            elif tr_name in set_rules.carry_ap_hybrid_team_buff_traits:
                if cfg.carry_damage_profile in {'magic', 'hybrid'}:
                    trait_bonus = TEAM_BUFF_BONUS + 1.5
                    if trait_factor is not None:
                        trait_bonus *= trait_factor
                    bonus += trait_bonus
                else:
                    bonus += 0.0
            elif tr_name in set_rules.carry_caster_team_buff_traits:
                if 'caster' in carry_subtypes:
                    trait_bonus = TEAM_BUFF_BONUS + 1.5
                    if trait_factor is not None:
                        trait_bonus *= trait_factor
                    bonus += trait_bonus
                else:
                    bonus += 0.0
            elif tr_name in set_rules.carry_attack_speed_team_buff_traits:
                if carry_subtypes & {'marksman', 'assassin', 'fighter'}:
                    trait_bonus = TEAM_BUFF_BONUS + 1.5
                    if trait_factor is not None:
                        trait_bonus *= trait_factor
                    bonus += trait_bonus
                else:
                    bonus += 0.0
            elif is_buff:
                bonus += 0.0
            else:
                if trait_factor is not None:
                    base_trait_value = trait_breakpoint_score(tdef, active_breakpoint(cnt, tdef))
                    bonus += base_trait_value * trait_factor
                elif trait_relevant_to_main_tank(tr_name, main_tank, set_rules):
                    bonus += 0.0
                elif is_unique_trait(tdef):
                    if cfg.carry:
                        bonus -= IRRELEVANT_TRAIT_PENALTY
                    else:
                        bonus += 0.0
                else:
                    bonus -= IRRELEVANT_TRAIT_PENALTY

    # --- Special champion penalties (always active) ---
    for unit in state.units:
        min_level = set_rules.special_champion_min_level.get(unit.name)
        if min_level is not None and cfg.level < min_level:
            bonus -= SPECIAL_NO_SYNERGY_PENALTY
            continue
        required = set_rules.special_champion_synergies.get(unit.name)
        if required is None:
            continue
        has_synergy = False
        for tr in required:
            cnt = state.trait_counts.get(tr, 0)
            tdef = trait_defs.get(tr)
            if tdef and _trait_is_active(cnt, tdef):
                has_synergy = True
                break
        if not has_synergy:
            bonus -= SPECIAL_NO_SYNERGY_PENALTY

    return bonus


def off_profile_damage_penalty(state: State, cfg: SearchConfig) -> float:
    """
    Penalize extra magic-damage carries when the chosen carry is attack-based.
    Tanks and flex units are intentionally ignored.
    """
    if cfg.carry_damage_profile != 'attack' or not cfg.carry:
        return 0.0

    penalty = 0.0
    carry_id = normalize_text(cfg.carry)
    set_rules = get_set_rules(cfg.set_number)
    for unit in state.units:
        if unit.id == carry_id:
            continue
        if unit.role != 'damage':
            continue
        if unit.damage_profile != 'magic':
            continue
        unit_penalty = OFF_PROFILE_MAGIC_DAMAGE_BASE_PENALTY + unit.cost * OFF_PROFILE_MAGIC_DAMAGE_COST_WEIGHT
        supportive_traits = {
            tr for tr in unit.traits
            if tr in set_rules.always_work_team_buff_traits or tr in cfg.carry_traits
        }
        if supportive_traits:
            unit_penalty *= (1.0 - SUPPORTIVE_OFF_PROFILE_DISCOUNT)
        penalty += unit_penalty
    return penalty


def total_cost_adjustment(state: State, cfg: SearchConfig) -> float:
    """
    Cheap carries prefer cheaper boards. Expensive carries prefer capped boards.
    """
    if cfg.carry_cost is not None and cfg.carry_cost >= 4:
        return state.total_cost * 0.45
    if cfg.carry_cost == 3:
        return state.total_cost * 0.15
    if cfg.carry_cost == 2:
        return state.total_cost * 0.08
    if cfg.carry_cost == 1:
        return state.total_cost * 0.04
    return -state.total_cost * 0.45


def carry_search_heuristic(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    if not cfg.carry:
        return 0.0
    bonus = 0.0
    remaining_slots = state_remaining_slots(state, cfg)
    effective_counts = effective_trait_counts_from_state(state, cfg)
    for trait_name in effective_carry_trait_names(cfg):
        tdef = trait_defs.get(trait_name)
        if not tdef:
            continue
        cnt = effective_counts.get(trait_name, 0)
        if cnt <= 0:
            continue
        active_bp = active_breakpoint(cnt, tdef)
        if active_bp <= 0:
            first_bp = tdef.breakpoints[0]
            if cnt + remaining_slots >= first_bp:
                bonus += 2.0 * (cnt / max(1, first_bp))
            continue
        bonus += 1.5
        try:
            idx = tdef.breakpoints.index(active_bp)
        except ValueError:
            continue
        if idx + 1 < len(tdef.breakpoints):
            next_bp = tdef.breakpoints[idx + 1]
            shortfall = next_bp - cnt
            if shortfall > 0 and shortfall <= remaining_slots:
                bonus += 4.0 * (1.0 - (shortfall / max(1, next_bp)))
    if cfg.carry_cost is not None and has_required_cost_tank(state, cfg):
        bonus += 4.0
    return bonus


def structure_bonus(state: State, cfg: SearchConfig) -> float:
    frontline_score, backline_score = frontline_backline_scores(state, cfg)
    front_target = frontline_target(cfg.level)
    back_target = backline_target(cfg.level)

    bonus = 0.0
    bonus -= max(0.0, front_target - frontline_score) * FRONTLINE_SHORTFALL_PENALTY
    bonus -= max(0.0, back_target - backline_score) * BACKLINE_SHORTFALL_PENALTY

    if frontline_score >= front_target:
        bonus += STRUCTURE_STABILITY_BONUS
    if backline_score >= back_target:
        bonus += STRUCTURE_STABILITY_BONUS * 0.75
    return bonus


def estimate_state_score(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> float:
    effective_trait_counts = effective_trait_counts_from_state(state, cfg)
    active, _, _, unused_count, _, trait_score = evaluate_state_traits(state, trait_defs, cfg)
    eff_tank, eff_damage, _ = effective_role_counts(state, cfg)
    diff = frontline_shortfall(state, cfg)
    slots_remaining = state_remaining_slots(state, cfg)
    cost_counts = state_cost_counts(state)
    score = trait_score
    score += total_cost_adjustment(state, cfg)
    score -= diff * cfg.role_balance_weight
    # light encouragement for minimum role coverage as search develops
    score -= max(0.0, cfg.min_tanks - eff_tank) * 3.5
    score -= max(0.0, cfg.min_damage - eff_damage) * 3.5
    if unused_count > cfg.max_unused_traits:
        score -= 20 * (unused_count - cfg.max_unused_traits)
    score -= max(0, len(active) - cfg.level) * ACTIVE_TRAIT_OVERFLOW_PENALTY
    for cost, (min_target, max_target) in cfg.cost_unit_ranges.items():
        current = cost_counts.get(cost, 0)
        if max_target is not None and current > max_target:
            score -= 25.0 * (current - max_target)
        if min_target is not None and current + slots_remaining < min_target:
            score -= 25.0 * (min_target - (current + slots_remaining))
    for trait_name, required_bp in cfg.required_trait_breakpoints.items():
        shortfall = required_trait_shortfall(state, trait_name, required_bp, cfg)
        if shortfall == 0:
            score += 2.0
            continue
        if shortfall > slots_remaining:
            score -= 40.0 * shortfall
        else:
            score -= 8.0 * shortfall
    min_mecha_transforms, _ = cfg.mecha_transform_range
    if min_mecha_transforms is not None:
        _, transformed_mechas, _, _ = mecha_state_metrics(state, cfg)
        if transformed_mechas < min_mecha_transforms:
            score -= 20.0 * (min_mecha_transforms - transformed_mechas)
    if cfg.carry and cfg.min_active_carry_traits > 0:
        active_carry = active_carry_trait_count(state, trait_defs, cfg)
        shortfall = max(0, cfg.min_active_carry_traits - active_carry)
        if shortfall:
            score -= 10.0 * shortfall
    if cfg.carry_cost is not None and not has_required_cost_tank(state, cfg):
        if state_remaining_slots(state, cfg) <= 0:
            score -= 20.0
        else:
            score -= 6.0
    score += carry_search_heuristic(state, trait_defs, cfg)
    # carry bonus + special champion penalties
    score += carry_and_special_bonus(state, trait_defs, cfg)
    score -= off_profile_damage_penalty(state, cfg)
    score += structure_bonus(state, cfg)
    return score


def state_sort_key(result: dict, sort_by: str):
    if sort_by == 'cost':
        return (result['total_cost'], -result['score'], result['champion_names'])
    return (-result['score'], -result['total_cost'], result['champion_names'])


def result_unit_set_key(result: dict) -> Tuple[str, ...]:
    return tuple(sorted(result['champion_names']))


def finalize_candidate_limit(cfg: SearchConfig) -> int:
    if cfg.limit <= 0:
        return max(300, cfg.beam_width)
    if cfg.limit <= 10:
        return min(cfg.beam_width, max(40, cfg.limit * 4))
    if cfg.limit <= 50:
        return min(cfg.beam_width, max(120, cfg.limit * 3))
    if cfg.limit <= 100:
        return min(cfg.beam_width, max(220, cfg.limit * 3))
    return min(cfg.beam_width, max(300, cfg.limit * 2))


def is_broad_query(cfg: SearchConfig) -> bool:
    cost_filters = sum(1 for bounds in cfg.cost_unit_ranges.values() if bounds != (None, None))
    constraint_score = (
        len(cfg.include_units)
        + len(cfg.exclude_units)
        + len(cfg.exclude_costs)
        + len(cfg.required_trait_breakpoints)
        + cost_filters
        + (1 if cfg.trait_plus1 else 0)
        + (1 if cfg.carry else 0)
        + (1 if cfg.mecha_transform_range != (None, None) else 0)
    )
    return constraint_score <= 3


def adaptive_beam_schedule(cfg: SearchConfig) -> List[int]:
    return [cfg.beam_width]


def should_expand_search(cfg: SearchConfig, current_results: List[dict], pass_index: int, total_passes: int) -> bool:
    return False


def merge_search_results(result_sets: List[List[dict]], sort_by: str, limit: int) -> List[dict]:
    merged: List[dict] = []
    for batch in result_sets:
        merged.extend(batch)
    merged.sort(key=lambda r: state_sort_key(r, sort_by))
    deduped: List[dict] = []
    seen_unit_sets: Set[Tuple[str, ...]] = set()
    for result in merged:
        unit_set_key = result_unit_set_key(result)
        if unit_set_key in seen_unit_sets:
            continue
        seen_unit_sets.add(unit_set_key)
        deduped.append(result)
    return deduped if limit == 0 else deduped[:limit]


def final_valid(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> bool:
    _, _, _, unused_count, _, _ = evaluate_state_traits(state, trait_defs, cfg)
    if unused_count > cfg.max_unused_traits:
        return False
    eff_tank, eff_damage, _ = effective_role_counts(state, cfg)
    diff = frontline_shortfall(state, cfg)
    set_rules = get_set_rules(cfg.set_number)
    if eff_tank < cfg.min_tanks:
        return False
    if eff_damage < cfg.min_damage:
        return False
    if diff > cfg.max_role_diff:
        return False
    cost_counts = state_cost_counts(state)
    for cost, (min_target, max_target) in cfg.cost_unit_ranges.items():
        current = cost_counts.get(cost, 0)
        if min_target is not None and current < min_target:
            return False
        if max_target is not None and current > max_target:
            return False
    if not mecha_transform_range_satisfied(state, cfg):
        return False
    if not required_trait_breakpoints_met(state, cfg):
        return False
    if cfg.carry and cfg.min_active_carry_traits > 0:
        if active_carry_trait_count(state, trait_defs, cfg) < cfg.min_active_carry_traits:
            return False
    if not has_required_cost_tank(state, cfg):
        return False
    # Special champions must have at least one required trait active
    for unit in state.units:
        min_level = set_rules.special_champion_min_level.get(unit.name)
        if min_level is not None and cfg.level < min_level:
            return False
        required = set_rules.special_champion_synergies.get(unit.name)
        if required is None:
            continue
        has_synergy = False
        for tr in required:
            cnt = state.trait_counts.get(tr, 0)
            tdef = trait_defs.get(tr)
            if tdef and _trait_is_active(cnt, tdef):
                has_synergy = True
                break
        if not has_synergy:
            return False
    return True


def build_result(state: State, trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> dict:
    active, near, unused, unused_count, leftover_units, trait_score = evaluate_state_traits(state, trait_defs, cfg)
    # Keep near-breakpoint encouragement during beam search, but do not let unfinished
    # traits inflate the final displayed ranking.
    final_trait_score = trait_score - len(near) * NEAR_BREAKPOINT_BONUS
    eff_tank, eff_damage, effective_diff = effective_role_counts(state, cfg)
    diff = frontline_shortfall(state, cfg)
    raw_diff = raw_role_diff(state, cfg)
    frontline_score, backline_score = frontline_backline_scores(state, cfg)
    team_capacity, transformed_mechas, occupied_slots, effective_mecha = mecha_state_metrics(state, cfg)
    main_tank_started_at = time.perf_counter()
    main_tank = determine_main_tank(state, trait_defs, cfg)
    accumulate_debug_timing(cfg, "final_main_tank_ms", (time.perf_counter() - main_tank_started_at) * 1000.0)
    scoring_started_at = time.perf_counter()
    cs_bonus = carry_and_special_bonus(state, trait_defs, cfg)
    off_profile_penalty = off_profile_damage_penalty(state, cfg)
    structure_score = structure_bonus(state, cfg)
    cost_adjustment = total_cost_adjustment(state, cfg)
    active_trait_penalty = max(0, len(active) - cfg.level) * ACTIVE_TRAIT_OVERFLOW_PENALTY
    cost_counts = state_cost_counts(state)
    accumulate_debug_timing(cfg, "final_scoring_ms", (time.perf_counter() - scoring_started_at) * 1000.0)
    score = final_trait_score + cost_adjustment - diff * cfg.role_balance_weight + cs_bonus - off_profile_penalty + structure_score - active_trait_penalty
    return {
        'score': round(score, 2),
        'total_cost': state.total_cost,
        'cost_counts': cost_counts,
        'champion_names': [u.name for u in state.units],
        'units': [dataclasses.asdict(u) for u in state.units],
        'roles': {
            'tank': state.tank_count,
            'damage': state.damage_count,
            'flex': state.flex_count,
            'effective_tanks': round(eff_tank, 1),
            'effective_damage': round(eff_damage, 1),
            'effective_diff': round(effective_diff, 1),
            'diff': diff,
            'raw_diff': raw_diff,
            'frontline': round(frontline_score, 1),
            'backline': round(backline_score, 1),
        },
        'team_capacity': team_capacity,
        'occupied_slots': occupied_slots,
        'transformed_mechas': transformed_mechas,
        'effective_mecha_count': effective_mecha,
        'main_tank': main_tank.name if main_tank else None,
        'main_tank_display_name': main_tank.display_name if main_tank else None,
        'main_tank_trait_value': round(main_tank_trait_value(main_tank, state, trait_defs, cfg), 2) if main_tank else 0.0,
        'active_carry_trait_count': active_carry_trait_count(state, trait_defs, cfg) if cfg.carry else 0,
        'active_traits': active,
        'near_traits': near,
        'unused_traits': unused,
        'unused_trait_count': unused_count,
        'leftover_units': leftover_units,
        'trait_score': round(final_trait_score, 2),
        'active_trait_penalty': round(active_trait_penalty, 2),
        'cost_adjustment': round(cost_adjustment, 2),
        'off_profile_damage_penalty': round(off_profile_penalty, 2),
        'structure_bonus': round(structure_score, 2),
    }


def search(champions: List[Champion], trait_defs: Dict[str, TraitDef], cfg: SearchConfig) -> List[dict]:
    stage_started_at = time.perf_counter()
    timings: Dict[str, float] = {}

    def mark(stage_name: str, started_at: float) -> float:
        timings[stage_name] = round((time.perf_counter() - started_at) * 1000.0, 2)
        return time.perf_counter()

    champ_by_name = {normalize_text(c.name): c for c in champions}
    set_rules = get_set_rules(cfg.set_number)
    include_units = []
    used_ids = set()
    excluded_ids = set()

    for raw in cfg.exclude_units:
        key = normalize_text(raw)
        if key not in champ_by_name:
            raise RuntimeError(f"Unknown excluded unit: {raw}")
        excluded_ids.add(champ_by_name[key].id)

    for raw in cfg.include_units:
        key = normalize_text(raw)
        if key not in champ_by_name:
            raise RuntimeError(f"Unknown unit: {raw}")
        c = champ_by_name[key]
        if c.id in excluded_ids:
            raise RuntimeError(f"Unit {c.name} cannot be both included and excluded")
        if not is_level_allowed(c.name, cfg.level):
            min_level = set_rules.special_champion_min_level.get(c.name)
            raise RuntimeError(f"Unit {c.name} requires level {min_level}+")
        if c.cost in cfg.exclude_costs:
            raise RuntimeError(f"Included unit {c.name} is excluded by cost filter")
        base_key = normalize_text(c.base_name or c.name)
        if base_key in {normalize_text(u.base_name or u.name) for u in include_units}:
            raise RuntimeError(f"Unit {c.display_name} cannot be included twice in different variants")
        if c.id not in used_ids:
            include_units.append(c)
            used_ids.add(c.id)
    if len(include_units) > cfg.level:
        raise RuntimeError("More included units than level")
    include_cost_counts = {i: 0 for i in range(1, 6)}
    for c in include_units:
        include_cost_counts[c.cost] += 1
    for cost, (min_target, max_target) in cfg.cost_unit_ranges.items():
        current = include_cost_counts.get(cost, 0)
        if max_target is not None and current > max_target:
            raise RuntimeError(f"Included units already exceed max count for {cost}-cost units")
        max_possible = current + (cfg.level - len(include_units))
        if min_target is not None and max_possible < min_target:
            raise RuntimeError(f"Impossible range: need at least {min_target} {cost}-cost units at level {cfg.level}")
    stage_started_at = mark("constraint_setup_ms", stage_started_at)
    # Only search over optional units; included units are fixed in every state.
    pool = [
        c for c in champions
        if c.cost not in cfg.exclude_costs
        and c.id not in used_ids
        and c.id not in excluded_ids
        and is_level_allowed(c.name, cfg.level)
        and (c.name not in set_rules.opt_in_only_names)
    ]
    # For champions with identical trait profiles, prefer the pricier option.
    pool = prefer_expensive_equivalents(pool, locked_ids=used_ids)
    stage_started_at = mark("pool_prep_ms", stage_started_at)

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
    def make_state_from_units(unit_list: List[Champion]) -> State:
        tc: Dict[str, int] = {}
        tank_n = damage_n = flex_n = total = 0
        for unit in unit_list:
            total += unit.cost
            for tr in unit.traits:
                tc[tr] = tc.get(tr, 0) + 1
            if unit.role == 'tank':
                tank_n += 1
            elif unit.role == 'damage':
                damage_n += 1
            else:
                flex_n += 1
        return State(
            units=tuple(unit_list),
            next_idx=0,
            trait_counts=tc,
            total_cost=total,
            tank_count=tank_n,
            damage_count=damage_n,
            flex_count=flex_n,
            score_estimate=0.0,
        )

    seed_unit_lists: List[List[Champion]] = [list(include_units)]
    if cfg.carry_cost is not None:
        tank_seed_names = set(cfg.required_tank_names or cfg.required_four_cost_tank_names)
        tank_seed_units = [c for c in pool if c.name in tank_seed_names]
        carry_trait_names = effective_carry_trait_names(cfg)
        carry_trait_seed_names = carry_trait_names[:cfg.min_active_carry_traits] if cfg.min_active_carry_traits > 0 else []
        trait_seed_bundles: List[List[Tuple[Champion, ...]]] = []
        for idx, trait_name in enumerate(carry_trait_seed_names):
            options = [
                c for c in pool
                if trait_name in c.traits and normalize_text(c.name) != normalize_text(cfg.carry or "")
            ]
            options.sort(key=lambda c: (c.raw_cost, c.cost, c.name))
            if not options:
                continue
            capped = options[:5]
            bundles: List[Tuple[Champion, ...]] = [(unit,) for unit in capped]
            if idx == 0:
                primary_pair_source = options[:3]
                bundles.extend(itertools.combinations(primary_pair_source, 2))
            trait_seed_bundles.append(bundles)
        candidate_seed_lists: List[List[Champion]] = []
        base_has_tank = any(u.name in tank_seed_names for u in include_units)
        if tank_seed_units and not base_has_tank:
            if trait_seed_bundles:
                for tank_seed in tank_seed_units:
                    for combo in itertools.product(*trait_seed_bundles):
                        seed = list(include_units) + [tank_seed]
                        existing = {u.id for u in seed}
                        existing_base = {normalize_text(u.base_name or u.name) for u in seed}
                        for bundle in combo:
                            for unit in bundle:
                                unit_base = normalize_text(unit.base_name or unit.name)
                                if unit.id not in existing and unit_base not in existing_base:
                                    seed.append(unit)
                                    existing.add(unit.id)
                                    existing_base.add(unit_base)
                        candidate_seed_lists.append(seed)
            else:
                candidate_seed_lists.extend([list(include_units) + [tank_seed] for tank_seed in tank_seed_units])
        if candidate_seed_lists:
            seed_unit_lists = candidate_seed_lists[:120]
    stage_started_at = mark("seed_prep_ms", stage_started_at)

    states: List[State] = []
    seen_seed_keys: Set[Tuple[str, ...]] = set()
    for seed_units in seed_unit_lists:
        seed_state = make_state_from_units(seed_units)
        if state_occupied_slots(seed_state, cfg) > state_team_capacity(seed_state, cfg):
            continue
        slots_remaining_after_include = state_remaining_slots(seed_state, cfg)
        feasible = True
        for trait_name, required_bp in cfg.required_trait_breakpoints.items():
            current = effective_trait_count(seed_state, trait_name, cfg)
            if current >= required_bp:
                continue
            if current + slots_remaining_after_include < required_bp:
                feasible = False
                break
        if not feasible:
            continue
        seed_state.score_estimate = estimate_state_score(seed_state, trait_defs, cfg)
        seed_key = tuple(sorted(u.id for u in seed_state.units))
        if seed_key in seen_seed_keys:
            continue
        seen_seed_keys.add(seed_key)
        states.append(seed_state)

    if not states:
        cfg.debug_timings = timings | {"seed_build_ms": 0.0, "beam_search_ms": 0.0, "result_finalize_ms": 0.0}
        return []
    stage_started_at = mark("seed_build_ms", stage_started_at)

    max_steps = cfg.level + 1
    stable_top_estimate_rounds = 0
    previous_top_estimate: Optional[float] = None
    for _ in range(max_steps):
        next_states: List[State] = []
        for st in states:
            if state_remaining_slots(st, cfg) <= 0:
                next_states.append(st)
                continue
            existing_ids = {u.id for u in st.units}
            existing_base_names = {normalize_text(u.base_name or u.name) for u in st.units}
            for idx in range(st.next_idx, len(pool)):
                c = pool[idx]
                if c.id in existing_ids:
                    continue
                if normalize_text(c.base_name or c.name) in existing_base_names:
                    continue
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
                if state_occupied_slots(ns, cfg) > state_team_capacity(ns, cfg):
                    continue
                ns.score_estimate = estimate_state_score(ns, trait_defs, cfg)
                next_states.append(ns)
        states = sorted(next_states, key=lambda s: (-s.score_estimate, -s.total_cost))[:cfg.beam_width]
        if not states:
            break
        final_ready_states = [s for s in states if state_remaining_slots(s, cfg) <= 0]
        top_estimate = states[0].score_estimate if states else None
        if previous_top_estimate is not None and top_estimate is not None and abs(top_estimate - previous_top_estimate) < 0.01:
            stable_top_estimate_rounds += 1
        else:
            stable_top_estimate_rounds = 0
        previous_top_estimate = top_estimate
        enough_ready_states = cfg.limit > 0 and len(final_ready_states) >= max(cfg.limit * 3, 30)
        if enough_ready_states and stable_top_estimate_rounds >= 1:
            break
    stage_started_at = mark("beam_search_ms", stage_started_at)

    candidate_limit = finalize_candidate_limit(cfg)
    states = sorted(states, key=lambda s: (-s.score_estimate, -s.total_cost))[:candidate_limit]
    results = []
    for st in states:
        if final_valid(st, trait_defs, cfg):
            results.append(build_result(st, trait_defs, cfg))
    results.sort(key=lambda r: state_sort_key(r, cfg.sort_by))
    deduped_results = []
    seen_unit_sets: Set[Tuple[str, ...]] = set()
    for result in results:
        unit_set_key = result_unit_set_key(result)
        if unit_set_key in seen_unit_sets:
            continue
        seen_unit_sets.add(unit_set_key)
        deduped_results.append(result)
    results = deduped_results
    timings["result_finalize_ms"] = round((time.perf_counter() - stage_started_at) * 1000.0, 2)
    cfg.debug_timings = timings
    return results if cfg.limit == 0 else results[: cfg.limit]


def print_text_results(results: List[dict], meta: dict):
    print(f"Set: {meta['set_display_name']} ({meta['set_name']})")
    print(f"Champions: {meta['champion_count']} | Traits: {meta['trait_count']}")
    if meta.get('carry'):
        print(f"Carry: {meta['carry']} (traits: {', '.join(meta.get('carry_traits', []))})")
    if not results:
        print("No results matched the constraints.")
        return
    for i, r in enumerate(results, 1):
        print()
        print(f"#{i}  score={r['score']:.2f}  cost={r['total_cost']}")
        print("Units: " + ", ".join(r['champion_names']))
        print("Cost Buckets: " + ", ".join(f"{cost}g={count}" for cost, count in sorted(r['cost_counts'].items())))
        roles = r['roles']
        print(
            f"Roles: tank={roles['tank']}, damage={roles['damage']}, flex={roles['flex']} | "
            f"effective_tanks={roles['effective_tanks']}, effective_damage={roles['effective_damage']}, "
            f"diff={roles['diff']}, raw_diff={roles['raw_diff']}, effective_diff={roles['effective_diff']}, "
            f"frontline={roles['frontline']}, backline={roles['backline']}"
        )
        print("Active: " + ("; ".join(r['active_traits']) if r['active_traits'] else "none"))
        print("Near: " + ("; ".join(r['near_traits']) if r['near_traits'] else "none"))
        print("Unused: " + ("; ".join(r['unused_traits']) if r['unused_traits'] else "none"))


def parse_args() -> SearchConfig:
    p = argparse.ArgumentParser(description="Find TFT perfect-synergy comps using CommunityDragon JSON only.")
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--set-number', type=str, default='', help='Force a specific TFT set number, e.g. 17')
    p.add_argument('--level', type=int, required=True)
    p.add_argument('--carry', type=str, default='', help='Main carry champion (auto-included, gets synergy bonus)')
    p.add_argument('--include-units', type=str, default='')
    p.add_argument('--exclude-units', type=str, default='')
    p.add_argument('--exclude-costs', type=str, default='')
    p.add_argument('--cost-1-count', type=int)
    p.add_argument('--cost-2-count', type=int)
    p.add_argument('--cost-3-count', type=int)
    p.add_argument('--cost-4-count', type=int)
    p.add_argument('--cost-5-count', type=int)
    p.add_argument('--mecha-transform-min', type=int)
    p.add_argument('--mecha-transform-max', type=int)
    p.add_argument('--enable-anima-trait', action='store_true')
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
    exclude_units = [titleish(x) for x in args.exclude_units.split(',') if x.strip()]
    exclude_costs = [int(x) for x in args.exclude_costs.split(',') if x.strip()]
    cost_unit_ranges = {}
    for cost, count in {
        1: args.cost_1_count,
        2: args.cost_2_count,
        3: args.cost_3_count,
        4: args.cost_4_count,
        5: args.cost_5_count,
    }.items():
        lo, hi = normalize_cost_range(count, count, args.level)
        if lo is not None or hi is not None:
            cost_unit_ranges[cost] = (lo, hi)
    mecha_transform_range = normalize_cost_range(args.mecha_transform_min, args.mecha_transform_max, 3)
    return SearchConfig(
        level=args.level,
        set_number=args.set_number.strip(),
        include_units=include_units,
        exclude_units=exclude_units,
        exclude_costs=exclude_costs,
        cost_unit_ranges=cost_unit_ranges,
        mecha_transform_range=mecha_transform_range,
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
        carry=titleish(args.carry) if args.carry.strip() else None,
        enable_anima_trait=args.enable_anima_trait,
    ), args.refresh


def load_runtime_bundle(cfg: SearchConfig, refresh: bool = False) -> Tuple[dict, Dict[str, TraitDef], List[Champion]]:
    bundle_started_at = time.perf_counter()
    timings: Dict[str, float] = {}

    def mark(stage_name: str, started_at: float) -> float:
        timings[stage_name] = round((time.perf_counter() - started_at) * 1000.0, 2)
        return time.perf_counter()

    if cfg.set_number:
        set_num = cfg.set_number
        set_name = f"TFTSet{set_num}"
        set_display_name = f"TFT Set {set_num}"
    else:
        set_name, set_display_name, set_num = pick_current_set(fetch_json(SETS_URL, refresh))
        cfg.set_number = set_num
    current_started_at = mark("set_resolution_ms", bundle_started_at)

    traits = load_traits(refresh, set_num)
    current_started_at = mark("load_traits_ms", current_started_at)
    try:
        unit_profiles = load_unit_profiles(refresh, set_num)
    except Exception as err:
        eprint(f"WARNING: Failed to load unit profiles from tactics.tools: {err}")
        unit_profiles = {}
    current_started_at = mark("load_profiles_ms", current_started_at)
    champs = load_champions(refresh, set_num, traits, unit_profiles)
    current_started_at = mark("load_champions_ms", current_started_at)
    cfg.carry = resolve_special_unit_name(cfg.carry, champs)
    cfg.include_units = [titleish(resolve_special_unit_name(name, champs) or name) for name in cfg.include_units]
    cfg.exclude_units = [titleish(resolve_special_unit_name(name, champs) or name) for name in cfg.exclude_units]
    meta = {
        'set_name': set_name,
        'set_display_name': set_display_name,
        'set_number': set_num,
        'champion_count': len({c.base_name or c.name for c in champs}),
        'trait_count': len(traits),
        'unit_profile_count': len(unit_profiles),
        'sources': {
            'sets': SETS_URL if not cfg.set_number or set_num != "17" else str(SET17_SNAPSHOT_PATH),
            'champions': CHAMPS_TEAMPLANNER_URL if set_num != "17" else str(SET17_SNAPSHOT_PATH),
            'traits': TRAITS_URL if set_num != "17" else str(SET17_SNAPSHOT_PATH),
            'unit_profiles': TACTICS_TOOLS_SET_UPDATE_URL if set_num == "17" else TACTICS_TOOLS_UNITS_URL,
        }
    }
    if cfg.trait_plus1 and cfg.trait_plus1 not in traits:
        raise RuntimeError(f"Unknown trait: {cfg.trait_plus1}")
    for trait_name, required_bp in cfg.required_trait_breakpoints.items():
        tdef = traits.get(trait_name)
        if not tdef:
            raise RuntimeError(f"Unknown trait filter: {trait_name}")
        if required_bp not in tdef.breakpoints:
            joined = ", ".join(str(bp) for bp in tdef.breakpoints)
            raise RuntimeError(f"Invalid breakpoint for {trait_name}: {required_bp}. Valid breakpoints: {joined}")

    if cfg.carry:
        carry_key = normalize_text(cfg.carry)
        carry_champ = next((c for c in champs if c.id == carry_key), None)
        if not carry_champ:
            raise RuntimeError(f"Unknown carry: {cfg.carry}")
        cfg.carry_traits = list(carry_champ.traits)
        cfg.carry_cost = carry_champ.raw_cost
        cfg.carry_damage_profile = carry_champ.damage_profile
        cfg.carry_archetype = carry_champ.unit_archetype
        tank_cost = 4 if carry_champ.raw_cost >= 4 else carry_champ.raw_cost
        cfg.required_tank_cost = tank_cost
        cfg.required_tank_names = sorted({
            c.name for c in champs
            if c.raw_cost == tank_cost and c.role == 'tank'
        })
        cfg.required_four_cost_tank_names = list(cfg.required_tank_names)
        carry_trait_count = len(cfg.carry_traits)
        cfg.min_active_carry_traits = 1 if carry_trait_count >= 3 else min(2, len(effective_carry_trait_names(cfg)))
        if carry_key not in {normalize_text(u) for u in cfg.include_units}:
            cfg.include_units.insert(0, carry_champ.name)
        meta['carry'] = carry_champ.display_name
        meta['carry_query_name'] = carry_champ.name
        meta['carry_mode'] = carry_champ.special_mode
        meta['carry_cost'] = carry_champ.raw_cost
        meta['carry_traits'] = carry_champ.traits
        meta['carry_damage_profile'] = carry_champ.damage_profile
        meta['carry_archetype'] = carry_champ.unit_archetype
        meta['min_active_carry_traits'] = cfg.min_active_carry_traits
        meta['required_tank_cost'] = cfg.required_tank_cost
        meta['required_tanks'] = cfg.required_tank_names
        meta['required_four_cost_tanks'] = cfg.required_four_cost_tank_names if cfg.carry_cost and cfg.carry_cost >= 4 else []
    timings["carry_setup_ms"] = round((time.perf_counter() - current_started_at) * 1000.0, 2)
    timings["runtime_bundle_total_ms"] = round((time.perf_counter() - bundle_started_at) * 1000.0, 2)
    meta["timings"] = timings

    return meta, traits, champs


def run_search_with_config(cfg: SearchConfig, refresh: bool = False) -> dict:
    started_at = time.perf_counter()
    meta, traits, champs = load_runtime_bundle(cfg, refresh=refresh)
    beam_schedule = adaptive_beam_schedule(cfg)
    pass_results: List[List[dict]] = []
    pass_timings: List[Dict[str, float]] = []
    pass_cumulative_timings: List[Dict[str, float]] = []
    merged_results: List[dict] = []
    executed_beams: List[int] = []
    for pass_index, beam_width in enumerate(beam_schedule):
        pass_cfg = dataclasses.replace(
            cfg,
            beam_width=beam_width,
            debug_timings={},
            debug_cumulative_timings={},
        )
        results_for_pass = search(champs, traits, pass_cfg)
        executed_beams.append(beam_width)
        pass_results.append(results_for_pass)
        pass_timings.append(dict(getattr(pass_cfg, "debug_timings", {}) or {}))
        pass_cumulative_timings.append(dict(getattr(pass_cfg, "debug_cumulative_timings", {}) or {}))
        merged_results = merge_search_results(pass_results, cfg.sort_by, cfg.limit)
        if not should_expand_search(cfg, merged_results, pass_index, len(beam_schedule)):
            break
    results = merged_results
    timings = dict(meta.get("timings", {}))
    combined_search_timings: Dict[str, float] = {}
    for timing_map in pass_timings:
        for key, value in timing_map.items():
            combined_search_timings[key] = round(combined_search_timings.get(key, 0.0) + value, 2)
    timings.update(combined_search_timings)
    timings["concept_team_rules_ms"] = round(
        timings.get("carry_setup_ms", 0.0)
        + timings.get("constraint_setup_ms", 0.0)
        + timings.get("seed_prep_ms", 0.0),
        2,
    )
    timings["concept_tank_join_ms"] = round(timings.get("seed_build_ms", 0.0), 2)
    timings["concept_main_tank_ms"] = round(sum(item.get("final_main_tank_ms", 0.0) for item in pass_cumulative_timings), 2)
    timings["concept_scoring_ms"] = round(sum(item.get("final_scoring_ms", 0.0) for item in pass_cumulative_timings), 2)
    timings["concept_form_output_ms"] = round(timings.get("result_finalize_ms", 0.0), 2)
    timings["adaptive_pass_count"] = float(len(executed_beams))
    timings["engine_total_ms"] = round((time.perf_counter() - started_at) * 1000.0, 2)
    meta["beam_schedule"] = executed_beams
    meta["timings"] = timings
    return {
        'meta': meta,
        'traits': traits,
        'champions': champs,
        'results': results,
    }


def main() -> int:
    cfg, refresh = parse_args()
    try:
        bundle = run_search_with_config(cfg, refresh=refresh)
        meta = bundle['meta']
        traits = bundle['traits']
        champs = bundle['champions']
        results = bundle['results']

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
