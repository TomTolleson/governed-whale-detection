# Model notes: Google multispecies whale model (Kaggle `google/multispecies-whale`)

Written 2026-11-09 by claude-code.

## Sources, and what could not be read

- **Kaggle model page: not readable.** `https://www.kaggle.com/models/google/multispecies-whale` and
  its `/tensorFlow2/default` and `/tensorFlow2/default/2` pages return only the title ("Google |
  multispecies-whale | Kaggle") without a JavaScript-capable browser. The Kaggle JSON API returns 404
  anonymously, and no Kaggle credentials are configured. The legacy URL
  `tfhub.dev/google/multispecies-whale/1` redirects to a generic Kaggle listing.
  Only the "License and model card" section comes from the page, as relayed by the owner. Nothing else
  here comes from the model documentation.
- **What is verified** comes from the downloaded SavedModel itself
  (`data/models/models/google/multispecies-whale/tensorFlow2/default/2`, version 2, via kagglehub
  0.3.12, file SHA-256s in `audit_log.jsonl`, action `model_download`). Values were read with the model's own
  `metadata()` signature and by inspecting signatures and running it on **synthetic noise only**.

## Facts read from the SavedModel

| Item | Value | How verified |
|---|---|---|
| Required sample rate | **24,000 Hz** | `metadata()["input_sample_rate"]` |
| Window (context) length | **120,000 samples = 5.0 s** at 24 kHz | `metadata()["context_width_samples"]` |
| `score` input | `waveform` float32 `[batch, samples, 1]`, plus `context_step_samples` int64 scalar (hop) | signature |
| `score` output | `score` float32 `[batch, n_windows, 12]`; values in (0, 1) | signature; sigmoid of the logits (see below) |
| Other signatures | `front_end(waveform) -> [batch, frames, 128]` (161 frames per 5 s window); `logits(spectrogram [b,128,128]) -> [b,12]`; `features(spectrogram [b,128,128]) -> [b,1280]`; `metadata()` | signature |
| Output classes (index order) | `Oo, Mn, Eg, Be, Upcall, Bp, Call, Gunshot, Echolocation, Bm, Whistle, Ba` | `metadata()["class_names"]` |
| Humpback class | **`Mn`, index 1** (*Megaptera novaeangliae*) | `Mn` is the standard humpback species code. The label meaning is inferred from the code, since no documentation was readable |
| TF version | SavedModel loads and runs in TensorFlow 2.17.1 on GPU | run |

How `score` is computed (checked on synthetic noise and a tone): `score` equals the Keras call on
the 161 front-end frames, and equals `sigmoid(logits(front_end[:, 16:144]))` exactly (max abs
difference 0.0). That is, the model scores the **centre 128 of 161 frames**. The pilot takes the 1280-d embedding
from `features` on that same centre crop, so embeddings and scores see the same input. Scoring a
long waveform with `context_step_samples=120000` matched per-window scoring to within 1e-4.

## License and model card (owner-supplied, added 2026-11-10)

**Source:** the owner's Claude Desktop session read `https://www.kaggle.com/models/google/multispecies-whale`
in a browser on 2026-11-09 and passed on the details below. They were **not verified through the Kaggle API**,
and claude-code has not seen the page.

- **The downloaded model folder contains no license file.** Checked 2026-11-10: it holds only
  `saved_model.pb`, `keras_metadata.pb`, `fingerprint.pb` and `variables/` (plus kagglehub's `2.complete`
  marker), and no file named like LICENSE, COPYING or NOTICE. The license terms above therefore rest only on the
  model page.
- **Evidence snapshot: pending.** The owner will save a PDF of the Kaggle model page in `docs/evidence/`.
  Its SHA-256 and date go in `audit_log.jsonl` once the file exists. This does not block other work.

- **License (TensorFlow 2 `default` variation): Apache 2.0.**
- **Terms of Use (summary, not the page's wording):** users are asked to follow Google's AI principles and to
  use the model for wildlife conservation, research or education, not for profit. The section states
  that the official license remains Apache 2.0. *The verbatim text is not yet recorded. It is pending a
  paste from the owner.*
- **Training data (model card citations) includes:**
  - SanctSound Raw Passive Acoustic Data, doi 10.25921/saca-sp25. **This is the dataset this
    project evaluates on.**
  - an NEFSC Stellwagen Bank dataset, doi 10.25921/g3vk-v972.
  - Which sites, deployments and dates were used: **not stated**. Any of our train/val or test
    days may therefore be in the model's training data (see the amendment in `docs/eval_plan.md` §6).

## Not known (documentation not read directly). Do not treat as settled

- **Expected input amplitude scaling: not documented here.** The pilot feeds int16 PCM / 32768
  (range [-1, 1)). This is an assumption.
- What each non-species class means (`Upcall`, `Call`, `Gunshot`, `Echolocation`, `Whistle`) and the
  training data, regions and intended use: not known.
- Whether scores are calibrated probabilities: not known. They are sigmoid outputs, nothing more.
- Differences between version 2 and earlier versions: not known.
