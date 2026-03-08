# TFT Synergies Live

Script Python tim doi hinh TFT theo synergy tu du lieu CommunityDragon (live JSON), co ho tro rang buoc vai tro, chi phi va trait.

## 1. Yeu cau

- Python 3.10+ (khuyen nghi 3.11/3.12)
- Co ket noi Internet de lay du lieu lan dau

Kiem tra nhanh:

```bash
python --version
```

## 2. Chay nhanh cho nguoi moi

Tai thu muc project, chay:

```bash
python tft_synergies_live.py --level 8
```

Lenh tren se:

- Tu dong lay set TFT hien tai
- Lay danh sach champion va trait
- Tim doi hinh phu hop cho level da cho

## 3. Cac lenh hay dung

### Lam moi cache du lieu

```bash
python tft_synergies_live.py --refresh --level 8
```

### Dump danh sach champion hien tai

```bash
python tft_synergies_live.py --refresh --level 8 --dump-champions
```

### Dump danh sach trait

```bash
python tft_synergies_live.py --level 8 --dump-traits
```

### Chay voi rang buoc cu the

```bash
python tft_synergies_live.py \
  --level 8 \
  --include-units "Skarner, Ahri" \
  --max-unused-traits 1 \
  --beam-width 1000 \
  --limit 50 \
  --min-tanks 3 \
  --min-damage 3 \
  --max-role-diff 2 \
  --role-balance-weight 10
```

### Xuat ket qua dang JSON

```bash
python tft_synergies_live.py --level 8 --json
```

## 4. Giai thich tham so quan trong

- `--level`: So luong unit trong doi hinh (bat buoc)
- `--include-units`: Ep bat buoc co nhung tuong nay (phan tach bang dau phay)
- `--exclude-costs`: Loai bo cac moc gia, vi du `--exclude-costs 4,5`
- `--max-unused-traits`: So trait duoc phep "le" toi da
- `--beam-width`: Do rong tim kiem
- `--limit`: So ket qua tra ve
- `--min-tanks`: Muc toi thieu vai tro tank
- `--min-damage`: Muc toi thieu vai tro damage
- `--max-role-diff`: Do lech toi da giua tank/damage hieu dung
- `--role-balance-weight`: Trong so phat do lech vai tro
- `--refresh`: Bo qua cache, tai du lieu moi

## 5. Meo de chay nhanh hon

- Giam `--beam-width` (vi du 400-700) de tang toc
- Giam `--limit` neu chi can top it ket qua
- Khong dung `--refresh` moi lan chay neu khong can cap nhat data

## 6. Thu muc cache

Script luu cache tai:

- `.tft_synergy_cache/`

Neu muon reset cache:

```bash
rm -rf .tft_synergy_cache
```

Script se tu tao lai khi chay lan tiep theo.

## 7. Loi thuong gap

### `ERROR: Unexpected tftsets.json format`

- Nguyen nhan: schema du lieu CommunityDragon thay doi
- Cach xu ly: cap nhat source len ban moi nhat (ban hien tai da fix)

### `ERROR: Unknown unit: ...`

- Kiem tra lai ten tuong trong `--include-units`
- Dung `--dump-champions` de xem ten chinh xac

### Chay lau

- Thu giam `--beam-width`
- Tang dieu kien rang buoc ro hon (`--include-units`, `--max-unused-traits`)

## 8. Luong su dung de xuat

1. Chay `--dump-champions` de xem pool tuong hien tai
2. Chay tim comp co rang buoc ban muon
3. Neu can parse bang script khac, them `--json`
