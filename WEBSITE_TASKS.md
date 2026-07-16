# Website Backlog

## Muc tieu

Xay dung website theo huong tuong tu `https://tactics.tools/perfect-synergies`, nhung su dung engine hien tai cua project nay.

Muc tieu san pham:

- tim doi hinh TFT manh va flex
- cho phep nguoi dung tu do chon filter
- tra ve top doi hinh theo heuristic scoring
- uu tien huong phat trien web app that su dung duoc, khong chi la script CLI

## Pham vi ban dau

- ho tro `Set 17`
- trang chinh la `Perfect Synergies`
- backend dung engine Python hien tai
- frontend cho nguoi dung nhap filter va xem top result

## Epic 1: Product Scope

1. Chot pham vi MVP
   - MVP chi ho tro `Set 17`
   - chi co 1 tool: `Perfect Synergies`
2. Chot user flow
   - vao trang
   - chon filter
   - bam tim
   - xem doi hinh
   - sua filter va tim lai

## Epic 2: Engine Hardening

1. Tach `tft_synergies_live.py` thanh cac module backend
2. Tach rieng:
   - data loading
   - set rules
   - search
   - scoring
3. Chuan hoa ham search de goi duoc tu API
4. Them regression tests cho 5-10 carry mau
5. Benchmark thoi gian response theo `beam_width`
6. Chuan hoa alias ten unit / trait Set 17

## Epic 3: Set 17 Data Layer

1. Chot `data/tft_set17_snapshot.json` lam source local mac dinh
2. Viet script refresh snapshot tu `https://tactics.tools/info/set-update`
3. Version hoa snapshot
4. Them validation:
   - du so unit
   - du so trait
   - breakpoint hop le
5. Log canh bao neu HTML structure cua source thay doi

## Epic 4: Backend API

1. Tao backend bang FastAPI
2. Tao `GET /api/meta`
3. Tao `GET /api/units`
4. Tao `GET /api/traits`
5. Tao `POST /api/search`
6. Validate request bang Pydantic
7. Chuan hoa response schema
8. Them error handling cho:
   - unknown unit
   - invalid carry
   - impossible filters
9. Them cache response cho query lap lai

## Epic 5: Search API Features

1. Ho tro input:
   - `set_number`
   - `level`
   - `carry`
   - `include_units`
   - `exclude_units`
   - `exclude_costs`
   - `cost_1_count ... cost_5_count`
   - `max_unused_traits`
   - `trait_plus1`
   - `sort_by`
   - `limit`
2. Tra ve score breakdown
3. Tra ve role/frontline/backline breakdown
4. Tra ve active/near/unused traits
5. Tra ve cost buckets

## Epic 6: Frontend Foundation

1. Chon stack frontend
   - khuyen nghi `Next.js`
2. Setup project frontend
3. Setup design tokens
4. Setup API client
5. Setup global state cho filter form
6. Setup routing

## Epic 7: Builder UI

1. Tao trang `Perfect Synergies`
2. Tao filter panel
3. Tao cac control:
   - set selector
   - level selector
   - carry autocomplete
   - include units multi-select
   - exclude units multi-select
   - exclude cost toggles
   - cost bucket inputs
   - unused traits input
   - trait +1 select
   - sorting select
4. Them nut `Find Comp`
5. Them nut `Reset Filters`

## Epic 8: Results UI

1. Tao danh sach ket qua
2. Moi result card hien thi:
   - score
   - total cost
   - units
   - active traits
   - near traits
   - unused traits
   - roles
   - cost buckets
3. Them score breakdown expandable
4. Them loading state
5. Them empty state
6. Them error state

## Epic 9: UX Improvements

1. Luu filter vao URL query params
2. Ho tro share link
3. Ho tro debounce khi doi filter
4. Them preset pho bien
5. Cho copy doi hinh
6. Highlight unit thuoc carry trait
7. Highlight trait buff toan team

## Epic 10: Website-Specific Pages

1. Trang `Units`
2. Trang `Traits`
3. Trang `How Scoring Works`
4. Trang `Patch / Data Version`
5. Trang `Debug` noi bo
   - xem snapshot
   - refresh snapshot
   - test query

## Epic 11: Ops

1. Dockerize backend
2. Deploy frontend
3. Deploy backend
4. Setup environment config
5. Setup monitoring
6. Setup request logs
7. Setup rate limiting

## Epic 12: Quality

1. Unit tests cho parser
2. API tests
3. Snapshot tests
4. Frontend integration tests
5. Performance test cho search API
6. Mobile responsiveness test

## Thu tu lam khuyen nghi

1. Tach engine thanh backend module
2. Lam `POST /api/search`
3. Lam UI filter + results
4. Them `GET /api/units` va `GET /api/traits`
5. Toi uu score breakdown va UX
6. Moi lam refresh snapshot, share link, preset

## MVP Sprint Plan

### Sprint 1

- refactor engine
- FastAPI
- `/api/search`
- snapshot Set 17

### Sprint 2

- frontend builder page
- results page
- carry/include/exclude filters

### Sprint 3

- units/traits endpoints
- score breakdown
- URL sync
- deploy

## Goi y phan vai

### Backend dev

- engine refactor
- data snapshot
- API

### Frontend dev

- builder UI
- result cards
- routing/state

### Fullstack / lead

- response contract
- scoring review
- deploy

## API de xay

### `GET /api/meta`

Tra ve:

- set hien tai
- version
- champion count
- trait count

### `GET /api/units`

Tra ve:

- danh sach units
- cost
- traits
- role
- archetype
- range

### `GET /api/traits`

Tra ve:

- trait name
- breakpoints
- units
- description

### `POST /api/search`

Input:

- set number
- level
- carry
- include units
- exclude units
- exclude costs
- cost bucket counts
- beam width
- max unused traits
- min tanks
- min damage
- max role diff

Output:

- meta
- top results
- score breakdown cua tung result

## Product Direction

Tinh than quan trong cua project:

- khong tim comp theo kieu nhieu trait nhat
- uu tien comp manh, co logic support carry, board shape hop ly
- trait phai co gia tri thuc chien
- scoring phai nghiêng ve suc manh doi hinh hon la trait cho dep

## Next Step De Xay Website

1. giu engine hien tai
2. tach thanh backend FastAPI
3. expose search API
4. xay frontend builder page
5. sau do moi tune scoring tiep
