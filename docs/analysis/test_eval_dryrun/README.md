# Dry run of `src/test_eval.py` (2026-11-13)

**The metrics in `dryrun_summary.json` are meaningless as performance.** The labels are fake. The features are
train/val features, and the final model was trained on them. The run checks plumbing only: recomputation,
refusals and the order in which labels are read.

## What was run

- **Command:** `python -m tools.dryrun_test_eval <scratch dir>`.
- **Days:** train/val feature files were copied into scratch under fake "test" keys: 102 Test T days and
  148 Test S days. No test day was read or touched.
- **Labels:** all fake and seeded. The harness read `data/sample_days.csv` and the cv_v1.1 OOF file
  without their label columns.
- **Audit log:** every audit entry went to a scratch log. The real `audit_log.jsonl` was hashed before and
  after, and it was unchanged.

## Results (all checks pass)

- **Scores.** The final-model, ambient-noise and zero-shot day scores equal an independent recomputation to
  within 1.1e-16. The zero-shot scores also match the committed cv_v1.1 OOF file.
- **Headline AUROC.** Both within-site and pooled AUROC equal an independent recomputation.
- **Known answer.** With labels set by the final-model score's median, AUROC_ws is 1.0 on all three splits.
  With random labels it is near 0.5 and no improvement is claimed.
- **QA exclusions** are dropped and listed. The concentration rule flags a deployment holding 3 of 3
  exclusions. The sb01_02-equivalent sensitivity variant is produced when flagged.
- **Refusals.** It refuses, every time, when any of these is tampered with or missing:
  - the artefact;
  - `spec.json`;
  - a Stage A drift report;
  - a score file;
  - the freeze-tag commit stamp;
  - the Stage B release.

  In each refused run, no label column was read and no `stage_b_release` was logged.
- **Label reads.** In each completed run, the label column was read exactly once, after `stage_b_release`
  was in the log. No scratch log contains a label field.
