# SanctSound Stellwagen Bank inventory (sb01, sb02, sb03)

Generated 2026-11-09 by claude-code with anonymous `gcsfs` (`token="anon"`); no credentials were needed.
Source: public bucket `gs://noaa-passive-bioacoustic/sanctsound/`. Reproduce with
`python -m src.inventory data/inventory.json` (one non-recursive `ls` per folder, ~7 s total).

Citation: NOAA Office of National Marine Sanctuaries and U.S. Navy. 2020. SanctSound Raw Passive
Acoustic Data. NOAA NCEI. https://doi.org/10.25921/saca-sp25 [access date]

## Bucket layout (as listed, not assumed)

```
sanctsound/
  README.pdf
  audio/<site>/sanctsound_<site>_<NN>/        NN = 01..21 for all three sites
      audio/       *.flac  (flat, no subfolders)
      metadata/    SanctSound_<SITE>_<NN>.json  (deployment metadata, ~1 KB)
      ancillary/   calibration/
  products/detections/<site>/sanctsound_<site>_<NN>_<product>/
      data/        <name>.csv + <name>.nc
      metadata/    <name>-metadata.json + NOAA-Navy-<name>.xml (ISO 19115)
```

Detection products per deployment: atlanticcod, bluewhale_1d, dolphins_1h, finwhale_1d,
**humpbackwhale_1d**, minkewhale_1d, northatlanticrightwhale_1d, seiwhale_1d, ships.

## Summary

| Site | Deployments with audio | With humpbackwhale_1d | Audio total | Audio in labelled deployments (01–12) |
|---|---|---|---|---|
| sb01 | 21 (01–21) | 12 (01–12) | 2.50 TB | 1.44 TB, 4,130 files |
| sb02 | 21 (01–21) | 12 (01–12) | 2.46 TB | 1.40 TB, 4,213 files |
| sb03 | 21 (01–21) | 12 (01–12) | 2.48 TB | 1.38 TB, 4,010 files |
| **all** | 63 | **36** | **7.44 TB** | **4.22 TB, 12,353 files** |

**Usable set (audio AND humpback labels): deployments 01–12 at each of sb01, sb02, sb03 = 36 deployments.**
Deployments 13–21 have audio but no humpback product (13–14: cod, minke, dolphins, ships;
15: minke, dolphins, ships; 16–18: dolphins, ships; 19–21: no detection products at all).

## Per-deployment detail

"GB" = sum of object sizes in `<deployment>/audio/` (10^9 bytes). Sample file = first object in listing order.

| Site | Dep | Audio | Files | GB | Ext | Sample file | Sample MB | Humpback 1d labels | Label files |
|---|---|---|---|---|---|---|---|---|---|
| sb01 | 01 | yes | 313 | 174.3 | .flac×313 | `SanctSound_SB01_01_1678032935_20181112T190000Z_Post-Deployment.flac` | 489 | yes | .csv×1, .nc×1 |
| sb01 | 02 | yes | 256 | 131.7 | .flac×256 | `SanctSound_SB01_02_671404073_20190128T180000Z_Post-Deployment.flac` | 495 | yes | .csv×1, .nc×1 |
| sb01 | 03 | yes | 316 | 100.6 | .flac×316 | `SanctSound_SB01_03_1677778970_20190410T040000Z_Post-Deployment.flac` | 258 | yes | .csv×1, .nc×1 |
| sb01 | 04 | yes | 373 | 108.3 | .flac×373 | `SanctSound_SB01_04_1678032935_190601180000.flac` | 158 | yes | .csv×1, .nc×1 |
| sb01 | 05 | yes | 384 | 118.2 | .flac×384 | `SanctSound_SB01_05_67678214_190802190000.flac` | 199 | yes | .csv×1, .nc×1 |
| sb01 | 06 | yes | 373 | 135.5 | .flac×373 | `SanctSound_SB01_06_1677758490_191005160000.flac` | 297 | yes | .csv×1, .nc×1 |
| sb01 | 07 | yes | 336 | 114.6 | .flac×336 | `SanctSound_SB01_07_67403784_191206160000.flac` | 259 | yes | .csv×1, .nc×1 |
| sb01 | 08 | yes | 404 | 136.1 | .flac×404 | `SanctSound_SB01_08_67678214_200131150000.flac` | 270 | yes | .csv×1, .nc×1 |
| sb01 | 09 | yes | 396 | 131.3 | .flac×396 | `SanctSound_SB01_09_67403784_200407210000.flac` | 268 | yes | .csv×1, .nc×1 |
| sb01 | 10 | yes | 378 | 103.9 | .flac×378 | `SanctSound_SB01_10_67678214_200612193000.flac` | 238 | yes | .csv×1, .nc×1 |
| sb01 | 11 | yes | 204 | 60.1 | .flac×204 | `SanctSound_SB01_11_67403784_200814180000.flac` | 259 | yes | .csv×1, .nc×1 |
| sb01 | 12 | yes | 397 | 129.7 | .flac×397 | `SanctSound_SB01_12_67678214_200917183000.flac` | 194 | yes | .csv×1, .nc×1 |
| sb01 | 13 | yes | 391 | 135.5 | .flac×391 | `SanctSound_SB01_13_67403784_201122183500.flac` | 227 | **no** | – |
| sb01 | 14 | yes | 324 | 113.5 | .flac×324 | `SanctSound_SB01_14_67678214_210126200000.flac` | 205 | **no** | – |
| sb01 | 15 | yes | 401 | 130.0 | .flac×401 | `SanctSound_SB01_15_67403784_210321191500.flac` | 214 | **no** | – |
| sb01 | 16 | yes | 367 | 103.0 | .flac×367 | `SanctSound_SB01_16_67678214_210527141500.flac` | 204 | **no** | – |
| sb01 | 17 | yes | 360 | 100.7 | .flac×360 | `SanctSound_SB01_17_67403784_210727180000.flac` | 270 | **no** | – |
| sb01 | 18 | yes | 486 | 165.9 | .flac×486 | `SanctSound_SB01_18_67678214_210925183000.flac` | 297 | **no** | – |
| sb01 | 19 | yes | 378 | 131.3 | .flac×378 | `SanctSound_SB01_19_67403784_211215173000.flac` | 289 | **no** | – |
| sb01 | 20 | yes | 392 | 133.2 | .flac×392 | `SanctSound_SB01_20_67678214_220216151500.flac` | 107 | **no** | – |
| sb01 | 21 | yes | 135 | 41.9 | .flac×135 | `SanctSound_SB01_21_67403784_220422180000.flac` | 50 | **no** | – |
| sb02 | 01 | yes | 351 | 167.4 | .flac×351 | `SanctSound_SB02_01_1677778970_20181112T180000Z_Post-Deployment.flac` | 405 | yes | .csv×1, .nc×1 |
| sb02 | 02 | yes | 256 | 133.5 | .flac×256 | `SanctSound_SB02_02_805867544_20190128T200000Z_Post-Deployment.flac` | 463 | yes | .csv×1, .nc×1 |
| sb02 | 03 | yes | 360 | 109.7 | .flac×360 | `SanctSound_SB02_03_67403784_20190402T170000Z_Post-Deployment.flac` | 263 | yes | .csv×1, .nc×1 |
| sb02 | 04 | yes | 373 | 102.8 | .flac×373 | `SanctSound_SB02_04_1677758490_190601160000.flac` | 158 | yes | .csv×1, .nc×1 |
| sb02 | 05 | yes | 385 | 111.3 | .flac×385 | `SanctSound_SB02_05_67403784_190802180000.flac` | 135 | yes | .csv×1, .nc×1 |
| sb02 | 06 | yes | 372 | 128.7 | .flac×372 | `SanctSound_SB02_06_1678032935_191005180000.flac` | 156 | yes | .csv×1, .nc×1 |
| sb02 | 07 | yes | 337 | 113.5 | .flac×337 | `SanctSound_SB02_07_805867544_191206170000.flac` | 300 | yes | .csv×1, .nc×1 |
| sb02 | 08 | yes | 403 | 131.4 | .flac×403 | `SanctSound_SB02_08_1678008346_200131170000.flac` | 252 | yes | .csv×1, .nc×1 |
| sb02 | 09 | yes | 396 | 124.5 | .flac×396 | `SanctSound_SB02_09_1678032935_200407183000.flac` | 179 | yes | .csv×1, .nc×1 |
| sb02 | 10 | yes | 378 | 94.0 | .flac×378 | `SanctSound_SB02_10_1678008346_200612173000.flac` | 198 | yes | .csv×1, .nc×1 |
| sb02 | 11 | yes | 205 | 58.6 | .flac×205 | `SanctSound_SB02_11_1678032935_200814162000.flac` | 263 | yes | .csv×1, .nc×1 |
| sb02 | 12 | yes | 397 | 120.2 | .flac×397 | `SanctSound_SB02_12_1678008346_200917163000.flac` | 155 | yes | .csv×1, .nc×1 |
| sb02 | 13 | yes | 392 | 140.1 | .flac×392 | `SanctSound_SB02_13_1678032935_201122172000.flac` | 302 | **no** | – |
| sb02 | 14 | yes | 324 | 109.7 | .flac×324 | `SanctSound_SB02_14_1678008346_210126180000.flac` | 195 | **no** | – |
| sb02 | 15 | yes | 402 | 121.7 | .flac×402 | `SanctSound_SB02_15_1678032935_210321172000.flac` | 156 | **no** | – |
| sb02 | 16 | yes | 367 | 96.3 | .flac×367 | `SanctSound_SB02_16_1678008346_210527160000.flac` | 149 | **no** | – |
| sb02 | 17 | yes | 361 | 96.4 | .flac×361 | `SanctSound_SB02_17_1678032935_210727163000.flac` | 70 | **no** | – |
| sb02 | 18 | yes | 485 | 152.6 | .flac×485 | `SanctSound_SB02_18_1678008346_210925170000.flac` | 89 | **no** | – |
| sb02 | 19 | yes | 369 | 131.1 | .flac×369 | `SanctSound_SB02_19_1678032935_211215163000.flac` | 270 | **no** | – |
| sb02 | 20 | yes | 391 | 127.4 | .flac×391 | `SanctSound_SB02_20_1678008346_220216134500.flac` | 236 | **no** | – |
| sb02 | 21 | yes | 313 | 91.5 | .flac×313 | `SanctSound_SB02_21_1678032935_220422160000.flac` | 224 | **no** | – |
| sb03 | 01 | yes | 286 | 160.2 | .flac×286 | `SanctSound_SB03_01_671879182_20181112T180000Z_Post-Deployment.flac` | 437 | yes | .csv×1, .nc×1 |
| sb03 | 02 | yes | 255 | 134.3 | .flac×255 | `SanctSound_SB03_02_1678278694_20190128T210000Z_Post-Deployment.flac` | 493 | yes | .csv×1, .nc×1 |
| sb03 | 03 | yes | 361 | 116.0 | .flac×361 | `SanctSound_SB03_03_67678214_20190402T150000Z_Post-Deployment.flac` | 89 | yes | .csv×1, .nc×1 |
| sb03 | 04 | yes | 373 | 98.5 | .flac×373 | `SanctSound_SB03_04_1678008346_190601140000.flac` | 237 | yes | .csv×1, .nc×1 |
| sb03 | 05 | yes | 416 | 114.2 | .flac×416 | `SanctSound_SB03_05_1677778970_190802160000.flac` | 188 | yes | .csv×1, .nc×1 |
| sb03 | 06 | yes | 372 | 131.4 | .flac×372 | `SanctSound_SB03_06_1678008346_191005190000.flac` | 174 | yes | .csv×1, .nc×1 |
| sb03 | 07 | yes | 169 | 63.3 | .flac×169 | `SanctSound_SB03_07_1677778970_191206190000.flac` | 289 | yes | .csv×1, .nc×1 |
| sb03 | 08 | yes | 402 | 143.8 | .flac×402 | `SanctSound_SB03_08_1677758490_200131190000.flac` | 255 | yes | .csv×1, .nc×1 |
| sb03 | 09 | yes | 396 | 127.9 | .flac×396 | `SanctSound_SB03_09_805867544_200407160000.flac` | 234 | yes | .csv×1, .nc×1 |
| sb03 | 10 | yes | 378 | 101.2 | .flac×378 | `SanctSound_SB03_10_1677758490_200612160000.flac` | 134 | yes | .csv×1, .nc×1 |
| sb03 | 11 | yes | 205 | 58.5 | .flac×205 | `SanctSound_SB03_11_805867544_200814152000.flac` | 192 | yes | .csv×1, .nc×1 |
| sb03 | 12 | yes | 397 | 134.6 | .flac×397 | `SanctSound_SB03_12_1677758490_200917150500.flac` | 243 | yes | .csv×1, .nc×1 |
| sb03 | 13 | yes | 358 | 130.6 | .flac×358 | `SanctSound_SB03_13_805867544_201122161000.flac` | 289 | **no** | – |
| sb03 | 14 | yes | 200 | 87.1 | .flac×200 | `SanctSound_SB03_14_1677758490_210126161500.flac` | 298 | **no** | – |
| sb03 | 15 | yes | 403 | 129.7 | .flac×403 | `SanctSound_SB03_15_805867544_210321153000.flac` | 205 | **no** | – |
| sb03 | 16 | yes | 366 | 114.2 | .flac×366 | `SanctSound_SB03_16_1677778970_210527171500.flac` | 205 | **no** | – |
| sb03 | 17 | yes | 380 | 111.2 | .flac×380 | `SanctSound_SB03_17_1677991977_210727153000.flac` | 121 | **no** | – |
| sb03 | 18 | yes | 427 | 147.8 | .flac×427 | `SanctSound_SB03_18_1677778970_210925160000.flac` | 150 | **no** | – |
| sb03 | 19 | yes | 378 | 145.3 | .flac×378 | `SanctSound_SB03_19_671404073_211215150000.flac` | 263 | **no** | – |
| sb03 | 20 | yes | 391 | 140.7 | .flac×391 | `SanctSound_SB03_20_1677778970_220216123000.flac` | 362 | **no** | – |
| sb03 | 21 | yes | 312 | 91.5 | .flac×312 | `SanctSound_SB03_21_671404073_220422140000.flac` | 264 | **no** | – |

## Audio format (one file, header only)

File: `audio/sb02/sanctsound_sb02_01/audio/SanctSound_SB02_01_1677778970_20181112T180000Z_Post-Deployment.flac` (405 MB).
Read with `soundfile.info()` on a streamed gcsfs handle; only the header was fetched, not the whole file.

| Property | Value |
|---|---|
| Format | FLAC, PCM_16 |
| Sample rate | 48,000 Hz |
| Channels | 1 |
| Duration | 18,429 s (≈ 5 h 07 min) |

Deployment metadata (`SanctSound_SB02_01.json`) agrees: SoundTrap 300, 48 kHz, continuous recording,
100 % recording, 1 channel, sensor depth 68.3 m, 42.4708 N, 70.2429 W, 2018-11-12 → 2019-01-28,
data quality "Good", "small data gaps between files" from 2019-01-26 onward.

## Humpback label file (one folder read)

Folder: `products/detections/sb02/sanctsound_sb02_01_humpbackwhale_1d/`

- `data/SanctSound_SB02_01_humpbackwhale_1d.csv` (1,115 B) + a `.nc` NetCDF file (not opened)
- Columns: **`ISOStartTime`** (date, `YYYY-MM-DD`), **`Presence`** (0/1)
- Date range: **2018-11-12 → 2019-01-28**, 78 rows (one per day, matches the deployment dates)
- Presence: **68 / 78 days = 87.2 %** present, 10 absent
- First and last days are partial recording days (deployment starts 18:00 UTC, ends 17:00 UTC)
  but are still labelled.

## Licence / use restrictions (unresolved)

- The product ISO XML gives `accessConstraints` and `useLimitation` = `otherRestrictions`, with a
  distribution-liability disclaimer and a required citation. **No CC0 statement appears in that XML.**
- The label metadata JSON says `"PUBLISH": "Y"`, published 15-Apr-2022.
- The CC0 vs "non-public" question raised earlier is **still open**. Treat the data as research use with
  citation until NCEI confirms. Not checked here: the NCEI landing page for the DOI and `sanctsound/README.pdf`.
