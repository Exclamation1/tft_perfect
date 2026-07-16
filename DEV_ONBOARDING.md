# Dev Onboarding

Tai lieu nay dung de dev moi vao project co the:

- hieu nhanh code dang chay
- biet luong request di qua nhung dau nao
- biet cac ngoai le quan trong cua Set 17
- biet nen sua o file nao neu can them feature hoac sua scoring

Tai lieu nay khong thay the [SCORING.md](SCORING.md).
`SCORING.md` giai thich cong thuc diem.
File nay giai thich codebase va cach tiep tuc lam viec.

## 1. Stack hien tai

- Core engine: Python, file [tft_synergies_live.py](tft_synergies_live.py)
- Backend API: FastAPI, folder [backend](backend)
- Frontend: React + Vite, folder [frontend](frontend)
- Du lieu Set 17: [data/tft_set17_snapshot.json](data/tft_set17_snapshot.json)
- Asset local:
  - unit avatars: `assets/set17/units`
  - trait icons: `assets/set17/traits`

Deploy production hien tai:

- app path tren VPS: `/opt/tft-perfect`
- backend service: `tft-perfect`
- frontend static serve qua `nginx`
- domain: `https://tft-perfect.chuyenlive.page`

## 2. Nhanh gon: doc file nao truoc

Neu moi vao project, doc theo thu tu nay:

1. [SCORING.md](SCORING.md)
2. [tft_synergies_live.py](tft_synergies_live.py)
3. [backend/service.py](backend/service.py)
4. [backend/main.py](backend/main.py)
5. [frontend/src/App.tsx](frontend/src/App.tsx)
6. [frontend/src/types.ts](frontend/src/types.ts)
7. [frontend/src/api.ts](frontend/src/api.ts)

## 3. Luong chay tu frontend den engine

### 3.1. Frontend

Nguoi dung bam `Find Best Boards` trong [frontend/src/App.tsx](frontend/src/App.tsx).

Frontend se:

- doc state cua form filter
- goi `runSearch(...)` trong [frontend/src/api.ts](frontend/src/api.ts)
- POST len `/api/search`
- nhan ve:
  - `meta`
  - `results`

Frontend hien tai con render them:

- panel timing search
- card result
- picker carry/include/exclude
- auth gate

### 3.2. Backend

Route `/api/search` nam trong [backend/main.py](backend/main.py).

Route nay goi:

- `search(...)` trong [backend/service.py](backend/service.py)

Trong `backend/service.py`:

1. request JSON duoc map thanh `SearchRequest`
2. `SearchRequest` duoc doi thanh `SearchConfig` bang `_request_to_config(...)`
3. `run_search_with_config(...)` trong [tft_synergies_live.py](tft_synergies_live.py) duoc goi
4. ket qua duoc enrich them:
   - local avatar url
   - local trait icon url
   - display traits

Backend hien tai co:

- auth cookie session
- in-memory cache
- warm-up cache khi khoi dong

### 3.3. Core engine

Trong [tft_synergies_live.py](tft_synergies_live.py), luong chinh la:

1. `load_runtime_bundle(...)`
2. `search(...)`
3. `build_result(...)`

Chi tiet:

- `load_runtime_bundle(...)`
  - load trait defs
  - load champions
  - resolve carry
  - setup carry metadata
  - setup rule lien quan tank bat buoc theo cost carry

- `search(...)`
  - validate include/exclude
  - tao pool
  - tao seed states
  - beam search
  - final validate
  - dedupe result theo unit-set

- `build_result(...)`
  - tinh trait summary
  - tinh main tank
  - tinh score
  - xuat payload cho backend/frontend

## 4. Cac model can nho

### `SetRuleConfig`

Nam trong [tft_synergies_live.py](tft_synergies_live.py).

Dung de khai bao rule theo tung set:

- trait teamwide
- trait frontline teamwide
- trait buff theo carry type
- special champion rules

Neu can sua trait logic theo set, day la noi sua dau tien.

### `SearchConfig`

La input chuan cua engine.

Bao gom:

- filter board
- carry
- trait targets
- mecha transforms
- role constraints
- tank requirement theo carry cost
- debug timings

Neu them filter moi, thuong sua:

1. [backend/schemas.py](backend/schemas.py)
2. [backend/service.py](backend/service.py)
3. [tft_synergies_live.py](tft_synergies_live.py)
4. [frontend/src/App.tsx](frontend/src/App.tsx)
5. [frontend/src/types.ts](frontend/src/types.ts)

### `State`

Node cua beam search.

Giu:

- units da chon
- trait counts
- total cost
- role counts
- estimate score

Moi heuristic trong search chu yeu danh vao `State`.

## 5. Logic dac biet dang ton tai

Day la nhung logic khong duoc phep vo tinh lam mat khi refactor.

### 5.1. Mecha

`Mecha` khong tinh nhu trait thuong.

- mecha co transform
- transform an them slot
- effective mecha count co the cao hon raw mecha count
- `Mecha 6` co the mo them `+1 team size`

Code lien quan:

- `mecha_state_metrics(...)`
- `effective_trait_counts_from_state(...)`
- `mecha_transform_range_satisfied(...)`

### 5.2. Main tank

Board ra xong moi xac dinh `main tank`.

Logic hien tai:

- neu carry `4+ vang` -> can mot tank `4 vang`
- neu carry `<4 vang` -> can mot tank cung cost voi carry
- neu co nhieu ung vien tank dung cost
  - chon con co `trait value` cao nhat tren chinh no

Code lien quan:

- `has_required_cost_tank(...)`
- `main_tank_trait_value(...)`
- `determine_main_tank(...)`
- `trait_relevant_to_main_tank(...)`

### 5.3. Miss Fortune modes

`Miss Fortune` duoc expand thanh 3 variant:

- `Miss Fortune [Channeler]`
- `Miss Fortune [Challenger]`
- `Miss Fortune [Replicator]`

Luu y:

- frontend phai hien dung mode
- search khong duoc phep co 2 mode cua Miss Fortune trong cung mot comp

Code lien quan:

- `expand_special_variants(...)`
- `resolve_special_unit_name(...)`

### 5.4. Opt-in only units

Set 17 hien co:

- `Zed`
- `Rhaast`

Hai unit nay khong nam trong pool search mac dinh.
Chi duoc vao search neu:

- la carry
- hoac nam trong `include_units`

### 5.5. Near breakpoint

Near breakpoint duoc giu cho search nhung khong duoc cong vao final score.

Y nghia:

- beam search van di theo board "sap dep"
- nhung bang xep hang cuoi cung chi thuong trait active that

Code lien quan:

- `evaluate_traits(...)`
- `build_result(...)`

### 5.6. Teamwide va unique trait

Co nhieu trait dac biet cua Set 17 da duoc scale rieng.
Khong nen doan theo cam tinh.
Phai doc [SCORING.md](SCORING.md) truoc khi sua.

Vi du:

- `Dark Lady`
- `Factory New`
- `Doomer`
- `Commander`
- `Eradicator`
- `N.O.V.A.`
- `Redeemer`

## 6. Search va scoring sua o dau

### Neu sua search

Doc va sua cac ham:

- `search(...)`
- `estimate_state_score(...)`
- `final_valid(...)`
- `carry_search_heuristic(...)`

### Neu sua scoring final

Doc va sua cac ham:

- `evaluate_traits(...)`
- `carry_and_special_bonus(...)`
- `off_profile_damage_penalty(...)`
- `structure_bonus(...)`
- `total_cost_adjustment(...)`
- `build_result(...)`

### Neu sua logic theo trait

Thuong sua o:

- `SET_RULES`
- `TRAIT_BONUS_FACTOR_BY_TRAIT`
- `SINGLE_TRAIT_FACTOR_BY_TRAIT`
- cac helper rieng theo trait

## 7. Debug timing va performance

Hien tai backend co instrument timing theo 2 lop:

### 7.1. Timing ky thuat

Dung de debug performance engine:

- `load_traits_ms`
- `load_profiles_ms`
- `load_champions_ms`
- `constraint_setup_ms`
- `pool_prep_ms`
- `seed_prep_ms`
- `seed_build_ms`
- `beam_search_ms`
- `result_finalize_ms`
- `engine_total_ms`

### 7.2. Timing nghiep vu de hien frontend

Frontend dang hien cac nhan de doc:

- `Chuẩn bị dữ liệu`
- `Tìm team kích tộc hệ`
- `Ghép tank X vàng`
- `Xác định tank chính`
- `Tính điểm với điều kiện`
- `Ra form bài`
- `Tổng backend`
- `Tổng trình duyệt`

Neu can doi ten timing tren UI, sua o:

- [frontend/src/App.tsx](frontend/src/App.tsx)

Neu can doi cach gom stage timing, sua o:

- `run_search_with_config(...)` trong [tft_synergies_live.py](tft_synergies_live.py)

## 8. Cache va deploy

### Cache

Backend dang dung:

- in-memory TTL cache

Vi vay:

- restart backend = clear toan bo cache
- hoac goi `POST /api/cache/clear`

### Deploy nhanh

Deploy thuong can:

1. upload file python/frontend
2. neu frontend doi:
   - build `frontend/dist`
   - upload `dist`
   - reload `nginx`
3. restart backend:
   - `systemctl restart tft-perfect`
4. clear cache cu
5. verify lai `/api/search`

## 9. Kiem tra truoc khi noi la da xong

Toi thieu can chay:

### Local

```bash
python -m py_compile tft_synergies_live.py backend/service.py backend/main.py backend/schemas.py
cd frontend
npm run build
```

Neu sua scoring/search:

- chay it nhat 1-2 query that bang script nho hoac qua `backend.service`

### Production

Sau deploy:

1. login API
2. clear cache
3. goi `POST /api/search`
4. check:
   - status `200`
   - `meta.timings`
   - top result co hop ly

## 10. Cac cho de vo tinh sua hong

Day la checklist truoc khi commit:

- co vo tinh mat dedupe result theo `unit-set` khong
- co vo tinh cho 2 variant `Miss Fortune` vao cung 1 comp khong
- co vo tinh dua `Zed`/`Rhaast` vao pool mac dinh khong
- co vo tinh cho `near breakpoint` cong vao final score khong
- co vo tinh lam sai `main tank` requirement theo carry cost khong
- co vo tinh sua `teamwide` thanh penalty khong
- co vo tinh lam frontend va backend lech schema khong

## 11. Goc nhin khi tiep tuc phat trien

Neu dev moi tiep tuc lam feature, nen uu tien:

1. giu schema on dinh
2. giu deploy flow don gian
3. them regression test cho cac case carry quan trong
4. tach dan logic khoi `tft_synergies_live.py` thay vi tiep tuc nhoi them

## 12. De xuat refactor sau nay

Hien tai `tft_synergies_live.py` van la file qua lon.

Refactor hop ly sau nay:

- `engine/data_loader.py`
- `engine/set_rules.py`
- `engine/search.py`
- `engine/scoring.py`
- `engine/special_traits.py`
- `engine/models.py`

Nhung truoc khi tach, nen dong bang behavior bang test regression.
