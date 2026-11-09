# Labeling rules for `data/day_table.csv`

## Rule as stated by the project owner (2026-11-09), verbatim

> Build data/day_table.csv with one row per deployment-day: site, deployment, date, label,
> audio_hours, is_partial_day, no_audio, is_changeover_day, eligible (true only if audio_hours >= 20
> and not no_audio).

## How each column is computed

Implemented in `src/day_table.py`. Definitions marked *(claude-code)* are not spelled out in the
rule above. claude-code chose them, and they **need owner confirmation**.

| Column | Definition |
|---|---|
| site, deployment | From the label file name, e.g. `sb01`, `03`. |
| date | `ISOStartTime` from the humpbackwhale_1d CSV (UTC day). One row per label row; days without a label row are not in the table (there are none with audio). |
| label | `Presence` from the CSV (0/1), unchanged. |
| audio_hours | Hours of that UTC day covered by audio files of **that deployment**, estimated from file names (see `docs/label_survey.md` and `docs/header_check.md`), rounded to 0.001 h. |
| no_audio | *(claude-code)* `audio_hours == 0`. |
| is_partial_day | *(claude-code)* `0 < audio_hours < 24 h − 1 min`. Informational; not used by `eligible`. |
| is_changeover_day | *(claude-code)* The same site and date also appear in another deployment's label file. Informational; not used by `eligible`. |
| **eligible** | **`audio_hours >= 20` and not `no_audio`** (the owner's rule). |

## Notes

- `no_audio` days have `audio_hours == 0`, so they already fail the `>= 20` test. The second condition
  never changes the result but is kept because the rule states it.
- With the current data, no changeover day is eligible: both halves of every changeover day have under 20 h.
- sb01_03 2019-04-10 has `audio_hours == 20.000` (audio starts 04:00 UTC) and is eligible by the rule. The
  header check shows that day's first file is 0.3 s shorter than its slot, so the true value is within about
  1 s of the cut.
