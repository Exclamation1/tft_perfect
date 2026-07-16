export type TimingMap = Record<string, number>;

export type ApiMeta = {
  set_name: string;
  set_display_name: string;
  set_number: string;
  champion_count: number;
  trait_count: number;
  carry?: string;
  carry_query_name?: string;
  carry_mode?: string | null;
  carry_traits?: string[];
  required_tank_cost?: number;
  timings?: TimingMap;
};

export type Unit = {
  id: string;
  api_name: string;
  name: string;
  display_name?: string;
  base_name?: string | null;
  special_mode?: string | null;
  cost: number;
  traits: string[];
  role: string;
  unit_archetype?: string | null;
  damage_profile?: string | null;
  attack_range?: number | null;
  avatar_local_url?: string | null;
  avatar_remote_url?: string | null;
};

export type Trait = {
  id: string;
  name: string;
  breakpoints: number[];
  description?: string;
  icon_slug?: string;
  icon_local_url?: string | null;
  icon_remote_url?: string | null;
};

export type DisplayTrait = {
  label: string;
  name: string;
  icon_slug?: string;
  icon_local_url?: string | null;
  icon_remote_url?: string | null;
};

export type SearchResult = {
  score: number;
  total_cost: number;
  champion_names: string[];
  units: Unit[];
  active_traits: string[];
  near_traits: string[];
  unused_traits: string[];
  display_traits?: DisplayTrait[];
  cost_counts: Record<string, number>;
  roles: {
    tank: number;
    damage: number;
    flex: number;
    effective_tanks: number;
    effective_damage: number;
    effective_diff: number;
    diff: number;
    raw_diff: number;
    frontline: number;
    backline: number;
  };
};

export type SearchResponse = {
  meta: ApiMeta;
  results: SearchResult[];
};

export type BootstrapResponse = {
  meta: ApiMeta;
  units: Unit[];
  traits: Trait[];
};

export type AuthStatus = {
  authenticated: boolean;
  username?: string | null;
};
