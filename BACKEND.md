# Backend Guide

## Cai dat

```bash
python -m pip install -r requirements-backend.txt
```

## Tai asset local cho frontend

```bash
python sync_set17_assets.py
```

Lenh nay se tai:

- `63` avatar unit Set 17
- `35` trait icons Set 17

vao:

- `assets/set17/units/`
- `assets/set17/traits/`

## Chay local

```bash
python -m uvicorn backend.main:app --reload
```

Server mac dinh:

- `http://127.0.0.1:8000`

Swagger UI:

- `http://127.0.0.1:8000/docs`

Static assets:

- `http://127.0.0.1:8000/assets/...`

## Endpoint

### `GET /api/health`

Kiem tra backend song.

Response hien co them thong tin cache nho:

- `entries`
- `hits`
- `misses`

### `GET /api/cache`

Lay thong ke cache hien tai.

### `POST /api/cache/clear`

Xoa cache trong bo nho.

### `GET /api/meta?set_number=17`

Lay metadata cua set.

### `GET /api/units?set_number=17`

Lay danh sach units.

Set 17 se co them:

- `avatar_local_url`
- `avatar_remote_url`

### `GET /api/traits?set_number=17`

Lay danh sach traits.

Set 17 se co them:

- `icon_local_url`
- `icon_remote_url`
- `description`
- `variants`

### `POST /api/search`

Body vi du:

```json
{
  "set_number": "17",
  "level": 8,
  "carry": "Kai'Sa",
  "include_units": [],
  "exclude_units": [],
  "exclude_costs": [],
  "limit": 10
}
```

Response search hien tai da duoc enrich cho frontend:

- `units[].avatar_local_url`
- `units[].avatar_remote_url`
- `display_traits[]`
  - `name`
  - `label`
  - `icon_local_url`
  - `icon_remote_url`

## Cache

Backend da co cache memory TTL de web muot hon:

- `meta / units / traits`: cache `24 gio`
- `search`: cache `1 gio`
- `perfect-synergies compact route`: cache `1 gio`

Khi backend khoi dong, cache warm-up se tu chay san cho:

- `meta / units / traits` cua Set 17
- 1 query khong carry o level 8
- 1 query carry `Kai'Sa` o level 8
- 1 query carry `Miss Fortune` o level 8

Neu muon bo qua cache va refresh lai du lieu, truyen:

```text
refresh=true
```

Vi du:

```text
GET /api/units?set_number=17&refresh=true
POST /api/search {"set_number":"17","level":8,"refresh":true}
```

## Ghi chu

- backend hien tai goi truc tiep engine trong `tft_synergies_live.py`
- Set 17 dang chay bang snapshot local `data/tft_set17_snapshot.json`
- CORS dang mo `*` de frontend local de goi de dang

## Route compatible voi tactics.tools

Backend da co route compact:

```text
GET /api/perfect-synergies/{set_number}/{max_unused_traits}/{level}/{mode}
```

Vi du:

```text
/api/perfect-synergies/170/0/7/base
```

Hien tai route nay map practical nhu sau:

- `170` -> Set `17`
- `0` -> `max_unused_traits=0`
- `7` -> `level=7`
- `base` -> khong exclude cost, sort theo cost

Mode hien dang ho tro:

- `base`
- `score`
- `x4`
- `x5`
- `x45`

Response cua route nay la compact list:

```json
[
  ["TFT17_Aatrox", "TFT17_Caitlyn", "..."],
  ["TFT17_Aatrox", "TFT17_Caitlyn", "..."]
]
```
