# ERR-001: wrong per-day count of continuous stretches

| | |
|---|---|
| Found | 2026-11-11, by claude-code, while checking the v2 train/val run |
| Introduced | `d2f4fe5` (pipeline v2) |
| Fixed | `90c6deb`, "Count stretches from window times; log v2 train/val run" |
| Affected field | `stretches` in `score_day` audit-log entries and `data/scores/v2/run_report.json` |
| Not affected | every array in `data/scores/v2/*.npz`: scores, embeddings, band levels, window times, zero fraction |
| Status | Fixed. Corrected counts are logged. No re-scoring needed |

## The bug

`stretches` is meant to be the number of continuous runs of 5 s windows in a UTC day. Two things reset
the grid: midnight, and a real gap between files. At `d2f4fe5` the counter went up only when a piece of
audio produced at least one window **and** started a new grid (`if n: stretches += int(j > 0 or not stitched)`).

At sb02_03 the files are 4 h long and start at hh:00:02. The file that crosses midnight contributes only
2 s to the new day. That is less than one window, so it produced none (`n == 0`) and was not counted. The
2 s were carried into the next file, which was stitched to it and so was not counted either. As a
result, a day of one continuous stretch was reported as 0. On one day, a later real gap was counted
but the midnight start was not, so it showed 1 instead of 2.

The fix, `count_stretches(t)`, computes the count from the saved window start times as
`1 + (number of steps between consecutive windows larger than 5 s)`, and 0 for a day with no windows.
It is tested in `tests/test_pilot.py::test_count_stretches`.

## Affected days (train/val, v2 run)

| Day | Logged at d2f4fe5 | Correct |
|---|---|---|
| sb02_03_2019-04-14 | 0 | 1 |
| sb02_03_2019-04-15 | 0 | 1 |
| sb02_03_2019-04-18 | 0 | 1 |
| sb02_03_2019-04-24 | 0 | 1 |
| sb02_03_2019-04-28 | 0 | 1 |
| sb02_03_2019-05-07 | 1 | 2 |
| sb02_03_2019-05-13 | 0 | 1 |
| sb02_03_2019-05-18 | 0 | 1 |
| sb02_03_2019-05-19 | 0 | 1 |
| sb02_03_2019-05-22 | 0 | 1 |
| sb02_03_2019-05-23 | 0 | 1 |
| sb02_03_2019-05-24 | 0 | 1 |

The other 288 days were counted correctly. The corrected distribution over all 300 days is
1 stretch: 284, 2 stretches: 15, 4 stretches: 1. The corrected counts were recomputed from each `.npz`'s
`window_start_s` and logged as a `correction` entry on 2026-11-11, and again with this note (`errata` entry).

## Scope of impact

- **Wrong:** the `stretches` value in the 12 `score_day` entries above, and the same field in
  `data/scores/v2/run_report.json`. The audit log is append-only, so those entries stay as written, and
  the correction entry supersedes them. `run_report.json` is not rewritten.
- **Not stored in the score files:** `stretches` is not saved in the `.npz` files.
- **No consumers:** nothing outside `src/pilot.py` reads `stretches`. A grep of `src/`, `tests/` and `docs/`
  finds only the new test. The day table, the pilot review, the deployment check and the evaluation
  plan do not use it.
- **QA impact:** none. `stretches` is informational. The real-gap QA signals are the window count, the
  `>1 min gap` flag and `dropped_tail_s`, and none of them changed.

## Evidence that the scoring path is unaffected

**1. Code paths.** `git diff d2f4fe5 90c6deb -- src/pilot.py` makes four changes:
- it removes the attribute `DayAccumulator.stretches`;
- it removes the two lines that incremented it inside `process()`;
- it adds the pure function `count_stretches(t)`;
- it changes the report dict in `save_day()` to `"stretches": count_stretches(t)`.

None of the removed lines fed into anything else. The counter was written only in `process()` and read
only in the report dict. The functions that produce stored data are unchanged: decoding, trimming,
stitching (`decode_task`, `trim_target`, `day_pieces`, the carry logic), the GPU `run()`/`score()`, the
accumulation in `DayAccumulator.add()`, and the `np.savez_compressed(...)` call. `count_stretches` runs
after the arrays are final, and only on the window times.

**2. Re-scoring at the fixed commit.** Three affected days were scored again at `90c6deb` (clean tree) into
`data/scores/errata_check/` and compared with `data/scores/v2/` (`d2f4fe5`):

| Array (SHA-256 of raw bytes, first 16 hex) | sb02_03_2019-04-14 | sb02_03_2019-04-15 | sb02_03_2019-05-07 |
|---|---|---|---|
| `scores` (all 12 classes) | identical `ad257d995029bb2d` | identical `a17a707790ef8bd2` | identical `406bff538ea70d81` |
| `humpback` | identical `09c28f9db7ede3fa` | identical `51c19eb78474e5d7` | identical `6fcf09ccb8018191` |
| `window_start_s` | identical `31debbc1d95f60af` | identical `31debbc1d95f60af` | identical `d1a721de3ac2453b` |
| `block_emb` | identical `26506715845da237` | identical `33a8f576801dd6a8` | identical `cdab702aae6296bf` |
| `block_band_db` | identical `f39d0818a530b1ec` | identical `ea3fa3bc4e401ff4` | identical `29b445c2f29ec547` |
| `block_n_windows`, `block_start_s`, `zero_fraction`, `class_names`, `band_names`, `band_edges_hz`, `pipeline_version` | identical | identical | identical |
| `files` metadata, without timing fields | identical | identical | identical |
| `git_commit` | `d2f4fe5…` vs `90c6deb…`, as expected | same | same |

**The whole `.npz` files are not byte-identical, and should not be.** The re-scored files carry the new
commit in `git_commit`, and the `files` metadata records wall-clock `download_s` and `decode_resample_s`,
which change from run to run. The zip entry timestamps are fixed (1980-01-01), so they add no difference.
Every data array is byte-identical. The new `score_day` entries report the correct counts: 1, 1 and 2.

## Why the d2f4fe5 stamp on data/scores/v2 is still valid

The stamp records the code that **produced** the stored arrays, and that is still true. The fix touched
no line on the path that produces them, and re-scoring at the fixed commit reproduces them bit for bit.
`pipeline_version` stays `"2"` because the outputs did not change. The 300 files in `data/scores/v2/` are
not re-run or re-stamped. The only wrong value they were linked to, the logged `stretches` count, is
corrected in the audit log. Test-day outputs will be produced at the frozen evaluation commit (see
`docs/evaluation-plan.md`), which includes this fix. They will carry that commit, which differs from the
train/val stamp only by this errata and later documentation and gating changes.
