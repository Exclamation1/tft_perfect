# TFT Perfect Project Handoff

Tai lieu nay la handoff cap project, dung cho dev moi vao de hieu nhanh:

- san pham hien dang la gi
- code dang song o dau
- production dang chay nhu the nao
- cac logic dac biet nao tuyet doi khong duoc vo tinh lam mat
- nhung viec nao da lam xong, nhung viec nao dang la diem nong

Tai lieu nay di cung voi:

- [SCORING.md](SCORING.md): cong thuc tinh diem hien tai
- [DEV_ONBOARDING.md](DEV_ONBOARDING.md): doc codebase va tiep tuc lam viec

## 1. Product Hien Tai

Project hien tai khong con la mot script don le nua.
No da la mot web app hoan chinh cho viec tim doi hinh TFT Set 17:

- frontend React + Vite
- backend FastAPI
- core search/scoring engine trong Python
- production VPS da deploy
- auth, cache, warm-up, timing panel da co

Muc tieu san pham:

- tim top comp theo carry / filter / trait target
- tra ket qua nhanh nhat co the ma van giu duoc chat luong search
- cho phep dieu chinh scoring theo meta va intuition thuc chien

## 2. Production Hien Tai

Production dang song tai:

- `https://tft-perfect.chuyenlive.page`

Thanh phan production:

- `nginx`: serve frontend va reverse proxy API
- `tft-perfect` systemd service: backend FastAPI
- in-memory cache trong backend

Dang nhap hardcode hien tai:

- username: `admin`
- password: `tftAbc123@`

Luu y:

- toan bo `/api/*` yeu cau session cookie auth, tru auth routes
- frontend tu gate vao `/login` neu chua co session

## 3. Repo Structure

- [tft_synergies_live.py](tft_synergies_live.py)
  - file quan trong nhat
  - chua engine search, trait rules, scoring, timing, data loading
- [backend](backend)
  - FastAPI app, schemas, request -> config mapping, cache logic
- [frontend](frontend)
  - React app, search controls, result feed, login screen, timing panel
- [data/tft_set17_snapshot.json](data/tft_set17_snapshot.json)
  - snapshot Set 17 duoc project dung lam nguon du lieu chinh
- `assets/set17/units`
  - avatar local cho unit
- `assets/set17/traits`
  - icon local cho traits
- [SCORING.md](SCORING.md)
  - cong thuc tinh diem
- [DEV_ONBOARDING.md](DEV_ONBOARDING.md)
  - tai lieu doc code va tiep tuc lam viec

## 4. Luong Chay End-to-End

### 4.1. Frontend

Frontend goi:

- `POST /api/search`
- `GET /api/bootstrap`
- auth routes:
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - `POST /api/auth/logout`

Frontend hien tai da co:

- search controls day du
- carry picker
- include/exclude unit picker
- trait target picker
- mecha transform slider
- cost-range dual slider
- timing panel bang tieng Viet
- badge thong bao `Zed` va `Rhaast` bi khoa mac dinh

### 4.2. Backend

Backend chinh nam trong:

- [backend/main.py](backend/main.py)
- [backend/service.py](backend/service.py)

`backend/service.py` co nhung viec chinh:

- map `SearchRequest` -> `SearchConfig`
- chon `beam_width`
- cache request search
- warm-up startup
- enrich output units / traits cho frontend

### 4.3. Core Engine

Core engine nam trong [tft_synergies_live.py](tft_synergies_live.py).

Luong chinh:

1. `load_runtime_bundle(...)`
2. `search(...)`
3. `build_result(...)`

Trong do:

- `load_runtime_bundle(...)`
  - load snapshot / trait defs / champions
  - resolve carry
  - setup carry metadata
  - setup tank requirement theo carry cost

- `search(...)`
  - build pool
  - build seed states
  - chay beam search 1 pass
  - finalize results
  - dedupe theo `unit-set`

- `build_result(...)`
  - tinh trait summary
  - xac dinh main tank
  - tinh final score
  - xuat payload cho frontend

## 5. Search Strategy Hien Tai

### 5.1. Beam Search

Project dang dung beam search, khong brute force.

Trang thai hien tai:

- **progressive beam da tat**
- hien tai chi con **1 pass**
- `adaptive_beam_schedule(cfg)` tra ve:

```python
[cfg.beam_width]
```

- `should_expand_search(...)` tra ve `False`

Ly do:

- production multi-pass bi qua cham
- user chu yeu can top `10 / 50 / 100`
- 1-pass cho experience on dinh hon

### 5.2. Beam Width

Beam width duoc chon trong [backend/service.py](backend/service.py).

He thong dang scale beam theo:

- co carry hay khong
- `limit`
- query rong hay hep

Nhung direction da thu va da rollback:

- uu tien unit gan gia carry trong search
- progressive beam pass 2 / pass 3

Ly do rollback:

- chat luong khong tang du
- nhung runtime tang ro ret

## 6. Hotspots Ve Hieu Nang

### 6.1. Ket luan profile

Sau khi profile local va VPS, bottleneck chinh la:

- `estimate_state_score(...)`
- `carry_and_special_bonus(...)`
- `evaluate_traits(...)`
- `frontline_backline_scores(...)`
- `determine_main_tank(...)`
- `mecha_state_metrics(...)`

Day la CPU-bound search cost, khong phai network hay frontend.

### 6.2. Toi uu da lam

Da them cache theo `State` trong [tft_synergies_live.py](tft_synergies_live.py):

- `state_mecha_metrics_cache`
- `state_effective_trait_counts_cache`
- `state_trait_evaluation_cache`
- `state_frontline_backline_cache`
- `state_role_metrics_cache`
- `state_archetype_subtypes_cache`
- `state_main_tank_cache`
- `state_active_carry_trait_count_cache`

Them nua:

- `State.cache_key`
- moi `state` chi tinh cache key mot lan

Muc tieu:

- giam viec tinh lai cung mot du lieu cho hang chuc nghin state evaluations

### 6.3. Trang thai hieu nang hien tai

Tinh den luc update file nay:

- local search da xuong dang ke
- tren VPS, `_search_uncached` cho carry `limit=10` dang quanh `8-9s`

Luu y quan trong:

- `POST /api/search` cong khai co the cao hon so `_search_uncached`
- nghia la phan chenh hien nay co kha nang nam o layer API / request path / runtime bundle / cache path
- neu toi uu tiep, nen do tach:
  - `_search_uncached` trong process
  - `POST /api/search` qua app live

## 7. Cac Logic Dac Biet Dang Song

Day la cac logic tuyet doi can giu khi refactor.

### 7.1. Miss Fortune modes

`Miss Fortune` duoc expand thanh 3 variant:

- `Miss Fortune [Channeler]`
- `Miss Fortune [Challenger]`
- `Miss Fortune [Replicator]`

Y nghia:

- carry / include / output phai cho biet mode
- khong duoc co 2 mode Miss Fortune trong cung 1 comp

### 7.2. Mecha

`Mecha` co logic rieng:

- transform an them slot
- effective mecha count co the cao hon raw count
- `Mecha 6` co the mo `+1 team size`

Filter `Mecha Transforms` dang hoat dong:

- `0-0`
- `0-3`
- `3-3`

### 7.3. Main tank

Main tank chi duoc xac dinh **sau khi ra board**.

Rule hien tai:

- carry `4+ vang` -> can mot tank `4 vang`
- carry `<4 vang` -> can mot tank cung cost voi carry
- neu co nhieu tank hop le:
  - chon con co `trait value` cao nhat tren chinh no

Trait relevance cua main tank duoc dung de tranh phat oan mot so trait support tank.

### 7.4. Opt-in only units

Hien tai:

- `Zed`
- `Rhaast`

khong nam trong pool search mac dinh.

Chi duoc vao search neu:

- la `carry`
- hoac nam trong `include_units`

Frontend co badge thong bao dieu nay.

### 7.5. Near breakpoint

Logic hien tai:

- `near breakpoint` chi dung de dan huong search
- final score khong cong diem near breakpoint nua

He qua:

- search van co xu huong di theo board sap dep trait
- nhung bang xep hang cuoi khong bi “an gian” boi trait chua kich

## 8. Scoring: Muc Doc Nhanh

Cong thuc day du nam trong [SCORING.md](SCORING.md).

Can nho nhanh:

- `trait_score`
- `cost_adjustment`
- `carry_and_special_bonus`
- `off_profile_damage_penalty`
- `structure_bonus`

Nhung trait / rule dac biet dang ton tai:

- `N.O.V.A.`
- `Redeemer`
- `Dark Lady`
- `Factory New`
- `Doomer`
- `Commander`
- `Eradicator`
- `Psionic`
- `Dark Star`
- `Shepherd`
- `Marauder`

Neu thay ranking “ky”, doc [SCORING.md](SCORING.md) truoc khi sua code.

## 9. Timing Panel

Frontend hien tai dang hien panel timing bang tieng Viet.

Nhung stage nghiep vu dang hien:

- `Chuẩn bị dữ liệu`
- `Tìm team kích tộc hệ`
- `Ghép tank X vàng`
- `Xác định tank chính`
- `Tính điểm với điều kiện`
- `Ra form bài`
- `Tổng backend`
- `Tổng trình duyệt`

Timing ky thuat chi giu o backend de debug, khong show het len UI.

## 10. Cache

Cache hien tai la:

- in-memory
- process-local
- theo request payload

Da co:

- startup warm-up
- endpoint clear cache
- endpoint health / cache stats

Luu y:

- restart backend = xoa toan bo cache cu
- doi scoring/search logic thi can clear cache

## 11. Auth

Auth hien tai la session cookie hardcoded, muc dich de khoa website/API.

Da co:

- login route
- frontend login gate
- middleware chot API

Chua phai auth production-grade.
Neu sau nay mo rong, can doi sang env + secret store.

## 12. Deploy Flow

Deploy production hien tai thuong la:

1. sua code local
2. upload file len VPS
3. restart `tft-perfect`
4. clear cache
5. verify qua API live
6. warm-up lai query pho bien neu can

Nhung gi can verify sau deploy:

- service `tft-perfect` phai `active`
- SHA file local va VPS neu patch quan trong
- top1 cua mot vai carry chuan khong bi lech
- `/api/cache` va `/api/health` hoat dong

## 13. Known Risks

### 13.1. Search quality vs speed

Day la tradeoff lon nhat cua project.

- beam nho hon -> nhanh hon
- nhung de miss comp manh

Da thu:

- progressive beam
- search bias theo cost carry

nhung hien tai da rollback vi gia tri/chi phi chua tot.

### 13.2. VPS va local khac nhau ro

Local nhanh hon production rat nhieu vi:

- Python version khac
- CPU local manh hon
- production la VPS 4 vCPU

Nghia la:

- benchmark local chi dung de so sanh tuong doi
- can verify tren VPS truoc khi ket luan

### 13.3. `POST /api/search` va `_search_uncached` khong giong nhau 100%

Neu thay live API cham hon direct engine:

- khong duoc vo tinh ket luan la beam van cham
- phai tach layer:
  - engine
  - backend request path
  - cache
  - auth/session

## 14. Viec Nen Lam Tiep Neu Co Thoi Gian

Thu tu uu tien hop ly:

1. do chenh lech giua `_search_uncached` va `POST /api/search`
2. toi uu tiep request path neu chenh lech van lon
3. benchmark theo bo carry pho bien de co baseline on dinh
4. chuan hoa deploy script
5. tiep tuc gom code scoring/search thanh module nho hon

## 15. Rule Quan Trong Nhat Cho Dev Moi

Neu muon sua project nay an toan:

1. dung sua scoring mu khi chua doi top1 cua vai carry chuan
2. dung toi uu toc do ma khong benchmark local + VPS
3. moi thay doi search/scoring deu phai:
   - verify local
   - verify live
   - clear cache
4. doc [SCORING.md](SCORING.md) truoc khi sua logic diem
5. doc [DEV_ONBOARDING.md](DEV_ONBOARDING.md) truoc khi refactor lon

Handoff nay du de dev moi vao project co the:

- hieu luong chay
- biet production dang o dau
- biet nhung logic nao dang nhay cam
- va tiep tuc toi uu ma khong vo tinh pha ranking/search.
