# Pilot review (pipeline v1)

> **Exploratory, train/val days only, no model or threshold choices made.**

Generated 2026-11-10 by `python -m src.pilot_review` from the v1 pilot outputs in `data/pilot/`.
Those outputs are now **superseded** by pipeline v2 (`data/scores/v2/`), which trims every file overlap,
stitches contiguous files and adds band levels. This review is kept as a record of what was looked at
before the full run. It does not describe v2.

## What was compared

- The 60 pilot days (`data/pilot_days.csv`): all train/val, sb01 and sb02, deployments 01-09.
  37 are present and 23 absent.
- Zero-shot humpback (`Mn`) window scores were compared with the daily labels for **these 60 train/val days
  only**. No test-day audio was processed, and no test-day label was compared with any score.
  (Test-day labels were read earlier, only to build `data/day_table.csv` and to stratify the test-split
  samples, as the frozen plan requires.)
- Nothing here was used to choose a model, a threshold, features or a day rule.

## Completeness

- Every day has 23.996-24.000 h of windows and 288 five-minute blocks. All embeddings are finite.
- Flags:
  - `sb01_02_2019-02-04`, `-02-07`, `-03-01`: more than 1% exact-zero samples (1.3-1.7% per file). These
    may be recorder dropouts. This led to the `zero_fraction` field and to eval plan §7 (amendment 2).
  - `sb02_01_2018-11-15`, `sb02_02_2019-02-20`: a file overlapped the next one by 2.0 s, and v1 trimmed it.
  - `sb02_02_2019-02-14`: one pair of windows overlapped by 1 s at a file boundary. v1 only trimmed
    overlaps over 2 s, and the typical overlap is about 1.3 s. v2 trims every overlap.

## Zero-shot day scores (descriptive)

Day scores follow eval plan §4. The primary score is the 3rd-highest window score in the best 10-minute
span.

| Day score | AUROC | PR-AUC (absent = positive) | Median, present | Median, absent |
|---|---|---|---|---|
| Primary (3 in 10 min) | 0.693 | 0.617 | 0.854 | 0.531 |
| Max window | 0.657 | 0.596 | 0.984 | 0.907 |
| Mean of top 10 | 0.709 | 0.619 | 0.893 | 0.716 |

The absent prevalence is 0.383, which is PR-AUC's chance level. With 60 days and no confidence
intervals, these are a sanity check only. The model's training data may also include SanctSound (eval
plan §6, amendment 1). Absent days still score high (median max 0.91), so the trained classifier will
have to do most of the work.

## Throughput (v1)

The first run took about 100 s per day. The resumed run after the host reboot took 60 s per day. That
projects 12-20 h for 700 days.
