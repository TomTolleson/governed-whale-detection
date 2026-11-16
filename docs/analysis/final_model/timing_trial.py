"""Timing trial: throughput of real full-data block+day fits at one C, for a given job count.
Run from the repo root: python <this> <jobs>. Writes nothing in the repo; prints one JSON line."""
import itertools
import json
import os
import sys
import time

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, os.getcwd())
import src.final_model as fm  # noqa: E402

jobs = int(sys.argv[1])
s, band, emb, blocks, bd, zs = fm.load()
y, fold = s["label"].to_numpy(), s["deployment"].to_numpy()
keep = np.ones(len(s), bool)
sets = [frozenset(p) for p in itertools.combinations(sorted(np.unique(fold)), 2)][:jobs]
t_start = fm.read_tctl()
t0 = time.time()
res = Parallel(n_jobs=jobs)(delayed(fm.fit_heldout)(h, 0.1, keep, fold, y, blocks, bd, emb, True) for h in sets)
wall = time.time() - t0
print(json.dumps({"jobs": jobs, "blas_threads": os.environ.get("OPENBLAS_NUM_THREADS"), "fits": len(sets),
                  "wall_s": round(wall, 1), "s_per_fit_throughput": round(wall / len(sets), 1),
                  "fit_s_each": [r[3]["fit_s"] for r in res], "n_iter": [r[3]["n_iter_block"] for r in res],
                  "warnings": sorted({w for r in res for w in r[3]["warnings"]}),
                  "tctl_start": t_start, "tctl_end": fm.read_tctl()}), flush=True)
