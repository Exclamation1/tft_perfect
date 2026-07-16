import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { fetchBootstrap, getAuthStatus, login, logout, resolveImageUrl, runSearch } from "./api";
import type { ApiMeta, AuthStatus, SearchResult, TimingMap, Trait, Unit } from "./types";

type SortMode = "score" | "cost";
type PickerMode = "carry" | "include" | "exclude";
type CostRange = { min: number; max: number };
type TraitFilter = { name: string; breakpoint: number };

const costAccent: Record<number, string> = {
  1: "var(--cost-1)",
  2: "var(--cost-2)",
  3: "var(--cost-3)",
  4: "var(--cost-4)",
  5: "var(--cost-5)",
};

const DEFAULT_SEARCH_PAYLOAD = {
  set_number: "17",
  level: 8,
  max_unused_traits: 3,
  sort_by: "score" as SortMode,
  limit: 12,
};

const SPECIAL_LOCKED_UNITS = ["Zed", "Rhaast"];
const TIMING_LABELS: Record<string, string> = {
  runtime_bundle_total_ms: "Chuẩn bị dữ liệu",
  concept_team_rules_ms: "Tìm team kích tộc hệ",
  concept_tank_join_ms: "Ghép tank theo giá carry",
  concept_main_tank_ms: "Xác định tank chính",
  concept_scoring_ms: "Tính điểm với điều kiện",
  concept_form_output_ms: "Ra form bài",
  search_response_total_ms: "Tổng backend",
  frontend_request_total_ms: "Tổng trình duyệt",
};
const TIMING_ORDER = [
  "runtime_bundle_total_ms",
  "concept_team_rules_ms",
  "concept_tank_join_ms",
  "concept_main_tank_ms",
  "concept_scoring_ms",
  "concept_form_output_ms",
  "search_response_total_ms",
  "frontend_request_total_ms",
];

function unitTitle(unit?: Unit | null): string {
  if (!unit) {
    return "";
  }
  return unit.display_name || unit.base_name || unit.name;
}

function createDefaultCostRanges(level: number): Record<number, CostRange> {
  return {
    1: { min: 0, max: Math.min(2, level) },
    2: { min: 0, max: Math.min(2, level) },
    3: { min: 0, max: level },
    4: { min: Math.min(2, level), max: level },
    5: { min: 0, max: level },
  };
}

function App() {
  const pageSize = 12;
  const [authChecked, setAuthChecked] = useState(false);
  const [auth, setAuth] = useState<AuthStatus>({ authenticated: false, username: null });
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [traits, setTraits] = useState<Trait[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestTimingMs, setRequestTimingMs] = useState<number | null>(null);

  const [level, setLevel] = useState(8);
  const [carry, setCarry] = useState("");
  const [sortBy, setSortBy] = useState<SortMode>("score");
  const [limit, setLimit] = useState(12);
  const [maxUnusedTraits, setMaxUnusedTraits] = useState(3);
  const [traitPlus1, setTraitPlus1] = useState("");
  const [enableAnimaTrait, setEnableAnimaTrait] = useState(false);
  const [traitFilterDraft, setTraitFilterDraft] = useState("");
  const [traitFilters, setTraitFilters] = useState<TraitFilter[]>([]);
  const [mechaTransformRange, setMechaTransformRange] = useState<CostRange>({ min: 0, max: 0 });
  const [excludeCosts, setExcludeCosts] = useState<number[]>([]);
  const [costRanges, setCostRanges] = useState<Record<number, CostRange>>(() => createDefaultCostRanges(8));
  const [includeUnits, setIncludeUnits] = useState<string[]>([]);
  const [excludeUnits, setExcludeUnits] = useState<string[]>([]);
  const [pickerMode, setPickerMode] = useState<PickerMode | null>(null);
  const [pickerQuery, setPickerQuery] = useState("");
  const [page, setPage] = useState(1);
  const isLoginRoute = window.location.pathname === "/login";

  const sortedUnits = useMemo(
    () => [...units].sort((a, b) => a.cost - b.cost || a.name.localeCompare(b.name)),
    [units],
  );

  const filteredPickerUnits = useMemo(() => {
    const query = pickerQuery.trim().toLowerCase();
    return sortedUnits.filter((unit) => {
      if (!query) {
        return true;
      }
      return (
        unit.name.toLowerCase().includes(query) ||
        unitTitle(unit).toLowerCase().includes(query) ||
        (unit.special_mode || "").toLowerCase().includes(query) ||
        unit.traits.some((trait) => trait.toLowerCase().includes(query))
      );
    });
  }, [pickerQuery, sortedUnits]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(results.length / pageSize)),
    [results.length, pageSize],
  );

  const pagedResults = useMemo(() => {
    const start = (page - 1) * pageSize;
    return results.slice(start, start + pageSize);
  }, [page, pageSize, results]);

  const traitOptions = useMemo(
    () => [...traits].sort((a, b) => a.name.localeCompare(b.name)),
    [traits],
  );
  const traitBreakpointOptions = useMemo(
    () =>
      [...traits]
        .sort((a, b) => a.name.localeCompare(b.name))
        .flatMap((trait) =>
          [...trait.breakpoints]
            .sort((a, b) => a - b)
            .map((breakpoint) => ({
              key: `${trait.name}::${breakpoint}`,
              name: trait.name,
              breakpoint,
              label: `${trait.name} ${breakpoint}`,
            })),
        ),
    [traits],
  );
  const visibleTimings = useMemo(() => {
    const timingMap: TimingMap = {
      ...(meta?.timings ?? {}),
      ...(requestTimingMs != null ? { frontend_request_total_ms: requestTimingMs } : {}),
    };
    return TIMING_ORDER
      .filter((key) => typeof timingMap[key] === "number")
      .map((key) => ({
        key,
        label:
          key === "concept_tank_join_ms" && meta?.required_tank_cost
            ? `Ghép tank ${meta.required_tank_cost} vàng`
            : (TIMING_LABELS[key] ?? key),
        value: Number(timingMap[key]),
      }));
  }, [meta?.timings, requestTimingMs]);

  useEffect(() => {
    async function checkAuth() {
      try {
        setAuth(await getAuthStatus());
      } catch {
        setAuth({ authenticated: false, username: null });
      } finally {
        setAuthChecked(true);
      }
    }
    void checkAuth();
  }, []);

  useEffect(() => {
    if (!authChecked || !auth.authenticated) {
      setLoading(false);
      return;
    }
    async function bootstrap() {
      try {
        setLoading(true);
        const bootstrapData = await fetchBootstrap("17");
        setMeta(bootstrapData.meta);
        setUnits(bootstrapData.units);
        setTraits(bootstrapData.traits);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load initial data.");
      } finally {
        setLoading(false);
      }
    }

    void bootstrap();
  }, [auth.authenticated, authChecked]);

  useEffect(() => {
    if (auth.authenticated && !loading && units.length > 0) {
      void handleSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.authenticated, loading, units.length]);

  useEffect(() => {
    setCostRanges((prev) => {
      const next = { ...prev };
      for (const cost of [1, 2, 3, 4, 5]) {
        const current = prev[cost] ?? { min: 0, max: level };
        const maxValue = Math.min(current.max, level);
        const minValue = Math.min(current.min, maxValue);
        next[cost] = { min: minValue, max: maxValue };
      }
      return next;
    });
  }, [level]);

  async function handleSearch() {
    if (!auth.authenticated) {
      return;
    }
    try {
      setSearching(true);
      setError(null);
      const requestStartedAt = performance.now();
      const response = await runSearch({
        ...DEFAULT_SEARCH_PAYLOAD,
        level,
        carry: carry || undefined,
        include_units: includeUnits,
        exclude_units: excludeUnits,
        exclude_costs: excludeCosts,
        max_unused_traits: maxUnusedTraits,
        trait_plus1: traitPlus1 || undefined,
        enable_anima_trait: enableAnimaTrait,
        trait_filters: traitFilters,
        mecha_transform_min: mechaTransformRange.min > 0 ? mechaTransformRange.min : undefined,
        mecha_transform_max: mechaTransformRange.max < 3 ? mechaTransformRange.max : undefined,
        cost_1_min: costRanges[1].min > 0 ? costRanges[1].min : undefined,
        cost_1_max: costRanges[1].max < level ? costRanges[1].max : undefined,
        cost_2_min: costRanges[2].min > 0 ? costRanges[2].min : undefined,
        cost_2_max: costRanges[2].max < level ? costRanges[2].max : undefined,
        cost_3_min: costRanges[3].min > 0 ? costRanges[3].min : undefined,
        cost_3_max: costRanges[3].max < level ? costRanges[3].max : undefined,
        cost_4_min: costRanges[4].min > 0 ? costRanges[4].min : undefined,
        cost_4_max: costRanges[4].max < level ? costRanges[4].max : undefined,
        cost_5_min: costRanges[5].min > 0 ? costRanges[5].min : undefined,
        cost_5_max: costRanges[5].max < level ? costRanges[5].max : undefined,
        sort_by: sortBy,
        limit,
      });
      setMeta(response.meta);
      setResults(response.results);
      setRequestTimingMs(Number((performance.now() - requestStartedAt).toFixed(2)));
      setPage(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  function chooseUnit(unit: Unit) {
    if (pickerMode === "carry") {
      setCarry(unit.name);
    } else if (pickerMode === "include") {
      setIncludeUnits((prev) => (prev.includes(unit.name) ? prev : [...prev, unit.name]));
      setExcludeUnits((prev) => prev.filter((name) => name !== unit.name));
    } else if (pickerMode === "exclude") {
      setExcludeUnits((prev) => (prev.includes(unit.name) ? prev : [...prev, unit.name]));
      setIncludeUnits((prev) => prev.filter((name) => name !== unit.name));
    }
  }

  function removeUnit(target: "include" | "exclude", unitName: string) {
    if (target === "include") {
      setIncludeUnits((prev) => prev.filter((name) => name !== unitName));
    } else {
      setExcludeUnits((prev) => prev.filter((name) => name !== unitName));
    }
  }

  function toggleCost(cost: number) {
    setExcludeCosts((prev) =>
      prev.includes(cost) ? prev.filter((value) => value !== cost) : [...prev, cost].sort(),
    );
  }

  function resetFilters() {
    setLevel(8);
    setCarry("");
    setSortBy("score");
    setLimit(12);
    setMaxUnusedTraits(3);
    setTraitPlus1("");
    setEnableAnimaTrait(false);
    setTraitFilterDraft("");
    setTraitFilters([]);
    setMechaTransformRange({ min: 0, max: 0 });
    setExcludeCosts([]);
    setCostRanges(createDefaultCostRanges(8));
    setIncludeUnits([]);
    setExcludeUnits([]);
    setPickerMode(null);
    setPickerQuery("");
    setPage(1);
  }

  const carryUnit = units.find((unit) => unit.name === carry);

  async function handleLoginSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setLoginError(null);
      const status = await login(loginUsername, loginPassword);
      setAuth(status);
      window.history.replaceState({}, "", "/");
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed.");
    }
  }

  async function handleLogoutClick() {
    await logout();
    setAuth({ authenticated: false, username: null });
    window.history.replaceState({}, "", "/login");
  }

  function addTraitFilter() {
    if (!traitFilterDraft) {
      return;
    }
    const [name, breakpointText] = traitFilterDraft.split("::");
    const breakpoint = Number(breakpointText);
    if (!name || !Number.isFinite(breakpoint)) {
      return;
    }
    setTraitFilters((prev) => {
      const next = prev.filter((item) => item.name !== name);
      return [...next, { name, breakpoint }].sort(
        (a, b) => a.name.localeCompare(b.name) || a.breakpoint - b.breakpoint,
      );
    });
    setTraitFilterDraft("");
  }

  function removeTraitFilter(name: string) {
    setTraitFilters((prev) => prev.filter((item) => item.name !== name));
  }

  if (!authChecked) {
    return (
      <div className="app-shell auth-shell">
        <div className="auth-card">Checking access...</div>
      </div>
    );
  }

  if (!auth.authenticated || isLoginRoute) {
    return (
      <div className="app-shell auth-shell">
        <div className="ambient ambient-left" />
        <div className="ambient ambient-right" />
        <div className="auth-card">
          <span className="eyebrow">Private Access</span>
          <h1>TFT Perfect Admin</h1>
          <p>Đăng nhập để vào website và toàn bộ API.</p>
          <form className="auth-form" onSubmit={handleLoginSubmit}>
            <Field label="Username">
              <input value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} autoComplete="username" />
            </Field>
            <Field label="Password">
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                autoComplete="current-password"
              />
            </Field>
            {loginError ? <div className="error-banner">{loginError}</div> : null}
            <button className="search-button auth-submit" type="submit">
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="hero">
        <div className="hero-copy">
          <span className="eyebrow">TFT Set 17 Composition Studio</span>
          <h1>Build stronger boards, not just prettier traits.</h1>
          <p>
            Search for powerful, flexible comps around a carry with live-enough Set 17 data,
            local assets, and score-aware board structure.
          </p>
          <div className="hero-stats">
            <Stat label="Set" value={meta?.set_display_name ?? "Loading"} />
            <Stat label="Units" value={String(meta?.champion_count ?? 0)} />
            <Stat label="Traits" value={String(meta?.trait_count ?? 0)} />
            <Stat label="Results" value={String(results.length)} />
          </div>
        </div>

        <div className="hero-feature">
          <div className="feature-card">
            <div className="feature-topline">Primary Carry</div>
            <div className="feature-main">
              {carryUnit ? (
                <>
                  <img
                    className="feature-avatar"
                    src={resolveImageUrl(carryUnit.avatar_local_url || carryUnit.avatar_remote_url)}
                    alt={carryUnit.name}
                    loading="eager"
                    decoding="async"
                  />
                  <div>
                    <h2>
                      {unitTitle(carryUnit)}
                      {carryUnit.special_mode ? <span className="mode-pill">{carryUnit.special_mode}</span> : null}
                    </h2>
                    <p>
                      {carryUnit.unit_archetype} • Range {carryUnit.attack_range ?? "-"}
                    </p>
                    <div className="pill-row">
                      {carryUnit.traits.map((trait) => (
                        <span key={trait} className="soft-pill">
                          {trait}
                        </span>
                      ))}
                      <button className="ghost-button auth-logout" type="button" onClick={handleLogoutClick}>
                        Logout
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="empty-carry">Choose a carry to start building.</div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="workspace">
        <aside className="control-panel">
          <section className="panel-card">
            <div className="panel-header">
              <h3>Search Controls</h3>
              <button className="ghost-button" onClick={resetFilters}>
                Reset
              </button>
            </div>

            <div className="field-grid two-col">
              <Field label="Level">
                <select value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                  {[5, 6, 7, 8, 9, 10].map((value) => (
                    <option key={value} value={value}>
                      Level {value}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Sorting">
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortMode)}>
                  <option value="score">Best Score</option>
                  <option value="cost">Lowest Cost</option>
                </select>
              </Field>
            </div>

            <Field label="Carry">
              <button
                className={`picker-trigger ${pickerMode === "carry" ? "active" : ""}`}
                type="button"
                onClick={() => {
                  setPickerMode((prev) => (prev === "carry" ? null : "carry"));
                  setPickerQuery("");
                }}
              >
                {carryUnit ? (
                  <div className="picker-trigger-content">
                    <img
                      src={resolveImageUrl(carryUnit.avatar_local_url || carryUnit.avatar_remote_url)}
                      alt={unitTitle(carryUnit)}
                    />
                    <div>
                      <strong>{unitTitle(carryUnit)}</strong>
                      <span>
                        {carryUnit.unit_archetype}
                        {carryUnit.special_mode ? ` • ${carryUnit.special_mode}` : ""}
                      </span>
                    </div>
                  </div>
                ) : (
                  <span>Optional carry</span>
                )}
              </button>
              {carryUnit ? (
                <button className="ghost-button carry-clear" type="button" onClick={() => setCarry("")}>
                  Clear carry
                </button>
              ) : null}
              {pickerMode === "carry" ? (
                <UnitPicker
                  mode="carry"
                  units={filteredPickerUnits}
                  selectedCarry={carry}
                  includeUnits={includeUnits}
                  excludeUnits={excludeUnits}
                  query={pickerQuery}
                  onQueryChange={setPickerQuery}
                  onChoose={(unit) => {
                    chooseUnit(unit);
                    setPickerMode(null);
                  }}
                  onClose={() => setPickerMode(null)}
                />
              ) : null}
              <div className="special-lock-note">
                <strong>Special locks:</strong> Zed and Rhaast stay out of the default pool.
                Add them manually or choose them as carry if you want them in comps.
              </div>
              <AvatarTagList items={SPECIAL_LOCKED_UNITS} units={units} onRemove={() => undefined} readonly />
            </Field>

            <Field label="Trait +1">
              <select
                className="trait-plus-select"
                value={traitPlus1}
                onChange={(e) => setTraitPlus1(e.target.value)}
              >
                <option value="">No +1 trait</option>
                {traitOptions.map((trait) => (
                  <option key={trait.name} value={trait.name}>
                    {trait.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Anima">
              <button
                className={`tier-toggle ${enableAnimaTrait ? "active" : ""}`}
                type="button"
                onClick={() => setEnableAnimaTrait((prev) => !prev)}
              >
                {enableAnimaTrait ? "Anima ON" : "Anima OFF"}
              </button>
            </Field>

            <Field label="Trait Targets">
              <div className="trait-filter-editor">
                <select value={traitFilterDraft} onChange={(e) => setTraitFilterDraft(e.target.value)}>
                  <option value="">Add required trait breakpoint</option>
                  {traitBreakpointOptions.map((option) => (
                    <option key={option.key} value={option.key}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <button className="solid-button" type="button" onClick={addTraitFilter} disabled={!traitFilterDraft}>
                  Add
                </button>
              </div>
              <div className="trait-filter-hint">
                Require a real active breakpoint from Set 17, like <code>N.O.V.A. 2</code> or <code>N.O.V.A. 5</code>.
              </div>
              {traitFilters.length ? (
                <div className="avatar-tag-list">
                  {traitFilters.map((item) => (
                    <button
                      key={item.name}
                      className="avatar-tag-chip trait-target-chip"
                      onClick={() => removeTraitFilter(item.name)}
                      type="button"
                    >
                      <span>{item.name} {item.breakpoint}</span>
                      <strong>×</strong>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="tag-list-empty">No trait requirements</div>
              )}
            </Field>

            <Field label="Mecha Transforms">
              <CostRangeSlider
                label="Allowed transforms"
                value={mechaTransformRange}
                max={3}
                onChange={setMechaTransformRange}
              />
              <div className="trait-filter-hint">
                Control how many Mecha units are allowed to transform. Use <code>0-0</code> if you only want to splash Mecha without paying extra slots.
              </div>
            </Field>

            <div className="field-grid two-col">
              <Field label="Limit">
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={limit}
                  onChange={(e) =>
                    setLimit(Math.min(1000, Math.max(1, Number(e.target.value) || 1)))
                  }
                />
              </Field>

              <Field label="Max Unused Traits">
                <input
                  type="number"
                  min={0}
                  max={3}
                  value={maxUnusedTraits}
                  onChange={(e) => setMaxUnusedTraits(Math.min(3, Math.max(0, Number(e.target.value) || 0)))}
                />
              </Field>
            </div>

            <Field label="Exclude Cost Tiers">
              <div className="toggle-row">
                {[1, 2, 3, 4, 5].map((cost) => (
                  <button
                    key={cost}
                    className={`tier-toggle ${excludeCosts.includes(cost) ? "active" : ""}`}
                    onClick={() => toggleCost(cost)}
                    type="button"
                  >
                    {cost}g
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Exact Cost Counts">
              <div className="cost-slider-stack">
                <div className="field-grid two-col cost-slider-grid">
                  <CostRangeSlider
                    label="1g Units"
                    value={costRanges[1]}
                    max={level}
                    onChange={(value) => setCostRanges((prev) => ({ ...prev, 1: value }))}
                  />
                  <CostRangeSlider
                    label="2g Units"
                    value={costRanges[2]}
                    max={level}
                    onChange={(value) => setCostRanges((prev) => ({ ...prev, 2: value }))}
                  />
                </div>
                <div className="field-grid three-col cost-slider-grid">
                  <CostRangeSlider
                    label="3g Units"
                    value={costRanges[3]}
                    max={level}
                    onChange={(value) => setCostRanges((prev) => ({ ...prev, 3: value }))}
                  />
                  <CostRangeSlider
                    label="4g Units"
                    value={costRanges[4]}
                    max={level}
                    onChange={(value) => setCostRanges((prev) => ({ ...prev, 4: value }))}
                  />
                  <CostRangeSlider
                    label="5g Units"
                    value={costRanges[5]}
                    max={level}
                    onChange={(value) => setCostRanges((prev) => ({ ...prev, 5: value }))}
                  />
                </div>
              </div>
            </Field>
          </section>

          <section className="panel-card">
            <div className="panel-header">
              <h3>Unit Locks</h3>
              <span className="panel-caption">Guide the board instead of brute forcing everything.</span>
            </div>

            <div className="special-lock-banner">
              <strong>Zed + Rhaast are locked by default.</strong>
              <span>Use Include Units or set one as carry to let search consider them.</span>
            </div>

            <Field label="Include Units">
              <button
                className={`picker-trigger slim ${pickerMode === "include" ? "active" : ""}`}
                type="button"
                onClick={() => {
                  setPickerMode((prev) => (prev === "include" ? null : "include"));
                  setPickerQuery("");
                }}
              >
                Add units with avatars
              </button>
              <AvatarTagList items={includeUnits} units={units} onRemove={(name) => removeUnit("include", name)} />
            </Field>

            <Field label="Exclude Units">
              <button
                className={`picker-trigger slim danger ${pickerMode === "exclude" ? "active" : ""}`}
                type="button"
                onClick={() => {
                  setPickerMode((prev) => (prev === "exclude" ? null : "exclude"));
                  setPickerQuery("");
                }}
              >
                Ban units with avatars
              </button>
              <AvatarTagList items={excludeUnits} units={units} onRemove={(name) => removeUnit("exclude", name)} />
            </Field>

            {pickerMode === "include" || pickerMode === "exclude" ? (
              <UnitPicker
                mode={pickerMode}
                units={filteredPickerUnits}
                selectedCarry={carry}
                includeUnits={includeUnits}
                excludeUnits={excludeUnits}
                query={pickerQuery}
                onQueryChange={setPickerQuery}
                onChoose={(unit) => {
                  chooseUnit(unit);
                }}
                onClose={() => setPickerMode(null)}
              />
            ) : null}
          </section>

          <section className="panel-card">
            <div className="panel-header">
              <h3>Set 17 Trait Atlas</h3>
              <span className="panel-caption">Useful for understanding comp shape while tuning filters.</span>
            </div>
            <div className="trait-cloud">
              {traits.slice(0, 18).map((trait) => (
                <div key={trait.name} className="trait-pill">
                  <img
                    src={resolveImageUrl(trait.icon_local_url || trait.icon_remote_url)}
                    alt={trait.name}
                  />
                  <span>{trait.name}</span>
                </div>
              ))}
            </div>
          </section>
        </aside>

        <section className="results-panel">
          <div className="results-toolbar">
            <div>
              <span className="eyebrow">Result Feed</span>
              <h2>{searching ? "Searching comps..." : `${results.length} compositions ready`}</h2>
            </div>
            <button className="search-button" onClick={() => void handleSearch()} disabled={searching}>
              {searching ? "Running Search..." : "Find Best Boards"}
            </button>
          </div>

          {visibleTimings.length ? (
            <div className="timing-panel">
              <div className="timing-panel-header">
                <span className="eyebrow">Search Timings</span>
                <strong>
                  {(
                    visibleTimings.find((item) => item.key === "frontend_request_total_ms")?.value
                    ?? visibleTimings.find((item) => item.key === "search_response_total_ms")?.value
                    ?? 0
                  ).toFixed(2)} ms
                </strong>
              </div>
              <div className="timing-grid">
                {visibleTimings.map((item) => (
                  <div key={item.key} className="timing-chip">
                    <span>{item.label}</span>
                    <strong>{item.value.toFixed(2)} ms</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {error ? <div className="error-banner">{error}</div> : null}

          {loading ? (
            <div className="skeleton-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="comp-card skeleton-card" />
              ))}
            </div>
          ) : (
            <div className="results-grid">
              {pagedResults.map((result, index) => (
                <CompCard
                  key={`${result.champion_names.join("-")}-${(page - 1) * pageSize + index}`}
                  index={(page - 1) * pageSize + index}
                  result={result}
                />
              ))}
            </div>
          )}

          {!loading && results.length > pageSize ? (
            <div className="pagination">
              <button
                className="page-button"
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <div className="page-summary">
                Page {page} / {totalPages}
              </div>
              <button
                className="page-button"
                type="button"
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                disabled={page === totalPages}
              >
                Next
              </button>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

function UnitPicker(props: {
  mode: PickerMode;
  units: Unit[];
  selectedCarry: string;
  includeUnits: string[];
  excludeUnits: string[];
  query: string;
  onQueryChange: (value: string) => void;
  onChoose: (unit: Unit) => void;
  onClose: () => void;
}) {
  const { mode, units, selectedCarry, includeUnits, excludeUnits, query, onQueryChange, onChoose, onClose } = props;

  return (
    <div className="unit-picker">
      <div className="unit-picker-top">
        <strong>{mode === "carry" ? "Choose carry" : mode === "include" ? "Add required units" : "Ban units"}</strong>
        <button className="ghost-button" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Search by unit or trait"
      />
      <div className="unit-picker-grid">
        {units.map((unit) => {
          const active =
            (mode === "carry" && selectedCarry === unit.name) ||
            (mode === "include" && includeUnits.includes(unit.name)) ||
            (mode === "exclude" && excludeUnits.includes(unit.name));
          return (
            <button
              key={unit.id}
              type="button"
              className={`unit-select-card ${active ? "active" : ""}`}
              onClick={() => onChoose(unit)}
            >
              <img
                src={resolveImageUrl(unit.avatar_local_url || unit.avatar_remote_url)}
                alt={unitTitle(unit)}
                className="unit-select-avatar"
                loading="lazy"
                decoding="async"
              />
              <div className="unit-select-body">
                <div className="unit-select-head">
                  <div className="unit-name-stack">
                    <strong>{unitTitle(unit)}</strong>
                    {unit.special_mode ? <span className="mode-pill compact">{unit.special_mode}</span> : null}
                  </div>
                  <span className="unit-select-cost" style={{ color: costAccent[unit.cost] }}>
                    {unit.cost}g
                  </span>
                </div>
                <span className="unit-select-role">{unit.unit_archetype}</span>
                <div className="unit-select-traits">
                  {unit.traits.map((trait) => (
                    <span key={trait}>{trait}</span>
                  ))}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CompCard({ index, result }: { index: number; result: SearchResult }) {
  return (
    <article className="comp-card">
      <div className="comp-top">
        <div>
          <span className="comp-rank">#{index + 1}</span>
          <h3>{result.champion_names.length} units</h3>
        </div>
        <div className="comp-chips">
          <div className="score-chip score-chip-primary">{result.score.toFixed(2)} score</div>
          <div className="score-chip">{result.total_cost} total cost</div>
        </div>
      </div>

      <div className="trait-strip">
        {(result.display_traits || []).map((trait) => (
          <div key={trait.label} className="trait-badge">
            <img src={resolveImageUrl(trait.icon_local_url || trait.icon_remote_url)} alt={trait.name} />
            <span>{trait.label}</span>
          </div>
        ))}
      </div>

      <div className="unit-row">
        {result.units.map((unit) => (
          <div key={unit.id} className="unit-card" style={{ "--unit-accent": costAccent[unit.cost] } as CSSProperties}>
            <img
              src={resolveImageUrl(unit.avatar_local_url || unit.avatar_remote_url)}
              alt={unitTitle(unit)}
              className="unit-avatar"
              loading="lazy"
              decoding="async"
            />
            <div className="unit-overlay">
              <span className="unit-cost">{unit.cost}</span>
            </div>
            <div className="unit-meta">
              <strong>{unitTitle(unit)}</strong>
              {unit.special_mode ? <span className="mode-pill compact">{unit.special_mode}</span> : null}
              <span>{unit.unit_archetype}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="comp-bottom">
        <div className="comp-copy">
          <div>
            <span className="detail-label">Near</span>
            <p>{result.near_traits.length ? result.near_traits.join(" • ") : "No near breakpoints"}</p>
          </div>
          <div>
            <span className="detail-label">Unused</span>
            <p>{result.unused_traits.length ? result.unused_traits.join(" • ") : "Clean board"}</p>
          </div>
        </div>
      </div>
    </article>
  );
}

function AvatarTagList({
  items,
  units,
  onRemove,
  readonly = false,
}: {
  items: string[];
  units: Unit[];
  onRemove: (item: string) => void;
  readonly?: boolean;
}) {
  if (items.length === 0) {
    return <div className="tag-list-empty">None selected</div>;
  }

  return (
    <div className="avatar-tag-list">
      {items.map((item) => {
        const unit = units.find((entry) => entry.name === item);
        return (
          <button
            key={item}
            className={`avatar-tag-chip ${readonly ? "readonly" : ""}`}
            onClick={() => {
              if (!readonly) {
                onRemove(item);
              }
            }}
            type="button"
          >
            {unit ? (
              <img
                src={resolveImageUrl(unit.avatar_local_url || unit.avatar_remote_url)}
                alt={unitTitle(unit)}
                loading="lazy"
                decoding="async"
              />
            ) : null}
            <span>{unit ? unitTitle(unit) : item}</span>
            {unit?.special_mode ? <span className="mode-pill compact">{unit.special_mode}</span> : null}
            <strong>{readonly ? "Locked" : "?"}</strong>
          </button>
        );
      })}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <span>{label}</span>
      {children}
    </div>
  );
}

function CostRangeSlider({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: CostRange;
  max: number;
  onChange: (value: CostRange) => void;
}) {
  const [activeThumb, setActiveThumb] = useState<"min" | "max" | null>(null);
  const minValue = Math.min(value.min, value.max, max);
  const maxValue = Math.max(value.max, minValue);
  const collapsed = minValue === maxValue;
  const valueLabel = minValue === 0 && maxValue === max ? "Any" : `${minValue}-${maxValue}`;
  const minPercent = (minValue / Math.max(max, 1)) * 100;
  const maxPercent = (maxValue / Math.max(max, 1)) * 100;
  let minZIndex = 2;
  let maxZIndex = 3;

  if (collapsed) {
    if (minValue <= 0) {
      minZIndex = 2;
      maxZIndex = 4;
    } else if (maxValue >= max) {
      minZIndex = 4;
      maxZIndex = 2;
    } else if (activeThumb === "min") {
      minZIndex = 4;
      maxZIndex = 2;
    } else {
      minZIndex = 2;
      maxZIndex = 4;
    }
  }

  return (
    <div className="cost-slider-card">
      <div className="cost-slider-head">
        <span>{label}</span>
        <strong>{valueLabel}</strong>
      </div>
      <div className="range-slider">
        <div className="range-slider-track" />
        <div
          className="range-slider-fill"
          style={{ left: `${minPercent}%`, width: `${Math.max(0, maxPercent - minPercent)}%` }}
        />
        <input
          className="cost-slider cost-slider-min"
          type="range"
          min={0}
          max={max}
          step={1}
          value={minValue}
          style={{ zIndex: minZIndex }}
          onMouseDown={() => setActiveThumb("min")}
          onTouchStart={() => setActiveThumb("min")}
          onChange={(e) => {
            setActiveThumb("min");
            const raw = Number(e.target.value);
            if (collapsed && raw !== maxValue) {
              onChange({ min: Math.min(raw, max), max: maxValue });
              return;
            }
            const next = Math.min(raw, maxValue);
            onChange({ min: next, max: maxValue });
          }}
        />
        <input
          className="cost-slider cost-slider-max"
          type="range"
          min={0}
          max={max}
          step={1}
          value={maxValue}
          style={{ zIndex: maxZIndex }}
          onMouseDown={() => setActiveThumb("max")}
          onTouchStart={() => setActiveThumb("max")}
          onChange={(e) => {
            setActiveThumb("max");
            const raw = Number(e.target.value);
            if (collapsed && raw !== minValue) {
              onChange({ min: minValue, max: Math.max(raw, 0) });
              return;
            }
            const next = Math.max(raw, minValue);
            onChange({ min: minValue, max: next });
          }}
        />
      </div>
      <div className="cost-slider-scale">
        <span>0</span>
        <span>Any</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
