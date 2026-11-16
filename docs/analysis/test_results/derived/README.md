# Derived output (logged deviation): thresholded metrics per site

`thresholded_per_site.csv` was **not produced by `src/test_eval.py`** (eval-tool-v1). That tool reports
balanced accuracy at the fixed threshold for each split, not per site. The owner's Stage B report request
asked for thresholded metrics per site, so this table was computed **after** the one evaluation pass.

How it was computed:
- Source: the committed `../test_day_scores.csv` (SHA-256 `0fcbed30…3360d6d`), as produced.
- Each method uses its **frozen** threshold from `results.json` (`thresholds`). Final model: 0.9804.
- A day is predicted present if its score is at or above the threshold.
- Columns: TP, FN, TN, FP (positive = present), sensitivity, specificity, and balanced accuracy.
- Nothing in `results.json` or `test_day_scores.csv` was changed, and no threshold, model or day was altered.

It is logged as a `deviation` entry in `audit_log.jsonl`, under the release's rule that any change after
Stage B is a logged deviation. Its split-level totals match `results.json`: Test S final-model balanced
accuracy is 0.772.
