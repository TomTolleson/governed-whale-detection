# NOAA SanctSound humpback detection (Stellwagen Bank)

Day-level **humpback whale presence/absence** detection on NOAA–U.S. Navy SanctSound passive
acoustic recordings from Stellwagen Bank National Marine Sanctuary (sites sb01, sb02, sb03).
The plan is a pretrained bioacoustic embedding model plus a small classifier, trained against
analyst-screened daily humpback labels.

**Research use only.** Outputs are experimental and must not be used for operational,
management, permitting or regulatory decisions.

**Non-commercial research.** This project is non-commercial research. It uses Google's multispecies
whale model (Kaggle `google/multispecies-whale`, Apache 2.0), whose Terms of Use ask that it be used for
wildlife conservation, research or education, not for profit (`docs/model_notes.md`).

## Data

- Audio and labels: public GCS bucket `gs://noaa-passive-bioacoustic/sanctsound/`, read anonymously.
  See `docs/inventory.md`.
- Cite: NOAA Office of National Marine Sanctuaries and U.S. Navy. 2020. SanctSound Raw Passive
  Acoustic Data. NOAA National Centers for Environmental Information.
  https://doi.org/10.25921/saca-sp25
- Licence terms are not yet confirmed (see `docs/inventory.md`). Raw data is never committed; it
  lives in `data/`, which git ignores.

## Layout

```
docs/             inventory and design notes
src/audit.py      append-only, hash-chained audit log (audit_log.jsonl)
src/inventory.py  bucket listing -> data/inventory.json
tests/            pytest tests
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## Audit log

Every action is appended to `audit_log.jsonl` through `src.audit.log_event`. Each line stores
the SHA-256 of the line before it, so `src.audit.verify_chain()` will detect any edit or deletion.
