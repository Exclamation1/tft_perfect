# TFT Synergies Live

Script Python tim doi hinh TFT theo synergy tu du lieu CommunityDragon (live JSON).
Tool ho tro loc theo level, unit bat buoc, moc gia, role balance, carry va xuat JSON.

## 1. Tool nay lam gi?

- Tu dong lay du lieu set TFT hien tai
- Tim doi hinh theo so slot ban muon (`--level`)
- Cham diem theo synergy + can bang role + chi phi
- Tra ve top doi hinh de tham khao

## 2. Yeu cau

- Python 3.10+ (khuyen nghi 3.11/3.12)
- Co Internet cho lan chay dau tien (de tai data)

Kiem tra Python:

```bash
python --version
```

## 3. Cai dat va chay lan dau (cho nguoi moi)

1. Mo terminal trong thu muc project (noi co file `tft_synergies_live.py`)
2. Chay lenh don gian nhat:

```bash
python tft_synergies_live.py --level 8
```

Neu chay thanh cong, ban se thay:

- Set hien tai
- So champion/trait da nap
- Danh sach top comp voi score/cost/traits

## 4. Giai thich nhanh output

Moi ket qua co:

- `score`: diem heuristic tong hop (cang cao thuong cang hop tieu chi script)
- `cost`: tong cost doi hinh
- `Units`: danh sach tuong
- `Roles`: so luong tank/damage/flex va do lech role
- `Active`: trait da kich hoat
- `Near`: trait con thieu 1 moc
- `Unused`: trait le

## 5. Cac lenh co san hay dung

### 5.1 Lam moi cache du lieu

```bash
python tft_synergies_live.py --refresh --level 8
```

### 5.2 Xem danh sach champion cua set hien tai

```bash
python tft_synergies_live.py --refresh --level 8 --dump-champions
```

### 5.3 Xem danh sach trait

```bash
python tft_synergies_live.py --level 8 --dump-traits
```

### 5.4 Xuat JSON de xu ly bang script khac

```bash
python tft_synergies_live.py --level 8 --json
```

## 6. Vi du theo nhu cau thuc te

### Ep mot vai tuong bat buoc

```bash
python tft_synergies_live.py --level 8 --include-units "Skarner, Ahri"
```

### Loai bo cac tuong dat

```bash
python tft_synergies_live.py --level 8 --exclude-costs 4,5
```

### Tim comp chat hon (it trait le hon)

```bash
python tft_synergies_live.py --level 8 --max-unused-traits 1
```

### Tim comp can bang role chat hon

```bash
python tft_synergies_live.py --level 8 --min-tanks 3 --min-damage 3 --max-role-diff 1.5
```

### Khoanh vao comp xoay quanh carry

```bash
python tft_synergies_live.py --level 8 --carry "Kai'Sa"
```

## 7. Giai thich tham so quan trong

- `--level` (bat buoc): so luong unit trong doi hinh
- `--include-units`: ep co nhung unit nay (tach bang dau phay)
- `--exclude-costs`: loai cac moc gia, vi du `4,5`
- `--carry`: xac dinh carry chinh; carry se duoc auto include
- `--max-unused-traits`: gioi han so trait le
- `--trait-plus1`: gia lap +1 trait
- `--sort-by`: `score` hoac `cost`
- `--limit`: so ket qua tra ve
- `--beam-width`: do rong tim kiem (cao hon = cham hon, nhung de ra ket qua tot hon)
- `--min-tanks`, `--min-damage`: role toi thieu
- `--max-role-diff`: do lech role toi da
- `--role-balance-weight`: muc phat cho role lech
- `--refresh`: bo cache, tai moi data
- `--json`: in ket qua JSON

## 8. Rule dac biet trong code hien tai

- Mot so tuong dac biet bi rang buoc synergy rieng (vi du Baron can kich Void)
- `Baron Nashor` chi duoc phep tu level 10 tro len
- Neu 2 tuong co cung bo trait profile, search uu tien giu ban dat hon

## 9. Cache du lieu

Script cache JSON trong:

- `.tft_synergy_cache/`

Xoa cache:

PowerShell:

```powershell
Remove-Item -Recurse -Force .tft_synergy_cache
```

Bash:

```bash
rm -rf .tft_synergy_cache
```

## 10. Loi thuong gap

### `ERROR: Unknown unit: ...`

- Ten unit khong dung voi du lieu hien tai
- Chay `--dump-champions` de copy ten chinh xac

### `ERROR: Unit Baron Nashor requires level 10+`

- Baron chi hop le khi `--level >= 10`

### Chay lau / ton CPU

- Giam `--beam-width` (vi du 300-700)
- Giam `--limit`
- Tang rang buoc (`--include-units`, `--max-unused-traits`)

## 11. Quy trinh de xuat cho nguoi moi

1. Chay `--dump-champions` de xem pool unit set hien tai
2. Chay `--level 8` de xem baseline
3. Them dan rang buoc: `--carry`, `--include-units`, `--max-unused-traits`
4. Neu can tich hop voi app khac, dung `--json`
