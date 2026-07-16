# Scoring Guide

Tai lieu nay mo ta day du logic scoring hien tai cua engine trong `tft_synergies_live.py`.
Muc tieu cua scoring la uu tien doi hinh:

- manh va dung form
- co trait gan voi carry
- co buff toan team hop voi board
- khong bi dan trait vo toi va
- ton trong cac ngoai le dac biet cua Set 17

Tai lieu nay co y giai thich theo logic hien dang chay trong code, khong phai y tuong cu.

## 1. Tong Quan

Score cuoi cung duoc tinh theo cong thuc:

```text
score
= trait_score
+ cost_adjustment
- frontline_shortfall * role_balance_weight
+ carry_and_special_bonus
- off_profile_damage_penalty
+ structure_bonus
- active_trait_penalty
```

Code lien quan:

- `evaluate_traits(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `total_cost_adjustment(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `frontline_shortfall(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `carry_and_special_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `off_profile_damage_penalty(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `structure_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- final assembly trong `estimate_state_score(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 2. Trait Score

`trait_score` la diem nen cua board, tinh trong `evaluate_traits(...)`.

### 2.1. Trait active

Mot so breakpoint thap nhung kho kich duoc buff rieng them khoang 20%:

- `Arbiter 3` -> `1.2x`
- `Primordian 3` -> `1.2x`
- `Timebreaker 4` -> `1.2x`
- `Fateweaver 4` -> `1.2x`

Cach hieu truc giac:

- `Arbiter 3` duoc xem nhu `3.6`
- `Primordian 3` duoc xem nhu `3.6`
- `Timebreaker 4` duoc xem nhu `4.8`
- `Fateweaver 4` duoc xem nhu `4.8`

Neu trait dat moc active, code lay moc cao nhat dang dat duoc la `best_bp` va cham theo **thu tu breakpoint trong trait**, khong cham theo con so raw `2/3/4/5`.

Cong thuc hien tai la:

```text
trait_breakpoint_score(rank) = rank^2 + 4 * rank + 7
```

Trong do:

- `rank = 1` = moc dau tien cua trait
- `rank = 2` = moc thu hai
- `rank = 3` = moc thu ba

Vi du:

- moc dau tien => `12`
- moc thu hai => `19`
- moc thu ba => `28`
- moc thu tu => `39`

Y nghia:

- `Shepherd 3/3` va `Marauder 2/2` se bang nhau neu cung la moc dau tien
- code uu tien tier cua trait, khong uu tien trait chi vi breakpoint dau tien can nhieu unit hon
- unique trait `1/1` duoc giu o muc nen `5` de khong phong qua tay trait_score

Code:

- `trait_breakpoint_score(...)`: [tft_synergies_live.py](tft_synergies_live.py)

### 2.2. Trait khong active

Neu trait chua dat moc dau tien:

```text
0.0
```

Trait do van di vao `unused_traits`, nhung khong con bi tru diem chi vi chua active.

### 2.3. Near breakpoint

Chi thuong near breakpoint khi:

- trait van chua active
- va con thieu dung `1` unit de cham moc dau tien

Cong:

```text
+4.0
```

Logic nay chi dung de dan huong cho `beam search` trong luc mo rong state.
Khi tinh `final score` de xep hang ket qua, `near breakpoint` duoc tinh la:

```text
0.0
```

Tuc la:

- search van co xu huong di theo board "sap dep trait"
- nhung bang xep hang cuoi cung chi thuong trait da active that

Vi du:

- `Brawler 1 -> 2`
- `N.O.V.A. 1 -> 2`

### 2.4. Leftover units

Neu trait da active nhung count vuot moc `best_bp`, phan du bi phat nhe:

```text
-1.5 * leftover_units
```

## 3. Ngoai Le Dac Biet: Mecha

`Mecha` khong duoc tinh nhu trait thuong.

Theo logic hien tai:

- moi `Mecha` duoc phep transform
- moi transform:
  - chiem them `1` slot board
  - cong them `+1` vao dem trait `Mecha`
- neu board dat `Mecha 6`, board duoc `+1 max team size`

Engine vi vay tinh rieng:

- `team_capacity`
- `occupied_slots`
- `transformed_mechas`
- `effective_mecha_count`

He qua:

- count trait `Mecha` de filter/cham diem la `effective_mecha_count`
- board co the it unit raw hon level vi slot da bi transform chiem
- `Mecha 6` co the hop le o level 8 neu board thuc su dung du slot theo logic transform

Frontend/backend hien co them filter `Mecha Transforms`:

- `0-0` = khong transform
- `0-3` = de engine tu chon so transform tot nhat
- `3-3` = ep full 3 transform neu du dieu kien

Code:

- `mecha_state_metrics(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `effective_trait_counts_from_state(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `mecha_transform_range_satisfied(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 4. Cost Adjustment

Code tach theo gia tri carry.

Neu carry co cost `4` hoac `5`:

```text
+ total_cost * 0.45
```

Neu carry co cost `3`:

```text
+ total_cost * 0.15
```

Neu carry co cost `2`:

```text
+ total_cost * 0.08
```

Neu carry co cost `1`:

```text
+ total_cost * 0.04
```

Neu khong co carry:

```text
- total_cost * 0.45
```

Y nghia:

- carry 4/5 vang duoc khuyen khich di voi board dat hon
- carry 3 vang van duoc thuong khi board cap hon, nhung he so nho hon nhieu
- carry 2 vang cung duoc thuong board dat hon, nhung nhe hon carry 3 vang
- carry 1 vang duoc thuong rat nhe
- board khong co carry thi van co xu huong tiet kiem cost

Code:

- `total_cost_adjustment(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 5. Role Balance Va Frontline Shortfall

Code hien tai khong phat board vi nhieu tank hon damage.
No chi phat khi board co qua nhieu damage ma thieu frontline.

Cong thuc:

```text
frontline_shortfall = max(0, damage_count - tank_count - 1)
role_penalty = frontline_shortfall * role_balance_weight
```

Mac dinh:

- `role_balance_weight = 8`

Y nghia:

- damage = tank -> khong phat
- damage = tank + 1 -> khong phat
- damage >= tank + 2 -> bat dau bi phat
- nhieu tank hon damage -> chap nhan duoc

Code:

- `frontline_shortfall(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 6. Minimum Role Coverage Trong Luc Search

Trong beam search, code them phat nhe neu board chua du tank hoac damage hieu dung:

```text
- max(0, min_tanks - effective_tanks) * 3.5
- max(0, min_damage - effective_damage) * 3.5
```

Trong do:

- `effective_tanks = tanks + 0.5 * flex`
- `effective_damage = damage + 0.5 * flex`

Code:

- `effective_role_counts(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `estimate_state_score(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 7. Teamwide Buff Va Carry Bonus

Day la phan scoring quan trong nhat de dua board ve suc manh thuc chien thay vi chi gom trait.

Hang so mac dinh:

- `CARRY_TRAIT_BONUS = 5.0`
- `TEAM_BUFF_BONUS = 4.0`
- `CARRY_TEAM_BUFF_STACK_BONUS = 5.0`
- `IRRELEVANT_TRAIT_PENALTY = 2.0`

### 7.1. Unit dac biet chi vao search khi nguoi dung chu dong bat

Set 17 hien co 2 unit `opt-in only`:

- `Zed`
- `Rhaast`

Hai unit nay khong nam trong pool search mac dinh.
Chi duoc dua vao board neu:

- nguoi dung `include` truc tiep
- hoac chon lam `carry`

Code:

- `SetRuleConfig.opt_in_only_names`: [tft_synergies_live.py](tft_synergies_live.py)
- pool filter trong `search(...)`: [tft_synergies_live.py](tft_synergies_live.py)

### 7.2. Trait vua la trait cua carry vua la teamwide buff

Neu trait dang active va:

- thuoc `carry_traits`
- dong thoi thuoc `team_buff_traits`

thi van giu ca hai y nghia:

- no la trait cua carry
- no cung la buff toan team

Nhung code khong con cong them `overlap stack bonus` rieng nhu truoc.
Cong thuc hien tai la:

```text
5.0 + 4.0 = +9.0
```

Tuc la:

- van giu logic teamwide buff
- van giu logic carry trait
- nhung khong con bonus chong them cho case overlap

### 7.3. Trait cua carry nhung khong phai teamwide buff

```text
+5.0
```

### 7.3.a. Carry trait chua kich duoc se bi phat nhe

Neu mot trait cua carry van chua active, code se tru nhe:

```text
-2.5 cho moi carry trait chua active
```

Y nghia:

- board co carry nhung bo qua trait chinh cua carry se bi keo diem xuong
- muc phat nay co y giu nhe, chi de dinh huong search
- cac board da kich du trait cua carry se khong bi anh huong


### 7.4. Teamwide buff "luon tot"

Neu trait active nam trong `always_work_team_buff_traits`, trait do duoc cong:

```text
+4.0 + 1.5 = +5.5
```

Set 17 hien tai gom:

- `Dark Lady`
- `Redeemer`
- `Timebreaker`
- `Bulwark`
- `Voyager`
- `Stargazer`
- `Marauder`
- `Eradicator`
- `Commander`

### 7.5. Teamwide buff can dung context moi duoc thuong

Mot so trait buff team khong phai luc nao cung dep. Code chia rieng:

- `frontline_team_buff_traits`
  - `Bastion`
  - `Brawler`
- `carry_caster_team_buff_traits`
  - `Channeler`
- `carry_attack_speed_team_buff_traits`
  - `Challenger`
- `carry_ap_hybrid_team_buff_traits`
  - Set 17 hien tai dang rong

Neu dung context:

- nhom caster / attack-speed -> `+4.0 + 1.5 = +5.5`
- nhom frontline va board du frontline muc cao -> `+4.0 + 2.0 = +6.0`

Neu khong dung context:

```text
+0.0
```

Quan trong:

- teamwide buff hien tai mac dinh **khong bi mismatch penalty**
- neu khong hop role/carry, no chi khong duoc thuong them

### 7.6. Unique traits mac dinh khong bi penalty

Neu trait la `1/1` va:

- khong phai teamwide buff dang duoc thuong
- khong co factor dac biet rieng

thi trait do mac dinh dung o muc:

```text
+0.0
```

Tuc la:

- khong duoc thuong them
- nhung cung khong bi `IRRELEVANT_TRAIT_PENALTY`

Vi du:

- `Oracle`
- `Party Animal`
- `Gun Goddess`

Code:

- `is_unique_trait(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- nhanh neutral trong `carry_and_special_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)

### 7.7. Trait active khong lien quan carry, khong phai teamwide, khong phai unique dac biet

Nhung trait con lai se bi tru nhe:

```text
-2.0
```

## 8. Danh Sach Teamwide Buff Cua Set 17

Code hien tai xem cac trait sau la `team_buff_traits` cua Set 17:

- `N.O.V.A.`
- `Bulwark`
- `Dark Lady`
- `Redeemer`
- `Stargazer`
- `Timebreaker`
- `Bastion`
- `Brawler`
- `Challenger`
- `Channeler`
- `Marauder`
- `Voyager`
- `Eradicator`
- `Commander`

Ngoai le dieu kien:

- `Marauder` chi duoc cong diem khi carry thuoc nhom `melee`
  - `melee` duoc xem la: `assassin`, `fighter`, `tank`
  - neu carry khong thuoc nhom nay thi `Marauder` = `+0`, khong bi penalty

- `Shepherd` chi duoc cong diem khi carry la `AP` hoac `hybrid`
  - code hien tai dung `carry_damage_profile in {'magic', 'hybrid'}`
  - neu carry khong phai AP/hybrid thi `Shepherd` = `+0`, khong bi penalty

Code:

- `SET_RULES['17']`: [tft_synergies_live.py](tft_synergies_live.py)
- `TRAIT_BONUS_FACTOR_BY_TRAIT`: [tft_synergies_live.py](tft_synergies_live.py)

## 9. Ngoai Le Dac Biet Theo Trait

### 9.1. N.O.V.A.

`N.O.V.A.` duoc cham rieng, khong dung generic team-buff logic.

Rule kich hoat:

- `1 N.O.V.A.` -> khong tinh bonus
- `2 / 3 / 4 N.O.V.A.` -> tinh theo moc `2`
- `5+ N.O.V.A.` -> tinh theo moc `5`

Moi nguon buff `N.O.V.A.` cho bonus:

- huu dung -> `+1.5`
- vo dung -> `+0.5`

Danh gia theo tung nguon:

- `Aatrox`: luon tot
- `Kindred`: luon tot
- `N.O.V.A. Emblem`: luon tot
- `Caitlyn`: tot cho `Marksman`, `Assassin`, `Fighter`, `Specialist`
- `Akali`: tot cho `Caster` va `Hybrid Fighter` (vi du case khep voi `Riven`)
- `Maokai`: tot khi board du frontline

Neu carry cung mang trait `N.O.V.A.` thi van duoc cong them `CARRY_TRAIT_BONUS`.

Code:

- `nova_team_buff_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `nova_buff_multiplier(...)`: [tft_synergies_live.py](tft_synergies_live.py)

### 9.2. Redeemer cua Rhaast

`Redeemer` cua `Rhaast` duoc cham rieng, khong di qua generic team-buff logic.

Trait description:

```text
(1) For each non-unique trait you have active, your team gains Attack Speed,
Armor, and Magic Resist.
```

Code lam theo huong:

1. dem so `non-unique active traits`

```text
z = so non-unique active traits
```

2. chuan hoa theo moc muc tieu `8 trait`

```text
scale = z / 8
```

3. lay he so cao nhat theo board:

- `Marksman` / `Specialist` -> `1.093 * scale`
- `Assassin` / `Fighter` -> `3.186 * scale`
- board du frontline -> `1.093 * scale`

4. bonus cuoi:

Neu khong khop nhom nao:

```text
TEAM_BUFF_BONUS
```

Neu khop:

```text
TEAM_BUFF_BONUS * (1 + weight)
```

Luu y:

- `Redeemer` duoc tinh rieng de tranh double-count
- unique traits `1/1` khac khong duoc dem vao `z`

Code:

- `active_non_unique_trait_count(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `redeemer_team_buff_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 10. Trait Scale Rieng Cho Cac Unit / Trait Dac Biet

Ngoai cac nhanh chung, code co them he so scale rieng cho mot so trait dac biet.

### 10.1. Morgana / Dark Lady

`Dark Lady` la teamwide buff va duoc scale:

```text
1.5x
```

Nghia la bonus positive cua `Dark Lady` se duoc nhan `1.5` neu board co `Morgana` la unit 1-trait.

### 10.2. Graves / Factory New

`Factory New` duoc xem la trait dac biet va scale:

```text
2.0x
```

Thuc thi hien tai:

```text
trait_breakpoint_score(active_breakpoint) * 2.0
```

### 10.3. Vex / Doomer

`Doomer` cua `Vex` duoc xu ly giong `Factory New`:

```text
2.0x
```

### 10.4. Sona / Commander

`Commander` la teamwide buff va duoc scale:

```text
1.5x
```

### 10.5. Eradicator

`Eradicator` la teamwide buff va duoc scale:

```text
1.5x
```

Code:

- `single_trait_special_multiplier(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `trait_bonus_multiplier(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `SINGLE_TRAIT_FACTOR_BY_TRAIT`: [tft_synergies_live.py](tft_synergies_live.py)
- `TRAIT_BONUS_FACTOR_BY_TRAIT`: [tft_synergies_live.py](tft_synergies_live.py)

## 11. Off-Profile Damage Penalty

Neu carry la AD (`damage_profile = attack`), code han che nhung unit damage AP di kem.

Chi phat khi mot unit:

- khong phai carry
- co `role = damage`
- co `damage_profile = magic`

Cong thuc co ban:

```text
unit_penalty = 2.0 + unit_cost * 1.5
```

Neu unit do co trait ho tro board hoac co trait trung voi carry, muc phat duoc giam manh:

```text
unit_penalty *= (1 - 0.65)
```

Tuc la giam `65%`.

Code:

- `off_profile_damage_penalty(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 12. Structure Bonus

Code co model rieng cho `frontline/backline`.

Map theo subtype:

- `tank` => `1.0 frontline`
- `fighter` / `assassin` => `0.5 frontline + 0.5 backline`
- `marksman` / `caster` / `specialist` => `1.0 backline`

### 12.1. Frontline target

- level 6: `2.5`
- level 7: `3.0`
- level 8: `3.5`
- level 9: `4.0`
- level 10: `4.5`

### 12.2. Backline target

- level 6: `0.0`
- level 7: `0.0`
- level 8: `1.0`
- level 9: `2.0`
- level 10: `3.0`

### 12.3. Cong thuc

```text
- positive(front_target - frontline_score) * 9.0
- positive(back_target - backline_score) * 7.0
+3.0 neu du frontline
+2.25 neu du backline
```

Code:

- `unit_frontline_backline_value(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `frontline_backline_scores(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `structure_bonus(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 13. Active Trait Overflow Penalty

De tranh board bi dan trai qua nhieu trait active nho, code phat neu:

```text
active_trait_count > level
```

Cong thuc:

```text
active_trait_penalty = (active_trait_count - level) * 3.0
```

## 14. Filter Va Validation

### 14.1. Max Unused Traits

Neu `unused_trait_count > max_unused_traits`:

- trong beam search: bi phat nang
- o ket qua cuoi: bi loai

Phat trong search:

```text
-20 * (unused_count - max_unused_traits)
```

### 14.2. Cost Ranges

Neu nguoi dung dat range so luong unit theo cost, code xu ly o 2 tang:

- trong luc search: prune/phat state vuot range hoac khong the dat range
- o ket qua cuoi: loai board neu khong nam trong range

### 14.3. Trait Filters

Nguoi dung co the ep breakpoint trait that su, vi du:

- `N.O.V.A. 2`
- `N.O.V.A. 5`
- `Mecha 3`

Code se:

- validate breakpoint co that trong trait data
- prune state neu khong con kha nang dat breakpoint
- loai ket qua cuoi neu khong dat

### 14.4. Mecha Transform Range

Nguoi dung co the ep khoang transform cua `Mecha`:

- `0-0`
- `0-3`
- `3-3`

Code se:

- chi giu state co so transform hop range
- su dung cung logic nay cho validation cuoi

Code:

- `required_trait_breakpoints_met(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `required_trait_shortfall(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `mecha_transform_range_satisfied(...)`: [tft_synergies_live.py](tft_synergies_live.py)
- `final_valid(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 15. Tie-break

Neu `sort_by = score` va hai doi hinh bang diem nhau, code uu tien:

1. `total_cost` cao hon
2. roi moi toi ten champion

Neu `sort_by = cost`, code uu tien:

1. `total_cost` thap hon
2. neu bang cost thi `score` cao hon

Code:

- `state_sort_key(...)`: [tft_synergies_live.py](tft_synergies_live.py)

## 16. Tom Tat Truc Giac

Neu muon nho nhanh scoring theo ngon ngu product:

- moc trait lon quan trong hon gom nhieu trait nho
- trait cua carry rat quan trong
- trait vua cua carry vua buff team la cuc manh
- teamwide buff khong bi penalty khi khong hop role; no chi khong duoc thuong them
- unique trait mac dinh cung khong bi penalty
- mot so trait dac biet duoc scale rieng (`Dark Lady`, `Factory New`, `Doomer`, `Commander`, `Eradicator`, `Redeemer`, `N.O.V.A.`)
- board thieu frontline bi phat nang
- carry 4/5 vang duoc khuyen khich di voi board dat hon
- carry AD bi han che AP damage lech he, nhung utility AP van co discount penalty
- qua nhieu trait active nho va qua nhieu trait rac se bi keo diem xuong
